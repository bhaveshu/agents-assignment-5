"""
Output filtering guardrails for the Financial Approval System.

Students implement output sanitization that masks PII and
sensitive financial details before responses reach users.

Part 2: Safety Guardrails (10 points from this file)
"""

import re

# --- GIVEN: PII detection patterns ---
PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
}


def sanitize_output(text: str) -> str:
    """
    Remove PII and sensitive information from output text.

    Student Note (Defense-in-Depth):
    Even if inputs are validated, LLMs can inadvertently hallucinate or echo PII
    from prompt context or training data into public-facing chat responses.
    Output filtering applies strict regex substitution across four standard PII types:
      - SSN: replaced with '***-**-XXXX'
      - Credit Cards: replaced with '****-****-****-XXXX'
      - Email: replaced with '[EMAIL REDACTED]'
      - Phone: replaced with '***-***-XXXX'

    Args:
        text: Output text that may contain PII

    Returns:
        Sanitized text with PII masked
    """
    text = PII_PATTERNS["ssn"].sub("***-**-XXXX", text)
    text = PII_PATTERNS["credit_card"].sub("****-****-****-XXXX", text)
    text = PII_PATTERNS["email"].sub("[EMAIL REDACTED]", text)
    text = PII_PATTERNS["phone"].sub("***-***-XXXX", text)
    return text


def mask_financial_details(text: str) -> str:
    r"""
    Mask specific financial details in output while preserving context.

    Student Note (Context-Preserving Redaction):
    For financial logs and external display, masking must obscure high-value
    figures and raw account numbers while preserving enough context for human
    verification (e.g. keeping cents/suffix or the last 4 digits of an account).

    Hints:
    - Use re.sub with a replacement function for dollar amounts
    - Pattern for dollars: r'\$[\d,]+\.?\d*'
    - Pattern for account numbers: r'\b\d{8,}\b'

    Args:
        text: Text containing financial details

    Returns:
        Text with financial details masked
    """
    # 1. Mask dollar amounts: keep the suffix/cents, replace leading digits with ***
    def _mask_amount(match):
        val = match.group(0)
        # If the amount is long enough (e.g. $45,000.00), preserve last 5 chars (.00 or digits)
        if len(val) > 5:
            return "$***" + val[-5:]
        return "$***"

    text = re.sub(r"\$[\d,]+(?:\.\d+)?", _mask_amount, text)

    # 2. Mask account numbers (8+ digits): mask all but the last 4 digits
    def _mask_account(match):
        digits = match.group(0)
        return "*" * (len(digits) - 4) + digits[-4:]

    text = re.sub(r"\b\d{8,}\b", _mask_account, text)
    return text
