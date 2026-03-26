import asyncio
import json
import logging
from typing import List, Dict
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
import aiosqlite

from marks_agent import settings, StudentPayload

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api-gateway")

class ConnectionManager:
    """Управляет активными WebSocket-соединениями."""
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, student_id: str):
        await websocket.accept()
        if student_id not in self.active_connections:
            self.active_connections[student_id] = []
        self.active_connections[student_id].append(websocket)
        logger.info(f"New connection for student: {student_id}")

    def disconnect(self, websocket: WebSocket, student_id: str):
        if student_id in self.active_connections:
            self.active_connections[student_id].remove(websocket)
            if not self.active_connections[student_id]:
                del self.active_connections[student_id]
        logger.info(f"Disconnected student: {student_id}")

    async def broadcast_to_student(self, student_id: str, message: dict):
        if student_id in self.active_connections:
            for ws in self.active_connections[student_id]:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {student_id}: {e}")

manager = ConnectionManager()
redis_client = None
db_client = None
listener_task = None

async def listen_to_agents():
    """Слушает результаты от агентов через Redis Pub/Sub."""
    try:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe('marks_agent_results', 'tutor_agent_results')
        logger.info("Listening to agent channels...")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                student_id = data.get("student_id")
                if student_id:
                    data["source_agent"] = message['channel']
                    await manager.broadcast_to_student(student_id, data)
    except asyncio.CancelledError:
        logger.info("Redis listener task cancelled.")
    except Exception as e:
        logger.error(f"Critical error in Redis listener: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, db_client, listener_task
    # Startup
    redis_client = redis.Redis(
        host=settings.redis_host, 
        port=settings.redis_port, 
        decode_responses=True
    )
    db_client = await aiosqlite.connect(settings.db_path)
    db_client.row_factory = aiosqlite.Row
    listener_task = asyncio.create_task(listen_to_agents())
    
    yield
    
    # Shutdown
    if listener_task:
        listener_task.cancel()
    if redis_client:
        await redis_client.close()
    if db_client:
        await db_client.close()

app = FastAPI(title="Mark Agent Gateway", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Рекомендуется ограничить в PROD через .env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Проверка доступности ресурсов."""
    redis_alive = await redis_client.ping()
    return {
        "status": "healthy",
        "redis": "connected" if redis_alive else "disconnected",
        "database": "connected" if db_client else "disconnected"
    }

@app.post("/api/v1/submit_marks")
async def submit_marks(payload: StudentPayload):
    try:
        await redis_client.publish('marks_agent_queue', payload.model_dump_json())
        return {
            "status": "success", 
            "student_id": payload.student_id,
            "message": "Task submitted to processing queue"
        }
    except Exception as e:
        logger.error(f"Submission failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to publish to queue")

@app.get("/api/v1/student/{student_id}")
async def get_student_profile(student_id: str):
    try:
        async with db_client.execute(
            "SELECT * FROM students_profiles WHERE student_id = ?", (student_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Student not found")
            
            return {
                "student_id": row["student_id"],
                "cognitive_pattern": row["cognitive_pattern"],
                "metrics": json.loads(row["metrics"]) if row["metrics"] else {}
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DB lookup failed for {student_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.websocket("/api/v1/ws/{student_id}")
async def websocket_endpoint(websocket: WebSocket, student_id: str):
    await manager.connect(websocket, student_id)
    try:
        while True:
            # Слушаем пинги от фронта для поддержания соединения
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, student_id)
    except Exception as e:
        logger.error(f"WebSocket error for {student_id}: {e}")
        manager.disconnect(websocket, student_id)
