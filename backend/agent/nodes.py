"""
Node functions for the Financial Approval workflow.

Students implement 8 node functions and 6 routing functions that
form the LangGraph approval pipeline with risk-based escalation.

Part 1: LangGraph Workflow + Interrupts (35 points)
"""

import json

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import interrupt, Command
from backend.agent.state import ApprovalState
from backend.config import (
    get_llm,
    BUDGET_CEILING,
    DEPARTMENT_BUDGETS,
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
)
from backend.guardrails.input_validator import validate_request
from backend.guardrails.output_filter import sanitize_output


# ============================================================
# NODE FUNCTIONS (8 total)
# ============================================================

def submit_request(state: ApprovalState) -> dict:
    """
    Node 1: Receive and validate the financial request.
    """
    import time

    title = state.get("title", "Untitled Request")
    amount = float(state.get("amount", 0))
    dept = state.get("department", "unknown")
    desc = state.get("description", "")
    just = state.get("justification", "")
    req_id = state.get("request_id") or f"REQ-{int(time.time() * 1000) % 1000000:06d}"

    # GOTCHA #1: Guardrail fallback
    # validate_request is implemented in Part 2. Wrapping in try/except allows
    # testing the graph workflow before Part 2 guardrails are completed.
    try:
        is_valid, validation_message = validate_request(
            amount=amount,
            department=dept,
            title=title,
            description=desc,
            justification=just,
        )
    except NotImplementedError:
        is_valid, validation_message = True, "Validation passed"

    # GOTCHA #2: Thread Reuse & Checkpoint Pollution
    # CopilotKit reuses a single thread across consecutive chat requests.
    # We must explicitly reset prior review decisions and risk ratings so that
    # previous state doesn't leak into subsequent submissions.
    #
    # GOTCHA #3: Budget 'None' vs '0'
    # High and critical requests skip budget validation. In the frontend ApprovalPanel,
    # None renders as "Not checked", whereas 0 renders as "$0, Within budget".
    updates = {
        "request_id": req_id,
        "is_valid": is_valid,
        "validation_message": validation_message,
        "decisions": [],
        "risk_level": None,
        "risk_reasoning": "",
        "manager_approved": None,
        "manager_comments": "",
        "finance_approved": None,
        "finance_comments": "",
        "final_approved": None,
        "final_comments": "",
        "department_budget": None,
        "budget_remaining": None,
        "within_budget": None,
    }

    if not is_valid:
        updates["status"] = "rejected"
        updates["current_stage"] = "rejection"
        updates["messages"] = [
            AIMessage(content=f"Request '{title}' rejected: {validation_message}")
        ]
    else:
        updates["status"] = "pending"
        updates["current_stage"] = "risk_assessment"
        updates["messages"] = [
            AIMessage(content=f"Received request: '{title}' for ${amount:,.2f} from {dept} department.")
        ]

    return updates


def assess_risk(state: ApprovalState) -> dict:
    """
    Node 2: Use LLM to assess risk level of the request.
    """
    title = state.get("title", "")
    desc = state.get("description", "")
    amount = float(state.get("amount", 0))
    dept = state.get("department", "")
    just = state.get("justification", "")
    priority = state.get("priority", "normal")

    # GOTCHA #4: Explicit Evaluation Rubric
    # The evaluation datasets in Parts 4 & 5 expect exact risk tiers. We encode
    # the exact boundary rules directly into the prompt to ensure deterministic scoring.
    prompt = f"""You are an enterprise financial risk assessor. Evaluate the risk level of this expense request.

Request Details:
- Title: {title}
- Description: {desc}
- Amount: ${amount:,.2f}
- Department: {dept}
- Justification: {just}
- Priority: {priority}

Rules for Risk Assessment:
1. Amount <= $10,000 -> "low"
2. Amount $10,001 - $50,000 -> "medium"
3. Amount $50,001 - $100,000 -> "high"
4. Priority "urgent" AND Amount > $50,000 -> "critical"

Respond strictly in this format:
RISK_LEVEL: <low|medium|high|critical>
REASONING: <brief justification>
"""
    try:
        llm = get_llm(temperature=0.0)
        response = llm.invoke([HumanMessage(content=prompt)])
        # GOTCHA #5: response.text vs response.content
        # OpenAI returns content as str, but Gemini returns content as a list of ContentBlocks.
        # Calling response.text (property) returns a clean string uniformly across both providers.
        text = response.text.strip()

        level = "medium"
        reasoning = text
        for line in text.splitlines():
            if line.upper().startswith("RISK_LEVEL:"):
                raw_level = line.split(":", 1)[1].strip().lower()
                for candidate in ("critical", "high", "medium", "low"):
                    if candidate in raw_level:
                        level = candidate
                        break
            elif line.upper().startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()
    except Exception as e:
        level = "medium"
        reasoning = f"Assessment fallback due to error: {e}"

    return {
        "risk_level": level,
        "risk_reasoning": reasoning,
        "current_stage": "risk_assessed",
        "messages": [AIMessage(content=f"Risk assessment: {level.upper()} — {reasoning}")],
    }


