"""
LLM-based evaluation dataset generator for the Financial Approval System.

Students implement functions to:
1. Generate diverse test cases using an LLM
2. Generate edge/adversarial cases
3. Upload datasets to LangSmith
4. Validate generated datasets

Part 5: Dataset Generation (16 points)
"""

import json

# ---------------------------------------------------------------------------
# Constants (GIVEN — do not modify)
# ---------------------------------------------------------------------------

VALID_DEPARTMENTS = ["engineering", "marketing", "operations", "research", "hr"]

BUDGET_CEILING = 100_000

DEPARTMENT_BUDGETS = {
    "engineering": 50000,
    "marketing": 30000,
    "operations": 40000,
    "research": 60000,
    "hr": 5000,
}

DATASET_SCHEMA = {
    "input": {
        "request_id": "str — unique identifier (e.g., 'GEN-001')",
        "title": "str — short description of the purchase",
        "description": "str — detailed description",
        "amount": "float — dollar amount (can be negative for edge cases)",
        "department": "str — one of VALID_DEPARTMENTS",
        "requester": "str — person making the request",
        "justification": "str — business justification",
        "priority": "str — one of: low, normal, high, urgent",
    },
    "expected": {
        "risk_level": "str or None: one of low, medium, high, critical; None (JSON null) "
                      "when the request is rejected at submit_request, because assess_risk never runs",
        "status": "str — one of: approved, rejected",
        "approval_path": "list[str] — ordered list of workflow stages",
        "human_reviews": "int — number of human review interrupts expected",
    },
}

OUTPUT_FORMAT = """
Output format (validate_generated_dataset rejects a case that does not follow it):
Each test case is a JSON object with exactly two keys, "input" and "expected".
"input" has all 8 of these fields:
  "request_id": string, unique (e.g. "GEN-001")
  "title": string, short name of the purchase
  "description": string, details of the purchase
  "amount": number, not a string (dollars)
  "department": one of {departments}
  "requester": string, name of the person making the request
  "justification": string, business reason for the purchase
  "priority": one of "low", "normal", "high", "urgent"
"expected" has all 4 of these fields:
  "risk_level": one of "low", "medium", "high", "critical", or null when the request is
    rejected at submit_request (its approval_path has no "assess_risk")
  "status": "approved" or "rejected" (lowercase)
  "approval_path": list of stage names in order, taken from: "submit_request",
    "assess_risk", "validate_budget", "manager_review", "finance_review",
    "final_signoff", "process_request", "handle_rejection"
  "human_reviews": integer >= 0, the number of "manager_review", "finance_review" and
    "final_signoff" stages in approval_path
Use these key names exactly ("approval_path", not "path"; "human_reviews", not
"review_count" or "required_reviews"). risk_level, status and priority are lowercase.
Expected values assume every human reviewer approves, so "rejected" is only for
requests rejected at submit_request.

Example of one test case:
{{"input": {{"request_id": "GEN-001", "title": "Team Laptops",
  "description": "Three laptops for new hires", "amount": 4500.0,
  "department": "engineering", "requester": "Dana Lee",
  "justification": "New hires start next month", "priority": "normal"}},
 "expected": {{"risk_level": "low", "status": "approved",
  "approval_path": ["submit_request", "assess_risk", "validate_budget", "process_request"],
  "human_reviews": 0}}}}

Return ONLY a JSON array of test case objects. No markdown, no explanation.
"""

GENERATION_PROMPT = """You are a test case generator for a Financial Approval System.

Generate {num_cases} diverse test cases for evaluating the system. Each test case
should be a JSON object with "input" and "expected" fields.

Business Rules:
- Amounts <= $10,000: low risk, auto-approved (0 human reviews)
  Path: submit_request → assess_risk → validate_budget → process_request
- Amounts $10,001-$50,000: medium risk, needs manager review (1 human review)
  Path: submit_request → assess_risk → manager_review → validate_budget → process_request
- Amounts $50,001-$100,000: high risk, needs manager + finance review (2 human reviews)
  Path: submit_request → assess_risk → manager_review → finance_review → process_request
- Amounts > $100,000: rejected (exceeds budget ceiling)
  Path: submit_request → handle_rejection
- Zero or negative amounts: rejected (invalid)
  Path: submit_request → handle_rejection
- Requests rejected at submit_request never reach assess_risk: their expected
  risk_level is null
- Priority "urgent" + amount > $50,000: critical risk, needs 3 reviews
  Path: submit_request → assess_risk → manager_review → finance_review → final_signoff → process_request
- Department budgets: engineering $50,000, marketing $30,000, operations $40,000,
  research $60,000, hr $5,000. validate_budget escalates when the amount is over budget:
  - Low risk over budget: manager review (1 human review)
    Path: submit_request → assess_risk → validate_budget → manager_review → process_request
  - Medium risk over budget: finance review after the budget check (2 human reviews)
    Path: submit_request → assess_risk → manager_review → validate_budget → finance_review → process_request

Valid departments: {departments}
Valid priorities: low, normal, high, urgent

Generate realistic financial requests covering different departments, amounts,
and risk levels. Include a mix of approved and rejected cases.
""" + OUTPUT_FORMAT

