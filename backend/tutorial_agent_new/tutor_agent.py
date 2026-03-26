import asyncio
import json
import logging
import signal
import redis.asyncio as redis
from openai import AsyncOpenAI
from pydantic_settings import BaseSettings
from marks_agent import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class TutorAgent:
    def __init__(self):
        self.redis_client = None
        self.llm_client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key
        )
        self.shutdown_event = asyncio.Event()

    def generate_prompt(self, cognitive_pattern: str, metrics: dict, xai: dict) -> str:
        prompt = f"""
Ты — доброжелательный AI-ментор, помогающий студентам развивать навыки верификации ИИ-контента.
Студент только что завершил анализ текста и расставил цветовые пометки (маркеры).
Нода системы классифицировала студента и выдала следующий когнитивный паттерн: "{cognitive_pattern}".

Метрики студента (если применимо):
Precision (Точность): {metrics.get('precision', 'Н/Д')}
Recall (Полнота): {metrics.get('recall', 'Н/Д')}
Точно найденные ошибки: {metrics.get('true_positives', 'Н/Д')}
Пропущенные ошибки: {metrics.get('false_negatives', 'Н/Д')}

Объяснение системы (XAI):
{json.dumps(xai, ensure_ascii=False, indent=2)}

Твоя задача:
Напиши короткий (2-3 абзаца), ободряющий и образовательный отзыв для студента. 
Объясни ему понятным языком, что означает его паттерн, похвали за успехи и дай 1-2 совета, как улучшить навык фактчекинга в следующий раз.
Никогда не ругай студента. Пиши на русском языке.
"""
        return prompt

    async def get_llm_feedback(self, prompt: str) -> str:
        try:
            response = await self.llm_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "Ты эксперт по когнитивной педагогике и образовательному фактчекингу."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"LLM generation failed: {e}")
            return "К сожалению, ментор сейчас недоступен (LLM не отвечает). Продолжайте тренировки!"

    async def process_message(self, data: dict):
        student_id = data.get("student_id", "Unknown")
        pattern = data.get("cognitive_pattern", "Unknown")
        metrics = data.get("metrics", {})
        xai = data.get("xai_explanations", {})

        logging.info(f"Generating LLM feedback for student {student_id} (Pattern: {pattern})...")
        prompt = self.generate_prompt(pattern, metrics, xai)
        
        feedback = await self.get_llm_feedback(prompt)
        
        result = {
            "student_id": student_id,
            "tutor_feedback": feedback,
            "cognitive_pattern": pattern
        }
        
        if self.redis_client:
            await self.redis_client.publish('tutor_agent_results', json.dumps(result, ensure_ascii=False))
            logging.info(f"LLM Feedback published to queue for {student_id}.")

    def handle_shutdown(self, sig):
        logging.info(f"Received signal {sig}. Gracefully shutting down TutorAgent...")
        self.shutdown_event.set()

    async def listen(self):
        self.redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe('marks_agent_results')
        
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.handle_shutdown, sig)
            except NotImplementedError:
                pass
                
        logging.info("TutorAgent started listening to marks_agent_results...")
        tasks = set()
        
        try:
            while not self.shutdown_event.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    data = json.loads(message['data'])
                    task = asyncio.create_task(self.process_message(data))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
        except Exception as e:
            logging.error(f"TutorAgent Redis connection error: {e}")
        finally:
            logging.info("Awaiting pending LLM requests to finish...")
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await pubsub.unsubscribe('marks_agent_results')
            await self.redis_client.close()
            logging.info("TutorAgent shut down completely.")

if __name__ == "__main__":
    agent = TutorAgent()
    asyncio.run(agent.listen())