def manager_review(state: ApprovalState) -> dict:
    """
    Node 3: Manager review with human-in-the-loop interrupt.
    """
    raw = interrupt({
        "type": "manager_review",
        "request_id": state.get("request_id", ""),
        "title": state.get("title", ""),
        "amount": state.get("amount", 0),
        "department": state.get("department", ""),
        "risk_level": state.get("risk_level", "medium"),
        "risk_reasoning": state.get("risk_reasoning", ""),
    })

    # GOTCHA #6: String vs Dict Return from interrupt()
    # CopilotKit's resolve() passes JSON.stringify(...) over the wire, so the returned
    # payload may be a string rather than a dict.
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {"approved": False, "comments": raw}
    approved = raw.get("approved", False) if isinstance(raw, dict) else False
    comments = raw.get("comments", "") if isinstance(raw, dict) else ""

    # GOTCHA #7: Audit Trail Keys Required by Part 5
    # The Part 5 audit trail evaluator specifically inspects 'decision' ('approved'|'rejected')
    # and 'reasoning', in addition to 'approved' and 'comments'.
    decision_entry = {
        "stage": "manager_review",
        "approved": approved,
        "decision": "approved" if approved else "rejected",
        "reviewer": "Manager",
        "comments": comments,
        "reasoning": comments,
    }

    status_str = "approved" if approved else "rejected"
    comment_suffix = f" Comments: {comments}" if comments else ""

    # GOTCHA #8: decisions list has NO Reducer
    # Unlike 'messages' (which appends automatically via MessagesState), 'decisions' will be
    # overwritten unless we explicitly concatenate with state.get('decisions', []).
    return {
        "manager_approved": approved,
        "manager_comments": comments,
        "decisions": state.get("decisions", []) + [decision_entry],
        "messages": [AIMessage(content=f"Manager {status_str} the request.{comment_suffix}")],
    }

def validate_budget(state: ApprovalState) -> dict:
    """
    Node 4: Validate request against department budget.

    """
    dept = state.get("department", "")
    amount = float(state.get("amount", 0))
    budget = float(DEPARTMENT_BUDGETS.get(dept, 0))
    within = amount <= budget
    remaining = budget - amount
    status_word = "within" if within else "OVER"
    msg = f"Budget check: {dept} budget is ${budget:,.2f}. Request for ${amount:,.2f} is {status_word} budget (remaining: ${remaining:,.2f})."
    return {
        "department_budget": budget,
        "budget_remaining": remaining,
        "within_budget": within,
        "current_stage": "budget_validated",
        "messages": [AIMessage(content=msg)],
    }

def finance_review(state: ApprovalState) -> dict:
    """
    Node 5: Finance team review with human-in-the-loop interrupt.

    """
    raw = interrupt({
        "type": "finance_review",
        "request_id": state.get("request_id", ""),
        "title": state.get("title", ""),
        "amount": state.get("amount", 0),
        "department": state.get("department", ""),
        "risk_level": state.get("risk_level", "high"),
        "within_budget": state.get("within_budget", True),
        "department_budget": state.get("department_budget", 0),
        "budget_remaining": state.get("budget_remaining", 0),
        "manager_comments": state.get("manager_comments", ""),
    })
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {"approved": False, "comments": raw}
    approved = raw.get("approved", False) if isinstance(raw, dict) else False
    comments = raw.get("comments", "") if isinstance(raw, dict) else ""
    decision_entry = {
        "stage": "finance_review",
        "approved": approved,
        "decision": "approved" if approved else "rejected",
        "reviewer": "Finance",
        "comments": comments,
        "reasoning": comments,
    }
    status_str = "approved" if approved else "rejected"
    comment_suffix = f" Comments: {comments}" if comments else ""
    return {
        "finance_approved": approved,
        "finance_comments": comments,
        "decisions": state.get("decisions", []) + [decision_entry],
        "messages": [AIMessage(content=f"Finance {status_str} the request.{comment_suffix}")],
    }

