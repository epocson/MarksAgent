import asyncio
import json
import logging
import signal
import redis.asyncio as redis
import aiosqlite
import os
from typing import Dict, Any, List
from pydantic import ValidationError
from marks_agent import settings, StudentPayload, MarksSchema


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MarksAgent:
    def __init__(self, redis_host: str = settings.redis_host, redis_port: int = settings.redis_port, db_path: str = settings.db_path):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.db_path = db_path
        self.db_client = None
        self.redis_client = None
        self.shutdown_event = asyncio.Event()

    async def init_db(self):
        """Асинхронная инициализация постоянного соединения с БД SQLite."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self.db_client = await aiosqlite.connect(self.db_path)
        await self.db_client.execute('''
            CREATE TABLE IF NOT EXISTS students_profiles (
                student_id TEXT PRIMARY KEY,
                cognitive_pattern TEXT,
                metrics JSON
            )
        ''')
        await self.db_client.commit()

    async def close_db(self):
        if self.db_client:
            await self.db_client.close()

    async def _save_to_db(self, student_id: str, pattern: str, metrics: dict):
        """Асинхронное сохранение итогового диагноза через пул."""
        if not self.db_client:
            return
        await self.db_client.execute('''
            INSERT OR REPLACE INTO students_profiles (student_id, cognitive_pattern, metrics)
            VALUES (?, ?, ?)
        ''', (student_id, pattern, json.dumps(metrics)))
        await self.db_client.commit()

    def _calculate_metrics(self, marks: MarksSchema, ground_truth: List[int]) -> Dict[str, float]:
        red_marks = set(marks.red)
        gt_errors = set(ground_truth)
        
        tp = len(red_marks & gt_errors)
        fp = len(red_marks - gt_errors)
        fn = len(gt_errors - red_marks)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        fn_ratio = fn / len(gt_errors) if len(gt_errors) > 0 else 0.0
        
        # Исправлено: Возвращаем Dict (Rules: "Избавление от хрупких кортежей")
        return {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1_score": round(f1, 3),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "fn_ratio": round(fn_ratio, 3)
        }

    def calculate_features(self, marks: MarksSchema, total_fragments: int) -> Dict[str, float]:
        green_count = len(marks.green)
        yellow_count = len(marks.yellow)
        red_count = len(marks.red)
        total_marks = green_count + yellow_count + red_count

        return {
            "green_ratio_fragments": round(green_count / total_fragments if total_fragments > 0 else 0.0, 3),
            "yellow_ratio_fragments": round(yellow_count / total_fragments if total_fragments > 0 else 0.0, 3),
            "red_ratio_fragments": round(red_count / total_fragments if total_fragments > 0 else 0.0, 3),
            "green_ratio_marks": round(green_count / total_marks if total_marks > 0 else 0.0, 3),
            "yellow_ratio_marks": round(yellow_count / total_marks if total_marks > 0 else 0.0, 3),
            "red_ratio_marks": round(red_count / total_marks if total_marks > 0 else 0.0, 3),
            "yellow_green_ratio": round(yellow_count / green_count if green_count > 0 else 0.0, 3),
            "uncertainty_index": round((yellow_count + red_count) / total_marks if total_marks > 0 else 0.0, 3)
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
        try:
            payload = StudentPayload(**raw_data)
        except ValidationError as e:
            return {"error": "JSON validation failed", "details": e.errors()}

        if payload.total_fragments <= 0:
            return {"error": "total_fragments must be greater than 0"}

        features = self.calculate_features(payload.marks, payload.total_fragments)
        
        has_metrics = False
        metrics_res = {}
        if payload.ground_truth_errors is not None:
            metrics_res = self._calculate_metrics(payload.marks, payload.ground_truth_errors)
            has_metrics = True
            
        pattern = self._classify_pattern(
            features, 
            has_metrics, 
            metrics_res.get("f1_score", 0.0), 
            metrics_res.get("fn_ratio", 0.0)
        )
        explanation = self.generate_explanation(payload.marks, pattern)
        
        result = {
            "student_id": payload.student_id,
            "features": features,
            "cognitive_pattern": pattern,
            "xai_explanations": explanation
        }
        
        if has_metrics:
            out_metrics = metrics_res.copy()
            out_metrics.pop("fn_ratio", None)
            result['metrics'] = out_metrics
            
        await self._save_to_db(payload.student_id, pattern, result.get('metrics', {}))
        return result

    def handle_shutdown(self, sig):
        logging.info(f"Received signal {sig}. Gracefully shutting down MarksAgent...")
        self.shutdown_event.set()

    async def listen(self):
        await self.init_db()
        self.redis_client = redis.Redis(host=self.redis_host, port=self.redis_port, decode_responses=True)
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe('marks_agent_queue')
        
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.handle_shutdown, sig)
            except NotImplementedError:
                pass
        
        logging.info("Started listening to marks_agent_queue...")
        tasks = set()
        
        try:
            while not self.shutdown_event.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    raw_data = json.loads(message['data'])
                    task = asyncio.create_task(self._handle_message(raw_data))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
        except Exception as e:
            logging.error(f"Redis listen error: {e}")
        finally:
            logging.info("Awaiting pending tasks to finish...")
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await pubsub.unsubscribe('marks_agent_queue')
            await self.redis_client.close()
            await self.close_db()
            logging.info("MarksAgent shut down completely.")

    async def _handle_message(self, raw_data):
        try:
            result = await self.process_payload(raw_data)
            logging.info(f"Processed message for student: {result.get('student_id', 'Unknown')}")
            if "error" not in result:
                await self.redis_client.publish('marks_agent_results', json.dumps(result, ensure_ascii=False))
        except Exception as e:
            logging.error(f"Error processing message: {e}")

if __name__ == "__main__":
    agent = MarksAgent()
    asyncio.run(agent.listen())
