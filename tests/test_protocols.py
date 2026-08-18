from src.protocols.aggregation import majority_vote
from src.schemas.agent_outputs import SolverOutput


def test_majority_vote() -> None:
    answer, confidence = majority_vote(
        [
            SolverOutput(sample_id="x", answer="A", confidence=0.5),
            SolverOutput(sample_id="x", answer="A", confidence=0.6),
            SolverOutput(sample_id="x", answer="B", confidence=0.7),
        ]
    )
    assert answer == "A"
    assert confidence == 2 / 3