def final_signoff(state: ApprovalState) -> dict:
    """
    Node 6: Executive final sign-off with human-in-the-loop interrupt.

    """
    raw = interrupt({
        "type": "final_signoff",
        "request_id": state.get("request_id", ""),
        "title": state.get("title", ""),
        "amount": state.get("amount", 0),
        "department": state.get("department", ""),
        "risk_level": state.get("risk_level", "critical"),
        "manager_approved": state.get("manager_approved", False),
        "finance_approved": state.get("finance_approved", False),
        "within_budget": state.get("within_budget", True),
        "decisions": state.get("decisions", []),
    })
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {"approved": False, "comments": raw}
    approved = raw.get("approved", False) if isinstance(raw, dict) else False
    comments = raw.get("comments", "") if isinstance(raw, dict) else ""
    decision_entry = {
        "stage": "final_signoff",
        "approved": approved,
        "decision": "approved" if approved else "rejected",
        "reviewer": "Executive",
        "comments": comments,
        "reasoning": comments,
    }
    status_str = "approved" if approved else "rejected"
    comment_suffix = f" Comments: {comments}" if comments else ""
    return {
        "final_approved": approved,
        "final_comments": comments,
        "current_stage": "processing" if approved else "rejection",
        "decisions": state.get("decisions", []) + [decision_entry],
        "messages": [AIMessage(content=f"Executive {status_str} the request.{comment_suffix}")],
    }

def process_request(state: ApprovalState) -> dict:
    """
    Node 7: Process the fully-approved request.

    """
    title = state.get("title", "request")
    risk = state.get("risk_level", "unknown")
    amount = float(state.get("amount", 0))
    summary = f"Request '{title}' for ${amount:,.2f} (risk: {risk}) has been APPROVED and processed."
    try:
        summary = sanitize_output(summary)
    except NotImplementedError:
        pass
    return {
        "status": "approved",
        "current_stage": "complete",
        "messages": [AIMessage(content=summary)],
    }

def handle_rejection(state: ApprovalState) -> dict:
    """
    Node 8: Handle a rejected request.

    """
    title = state.get("title", "request")
    decisions = state.get("decisions", [])
    rejector = "system validation"
    reason = state.get("validation_message", "")
    for d in reversed(decisions):
        if not d.get("approved", True):
            rejector = d.get("reviewer", "reviewer")
            reason = d.get("comments") or d.get("reasoning", "")
            break
    reason_suffix = f" Reason: {reason}" if reason else ""
    summary = f"Request '{title}' was REJECTED by {rejector}.{reason_suffix}"
    try:
        summary = sanitize_output(summary)
    except NotImplementedError:
        pass
    return {
        "status": "rejected",
        "current_stage": "complete",
        "messages": [AIMessage(content=summary)],
    }

# ============================================================
# ROUTING FUNCTIONS (6 total — implement the escalation logic)
# ============================================================

def route_after_submission(state: ApprovalState) -> str:
    """
    Router: After submit_request, go to risk assessment or rejection.
    """
    if state.get("is_valid", False):
        return "assess_risk"
    return "handle_rejection"


def route_after_risk(state: ApprovalState) -> str:
    """
    Router: After assess_risk, route based on risk level.

    This is the core escalation entry point. Low-risk requests skip
    human review and go directly to budget validation (auto-approve path).
    All other risk levels require manager review first.
    """
    if state.get("risk_level") == "low":
        return "validate_budget"
    return "manager_review"


def route_after_manager(state: ApprovalState) -> str:
    """
    Router: After manager_review, route based on approval + risk level.

    The next step depends on BOTH the manager's decision AND the risk level:
    - Rejected → handle_rejection (any risk level)
    - Approved + low risk (over-budget escalation) → process_request
    - Approved + medium risk → validate_budget
    - Approved + high/critical risk → finance_review
    """
    if not state.get("manager_approved", False):
        return "handle_rejection"
    
    risk = state.get("risk_level", "medium")
    if risk == "low":
        return "process_request"
    if risk == "medium":
        return "validate_budget"
    return "finance_review"


def route_after_budget(state: ApprovalState) -> str:
    """
    Router: After validate_budget, route based on budget status + risk level.

    Within-budget requests proceed to processing (auto-approved).
    Over-budget requests escalate to the next human reviewer.
    """
    if state.get("within_budget", False):
        return "process_request"
    
    risk = state.get("risk_level", "low")
    if risk == "low":
        return "manager_review"
    return "finance_review"


def route_after_finance(state: ApprovalState) -> str:
    """
    Router: After finance_review, route based on approval + risk level.

    The next step depends on BOTH finance's decision AND the risk level:
    - Rejected → handle_rejection
    - Approved + critical risk → final_signoff (one more review)
    - Approved + any other risk → process_request (done)
    """
    if not state.get("finance_approved", False):
        return "handle_rejection"
    
    if state.get("risk_level") == "critical":
        return "final_signoff"
    return "process_request"


def route_after_final(state: ApprovalState) -> str:
    """
    Router: After final_signoff, go to processing or rejection.
    """
    if state.get("final_approved", False):
        return "process_request"
    return "handle_rejection"
