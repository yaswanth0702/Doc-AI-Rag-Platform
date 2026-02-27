from typing import List, Dict, Any
import google.generativeai as genai

from ..config import settings
from .citations import format_context
from .guardrails import redact_pii

SYSTEM_RULES = """You are a careful assistant.
Rules:
- Answer ONLY using the provided context.
- If the context does not contain the answer, say: "I don’t have enough information in the document to answer that."
- Keep it clear and direct.
- Add citations like [1] [2] that refer to the context chunk numbers.
"""

def _gemini_generate(prompt: str) -> str:
    if not settings.gemini_api_key:
        return "Gemini API key not set. Please set GEMINI_API_KEY."

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model)

    # Gemini doesn't have roles like OpenAI in the same way here, so we prepend rules.
    response = model.generate_content(f"{SYSTEM_RULES}\n\n{prompt}")
    text = getattr(response, "text", "") or ""
    return text.strip()

def generate_answer(question: str, retrieved: List[Dict[str, Any]]) -> str:
    context = format_context(retrieved)
    prompt = f"""Context:
{context}

Question: {question}

Write the answer using ONLY the context. Add citations like [1] [2]."""

    out = _gemini_generate(prompt)
    return redact_pii(out)
