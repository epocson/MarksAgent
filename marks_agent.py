import json
import logging
import redis
from typing import Dict, Any, Optional, List

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
        
        # Calculate false negatives ratio (since the prompt condition is false_negatives > 0.3, typical of a ratio/rate)
        fn_ratio = fn / len(gt_errors) if len(gt_errors) > 0 else 0.0
        
        return round(precision, 3), round(recall, 3), round(f1, 3), round(fn_ratio, 3)

    def process_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the payload and extract features, metrics, cognitive patterns, and XAI strings.
        """
        marks = payload.get('marks', {'green': [], 'yellow': [], 'red': []})
        total_fragments = payload.get('total_fragments', 0)
        ground_truth_errors = payload.get('ground_truth_errors', None)
        
        if total_fragments == 0:
            return {"error": "total_fragments must be greater than 0"}
            
        green_count = len(marks.get('green', []))
        yellow_count = len(marks.get('yellow', []))
        red_count = len(marks.get('red', []))
        
        green_ratio = round(green_count / total_fragments, 3)
        yellow_ratio = round(yellow_count / total_fragments, 3)
        red_ratio = round(red_count / total_fragments, 3)
        uncertainty_index = round((yellow_count + red_count) / total_fragments, 3)
        
        precision, recall, f1, fn_ratio = 0.0, 0.0, 0.0, 0.0
        has_metrics = False
        
        if ground_truth_errors is not None:
            precision, recall, f1, fn_ratio = self._calculate_metrics(marks, ground_truth_errors)
            has_metrics = True
            
        # Classification (evaluated top to bottom)
        cognitive_pattern = "смешанный"
        if has_metrics and f1 > 0.8:
            cognitive_pattern = "точный детектив"
        elif yellow_ratio > 0.4:
            cognitive_pattern = "осторожный сомневающийся"
        elif has_metrics and green_ratio > 0.7 and fn_ratio > 0.3:
            cognitive_pattern = "самоуверенный (пропускает ошибки)"
        elif has_metrics and red_ratio < 0.1 and fn_ratio > 0.5:
            cognitive_pattern = "пассивный наблюдатель"
            
        # XAI Strings
        xai_explanations = {}
        if green_count > 0:
            xai_explanations['green'] = "Студент уверен в правильности выделенных фрагментов."
        if yellow_count > 0:
            xai_explanations['yellow'] = "Зоны сомнения — индикатор повышенной когнитивной нагрузки."
        if red_count > 0:
            xai_explanations['red'] = "Фрагменты идентифицированы как содержащие концептуальные или фактические ошибки."
            
        result = {
            "features": {
                "green_ratio": green_ratio,
                "yellow_ratio": yellow_ratio,
                "red_ratio": red_ratio,
                "uncertainty_index": uncertainty_index
            },
            "cognitive_pattern": cognitive_pattern,
            "xai_explanations": xai_explanations
        }
        
        if has_metrics:
            result['metrics'] = {
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "false_negatives": fn_ratio  # Expose false negatives ratio
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
    # Uncomment to start listening
    # agent.listen()
