import pandas as pd

from src.evaluation.metrics import correction_degradation, semantic_diversity, summarize_predictions


def test_semantic_diversity_range() -> None:
    score = semantic_diversity(["A implies B", "B follows from A", "unrelated commonsense answer"])
    assert 0.0 <= score <= 1.0


def test_summary_metrics() -> None:
    df = pd.DataFrame(
        [
            {"dataset": "d", "method": "m", "correct": True, "confidence": 0.8, "total_tokens": 10, "latency_seconds": 1.0},
            {"dataset": "d", "method": "m", "correct": False, "confidence": 0.6, "total_tokens": 20, "latency_seconds": 2.0},
        ]
    )
    summary = summarize_predictions(df)
    assert summary.loc[0, "accuracy"] == 0.5


def test_correction_degradation() -> None:
    before = pd.DataFrame([{"sample_id": "1", "correct": False}, {"sample_id": "2", "correct": True}])
    after = pd.DataFrame([{"sample_id": "1", "correct": True}, {"sample_id": "2", "correct": False}])
    rates = correction_degradation(before, after)
    assert rates["correction_rate"] == 1.0
    assert rates["degradation_rate"] == 1.0
