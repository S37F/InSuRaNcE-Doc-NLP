"""Risk flag computation engine for extracted insurance entities."""

from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any

from dateutil import parser

try:
    from config.settings import (
        COVERAGE_LIMIT_THRESHOLD,
        DEDUCTIBLE_RATIO_THRESHOLD,
        ENTITY_SCHEMA,
        EXPIRY_WARNING_DAYS,
    )
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from config.settings import (
        COVERAGE_LIMIT_THRESHOLD,
        DEDUCTIBLE_RATIO_THRESHOLD,
        ENTITY_SCHEMA,
        EXPIRY_WARNING_DAYS,
    )

logger = logging.getLogger(__name__)


def _build_flag(filename: str, flag_name: str, severity: str, details: str) -> dict[str, str]:
    """Create a normalized risk flag payload.

    Args:
        filename: Source document filename.
        flag_name: Human-readable flag name.
        severity: Flag severity level.
        details: Human-readable explanation for the flag.

    Returns:
        Dictionary representing a risk flag row.
    """
    return {
        "filename": filename,
        "flag_name": flag_name,
        "severity": severity,
        "details": details,
    }


def _get_relevant_expiry_date(extracted_fields: dict[str, Any]) -> date | None:
    """Resolve policy expiry/end date from extracted fields.

    Args:
        extracted_fields: Extracted field dictionary.

    Returns:
        Parsed date object when available, otherwise None.
    """
    date_value: Any = extracted_fields.get("policy_end_date") or extracted_fields.get("expiry_date")
    if not date_value:
        return None
    try:
        return parser.parse(str(date_value)).date()
    except (ValueError, TypeError, OverflowError) as exc:
        logger.warning("Could not parse expiry date '%s': %s", date_value, exc)
        return None


def _missing_required_fields(extracted_fields: dict[str, Any], doc_type: str) -> list[str]:
    """List required schema fields that are null or empty.

    Args:
        extracted_fields: Extracted field dictionary.
        doc_type: Classified document type.

    Returns:
        Field names considered missing for the document type.
    """
    schema_fields: list[str] = list(ENTITY_SCHEMA.get(doc_type, {}).keys())
    missing: list[str] = []
    for field in schema_fields:
        value: Any = extracted_fields.get(field)
        if value is None:
            missing.append(field)
        elif isinstance(value, str) and not value.strip():
            missing.append(field)
        elif isinstance(value, list) and len(value) == 0:
            missing.append(field)
    return missing


def compute_risk_flags(
    extracted_fields: dict[str, Any],
    doc_type: str,
    filename: str,
) -> list[dict[str, str]]:
    """Compute risk flags from extracted insurance fields.

    Args:
        extracted_fields: Structured entity values for one document.
        doc_type: Classified document type.
        filename: Source filename.

    Returns:
        List of risk flag dictionaries. Returns empty list when no rule matches.
    """
    flags: list[dict[str, str]] = []

    if doc_type == "unknown":
        flags.append(
            _build_flag(
                filename,
                "Unrecognised Document Type",
                "High",
                "The document type could not be classified reliably.",
            )
        )

    expiry_date: date | None = _get_relevant_expiry_date(extracted_fields)
    if expiry_date is not None:
        days_to_expiry: int = (expiry_date - date.today()).days
        if days_to_expiry < 0:
            flags.append(
                _build_flag(
                    filename,
                    "Policy Already Expired",
                    "High",
                    f"Coverage ended on {expiry_date.isoformat()}.",
                )
            )
        elif days_to_expiry <= EXPIRY_WARNING_DAYS:
            flags.append(
                _build_flag(
                    filename,
                    "Policy Expiring Soon",
                    "High",
                    f"Coverage expires in {days_to_expiry} days on {expiry_date.isoformat()}.",
                )
            )

    coverage_limit_raw: Any = extracted_fields.get("coverage_limit")
    if isinstance(coverage_limit_raw, (int, float)):
        coverage_limit: float = float(coverage_limit_raw)
        if coverage_limit < COVERAGE_LIMIT_THRESHOLD:
            flags.append(
                _build_flag(
                    filename,
                    "Low Coverage Limit",
                    "Medium",
                    (
                        f"Coverage limit {coverage_limit:.2f} is below threshold "
                        f"{COVERAGE_LIMIT_THRESHOLD:.2f}."
                    ),
                )
            )

    deductible_raw: Any = extracted_fields.get("deductible")
    if isinstance(deductible_raw, (int, float)) and isinstance(coverage_limit_raw, (int, float)):
        deductible: float = float(deductible_raw)
        coverage_limit = float(coverage_limit_raw)
        if coverage_limit > 0 and (deductible / coverage_limit) > DEDUCTIBLE_RATIO_THRESHOLD:
            flags.append(
                _build_flag(
                    filename,
                    "High Deductible",
                    "Medium",
                    (
                        f"Deductible ratio {(deductible / coverage_limit):.2%} exceeds threshold "
                        f"{DEDUCTIBLE_RATIO_THRESHOLD:.2%}."
                    ),
                )
            )

    missing_fields: list[str] = _missing_required_fields(extracted_fields, doc_type)
    if missing_fields:
        flags.append(
            _build_flag(
                filename,
                "Missing Critical Fields",
                "High",
                f"Missing fields: {', '.join(missing_fields)}.",
            )
        )

    if "exclusions" in extracted_fields:
        exclusions: Any = extracted_fields.get("exclusions")
        if exclusions is None or (isinstance(exclusions, list) and len(exclusions) == 0):
            flags.append(
                _build_flag(
                    filename,
                    "No Exclusions Listed",
                    "Medium",
                    "No exclusions were extracted from this document.",
                )
            )

    claim_status: Any = extracted_fields.get("claim_status")
    if isinstance(claim_status, str) and claim_status.strip().lower() == "open":
        flags.append(
            _build_flag(
                filename,
                "Claim Status Open",
                "Medium",
                "Claim is currently marked as Open.",
            )
        )

    logger.info("Computed %d risk flags for '%s'.", len(flags), filename)
    return flags


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    sample_fields: dict[str, Any] = {
        "policy_number": "POL-123",
        "insured_name": "ACME Corp",
        "insurer_name": "Contoso Insurance",
        "coverage_type": "Property",
        "premium_amount": 2000.0,
        "coverage_limit": 50000.0,
        "deductible": 12000.0,
        "policy_start_date": "2025-01-01",
        "policy_end_date": (date.today()).isoformat(),
        "exclusions": [],
        "named_endorsements": None,
    }
    print(compute_risk_flags(sample_fields, "policy", "sample_policy.pdf"))
