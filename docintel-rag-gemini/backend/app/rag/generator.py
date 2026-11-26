from typing import List, Dict, Any
import requests
from urllib.parse import quote

from ..config import settings
from ..models import PreviousTurn
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


def provider_error(response: requests.Response) -> str:
    status = response.status_code
    # Google's structured reason distinguishes an invalid key from other 400s.
    # Only fixed messages reach the UI. Raw provider errors can contain user data.
    try:
        data = response.json()
    except ValueError:
        data = {}
    error = data.get("error") if isinstance(data, dict) else None
    details = error.get("details") if isinstance(error, dict) else None
    if isinstance(details, list) and any(
        isinstance(item, dict) and item.get("reason") in ("API_KEY_INVALID", "API_KEY_EXPIRED")
        for item in details
    ):
        advice = "Google rejected the API key. Set a valid GEMINI_API_KEY and restart the backend."
    elif status in (401, 403):
        advice = "Access denied. Check the key's API restrictions and the project's Gemini access."
    elif status == 404:
        advice = "The requested model or endpoint is unavailable. Check GEMINI_MODEL and its generateContent support."
    elif status == 429:
        advice = "Rate or quota limit reached. Check this project's model limits in Google AI Studio before retrying."
    elif 500 <= status < 600:
        advice = "Google's service returned a server error. Wait briefly and try again."
    else:
        advice = "Check the backend's Gemini model and request configuration."
    return f"Gemini API returned HTTP {status}. {advice}"


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
    except requests.HTTPError as exc:
        if exc.response is None:
            raise GenerationUnavailable("The backend could not complete the Gemini request.") from exc
        raise GenerationUnavailable(provider_error(exc.response)) from exc
    except requests.Timeout as exc:
        raise GenerationUnavailable("Gemini timed out. Wait briefly and try again.") from exc
    except requests.ConnectionError as exc:
        raise GenerationUnavailable("Could not connect to Gemini. Check the backend's internet connection.") from exc
    except requests.RequestException as exc:
        raise GenerationUnavailable("The backend could not complete the Gemini request.") from exc
    except ValueError as exc:
        raise GenerationUnavailable("Gemini returned an unreadable response. Try again shortly.") from exc

    if not isinstance(data, dict):
        raise GenerationUnavailable("Gemini returned an unexpected response format.")

    for candidate in data.get("candidates", []):
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if not part.get("thought")).strip()
        if text:
            return text
    raise GenerationUnavailable("Gemini returned no answer for this question.")


def generate_answer(question: str, retrieved: List[Dict[str, Any]], previous_turn: PreviousTurn | None = None) -> str:
    context = format_context(retrieved)
    history = ""
    if previous_turn:
        history = (
            "Previous exchange (only for interpreting the current question):\n"
            f"Question: {previous_turn.question}\nAnswer: {previous_turn.answer}\n\n"
        )
    prompt = f"""{history}Document passages:
{context}

Question: {question}

Support the answer only with the numbered document passages above. Cite their numbers like [1] [2]."""

    out = _gemini_generate(prompt)
    return redact_pii(out)
