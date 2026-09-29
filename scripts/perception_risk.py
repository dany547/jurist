"""Mechanical risk derivation for the perception audit."""
from __future__ import annotations

from collections.abc import Iterable


HIGH_RISK = frozenset({"efect_juridic", "conformitate", "sanctiune"})
MEDIUM_RISK = frozenset({
    "obligatie",
    "semnatar",
    "aprobare",
    "scutire",
    "exhaustivitate",
    "termen_cuantum",
})
ALLOWED_CATEGORIES = HIGH_RISK | MEDIUM_RISK


def derive_risk(categories: Iterable[str], user_subject: bool = False) -> str:
    """Return the risk level derived only from detected signal categories."""
    detected = set(categories)
    unknown = detected - ALLOWED_CATEGORIES
    if unknown:
        raise ValueError(f"categorii necunoscute: {', '.join(sorted(unknown))}")

    if user_subject or detected & HIGH_RISK:
        return "ridicat"
    if detected & MEDIUM_RISK:
        return "mediu"
    return "scazut"
