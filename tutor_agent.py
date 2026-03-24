import asyncio
import json
import logging
import redis.asyncio as redis
from openai import AsyncOpenAI
from pydantic_settings import BaseSettings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TutorSettings(BaseSettings):
    redis_host: str = "localhost"
    redis_port: int = 6379
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "llama3:8b"
    llm_api_key: str = "ollama"
    
    class Config:
        env_file = ".env"

settings = TutorSettings()

class TutorAgent:
    def __init__(self):
        self.redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
        self.llm_client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key
        )

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
        
        await self.redis_client.publish('tutor_agent_results', json.dumps(result, ensure_ascii=False))
        logging.info(f"LLM Feedback published to queue for {student_id}.")

    async def listen(self):
        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe('marks_agent_results')
            logging.info("TutorAgent started listening to marks_agent_results...")
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        # Запускаем обработку в фоне, чтобы не блокировать очередь,
                        # если LLM генерирует ответ 10-15 секунд
                        asyncio.create_task(self.process_message(data))
                    except Exception as e:
                        logging.error(f"Error processing marks result: {e}")
        except Exception as e:
            logging.error(f"TutorAgent Redis connection error: {e}")

if __name__ == "__main__":
    agent = TutorAgent()
    asyncio.run(agent.listen())
