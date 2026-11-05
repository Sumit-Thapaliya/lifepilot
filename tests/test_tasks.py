from backend.agents.capture_agent import confirm_capture, extract_capture

def test_capture_requires_confirmation_and_extracts_fields() -> None:
    proposal = extract_capture("add a task to revise algebra by Friday, urgent study")
    assert proposal["title"] == "revise algebra"
    assert proposal["category"] == "study"
    assert proposal["priority"] == "high"
    assert proposal["requires_confirmation"] is True
    assert confirm_capture(proposal, False)["action"] == "discard_proposal"
