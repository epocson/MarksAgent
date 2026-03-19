import json
from marks_agent import MarksAgent

def run_test():
    agent = MarksAgent()
    
    # Complex scenario to validate behavior
    # Testing "самоуверенный (пропускает ошибки)" pattern:
    # Requires: green_ratio > 0.7 AND false_negatives > 0.3
    
    payload = {
        "total_fragments": 20,
        "marks": {
            "green": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],  # 15 items -> green_ratio = 0.75
            "yellow": [16, 17],  # 2 items -> yellow_ratio = 0.1
            "red": [18]  # 1 item -> red_ratio = 0.05
        },
        "ground_truth_errors": [18, 19, 20]  # 3 total errors
    }
    # Here True Positives = 1 (item 18)
    # False Negatives = 2 (items 19, 20 missed)
    # False Negatives ratio = 2 / 3 = 0.667 (> 0.3)
    
    print("Testing payload...")
    print(json.dumps(payload, indent=2))
    print("\n--- Result ---")
    
    try:
        result = agent.process_payload(payload)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error during processing: {e}")

if __name__ == "__main__":
    run_test()
