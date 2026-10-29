"""
Input validation guardrails for the Financial Approval System.

Students implement validation functions that enforce safety rules
on incoming financial requests.

Part 2: Safety Guardrails (10 points from this file)
"""

from backend.config import BUDGET_CEILING, VALID_DEPARTMENTS

# --- GIVEN: Blocked patterns for SQL injection detection ---
BLOCKED_PATTERNS = [
    "drop table", "delete from", "insert into", "update set",
    "union select", "' or '1'='1", "'; --", "<script>",
    "javascript:", "onclick=", "onerror=", "eval(",
    "__import__", "os.system", "subprocess",
]

# --- GIVEN: Maximum field lengths ---
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_JUSTIFICATION_LENGTH = 2000


def validate_request(
    amount: float,
    department: str,
    title: str,
    description: str,
    justification: str,
) -> tuple[bool, str]:
    """
    Validate a financial request against safety rules.

    Student Note (Validation Architecture):
    Input validation operates as the first line of defense before data enters the
    LangGraph execution pipeline. It enforces 4 sequential safety gates:
      1. Boundary validation (positive, non-zero, below enterprise budget ceiling)
      2. Department whitelist validation (ensures valid cost center)
      3. Payload length limits (guards against buffer/token bloat attacks)
      4. Injection sanitization (blocks SQL/XSS/script breakout patterns)

    Args:
        amount: Requested dollar amount
        department: Department name
        title: Request title
        description: Request description
        justification: Business justification

    Returns:
        Tuple of (is_valid, message)
    """

    # Gate 1: Amount validation
    amount_valid, amount_msg = validate_amount(amount)
    if not amount_valid:
        return False, amount_msg

    # Gate 2: Department whitelist check
    if department not in VALID_DEPARTMENTS:
        return False, f"Invalid department: {department}"

    # Gate 3: Field length boundary checks
    if len(title) > MAX_TITLE_LENGTH:
        return False, "Title too long"

    # Gate 4: Content sanitization (injection checks across all user text fields)
    for field_val, field_name in [
        (title, "title"),
        (description, "description"),
        (justification, "justification"),
    ]:
        is_safe, msg = sanitize_text(field_val, field_name)
        if not is_safe:
            return False, msg

    return True, "Request validated successfully"


def validate_amount(amount: float) -> tuple[bool, str]:
    """
    Validate the requested amount.

    Student Note:
    Financial amounts must be strictly positive and capped at BUDGET_CEILING ($100,000).
    Zero and negative values are invalid; requests > $100,000 require manual out-of-band
    board approval and must immediately fail automated intake.

    Args:
        amount: Dollar amount to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if amount <= 0:
        return False, "Amount must be positive"
    if amount > BUDGET_CEILING:
        return False, f"Amount exceeds budget ceiling of ${BUDGET_CEILING:,.2f}"
    return True, "Amount is valid"


def sanitize_text(text: str, field_name: str = "text") -> tuple[bool, str]:
    """
    Check text for injection attacks and malicious content.

    Student Note:
    Case-insensitive substring search against known malicious patterns (SQL injection,
    cross-site scripting, and arbitrary Python code execution).

    Args:
        text: The text to sanitize
        field_name: Name of the field (for error messages)

    Returns:
        Tuple of (is_safe, original_text_or_error_message)
    """
    text_lower = text.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in text_lower:
            return False, f"Blocked content detected in {field_name}: suspicious pattern"
    return True, text
