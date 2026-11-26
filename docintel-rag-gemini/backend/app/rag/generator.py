from typing import List, Dict, Any
import requests
from urllib.parse import quote

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

class GenerationUnavailable(RuntimeError):
    pass


def _gemini_generate(prompt: str) -> str:
    if not settings.gemini_api_key:
        raise GenerationUnavailable("Set GEMINI_API_KEY on the backend to enable answers.")

    model = quote(settings.gemini_model, safe="")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        response = requests.post(
            url,
            headers={"x-goog-api-key": settings.gemini_api_key},
            json={
                "systemInstruction": {"parts": [{"text": SYSTEM_RULES}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            },
            timeout=(5, 90),
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise GenerationUnavailable("Gemini is unavailable. Check the model, API key and quota.") from exc

    for candidate in data.get("candidates", []):
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if not part.get("thought")).strip()
        if text:
            return text
    raise GenerationUnavailable("Gemini returned no answer for this question.")


def generate_answer(question: str, retrieved: List[Dict[str, Any]]) -> str:
    context = format_context(retrieved)
    prompt = f"""Context:
{context}

Question: {question}

Write the answer using ONLY the context. Add citations like [1] [2]."""

    out = _gemini_generate(prompt)
    return redact_pii(out)
