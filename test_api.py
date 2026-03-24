import asyncio
import httpx
import json

async def test_fastapi():
    print("====================================")
    print("🚀 Тест REST API (FastAPI Gateway)")
    print("====================================")
    try:
        async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=5.0) as client:
            payload = {
                "student_id": "api_test_student_1",
                "total_fragments": 10,
                "marks": {
                    "green": [1, 2, 3, 4],
                    "yellow": [5, 6],
                    "red": [7]
                },
                "ground_truth_errors": [7, 8]
            }
            print("\n1️⃣ [POST] Отправляем данные студента на сервер...")
            response = await client.post("/api/v1/submit_marks", json=payload)
            print(f"Статус: {response.status_code}")
            print(f"Ответ: {response.json()}")

            print("\n⏳ Polling: ждем, пока MarksAgent обработает JSON и сохранит в SQLite...")
            max_attempts = 10
            poll_interval = 0.5
            response = None
            for attempt in range(1, max_attempts + 1):
                await asyncio.sleep(poll_interval)
                response = await client.get("/api/v1/student/api_test_student_1")
                print(f"   Попытка {attempt}/{max_attempts} — Статус: {response.status_code}")
                if response.status_code == 200:
                    break

            print("\n2️⃣ [GET] Итоговый ответ от API:")
            print(f"Статус: {response.status_code}")
            print("👤 Итоговый Профиль студента:")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
            
            if response.status_code == 200 and "cognitive_pattern" in response.json():
                print("\n✅ Интеграционный тест FastAPI успешно завершен!")
            else:
                print("\n❌ Тест провалился. Неверный формат ответа.")
                
    except Exception as e:
        print(f"\n❌ Ошибка во время теста API: {e}")

if __name__ == "__main__":
    asyncio.run(test_fastapi())