EDGE_CASE_PROMPT = """You are a test case generator for a Financial Approval System.
Generate {num_cases} EDGE CASES and ADVERSARIAL scenarios.

Focus on boundary conditions and tricky scenarios:
1. Amounts exactly at thresholds ($10,000, $50,000, $100,000)
2. Negative amounts or zero amounts
3. Very large amounts (> $1,000,000)
4. Unusual descriptions that might confuse the system
5. Requests that test policy boundaries

Business Rules:
- Amounts <= $10,000: low risk, auto-approved (0 human reviews)
  Path: submit_request → assess_risk → validate_budget → process_request
- Amounts $10,001-$50,000: medium risk, manager review (1 human review)
  Path: submit_request → assess_risk → manager_review → validate_budget → process_request
- Amounts $50,001-$100,000: high risk, manager + finance review (2 human reviews)
  Path: submit_request → assess_risk → manager_review → finance_review → process_request
- Priority "urgent" + amount > $50,000: critical risk, 3 reviews (no budget check)
  Path: submit_request → assess_risk → manager_review → finance_review → final_signoff → process_request
- Rejected at submit_request: amounts > $100,000, zero or negative amounts, and text
  containing SQL or script injection (for example "<script>" or "' or '1'='1")
  Path: submit_request → handle_rejection. These never reach assess_risk: their
  expected risk_level is null and human_reviews is 0
- Over the department budget (engineering $50,000, marketing $30,000, operations $40,000,
  research $60,000, hr $5,000), only for low and medium risk:
  - Low risk: submit_request → assess_risk → validate_budget → manager_review → process_request (1 review)
  - Medium risk: submit_request → assess_risk → manager_review → validate_budget → finance_review → process_request (2 reviews)

Valid departments: {departments}
Use only these departments: an invalid department fails validate_generated_dataset.
""" + OUTPUT_FORMAT


# ═══════════════════════════════════════════════════════════════════════════
# Student Implementation — Dataset Generation Functions (16 points)
# ═══════════════════════════════════════════════════════════════════════════

