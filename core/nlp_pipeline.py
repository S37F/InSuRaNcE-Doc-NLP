"""spaCy-based fast entity extraction pipeline."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import spacy
from spacy.language import Language

try:
    from config.settings import ENTITY_SCHEMA
    from utils.formatters import normalise_currency, normalise_date
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from config.settings import ENTITY_SCHEMA
    from utils.formatters import normalise_currency, normalise_date

logger = logging.getLogger(__name__)

MAX_CHARS: int = 1_000_000
_NLP: Language | None = None


def _add_entity_ruler(nlp: Language) -> None:
    """Attach an insurance-domain entity ruler to the pipeline."""
    if "entity_ruler" in nlp.pipe_names:
        nlp.remove_pipe("entity_ruler")

    ruler = nlp.add_pipe("entity_ruler", before="ner")
    patterns: list[dict[str, object]] = [
        {"label": "POLICY_NUMBER", "pattern": [{"TEXT": {"REGEX": r"POL-\d+"}}]},
        {"label": "POLICY_NUMBER", "pattern": [{"TEXT": {"REGEX": r"P\d{6,}"}}]},
        {
            "label": "POLICY_NUMBER",
            "pattern": [
                {"LOWER": "policy"},
                {"LOWER": {"IN": ["no", "no.", "number"]}},
                {"IS_PUNCT": True, "OP": "?"},
                {"TEXT": {"REGEX": r"[A-Za-z0-9\-]+"}},
            ],
        },
        {"label": "PREMIUM_AMOUNT", "pattern": [{"TEXT": {"REGEX": r"₹\s*[\d,]+(?:\.\d+)?"}}]},
        {"label": "PREMIUM_AMOUNT", "pattern": [{"TEXT": {"REGEX": r"\$[\d,]+(?:\.\d+)?"}}]},
        {"label": "PREMIUM_AMOUNT", "pattern": [{"TEXT": {"REGEX": r"USD\s*[\d,]+(?:\.\d+)?"}}]},
        {
            "label": "COVERAGE_LIMIT",
            "pattern": [
                {"LOWER": {"IN": ["limit", "coverage"]}},
                {"LOWER": {"IN": ["amount", "limit", "of"]}, "OP": "*"},
                {"TEXT": {"REGEX": r"(?:₹|\$|USD)?\s*[\d,]+(?:\.\d+)?"}},
            ],
        },
        {
            "label": "COVERAGE_LIMIT",
            "pattern": [
                {"LOWER": "sum"},
                {"LOWER": "insured"},
                {"TEXT": {"REGEX": r"(?:₹|\$|USD)?\s*[\d,]+(?:\.\d+)?"}},
            ],
        },
        {
            "label": "DEDUCTIBLE",
            "pattern": [
                {"LOWER": {"IN": ["deductible", "excess"]}},
                {"IS_PUNCT": True, "OP": "?"},
                {"TEXT": {"REGEX": r"(?:₹|\$|USD)?\s*[\d,]+(?:\.\d+)?"}},
            ],
        },
        {"label": "CLAIM_NUMBER", "pattern": [{"TEXT": {"REGEX": r"CLM-\d+"}}]},
        {
            "label": "CLAIM_NUMBER",
            "pattern": [
                {"LOWER": "claim"},
                {"LOWER": {"IN": ["no", "no.", "number"]}},
                {"IS_PUNCT": True, "OP": "?"},
                {"TEXT": {"REGEX": r"[A-Za-z0-9\-]+"}},
            ],
        },
        {"label": "ENDORSEMENT_NUMBER", "pattern": [{"TEXT": {"REGEX": r"END-\d+"}}]},
        {
            "label": "ENDORSEMENT_NUMBER",
            "pattern": [
                {"LOWER": "endorsement"},
                {"LOWER": {"IN": ["no", "no.", "number"]}},
                {"IS_PUNCT": True, "OP": "?"},
                {"TEXT": {"REGEX": r"[A-Za-z0-9\-]+"}},
            ],
        },
    ]
    ruler.add_patterns(patterns)


def _get_nlp_model() -> Language:
    """Load and cache the spaCy model using a singleton pattern."""
    global _NLP
    if _NLP is None:
        try:
            _NLP = spacy.load("en_core_web_lg")
            _add_entity_ruler(_NLP)
            logger.info("Loaded spaCy model en_core_web_lg.")
        except OSError as exc:
            logger.error("Could not load spaCy model en_core_web_lg: %s", exc)
            raise
    return _NLP


def _empty_result(doc_type: str) -> dict[str, object]:
    """Build an all-None output dict for the requested document type."""
    schema = ENTITY_SCHEMA.get(doc_type, {})
    return {field: None for field in schema}


def _set_first_available(
    result: dict[str, object],
    candidate_fields: list[str],
    value: object,
) -> None:
    """Set value on the first matching empty field from candidate_fields."""
    for field in candidate_fields:
        if field in result and result[field] is None and value is not None:
            result[field] = value
            return


def _extract_id(raw_value: str, regex_pattern: str) -> str | None:
    """Extract a canonical identifier from a potentially longer entity span."""
    match = re.search(regex_pattern, raw_value, flags=re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_amount_by_keyword(full_text: str, keywords: list[str]) -> float | None:
    """Extract amount by searching keyword-local currency patterns."""
    amount_pattern: str = r"(?:₹|\$|USD|INR|Rs\.?)?\s*[\d,]+(?:\.\d+)?"
    for keyword in keywords:
        match = re.search(
            rf"{keyword}[\s:=-]{{0,10}}({amount_pattern})",
            full_text,
            flags=re.IGNORECASE,
        )
        if match:
            amount = normalise_currency(match.group(1))
            if amount is not None:
                return amount
    return None


def _extract_date_by_keyword(full_text: str, keywords: list[str]) -> str | None:
    """Extract date by searching keyword-local date snippets."""
    date_pattern = (
        r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4})"
    )
    for keyword in keywords:
        match = re.search(
            rf"{keyword}[\s:=-]{{0,12}}({date_pattern})",
            full_text,
            flags=re.IGNORECASE,
        )
        if match:
            parsed = normalise_date(match.group(1))
            if parsed is not None:
                return parsed
    return None


def extract_entities_spacy(full_text: str, doc_type: str) -> dict[str, object]:
    """Extract and normalise entities from text using spaCy and custom rules.

    Args:
        full_text: Full document text content.
        doc_type: Classified document type.

    Returns:
        A dictionary matching `ENTITY_SCHEMA[doc_type]`. Missing fields are None.
    """
    if doc_type not in ENTITY_SCHEMA or doc_type == "unknown":
        logger.info("Skipping spaCy extraction for unknown document type.")
        return {}

    text_to_process: str = full_text or ""
    if len(text_to_process) > MAX_CHARS:
        logger.warning(
            "Text length %d exceeds %d; truncating for spaCy extraction.",
            len(text_to_process),
            MAX_CHARS,
        )
        text_to_process = text_to_process[:MAX_CHARS]

    result: dict[str, object] = _empty_result(doc_type)

    try:
        nlp = _get_nlp_model()
        doc = nlp(text_to_process)
    except Exception as exc:
        logger.error("spaCy extraction failed for doc_type '%s': %s", doc_type, exc)
        return result

    for ent in doc.ents:
        raw_value: str = ent.text.strip()
        label: str = ent.label_

        if label == "POLICY_NUMBER":
            _set_first_available(
                result,
                ["policy_number"],
                _extract_id(raw_value, r"(?:POL-\d+|P\d{6,})"),
            )
        elif label == "CLAIM_NUMBER":
            _set_first_available(
                result,
                ["claim_number"],
                _extract_id(raw_value, r"(?:CLM-\d+|C\d{5,})"),
            )
        elif label == "ENDORSEMENT_NUMBER":
            _set_first_available(
                result,
                ["endorsement_number"],
                _extract_id(raw_value, r"(?:END-\d+|E\d{5,})"),
            )
        elif label == "PREMIUM_AMOUNT":
            _set_first_available(
                result,
                ["premium_amount", "additional_premium", "reserve_amount"],
                normalise_currency(raw_value),
            )
        elif label == "COVERAGE_LIMIT":
            _set_first_available(result, ["coverage_limit"], normalise_currency(raw_value))
        elif label == "DEDUCTIBLE":
            _set_first_available(result, ["deductible"], normalise_currency(raw_value))
        elif label == "ORG":
            _set_first_available(
                result,
                ["insurer_name", "insured_name", "certificate_holder"],
                raw_value,
            )
        elif label == "PERSON":
            _set_first_available(result, ["adjuster_name", "claimant_name"], raw_value)
        elif label == "DATE":
            _set_first_available(
                result,
                [
                    "policy_start_date",
                    "policy_end_date",
                    "effective_date",
                    "expiry_date",
                    "date_of_loss",
                ],
                normalise_date(raw_value),
            )
        elif label == "MONEY":
            money_value = normalise_currency(raw_value)
            _set_first_available(
                result,
                ["premium_amount", "coverage_limit", "deductible", "additional_premium"],
                money_value,
            )

    if "additional_insured" in result:
        result["additional_insured"] = bool(
            re.search(r"\badditional insured\b.{0,20}\b(?:yes|included|true)\b", text_to_process, re.I)
        )

    if "policy_number" in result and result["policy_number"] is None:
        result["policy_number"] = _extract_id(text_to_process, r"(?:POL-\d+|P\d{6,})")
    if "claim_number" in result and result["claim_number"] is None:
        result["claim_number"] = _extract_id(text_to_process, r"(?:CLM-\d+|C\d{5,})")
    if "endorsement_number" in result and result["endorsement_number"] is None:
        result["endorsement_number"] = _extract_id(text_to_process, r"(?:END-\d+|E\d{5,})")

    if "premium_amount" in result and result["premium_amount"] is None:
        result["premium_amount"] = _extract_amount_by_keyword(text_to_process, ["premium"])
    if "coverage_limit" in result and result["coverage_limit"] is None:
        result["coverage_limit"] = _extract_amount_by_keyword(
            text_to_process,
            ["coverage limit", "sum insured", "coverage amount", "limit"],
        )
    if "deductible" in result and result["deductible"] is None:
        result["deductible"] = _extract_amount_by_keyword(text_to_process, ["deductible", "excess"])

    if "policy_start_date" in result and result["policy_start_date"] is None:
        result["policy_start_date"] = _extract_date_by_keyword(
            text_to_process,
            ["policy start date", "start date", "inception date"],
        )
    if "policy_end_date" in result and result["policy_end_date"] is None:
        result["policy_end_date"] = _extract_date_by_keyword(
            text_to_process,
            ["policy end date", "end date", "expiry date", "expiration date"],
        )
    if "effective_date" in result and result["effective_date"] is None:
        result["effective_date"] = _extract_date_by_keyword(text_to_process, ["effective date"])
    if "expiry_date" in result and result["expiry_date"] is None:
        result["expiry_date"] = _extract_date_by_keyword(
            text_to_process,
            ["expiry date", "expiration date", "end date"],
        )

    logger.info("spaCy extraction complete for doc_type '%s'.", doc_type)
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    sample_text = (
        "Policy Number POL-998877 issued by Acme Insurance. "
        "Coverage limit USD 250,000 with deductible $25,000. "
        "Policy start date Jan 5, 2026 and end date Dec 31, 2026."
    )
    print(extract_entities_spacy(sample_text, "policy"))
