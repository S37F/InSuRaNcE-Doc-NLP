"""Claude-powered question answering over insurance document text."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

try:
    from core.llm_extractor import MODEL_NAME, get_claude_client
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from core.llm_extractor import MODEL_NAME, get_claude_client

logger = logging.getLogger(__name__)

MAX_CHAT_TOKENS: int = 1024
MAX_DOC_CHARS: int = 15_000
MAX_CHAT_TURNS: int = 10
ERROR_MESSAGE: str = "I encountered an error processing your question. Please try again."


def _truncate_document(full_text: str) -> str:
    """Trim long document text for chat context limits.

    Args:
        full_text: Full document text.

    Returns:
        Original text when within limits, else truncated text with trailing note.
    """
    if len(full_text) <= MAX_DOC_CHARS:
        return full_text
    return (
        f"{full_text[:MAX_DOC_CHARS]}\n\n"
        f"[NOTE: Document text truncated to {MAX_DOC_CHARS} characters.]"
    )


def _sanitize_history(chat_history: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Keep only valid user/assistant turns and cap to last 10 turns.

    Args:
        chat_history: Prior chat entries.

    Returns:
        Sanitized list suitable for Claude messages.
    """
    cleaned: list[dict[str, str]] = []
    for turn in chat_history:
        role: str = str(turn.get("role", "")).strip().lower()
        content: str = str(turn.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            cleaned.append({"role": role, "content": content})
    return cleaned[-MAX_CHAT_TURNS:]


def _response_to_text(response: Any) -> str:
    """Convert Anthropic response blocks to plain text.

    Args:
        response: Claude messages API response.

    Returns:
        Joined text payload extracted from response content blocks.
    """
    content_parts: list[str] = []
    for block in getattr(response, "content", []):
        block_text: str = getattr(block, "text", "") or ""
        if block_text:
            content_parts.append(block_text)
    return "\n".join(content_parts).strip()


def answer_question(
    question: str,
    full_text: str,
    chat_history: list[dict[str, Any]],
    doc_type: str,
) -> str:
    """Answer a user question using only document context and recent chat turns.

    Args:
        question: Latest user question.
        full_text: Full extracted document text.
        chat_history: Prior turns with `role` and `content`.
        doc_type: Document type context (policy/certificate/endorsement/claim/unknown).

    Returns:
        Assistant answer as plain string. Returns a generic error message on failure.
    """
    if not question or not question.strip():
        return "Please enter a question."

    try:
        client = get_claude_client()
        system_prompt: str = (
            "You are a specialist insurance document analyst. "
            "Answer questions based ONLY on the document text provided. "
            "If the answer is not in the document, say so clearly. "
            f"This is a {doc_type} document."
        )
        truncated_doc: str = _truncate_document(full_text)
        recent_turns: list[dict[str, str]] = _sanitize_history(chat_history)
        messages: list[dict[str, str]] = [
            {
                "role": "user",
                "content": (
                    "Here is the document:\n\n"
                    f"{truncated_doc}\n\n"
                    "Please confirm you have read it."
                ),
            },
            {
                "role": "assistant",
                "content": "Understood. I have read the document. What would you like to know?",
            },
        ]
        messages.extend(recent_turns)
        messages.append({"role": "user", "content": question.strip()})

        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_CHAT_TOKENS,
            temperature=0.3,
            system=system_prompt,
            messages=messages,
        )
        answer_text: str = _response_to_text(response)
        if not answer_text:
            logger.warning("Claude returned empty chat response.")
            return ERROR_MESSAGE
        return answer_text
    except Exception as exc:
        logger.error("Chat question processing failed: %s", exc)
        return ERROR_MESSAGE


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    sample_text: str = (
        "Policy Number POL-778899. Insured: ACME Industries. "
        "Policy End Date: 2026-12-31. Coverage Limit: USD 250000."
    )
    sample_history: list[dict[str, str]] = [
        {"role": "user", "content": "What is the policy number?"},
        {"role": "assistant", "content": "The policy number is POL-778899."},
    ]
    print(
        answer_question(
            question="When does this policy expire?",
            full_text=sample_text,
            chat_history=sample_history,
            doc_type="policy",
        )
    )
