import pytest
from marks_agent import MarksAgent

@pytest.fixture
def agent():
    return MarksAgent()

def test_basic_calculations(agent):
    payload = {
        "marks": {
            "green": [1, 2],
            "yellow": [3],
            "red": [4]
        },
        "total_fragments": 10,
        "ground_truth_errors": [4]
    }
    result = agent.process_payload(payload)
    features = result["features"]
    
    assert features["green_ratio"] == 0.2
    assert features["yellow_ratio"] == 0.1
    assert features["red_ratio"] == 0.1
    assert features["yellow_green_ratio"] == 0.5
    assert features["uncertainty_index"] == 0.5  # 2 uncertainties / 4 total marks

    metrics = result["metrics"]
    assert metrics["true_positives"] == 1
    assert metrics["false_positives"] == 0
    assert metrics["false_negatives"] == 0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 1.0

def test_pattern_точнои_детектив(agent):
    payload = {
        "marks": {"green": [1], "yellow": [], "red": [2, 3]},
        "total_fragments": 10,
        "ground_truth_errors": [2, 3]
    }
    result = agent.process_payload(payload)
    assert result["cognitive_pattern"] == "точный детектив"

def test_pattern_осторожныи_сомневающиися(agent):
    payload = {
        "marks": {"green": [], "yellow": [1, 2, 3, 4, 5], "red": []},
        "total_fragments": 10,
        "ground_truth_errors": [6]
    }
    result = agent.process_payload(payload)
    assert result["cognitive_pattern"] == "осторожный сомневающийся"

def test_pattern_самоуверенныи(agent):
    payload = {
        "marks": {"green": [1, 2, 3, 4, 5, 6, 7, 8], "yellow": [], "red": []},
        "total_fragments": 10,
        "ground_truth_errors": [9, 10]
    }
    result = agent.process_payload(payload)
    assert result["cognitive_pattern"] == "самоуверенный (пропускает ошибки)"

def test_pattern_пассивныи_наблюдатель(agent):
    payload = {
        "marks": {"green": [], "yellow": [], "red": []},
        "total_fragments": 10,
        "ground_truth_errors": [1, 2]
    }
    result = agent.process_payload(payload)
    assert result["cognitive_pattern"] == "пассивный наблюдатель"

def test_pattern_смешанныи(agent):
    payload = {
        "marks": {"green": [1, 2], "yellow": [3], "red": [4]},
        "total_fragments": 10,
        "ground_truth_errors": [5]
    }
    result = agent.process_payload(payload)
    assert result["cognitive_pattern"] == "смешанный"

def test_generate_explanation(agent):
    marks = {"green": [1], "yellow": [2], "red": [3]}
    pattern = "тестовый паттерн"
    explanation = agent.generate_explanation(marks, pattern)
    
    assert "green" in explanation
    assert "yellow" in explanation
    assert "red" in explanation
    assert "summary" in explanation
    assert pattern in explanation["summary"]
