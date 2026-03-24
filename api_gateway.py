import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
import aiosqlite
from pydantic import BaseModel, Field

from marks_agent import settings, StudentPayload

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

redis_client = None
db_client = None
manager = {}
listener_task = None

async def listen_to_agents():
    """Слушает результаты от MarksAgent и TutorAgent и рассылает их по WebSockets."""
    try:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe('marks_agent_results', 'tutor_agent_results')
        logging.info("API Gateway started listening to agents results...")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                student_id = data.get("student_id")
                
                if student_id and student_id in manager:
                    for ws in manager[student_id]:
                        try:
                            data["source_agent"] = message['channel']
                            await ws.send_json(data)
                        except Exception as e:
                            logging.error(f"WebSocket send error: {e}")
    except asyncio.CancelledError:
        logging.info("Gateway Redis listener cancelled.")
    except Exception as e:
        logging.error(f"Redis listen error in Gateway: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, db_client, listener_task
    # Startup: Открываем постоянные пулы
    redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
    db_client = await aiosqlite.connect(settings.db_path)
    db_client.row_factory = aiosqlite.Row
    listener_task = asyncio.create_task(listen_to_agents())
    
    yield
    
    # Shutdown: Безопасное закрытие
    if listener_task:
        listener_task.cancel()
    if redis_client:
        await redis_client.close()
    if db_client:
        await db_client.close()

app = FastAPI(title="MarksAgent Ecosystem API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/v1/submit_marks")
async def submit_marks(payload: StudentPayload):
    try:
        await redis_client.publish('marks_agent_queue', payload.model_dump_json())
        return {"status": "success", "message": "Payload published to agents cluster", "student_id": payload.student_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/student/{student_id}")
async def get_student_profile(student_id: str):
    async with db_client.execute("SELECT * FROM students_profiles WHERE student_id = ?", (student_id,)) as cursor:
        row = await cursor.fetchone()
        if row:
            return {
                "student_id": row["student_id"],
                "cognitive_pattern": row["cognitive_pattern"],
                "metrics": json.loads(row["metrics"]) if row["metrics"] else {}
            }
        else:
            raise HTTPException(status_code=404, detail="Student not found in database")

@app.websocket("/api/v1/ws/{student_id}")
async def websocket_endpoint(websocket: WebSocket, student_id: str):
    await websocket.accept()
    if student_id not in manager:
        manager[student_id] = []
    manager[student_id].append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager[student_id].remove(websocket)
        if not manager[student_id]:
            del manager[student_id]
