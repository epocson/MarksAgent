import asyncio
import json
import logging
import redis.asyncio as redis
import aiosqlite
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Settings(BaseSettings):
    redis_host: str = "localhost"
    redis_port: int = 6379
    db_path: str = "data/students_profiles.db"
    
    class Config:
        env_file = ".env"

settings = Settings()

class MarksSchema(BaseModel):
    green: List[int] = Field(default_factory=list)
    yellow: List[int] = Field(default_factory=list)
    red: List[int] = Field(default_factory=list)

class StudentPayload(BaseModel):
    student_id: str
    total_fragments: int
    marks: MarksSchema = Field(default_factory=MarksSchema)
    ground_truth_errors: Optional[List[int]] = None

class MarksAgent:
    def __init__(self, redis_host: str = settings.redis_host, redis_port: int = settings.redis_port, db_path: str = settings.db_path):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.db_path = db_path

    async def init_db(self):
        """Асинхронная инициализация локальной БД SQLite для хранения профилей."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS students_profiles (
                    student_id TEXT PRIMARY KEY,
                    cognitive_pattern TEXT,
                    metrics JSON
                )
            ''')
            await db.commit()

    async def _save_to_db(self, student_id: str, pattern: str, metrics: dict):
        """Асинхронное сохранение итогового диагноза студента в БД."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO students_profiles (student_id, cognitive_pattern, metrics)
                VALUES (?, ?, ?)
            ''', (student_id, pattern, json.dumps(metrics)))
            await db.commit()

    def _calculate_metrics(self, marks: MarksSchema, ground_truth: List[int]) -> tuple:
        red_marks = set(marks.red)
        gt_errors = set(ground_truth)
        
        tp = len(red_marks & gt_errors)
        fp = len(red_marks - gt_errors)
        fn = len(gt_errors - red_marks)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        fn_ratio = fn / len(gt_errors) if len(gt_errors) > 0 else 0.0
        return round(precision, 3), round(recall, 3), round(f1, 3), tp, fp, fn, round(fn_ratio, 3)

    def calculate_features(self, marks: MarksSchema, total_fragments: int) -> Dict[str, float]:
        green_count = len(marks.green)
        yellow_count = len(marks.yellow)
        red_count = len(marks.red)
        total_marks = green_count + yellow_count + red_count

        green_ratio_fragments = green_count / total_fragments if total_fragments > 0 else 0.0
        yellow_ratio_fragments = yellow_count / total_fragments if total_fragments > 0 else 0.0
        red_ratio_fragments = red_count / total_fragments if total_fragments > 0 else 0.0
        
        green_ratio_marks = green_count / total_marks if total_marks > 0 else 0.0
        yellow_ratio_marks = yellow_count / total_marks if total_marks > 0 else 0.0
        red_ratio_marks = red_count / total_marks if total_marks > 0 else 0.0

        yellow_green_ratio = yellow_count / green_count if green_count > 0 else 0.0
        uncertainty_index = (yellow_count + red_count) / total_marks if total_marks > 0 else 0.0
        
        return {
            "green_ratio_fragments": round(green_ratio_fragments, 3),
            "yellow_ratio_fragments": round(yellow_ratio_fragments, 3),
            "red_ratio_fragments": round(red_ratio_fragments, 3),
            "green_ratio_marks": round(green_ratio_marks, 3),
            "yellow_ratio_marks": round(yellow_ratio_marks, 3),
            "red_ratio_marks": round(red_ratio_marks, 3),
            "yellow_green_ratio": round(yellow_green_ratio, 3),
            "uncertainty_index": round(uncertainty_index, 3)
        }

    def _classify_pattern(self, features: Dict[str, float], has_metrics: bool, f1: float, fn_ratio: float) -> str:
        green_ratio = features.get("green_ratio_fragments", 0.0)
        yellow_ratio = features.get("yellow_ratio_fragments", 0.0)
        red_ratio = features.get("red_ratio_fragments", 0.0)

        if has_metrics and f1 > 0.8:
            return "точный детектив"
        elif yellow_ratio > 0.4:
            return "осторожный сомневающийся"
        elif has_metrics and green_ratio > 0.7 and fn_ratio > 0.3:
            return "самоуверенный (пропускает ошибки)"
        elif has_metrics and red_ratio < 0.1 and fn_ratio > 0.5:
            return "пассивный наблюдатель"
        return "смешанный"

    def generate_explanation(self, marks: MarksSchema, pattern: str) -> Dict[str, str]:
        xai = {}
        if len(marks.green) > 0:
            xai['green'] = "Студент уверен в правильности выделенных фрагментов."
        if len(marks.yellow) > 0:
            xai['yellow'] = "Зоны сомнения — индикатор повышенной когнитивной нагрузки."
        if len(marks.red) > 0:
            xai['red'] = "Фрагменты идентифицированы как содержащие концептуальные или фактические ошибки."
            
        xai['summary'] = f"Выявлен паттерн «{pattern}» на основе анализа цветовых выделений."
        return xai

    async def process_payload(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Асинхронная точка входа для обработки сырого JSON, валидации через Pydantic и расчетов."""
        try:
            payload = StudentPayload(**raw_data)
        except ValidationError as e:
            return {"error": "JSON validation failed", "details": e.errors()}

        if payload.total_fragments <= 0:
            return {"error": "total_fragments must be greater than 0"}

        features = self.calculate_features(payload.marks, payload.total_fragments)
        
        has_metrics = False
        precision, recall, f1, tp, fp, fn, fn_ratio = 0.0, 0.0, 0.0, 0, 0, 0, 0.0
        
        if payload.ground_truth_errors is not None:
            precision, recall, f1, tp, fp, fn, fn_ratio = self._calculate_metrics(payload.marks, payload.ground_truth_errors)
            has_metrics = True
            
        pattern = self._classify_pattern(features, has_metrics, f1, fn_ratio)
        explanation = self.generate_explanation(payload.marks, pattern)
        
        result = {
            "student_id": payload.student_id,
            "features": features,
            "cognitive_pattern": pattern,
            "xai_explanations": explanation
        }
        
        if has_metrics:
            result['metrics'] = {
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "precision": precision,
                "recall": recall,
                "f1_score": f1
            }
            
        await self._save_to_db(payload.student_id, pattern, result.get('metrics', {}))
        return result

    async def listen(self):
        await self.init_db()
        try:
            r = redis.Redis(host=self.redis_host, port=self.redis_port, decode_responses=True)
            pubsub = r.pubsub()
            await pubsub.subscribe('marks_agent_queue')
            logging.info("Started listening to marks_agent_queue...")
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        raw_data = json.loads(message['data'])
                        result = await self.process_payload(raw_data)
                        logging.info(f"Processed message for student: {result.get('student_id', 'Unknown')}")
                        
                        if "error" not in result:
                            # Публикуем результат в другую очередь 
                            await r.publish('marks_agent_results', json.dumps(result, ensure_ascii=False))
                    except Exception as e:
                        logging.error(f"Error processing message: {e}")
        except Exception as e:
            logging.error(f"Redis connection or listen error: {e}")

if __name__ == "__main__":
    agent = MarksAgent()
    asyncio.run(agent.listen())
