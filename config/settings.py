"""Project-wide settings, schemas, and thresholds."""

from __future__ import annotations

import os

DOC_TYPE_KEYWORDS: dict[str, list[str]] = {
    "policy": ["policy number", "insuring agreement", "declarations"],
    "certificate": ["certificate holder", "this is to certify", "acord"],
    "endorsement": ["endorsement number", "it is agreed", "forms part of"],
    "claim": ["claim number", "date of loss", "claimant"],
}

ENTITY_SCHEMA: dict[str, dict[str, str]] = {
    "policy": {
        "insured_name": "string",
        "policy_number": "string",
        "insurer_name": "string",
        "coverage_type": "string",
        "premium_amount": "float",
        "coverage_limit": "float",
        "deductible": "float",
        "policy_start_date": "date",
        "policy_end_date": "date",
        "exclusions": "list[string]",
        "named_endorsements": "list[string]",
    },
    "certificate": {
        "certificate_holder": "string",
        "insured_name": "string",
        "insurer_name": "string",
        "policy_number": "string",
        "coverage_type": "string",
        "coverage_limit": "float",
        "effective_date": "date",
        "expiry_date": "date",
        "additional_insured": "bool",
    },
    "endorsement": {
        "endorsement_number": "string",
        "policy_number": "string",
        "effective_date": "date",
        "description": "string",
        "additional_premium": "float",
        "amended_clause": "string",
    },
    "claim": {
        "claim_number": "string",
        "claimant_name": "string",
        "date_of_loss": "date",
        "loss_description": "string",
        "reserve_amount": "float",
        "claim_status": "string",
        "adjuster_name": "string",
    },
    "unknown": {},
}

RISK_FLAG_RULES: dict[str, dict[str, str]] = {
    "policy_expiring_soon": {
        "name": "Policy Expiring Soon",
        "condition": "End/Expiry date within EXPIRY_WARNING_DAYS",
        "severity": "High",
    },
    "policy_already_expired": {
        "name": "Policy Already Expired",
        "condition": "End/Expiry date in the past",
        "severity": "High",
    },
    "low_coverage_limit": {
        "name": "Low Coverage Limit",
        "condition": "Coverage limit below COVERAGE_LIMIT_THRESHOLD",
        "severity": "Medium",
    },
    "high_deductible": {
        "name": "High Deductible",
        "condition": "Deductible ratio above DEDUCTIBLE_RATIO_THRESHOLD",
        "severity": "Medium",
    },
    "missing_critical_fields": {
        "name": "Missing Critical Fields",
        "condition": "Required field is null or empty",
        "severity": "High",
    },
    "no_exclusions_listed": {
        "name": "No Exclusions Listed",
        "condition": "Exclusions list is empty",
        "severity": "Medium",
    },
    "claim_status_open": {
        "name": "Claim Status Open",
        "condition": 'Claim status equals "Open"',
        "severity": "Medium",
    },
    "unrecognised_document_type": {
        "name": "Unrecognised Document Type",
        "condition": "Document classification is unknown",
        "severity": "High",
    },
}

COVERAGE_LIMIT_THRESHOLD: float = float(os.getenv("COVERAGE_LIMIT_THRESHOLD", "100000"))
DEDUCTIBLE_RATIO_THRESHOLD: float = float(os.getenv("DEDUCTIBLE_RATIO_THRESHOLD", "0.10"))
EXPIRY_WARNING_DAYS: int = int(os.getenv("EXPIRY_WARNING_DAYS", "30"))
