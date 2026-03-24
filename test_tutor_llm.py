import asyncio
import urllib.request
import json
from tutor_agent import TutorAgent

async def test_ollama():
    print("====================================")
    print("🔍 Testing TutorAgent Local Connect")
    print("====================================")
    
    try:
        response = urllib.request.urlopen('http://localhost:11434/')
        if response.status == 200:
            print("✅ [Локальный сервер Ollama работает на 11434]")
            agent = TutorAgent()
            
            payload = {
                "student_id": "TEST_OLLAMA_USER",
                "cognitive_pattern": "осторожный сомневающийся",
                "metrics": {"precision": 0.9, "recall": 0.4, "true_positives": 4},
                "xai_explanations": {"yellow": "Студент постоянно сомневается даже в правильных терминах."}
            }
            
            prompt = agent.generate_prompt(
                payload["cognitive_pattern"], 
                payload["metrics"], 
                payload["xai_explanations"]
            )
            print("📋 [Сгенерирован промпт для LLM]:")
            print("------------------------------------")
            print(prompt)
            print("------------------------------------")
            
            print("⏳ [Отправка запроса к Ollama llama3... Ожидание ответа...]")
            feedback = await agent.get_llm_feedback(prompt)
            print("\n🤖 [Ответ от Нейросети (TutorAgent)]:")
            print("------------------------------------")
            print(feedback)
            print("------------------------------------")
            
            if "К сожалению, ментор сейчас недоступен" in feedback:
                print("❌ ОШИБКА: Ollama не смогла обработать запрос. Убедитесь, что модель 'llama3' скачана (команда 'ollama run llama3')!")
            else:
                print("✅ УСПЕХ: TutorAgent и Ollama работают идеально!")
        else:
            print(f"❌ Ollama сервер вернул странный статус: {response.status}")
    except Exception as e:
        print(f"❌ ОШИБКА: Ollama не запущена. Ошибка соединения: {e}")
        print("💡 Пожалуйста, запустите приложение Ollama на вашем компьютере.")

if __name__ == "__main__":
    asyncio.run(test_ollama())
