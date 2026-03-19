import json
import logging
import redis
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MarksAgent:
    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379):
        self.redis_host = redis_host
        self.redis_port = redis_port

    def _calculate_metrics(self, marks: Dict[str, List[int]], ground_truth: List[int]) -> tuple:
        red_marks = set(marks.get('red', []))
        gt_errors = set(ground_truth)
        
        tp = len(red_marks & gt_errors)
        fp = len(red_marks - gt_errors)
        fn = len(gt_errors - red_marks)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        fn_ratio = fn / len(gt_errors) if len(gt_errors) > 0 else 0.0
        
        return round(precision, 3), round(recall, 3), round(f1, 3), tp, fp, fn, round(fn_ratio, 3)

    def calculate_features(self, marks: Dict[str, List[int]], total_fragments: int) -> Dict[str, float]:
        green_count = len(marks.get('green', []))
        yellow_count = len(marks.get('yellow', []))
        red_count = len(marks.get('red', []))
        total_marks = green_count + yellow_count + red_count

        green_ratio = green_count / total_fragments if total_fragments > 0 else 0.0
        yellow_ratio = yellow_count / total_fragments if total_fragments > 0 else 0.0
        red_ratio = red_count / total_fragments if total_fragments > 0 else 0.0
        
        yellow_green_ratio = yellow_count / green_count if green_count > 0 else 0.0
        uncertainty_index = (yellow_count + red_count) / total_marks if total_marks > 0 else 0.0
        
        return {
            "green_ratio": round(green_ratio, 3),
            "yellow_ratio": round(yellow_ratio, 3),
            "red_ratio": round(red_ratio, 3),
            "yellow_green_ratio": round(yellow_green_ratio, 3),
            "uncertainty_index": round(uncertainty_index, 3)
        }

    def _classify_pattern(self, features: Dict[str, float], has_metrics: bool, f1: float, fn_ratio: float) -> str:
        green_ratio = features.get("green_ratio", 0.0)
        yellow_ratio = features.get("yellow_ratio", 0.0)
        red_ratio = features.get("red_ratio", 0.0)

        if has_metrics and f1 > 0.8:
            return "точный детектив"
        elif yellow_ratio > 0.4:
            return "осторожный сомневающийся"
        elif has_metrics and green_ratio > 0.7 and fn_ratio > 0.3:
            return "самоуверенный (пропускает ошибки)"
        elif has_metrics and red_ratio < 0.1 and fn_ratio > 0.5:
            return "пассивный наблюдатель"
        return "смешанный"

    def generate_explanation(self, marks: Dict[str, List[int]], pattern: str) -> Dict[str, str]:
        xai = {}
        if len(marks.get('green', [])) > 0:
            xai['green'] = "Студент уверен в правильности выделенных фрагментов."
        if len(marks.get('yellow', [])) > 0:
            xai['yellow'] = "Зоны сомнения — индикатор повышенной когнитивной нагрузки."
        if len(marks.get('red', [])) > 0:
            xai['red'] = "Фрагменты идентифицированы как содержащие концептуальные или фактические ошибки."
            
        xai['summary'] = f"Выявлен паттерн «{pattern}» на основе анализа цветовых выделений."
        return xai

    def process_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        marks = payload.get('marks', {'green': [], 'yellow': [], 'red': []})
        total_fragments = payload.get('total_fragments', 0)
        ground_truth_errors = payload.get('ground_truth_errors', None)
        
        if total_fragments <= 0:
            return {"error": "total_fragments must be greater than 0"}

        features = self.calculate_features(marks, total_fragments)
        
        has_metrics = False
        precision, recall, f1, tp, fp, fn, fn_ratio = 0.0, 0.0, 0.0, 0, 0, 0, 0.0
        
        if ground_truth_errors is not None:
            precision, recall, f1, tp, fp, fn, fn_ratio = self._calculate_metrics(marks, ground_truth_errors)
            has_metrics = True
            
        pattern = self._classify_pattern(features, has_metrics, f1, fn_ratio)
        explanation = self.generate_explanation(marks, pattern)
        
        result = {
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
            
        return result

    def listen(self):
        try:
            r = redis.Redis(host=self.redis_host, port=self.redis_port, decode_responses=True)
            pubsub = r.pubsub()
            pubsub.subscribe('marks_agent_queue')
            logging.info("Started listening to marks_agent_queue...")
            
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        payload = json.loads(message['data'])
                        result = self.process_payload(payload)
                        logging.info(f"Processed message: {json.dumps(result, ensure_ascii=False)}")
                    except Exception as e:
                        logging.error(f"Error processing message {message['data']}: {e}")
        except Exception as e:
            logging.error(f"Redis connection or listen error: {e}")

if __name__ == "__main__":
    agent = MarksAgent()
    # agent.listen()
