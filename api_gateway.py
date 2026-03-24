import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis
import aiosqlite
from pydantic import BaseModel, Field

# Импортируем настройки и схемы валидации из ядра
from marks_agent import settings, StudentPayload

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(title="MarksAgent Ecosystem API", version="1.0.0")

# Настройка CORS для будущего Frontend (React / Next.js на localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # На продакшене строго прописать домен
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ленивая инициализация redis клиента
redis_client = None

# Хранилище активных WebSocket соединений {student_id: [WebSocket, ...]}
manager = {}

@app.on_event("startup")
async def startup_event():
    global redis_client
    redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
    # Запускаем фоновый listener Redis для отправки данных по WebSockets
    asyncio.create_task(listen_to_agents())

@app.on_event("shutdown")
async def shutdown_event():
    global redis_client
    if redis_client:
        await redis_client.close()

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
                
                # Если студент сейчас подключен по WebSocket, отправляем ему результат
                if student_id and student_id in manager:
                    for ws in manager[student_id]:
                        try:
                            # Инжектим инфу о том, какой именно агент прислал данные
                            data["source_agent"] = message['channel']
                            await ws.send_json(data)
                        except Exception as e:
                            logging.error(f"WebSocket send error: {e}")
    except Exception as e:
        logging.error(f"Redis listen error in Gateway: {e}")


@app.post("/api/v1/submit_marks")
async def submit_marks(payload: StudentPayload):
    """
    REST эндпоинт для отправки данных (пометок) от Фронтенда.
    Валидирует JSON и ставит задание в брокер Redis для всех агентов.
    """
    try:
        await redis_client.publish('marks_agent_queue', payload.model_dump_json())
        return {"status": "success", "message": "Payload published to agents cluster", "student_id": payload.student_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/student/{student_id}")
async def get_student_profile(student_id: str):
    """
    REST эндпоинт для получения итогового профиля студента (сохраненного в БД).
    """
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM students_profiles WHERE student_id = ?", (student_id,)) as cursor:
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
    """
    WebSocket эндпоинт для получения мгновенных результатов от агентов (Real-time).
    """
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
