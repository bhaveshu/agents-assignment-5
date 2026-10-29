"""
Custom LangSmith evaluators for the Financial Approval System.

Students implement evaluator factory functions that return callables
taking LangSmith-style arguments (inputs, outputs, reference_outputs).
run_eval.py calls them directly, on your machine; nothing is sent to LangSmith.
(If you later pass them to langsmith.evaluate(), give each inner function its
own name: LangSmith uses the function name as the feedback key.)

Part 4: LangSmith Tracing + Evaluation (20 points)
"""


def create_risk_accuracy_evaluator():
    """
    Create an evaluator that checks risk assessment accuracy.

    Student Note (Factory Pattern & Partial Credit Scoring):
    LangSmith evaluators use a factory function pattern (`create_*`) returning
    a callable `(inputs, outputs, reference_outputs) -> dict`.

    Scoring Logic:
      - Exact match (e.g. 'medium' == 'medium', or None == None for rejected requests) -> 1.0
      - Adjacent risk level (e.g. 'low' vs 'medium' or 'high' vs 'critical') -> 0.5 partial credit
        because LLMs can reasonably straddle borderline thresholds.
      - Discrepancy > 1 tier (e.g. 'low' vs 'high' or 'critical') -> 0.0 (unacceptable misclassification).

    Returns:
        A callable evaluator function
    """
    risk_levels = ["low", "medium", "high", "critical"]

    def risk_accuracy(inputs: dict, outputs: dict, reference_outputs: dict = None) -> dict:
        actual = outputs.get("risk_level")
        expected = reference_outputs.get("risk_level") if reference_outputs else None

        # Exact match (including None == None for rejected requests that bypass assess_risk)
        if actual == expected:
            return {"score": 1.0}

        # If either is None or not in recognized risk levels, cannot be adjacent
        if actual not in risk_levels or expected not in risk_levels:
            return {"score": 0.0}

        # Check adjacency by calculating index distance in the ordered list
        actual_idx = risk_levels.index(actual)
        expected_idx = risk_levels.index(expected)
        if abs(actual_idx - expected_idx) == 1:
            return {"score": 0.5}

        return {"score": 0.0}

    return risk_accuracy


def create_approval_consistency_evaluator():
    """
    Create an evaluator that checks approval decision consistency.

    Student Note (Decision Consistency):
    Verifies that the agent's final outcome ('approved' vs 'rejected') strictly
    matches the expected business outcome from reference outputs.

    Returns:
        A callable evaluator function
    """
    def approval_consistency(inputs: dict, outputs: dict, reference_outputs: dict = None) -> dict:
        actual = outputs.get("status")
        expected = reference_outputs.get("status") if reference_outputs else None
        if actual == expected:
            return {"score": 1.0}
        return {"score": 0.0}

    return approval_consistency
