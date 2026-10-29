"""
LangGraph StateGraph assembly for the Financial Approval workflow.

Students wire together the 8 nodes and 6 routing functions into
a complete approval pipeline with risk-based escalation and
up to 3 human-in-the-loop interrupts.

Part 1: LangGraph Workflow + Interrupts (35 points)
"""

from langgraph.graph import StateGraph, START, END
from backend.agent.state import ApprovalState
from backend.agent.nodes import (
    submit_request,
    assess_risk,
    manager_review,
    validate_budget,
    finance_review,
    final_signoff,
    process_request,
    handle_rejection,
    route_after_submission,
    route_after_risk,
    route_after_manager,
    route_after_budget,
    route_after_finance,
    route_after_final,
)


def create_approval_graph(checkpointer=None):
    """
    Build and return the compiled Financial Approval StateGraph.

    The graph implements risk-based escalation:
    - Low risk:      auto-approve → budget check → done (0 human reviews)
    - Medium risk:   manager review → budget check → done (1 human review)
    - High risk:     manager → finance review → done (2 human reviews)
    - Critical risk: manager → finance → executive sign-off (3 human reviews)
    - Over-budget:   escalates to the next human reviewer

    """
    graph = StateGraph(ApprovalState)
    # 1. Add all 8 nodes
    graph.add_node("submit_request", submit_request)
    graph.add_node("assess_risk", assess_risk)
    graph.add_node("manager_review", manager_review)
    graph.add_node("validate_budget", validate_budget)
    graph.add_node("finance_review", finance_review)
    graph.add_node("final_signoff", final_signoff)
    graph.add_node("process_request", process_request)
    graph.add_node("handle_rejection", handle_rejection)
    # 2. Add entry edge
    graph.add_edge(START, "submit_request")
    # 3. Add 6 conditional edges
    graph.add_conditional_edges("submit_request", route_after_submission, {
        "assess_risk": "assess_risk",
        "handle_rejection": "handle_rejection",
    })
    graph.add_conditional_edges("assess_risk", route_after_risk, {
        "validate_budget": "validate_budget",
        "manager_review": "manager_review",
    })
    graph.add_conditional_edges("manager_review", route_after_manager, {
        "process_request": "process_request",
        "validate_budget": "validate_budget",
        "finance_review": "finance_review",
        "handle_rejection": "handle_rejection",
    })
    graph.add_conditional_edges("validate_budget", route_after_budget, {
        "process_request": "process_request",
        "manager_review": "manager_review",
        "finance_review": "finance_review",
    })
    graph.add_conditional_edges("finance_review", route_after_finance, {
        "process_request": "process_request",
        "final_signoff": "final_signoff",
        "handle_rejection": "handle_rejection",
    })
    graph.add_conditional_edges("final_signoff", route_after_final, {
        "process_request": "process_request",
        "handle_rejection": "handle_rejection",
    })
    # 4. Terminal edges
    graph.add_edge("process_request", END)
    graph.add_edge("handle_rejection", END)
    # 5. Compile with checkpointer
    return graph.compile(checkpointer=checkpointer)