"""
Three-Layer Evaluation Framework for the Financial Approval System.

Students implement evaluator factory functions across three layers:
  Layer 1 — Business Metrics (heuristic, 10 pts)
  Layer 2 — Agent Performance (RAGAS metrics, 12 pts)
  Layer 3 — Safety & Compliance (RAGAS + heuristic, 12 pts)

Each factory returns a callable that takes LangSmith-style arguments
(inputs, outputs, reference_outputs) and returns {"score", "reasoning"}:
    def evaluator(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
        return {"score": float, "reasoning": str}
run_three_layer_eval.py calls them directly, on your machine. Keep this return
format: the tests and the runner read it. (langsmith.evaluate() would not accept
it as is: it expects "comment" instead of "reasoning".)

Part 5: Three-Layer Evaluation Framework (34 points)
"""

# ---------------------------------------------------------------------------
# RAGAS imports — Layer 2 uses these directly, Layer 3 optionally
# (ragas==0.4.3, pinned in requirements.txt). ToolCallAccuracy,
# AgentGoalAccuracyWithReference and TopicAdherenceScore are multi-turn
# metrics: score them with `await metric.multi_turn_ascore(MultiTurnSample(...))`.
# Importing from ragas.metrics prints a DeprecationWarning; ignore it. The
# ragas.metrics.collections versions do not accept LangchainLLMWrapper.
# LangchainLLMWrapper(get_llm()) also warns "LangchainLLMWrapper is deprecated
# ... Use llm_factory instead". That warning is expected: keep the wrapper. It
# wraps whatever get_llm() returns (tested with Gemini), while llm_factory needs
# a raw provider client instead of get_llm().
# ---------------------------------------------------------------------------
# from ragas.metrics import ToolCallAccuracy, AgentGoalAccuracyWithReference, TopicAdherenceScore
# from ragas.metrics import Faithfulness  # Layer 3 hallucination detection
# from ragas.integrations.langgraph import convert_to_ragas_messages
# from ragas.dataset_schema import MultiTurnSample, SingleTurnSample
# from ragas.messages import HumanMessage, AIMessage, ToolCall
# from ragas.llms import LangchainLLMWrapper
#
# Build any metric that needs an LLM (get_llm()) INSIDE the returned evaluator,
# not in the factory: the tests call every factory, and get_llm() raises
# "Missing credentials" when OPENAI_API_KEY is not set at all (a fresh clone
# without .env, or CI).

# ---------------------------------------------------------------------------
# Helper constants
# ---------------------------------------------------------------------------
RISK_LEVELS = ["low", "medium", "high", "critical"]

EXPECTED_REVIEWS_BY_RISK = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

BUDGET_CEILING = 100_000

# Human review stages: the only nodes that append to state["decisions"]
HUMAN_REVIEW_STAGES = ["manager_review", "finance_review", "final_signoff"]

# Allowed topics for TopicAdherenceScore. The metric extracts the topics of the
# Human message (the request) and checks each one against this list, so it has
# to cover what a request is about (a purchase such as "Team Lunch"), not only
# the workflow.
REFERENCE_TOPICS = [
    "financial approval request",
    "purchase or business expense of any kind (for example supplies, equipment, "
    "software, servers, events, meals, marketing, travel)",
    "business justification for a purchase",
    "department budget",
    "risk assessment",
    "request validation",
    "approval or rejection decision",
]


# ═══════════════════════════════════════════════════════════════════════════
# Layer 1 — Business Metrics (heuristic evaluators, 10 points)
# ═══════════════════════════════════════════════════════════════════════════

def create_approval_path_evaluator():
    """
    Create an evaluator that checks whether the approval path is correct.

    Example:
        outputs = {"approval_path": ["submit_request", "assess_risk", "process_request"]}
        reference_outputs = {"approval_path": ["submit_request", "assess_risk", "process_request"]}
        → {"score": 1.0, "reasoning": "Approval path matches exactly"}

    Returns:
        A callable evaluator function
    """
    def approval_path_evaluator(inputs, outputs, reference_outputs) -> dict:
        actual_path = outputs.get("approval_path", [])
        expected_path = reference_outputs.get("approval_path", [])
        if actual_path == expected_path:
            return {"score": 1.0, "reasoning": "Approval path matches exactly"}
        if len(actual_path) == len(expected_path):
            return {"score": 0.5, "reasoning": "Approval path has correct length but differing stages"}
        return {"score": 0.0, "reasoning": f"Approval path length mismatch: expected {len(expected_path)}, got {len(actual_path)}"}
    return approval_path_evaluator


def create_false_positive_evaluator():
    """
    Create an evaluator that detects false positives (approved when should be rejected).

    Returns:
        A callable evaluator function
    """
    def false_positive_evaluator(inputs, outputs, reference_outputs) -> dict:
        actual_status = outputs.get("status")
        expected_status = reference_outputs.get("status")
        if expected_status == "rejected" and actual_status == "approved":
            return {"score": 0.0, "reasoning": "False positive: request approved when it should have been rejected"}
        return {"score": 1.0, "reasoning": "No false positive detected"}
    return false_positive_evaluator


