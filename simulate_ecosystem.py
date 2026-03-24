import redis
import json
import time
import threading
import random

REDIS_HOST = 'localhost'
REDIS_PORT = 6379

def loader_agent():
    """Генерирует фейковые данные и отправляет их в marks_agent_queue."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    print("[LoaderAgent] Запуск генерации и публикации 5 профилей студентов...")
    for i in range(1, 6):
        total_fragments = 20
        # Рандомно генерируем поведение студента
        green_marks = random.sample(range(1, 21), random.randint(5, 13))
        yellow_marks = random.sample(list(set(range(1, 21)) - set(green_marks)), random.randint(0, 5))
        red_marks = random.sample(list(set(range(1, 21)) - set(green_marks) - set(yellow_marks)), random.randint(0, 3))
        
        gt_errors = random.sample(range(1, 21), 4)

        payload = {
            "student_id": f"student_A0{i}",
            "total_fragments": total_fragments,
            "marks": {
                "green": green_marks,
                "yellow": yellow_marks,
                "red": red_marks
            },
            "ground_truth_errors": gt_errors
        }
        
        print(f"[LoaderAgent] -> Публикация данных: student_A0{i} (В очереди)")
        r.publish('marks_agent_queue', json.dumps(payload))
        time.sleep(1) # Задержка 1с для наглядной имитации потока данных

def cluster_agent():
    """Слушает результат работы MarksAgent из очереди marks_agent_results и выводит таблицу."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe('marks_agent_results')
    
    print("[ClusterAgent] Ожидание результатов классификации от MarksAgent...")
    print("-" * 60)
    print(f"{'Student ID':<15} | {'Когнитивный Паттерн':<38}")
    print("-" * 60)
    
    count = 0
    for message in pubsub.listen():
        if message['type'] == 'message':
            data = json.loads(message['data'])
            student_id = data.get('student_id', 'Unknown')
            pattern = data.get('cognitive_pattern', 'Unknown')
            
            print(f"{student_id:<15} | {pattern:<38}")
            count += 1
            if count >= 5: # Завершаем после обработки всех 5 тестовых студентов
                break
    print("-" * 60)

if __name__ == "__main__":
    # Запускаем приемщика (ClusterAgent) в отдельном потоке
    listener = threading.Thread(target=cluster_agent, daemon=True)
    listener.start()
    
    # Даем слушателю 500мс на успешную подписку
    time.sleep(0.5)
    
    # Запускаем поставщика (LoaderAgent)
    loader_agent()
    
    # Ждём завершения работы
    time.sleep(1)
    print("✅ [Система] Эмуляция мультиагентной среды успешно завершена.")
