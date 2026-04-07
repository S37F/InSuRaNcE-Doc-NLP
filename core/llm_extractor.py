"""Claude-powered entity extraction for insurance documents."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit may be unavailable in pure CLI tests
    st = None

try:
    from config.settings import ENTITY_SCHEMA
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from config.settings import ENTITY_SCHEMA

logger = logging.getLogger(__name__)

MODEL_NAME: str = "claude-sonnet-4-20250514"
MAX_TOKENS_EXTRACTION: int = 2048
MAX_TEXT_CHARS: int = 12_000


def safe_parse_json(text: str) -> dict[str, Any]:
    """Strip markdown fences and parse JSON safely.

    Args:
        text: Raw model response text.

    Returns:
        Parsed JSON dictionary, or empty dict when parsing fails.
    """
    cleaned: str = re.sub(r"```json|```", "", text).strip()
    try:
        parsed: Any = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        logger.error("Claude JSON response was not an object: %s", cleaned[:200])
        return {}
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude JSON: %s", text[:200])
        return {}


def _get_api_key() -> str | None:
    """Load Anthropic API key from dotenv and Streamlit secrets.

    Returns:
        API key string when available, otherwise None.
    """
    load_dotenv()
    streamlit_secret: str | None = None
    if st is not None:
        try:
            streamlit_secret = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            streamlit_secret = None
    return streamlit_secret or os.getenv("ANTHROPIC_API_KEY")


def get_claude_client() -> anthropic.Anthropic:
    """Create an Anthropic client using configured API credentials.

    Returns:
        Initialised Anthropic client.

    Raises:
        ValueError: If API key is not configured.
    """
    api_key: str | None = _get_api_key()
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured.")
    return anthropic.Anthropic(api_key=api_key)


def _truncate_text(full_text: str) -> str:
    """Truncate document text to model-safe size with an explicit note.

    Args:
        full_text: Full document content.

    Returns:
        Original text when short enough, else truncated text with note.
    """
    if len(full_text) <= MAX_TEXT_CHARS:
        return full_text
    truncated: str = full_text[:MAX_TEXT_CHARS]
    return (
        f"{truncated}\n\n[NOTE: Document text was truncated to {MAX_TEXT_CHARS} characters "
        "for extraction.]"
    )


def _merge_spacy_with_llm(spacy_result: dict[str, Any], llm_result: dict[str, Any]) -> dict[str, Any]:
    """Merge extraction results while preserving spaCy values.

    Args:
        spacy_result: Baseline extraction from spaCy.
        llm_result: Candidate values produced by Claude.

    Returns:
        Merged field dictionary where non-null spaCy values take priority.
    """
    merged: dict[str, Any] = dict(spacy_result)
    for key, value in llm_result.items():
        if key in merged and merged[key] is None and value is not None:
            merged[key] = value
    return merged


def _response_to_text(response: anthropic.types.Message) -> str:
    """Convert Anthropic message blocks to plain text.

    Args:
        response: Anthropic message response object.

    Returns:
        Concatenated text payload from response blocks.
    """
    content_parts: list[str] = []
    for block in response.content:
        block_text: str = getattr(block, "text", "") or ""
        if block_text:
            content_parts.append(block_text)
    return "\n".join(content_parts).strip()


def extract_entities_llm(full_text: str, doc_type: str, spacy_result: dict[str, Any]) -> dict[str, Any]:
    """Use Claude to fill missing entity fields left by spaCy extraction.

    Args:
        full_text: Full document text.
        doc_type: Classified document type.
        spacy_result: Baseline extracted fields from spaCy.

    Returns:
        Merged extraction dictionary where spaCy values take priority and
        Claude fills null fields only. On any LLM failure, returns spacy_result.
    """
    schema: dict[str, str] = ENTITY_SCHEMA.get(doc_type, {})
    if not schema:
        logger.warning("No schema found for doc_type '%s'; returning spaCy result.", doc_type)
        return spacy_result

    missing_fields: list[str] = [field for field, value in spacy_result.items() if value is None]
    if not missing_fields:
        logger.info("No missing fields for doc_type '%s'; skipping Claude call.", doc_type)
        return spacy_result

    schema_json: str = json.dumps(schema, indent=2)
    spacy_json: str = json.dumps(spacy_result, ensure_ascii=True)
    truncated_text: str = _truncate_text(full_text)
    system_prompt: str = (
        "You are an expert insurance document analyser.\n"
        f"Document type: {doc_type}\n"
        "Target JSON schema:\n"
        f"{schema_json}\n\n"
        "Existing spaCy extraction:\n"
        f"{spacy_json}\n\n"
        "Fill ONLY fields currently null in the spaCy extraction.\n"
        "Keep existing non-null values unchanged.\n"
        "Return ONLY a valid JSON object. No explanation, no markdown fences, no preamble."
    )

    try:
        client = get_claude_client()
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS_EXTRACTION,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": truncated_text}],
        )
        content_text: str = _response_to_text(response)
        llm_result: dict[str, Any] = safe_parse_json(content_text)
        merged: dict[str, Any] = _merge_spacy_with_llm(spacy_result, llm_result)
        logger.info(
            "Claude extraction completed for doc_type '%s'; attempted to fill %d fields.",
            doc_type,
            len(missing_fields),
        )
        return merged
    except anthropic.APIConnectionError as exc:
        logger.error("Claude API connection error: %s", exc)
        return spacy_result
    except anthropic.RateLimitError as exc:
        logger.error("Claude API rate limit error: %s", exc)
        return spacy_result
    except anthropic.APIStatusError as exc:
        logger.error("Claude API status error: %s", exc)
        return spacy_result
    except ValueError as exc:
        logger.error("Claude configuration error: %s", exc)
        return spacy_result
    except Exception as exc:
        logger.error("Unexpected Claude extraction error: %s", exc)
        return spacy_result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    sample_text: str = (
        "Policy Number POL-123456. Insured Name: ACME Logistics. "
        "Insurer: Contoso Insurance. Coverage Type: Property. "
        "Exclusions: Flood, Earthquake."
    )
    sample_spacy_result: dict[str, Any] = {
        "insured_name": "ACME Logistics",
        "policy_number": "POL-123456",
        "insurer_name": "Contoso Insurance",
        "coverage_type": None,
        "premium_amount": None,
        "coverage_limit": None,
        "deductible": None,
        "policy_start_date": None,
        "policy_end_date": None,
        "exclusions": None,
        "named_endorsements": None,
    }
    print(extract_entities_llm(sample_text, "policy", sample_spacy_result))