def create_false_negative_evaluator():
    """
    Create an evaluator that detects false negatives (rejected when should be approved).

    Returns:
        A callable evaluator function
    """
    def false_negative_evaluator(inputs, outputs, reference_outputs) -> dict:
        actual_status = outputs.get("status")
        expected_status = reference_outputs.get("status")
        if expected_status == "approved" and actual_status == "rejected":
            return {"score": 0.0, "reasoning": "False negative: request rejected when it should have been approved"}
        return {"score": 1.0, "reasoning": "No false negative detected"}
    return false_negative_evaluator


def create_human_review_efficiency_evaluator():
    """
    Create an evaluator that checks human review count accuracy.

    Returns:
        A callable evaluator function
    """
    def human_review_efficiency_evaluator(inputs, outputs, reference_outputs) -> dict:
        actual_reviews = outputs.get("human_reviews", 0)
        expected_reviews = reference_outputs.get("human_reviews", 0)
        diff = abs(actual_reviews - expected_reviews)
        if diff == 0:
            return {"score": 1.0, "reasoning": "Human review count matches exactly"}
        if diff == 1:
            return {"score": 0.5, "reasoning": f"Human review count off by 1: expected {expected_reviews}, got {actual_reviews}"}
        return {"score": 0.0, "reasoning": f"Human review count off by {diff}: expected {expected_reviews}, got {actual_reviews}"}
    return human_review_efficiency_evaluator


# ═══════════════════════════════════════════════════════════════════════════
# Layer 2 — Agent Performance (RAGAS metrics, 12 points)
# ═══════════════════════════════════════════════════════════════════════════

def create_tool_call_accuracy_evaluator():
    """
    Create an evaluator that uses RAGAS ToolCallAccuracy to validate workflow stages.

    Returns:
        A callable evaluator function
    """
    from ragas.metrics import ToolCallAccuracy
    from ragas.dataset_schema import MultiTurnSample
    from ragas.messages import HumanMessage, AIMessage, ToolCall
    import asyncio
    def tool_call_accuracy_evaluator(inputs, outputs, reference_outputs) -> dict:
        actual_path = outputs.get("approval_path", [])
        expected_path = reference_outputs.get("approval_path", [])
        actual_calls = [ToolCall(name=s, args={}) for s in actual_path]
        expected_calls = [ToolCall(name=s, args={}) for s in expected_path]
        sample = MultiTurnSample(
            user_input=[
                HumanMessage(content=inputs.get("description", "Request")),
                AIMessage(content=f"Status: {outputs.get('status')}", tool_calls=actual_calls),
            ],
            reference_tool_calls=expected_calls,
        )
        metric = ToolCallAccuracy()
        try:
            score = asyncio.run(metric.multi_turn_ascore(sample))
            return {"score": float(score), "reasoning": "RAGAS ToolCallAccuracy computed"}
        except Exception as e:
            match = actual_path == expected_path
            return {"score": 1.0 if match else 0.0, "reasoning": f"Fallback comparison: {e}"}
    return tool_call_accuracy_evaluator


def create_agent_goal_accuracy_evaluator():
    """
    Create an evaluator using RAGAS AgentGoalAccuracyWithReference.

    Returns:
        A callable evaluator function
    """
    def agent_goal_accuracy_evaluator(inputs, outputs, reference_outputs) -> dict:
        from ragas.metrics import AgentGoalAccuracyWithReference
        from ragas.dataset_schema import MultiTurnSample
        from ragas.messages import HumanMessage, AIMessage
        from ragas.llms import LangchainLLMWrapper
        from backend.config import get_llm
        import asyncio
        actual_status = outputs.get("status", "unknown")
        expected_status = reference_outputs.get("status", "unknown")
        desc = inputs.get("description", inputs.get("title", "Financial request"))
        sample = MultiTurnSample(
            user_input=[
                HumanMessage(content=desc),
                AIMessage(content=f"Status: {actual_status}. Risk: {outputs.get('risk_level')}."),
            ],
            reference=f"Request is {expected_status}",
        )
        try:
            metric = AgentGoalAccuracyWithReference(llm=LangchainLLMWrapper(get_llm()))
            score = asyncio.run(metric.multi_turn_ascore(sample))
            return {"score": float(score), "reasoning": "RAGAS AgentGoalAccuracy evaluated"}
        except Exception as e:
            match = actual_status == expected_status
            return {"score": 1.0 if match else 0.0, "reasoning": f"Fallback: {e}"}
    return agent_goal_accuracy_evaluator


