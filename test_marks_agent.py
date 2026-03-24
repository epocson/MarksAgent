import pytest
from marks_agent import MarksAgent

@pytest.fixture
def agent(tmp_path):
    db_file = tmp_path / "data" / "test.db"
    return MarksAgent(db_path=str(db_file))

@pytest.mark.asyncio
async def test_basic_calculations(agent):
    await agent.init_db()
    payload = {
        "student_id": "student_1",
        "marks": {
            "green": [1, 2],
            "yellow": [3],
            "red": [4]
        },
        "total_fragments": 10,
        "ground_truth_errors": [4]
    }
    result = await agent.process_payload(payload)
    features = result["features"]
    
    assert features["green_ratio_fragments"] == 0.2
    assert features["yellow_ratio_fragments"] == 0.1
    assert features["red_ratio_fragments"] == 0.1
    assert features["green_ratio_marks"] == 0.5
    assert features["yellow_ratio_marks"] == 0.25
    assert features["red_ratio_marks"] == 0.25
    assert features["yellow_green_ratio"] == 0.5
    assert features["uncertainty_index"] == 0.5

    metrics = result["metrics"]
    assert metrics["true_positives"] == 1
    assert metrics["false_positives"] == 0
    assert metrics["false_negatives"] == 0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 1.0

@pytest.mark.asyncio
async def test_pattern_точной_детектив(agent):
    await agent.init_db()
    payload = {"student_id": "1", "marks": {"green": [1], "yellow": [], "red": [2, 3]}, "total_fragments": 10, "ground_truth_errors": [2, 3]}
    res = await agent.process_payload(payload)
    assert res["cognitive_pattern"] == "точный детектив"

@pytest.mark.asyncio
async def test_pattern_осторожный_сомневающийся(agent):
    await agent.init_db()
    payload = {"student_id": "1", "marks": {"green": [], "yellow": [1, 2, 3, 4, 5], "red": []}, "total_fragments": 10, "ground_truth_errors": [6]}
    res = await agent.process_payload(payload)
    assert res["cognitive_pattern"] == "осторожный сомневающийся"

@pytest.mark.asyncio
async def test_pattern_самоуверенный(agent):
    await agent.init_db()
    payload = {"student_id": "1", "marks": {"green": [1, 2, 3, 4, 5, 6, 7, 8], "yellow": [], "red": []}, "total_fragments": 10, "ground_truth_errors": [9, 10]}
    res = await agent.process_payload(payload)
    assert res["cognitive_pattern"] == "самоуверенный (пропускает ошибки)"

@pytest.mark.asyncio
async def test_pattern_пассивный_наблюдатель(agent):
    await agent.init_db()
    payload = {"student_id": "1", "marks": {"green": [], "yellow": [], "red": []}, "total_fragments": 10, "ground_truth_errors": [1, 2]}
    res = await agent.process_payload(payload)
    assert res["cognitive_pattern"] == "пассивный наблюдатель"

@pytest.mark.asyncio
async def test_pattern_смешанный(agent):
    await agent.init_db()
    payload = {"student_id": "1", "marks": {"green": [1, 2], "yellow": [3], "red": [4]}, "total_fragments": 10, "ground_truth_errors": [5]}
    res = await agent.process_payload(payload)
    assert res["cognitive_pattern"] == "смешанный"

def test_generate_explanation(agent):
    from marks_agent import MarksSchema
    marks = MarksSchema(green=[1], yellow=[2], red=[3])
    pattern = "тестовый паттерн"
    explanation = agent.generate_explanation(marks, pattern)
    
    assert "green" in explanation
    assert "yellow" in explanation
    assert "red" in explanation
    assert "summary" in explanation
    assert pattern in explanation["summary"]
