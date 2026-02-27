
import re
from typing import Tuple

INJECTION_PATTERNS = [
    r"ignore (all|previous) instructions",
    r"system prompt",
    r"developer message",
    r"reveal.*prompt",
    r"jailbreak",
    r"do anything now",
]

PII_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
    (r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "[REDACTED_PHONE]"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[REDACTED_EMAIL]"),
]

def looks_like_prompt_injection(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in INJECTION_PATTERNS)

def redact_pii(text: str) -> str:
    out = text
    for pattern, repl in PII_PATTERNS:
        out = re.sub(pattern, repl, out)
    return out

def guard_question(question: str) -> Tuple[bool, str]:
    if looks_like_prompt_injection(question):
        return False, "Query looks like a prompt-injection attempt. Ask a normal question about the PDF content."
    return True, ""