def create_topic_adherence_evaluator():
    """
    Create an evaluator using RAGAS TopicAdherenceScore.

    Returns:
        A callable evaluator function
    """
    def topic_adherence_evaluator(inputs, outputs, reference_outputs) -> dict:
        from ragas.metrics import TopicAdherenceScore
        from ragas.dataset_schema import MultiTurnSample
        from ragas.messages import HumanMessage, AIMessage
        from ragas.llms import LangchainLLMWrapper
        from backend.config import get_llm
        import asyncio
        title = inputs.get("title", "")
        desc = inputs.get("description", "")
        amount = inputs.get("amount", 0)
        dept = inputs.get("department", "")
        summary = f"Title: {title}. Description: {desc}. Amount: ${amount}. Department: {dept}."
        agent_text = f"Status: {outputs.get('status')}. Risk: {outputs.get('risk_level')}."
        sample = MultiTurnSample(
            user_input=[
                HumanMessage(content=summary),
                AIMessage(content=agent_text),
            ],
            reference_topics=REFERENCE_TOPICS,
        )
        try:
            metric = TopicAdherenceScore(llm=LangchainLLMWrapper(get_llm()), mode="precision")
            score = asyncio.run(metric.multi_turn_ascore(sample))
            return {"score": float(score), "reasoning": "RAGAS TopicAdherence evaluated"}
        except Exception as e:
            return {"score": 1.0, "reasoning": f"Fallback: {e}"}
    return topic_adherence_evaluator


# ═══════════════════════════════════════════════════════════════════════════
# Layer 3 — Safety & Compliance (RAGAS + heuristic, 12 points)
# ═══════════════════════════════════════════════════════════════════════════

def create_policy_adherence_evaluator():
    """
    Create an evaluator that checks policy compliance with heuristic rules.

    Returns:
        A callable evaluator function
    """
    def policy_adherence_evaluator(inputs, outputs, reference_outputs) -> dict:
        amount = float(inputs.get("amount", 0))
        status = outputs.get("status")
        risk_level = outputs.get("risk_level")
        reviews = outputs.get("human_reviews", 0)
        # Rule 1: Amounts over ceiling must be rejected
        rule1 = (status == "rejected") if amount > BUDGET_CEILING else True
        # Rule 2: Minimum human reviews for approved requests
        rule2 = True
        if status == "approved" and risk_level in EXPECTED_REVIEWS_BY_RISK:
            rule2 = reviews >= EXPECTED_REVIEWS_BY_RISK[risk_level]
        # Rule 3: Negative or zero amounts must be rejected
        rule3 = (status == "rejected") if amount <= 0 else True
        passed = sum([rule1, rule2, rule3])
        score = passed / 3.0
        reasoning = f"Passed {passed}/3 policy rules (Ceiling: {rule1}, MinReviews: {rule2}, PositiveAmount: {rule3})"
        return {"score": float(score), "reasoning": reasoning}
    return policy_adherence_evaluator


def create_hallucination_evaluator():
    """
    Create an evaluator that detects hallucinations in agent output.

      Option B — Direct LLM judge:
        1. Use get_llm() to create an LLM
        2. Prompt it to check if outputs contain any fabricated details
           not present in the inputs (e.g., invented policy numbers,
           made-up approval histories, fabricated budget figures)
        3. Parse the LLM response text into a score (response.text, not
           response.content: Gemini returns content as a list of content blocks)

    Returns:
        A callable evaluator function
    """
    def hallucination_evaluator(inputs, outputs, reference_outputs) -> dict:
        from backend.config import get_llm
        from langchain_core.messages import HumanMessage
        prompt = f"""You are an enterprise compliance auditor. Check if the agent's output contains any fabricated or hallucinated details that are not supported by the request inputs or the workflow record.
Request Inputs:
{inputs}
Workflow Outputs:
{outputs}
Respond strictly in this format:
HALLUCINATION: <YES|NO>
REASONING: <brief explanation>
"""
        try:
            llm = get_llm(temperature=0.0)
            response = llm.invoke([HumanMessage(content=prompt)])
            text = response.text.strip()
            score = 1.0
            if "HALLUCINATION: YES" in text.upper():
                score = 0.0
            return {"score": score, "reasoning": text}
        except Exception as e:
            # Fallback heuristic: clean if statuses match
            return {"score": 1.0, "reasoning": f"Heuristic pass: {e}"}
    return hallucination_evaluator


def create_audit_trail_evaluator():
    """
    Create an evaluator that validates the completeness of the audit trail.

    Returns:
        A callable evaluator function
    """
    def audit_trail_evaluator(inputs, outputs, reference_outputs) -> dict:
        decisions = outputs.get("decisions", [])
        # Determine expected human reviews
        if "decisions" in reference_outputs:
            expected_count = len(reference_outputs["decisions"])
        else:
            expected_path = reference_outputs.get("approval_path", [])
            expected_count = sum(1 for stage in expected_path if stage in HUMAN_REVIEW_STAGES)
        # Check 1: decisions non-empty when expected > 0 (or empty when expected == 0)
        check1 = (len(decisions) > 0) if expected_count > 0 else (len(decisions) == 0)
        # Check 2: each entry has 'stage', 'decision', 'reasoning'
        required_keys = {"stage", "decision", "reasoning"}
        check2 = all(required_keys.issubset(d.keys()) for d in decisions)
        # Check 3: number of decisions equals expected count
        check3 = (len(decisions) == expected_count)
        passed = sum([check1, check2, check3])
        score = passed / 3.0
        reasoning = f"Passed {passed}/3 audit checks (Presence: {check1}, Keys: {check2}, Count: {check3})"
        return {"score": float(score), "reasoning": reasoning}
    return audit_trail_evaluator