def generate_eval_dataset(num_cases=10, llm=None):
    """
    Generate diverse evaluation test cases using an LLM.

    Student Note (Synthetic Data Generation with Structured Prompts):
    Uses a formatted generation prompt containing strict business rules and schema
    constraints. Strips markdown fences if returned by the model before parsing JSON.

    Returns:
        list[dict]: Generated test cases matching DATASET_SCHEMA
    """
    if llm is None:
        from backend.config import get_llm
        llm = get_llm(temperature=0.7)

    from langchain_core.messages import HumanMessage
    prompt = GENERATION_PROMPT.format(
        num_cases=num_cases,
        departments=", ".join(VALID_DEPARTMENTS)
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    text = response.text.strip()

    # Strip markdown code fences if returned by the LLM (e.g. ```json ... ```)
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return json.loads(text)


def generate_edge_cases(num_cases=5, llm=None):
    """
    Generate boundary and adversarial test cases using an LLM.

    Student Note (Adversarial Dataset Generation):
    Generates test cases specifically targeting edge boundaries:
      - Threshold boundary values ($10,000, $50,000, $100,000)
      - Negative/zero amounts
      - Prompt injection vectors (' or '1'='1, <script>)
      - Budget edge cases (low risk over department budget)

    Args:
        num_cases: Number of edge cases to generate (default 5)
        llm: Optional LangChain LLM instance (if None, use get_llm())

    Returns:
        list[dict]: Generated edge cases matching DATASET_SCHEMA
    """
    if llm is None:
        from backend.config import get_llm
        llm = get_llm(temperature=0.7)

    from langchain_core.messages import HumanMessage
    prompt = EDGE_CASE_PROMPT.format(
        num_cases=num_cases,
        departments=", ".join(VALID_DEPARTMENTS)
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    text = response.text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return json.loads(text)


def upload_to_langsmith(dataset, dataset_name="financial-approval-eval"):
    """
    Upload a dataset to LangSmith for evaluation runs.

    Student Note (LangSmith Dataset Management):
    Uses the official langsmith.Client to create a dataset and iterate over
    test cases to create examples with 'inputs' and 'outputs' (reference).

    Args:
        dataset: list[dict] — test cases with "input" and "expected" keys
        dataset_name: str — name for the LangSmith dataset

    Returns:
        str: The LangSmith dataset ID

    Raises:
        ValueError: If dataset is empty
    """
    if not dataset:
        raise ValueError("Dataset cannot be empty")

    import langsmith
    import backend.config  # ensures .env is loaded
    client = langsmith.Client()

    ls_dataset = client.create_dataset(dataset_name=dataset_name)
    for case in dataset:
        client.create_example(
            inputs=case["input"],
            outputs=case["expected"],
            dataset_id=ls_dataset.id,
        )
    return str(ls_dataset.id)


def validate_generated_dataset(dataset):
    """
    Validate that a generated dataset conforms to the expected schema.

    Student Note (Schema and Integrity Verification):
    Enforces strict structural and type validation:
      1. Non-empty list of dictionaries
      2. Exactly matches all 8 required input fields
      3. Validates amount is numerical (float/int)
      4. Validates department is one of VALID_DEPARTMENTS
      5. Validates risk_level is in ['low', 'medium', 'high', 'critical', None]
      6. Validates status is in ['approved', 'rejected']
      7. Validates approval_path is a list and human_reviews is non-negative int

    Args:
        dataset: list[dict] — the dataset to validate

    Returns:
        tuple[bool, list[str]]: (is_valid, error_messages)
    """
    errors = []

    if not isinstance(dataset, list) or len(dataset) == 0:
        return False, ["Dataset must be a non-empty list"]

    required_input_fields = [
        "request_id", "title", "description", "amount",
        "department", "requester", "justification", "priority"
    ]
    required_expected_fields = ["risk_level", "status", "approval_path", "human_reviews"]
    valid_risks = ["low", "medium", "high", "critical", None]

    for i, case in enumerate(dataset):
        prefix = f"Case {i+1}:"

        if not isinstance(case, dict):
            errors.append(f"{prefix} item is not a dictionary")
            continue

        inp = case.get("input")
        exp = case.get("expected")

        if not isinstance(inp, dict):
            errors.append(f"{prefix} missing 'input' dictionary")
            continue
        if not isinstance(exp, dict):
            errors.append(f"{prefix} missing 'expected' dictionary")
            continue

        # Check input fields
        for field in required_input_fields:
            if field not in inp:
                errors.append(f"{prefix} input missing '{field}'")

        if "amount" in inp and not isinstance(inp["amount"], (int, float)):
            errors.append(f"{prefix} amount must be a number")

        if "department" in inp and inp["department"] not in VALID_DEPARTMENTS:
            errors.append(f"{prefix} invalid department: {inp['department']}")

        # Check expected fields
        for field in required_expected_fields:
            if field not in exp:
                errors.append(f"{prefix} expected missing '{field}'")

        if "risk_level" in exp and exp["risk_level"] not in valid_risks:
            errors.append(f"{prefix} invalid risk_level: {exp['risk_level']}")

        if "status" in exp and exp["status"] not in ["approved", "rejected"]:
            errors.append(f"{prefix} invalid status: {exp['status']}")

        if "approval_path" in exp and not isinstance(exp["approval_path"], list):
            errors.append(f"{prefix} approval_path must be a list")

        if "human_reviews" in exp and (
            not isinstance(exp["human_reviews"], int)
            or exp["human_reviews"] < 0
            or isinstance(exp["human_reviews"], bool)
        ):
            errors.append(f"{prefix} human_reviews must be an integer >= 0")

    return (len(errors) == 0, errors)
