"""Rule registry for the verification engine.

Each rule inspects an `EvidenceBundle` and returns a single
`VerificationFinding`. The order here is the order in which findings
appear in API responses — keep it stable.
"""
from __future__ import annotations

from .area_match import AreaMatchRule
from .deed_mutation_area_match import DeedMutationAreaMatchRule
from .document_integrity import DocumentIntegrityRule
from .duplicate_transfer import DuplicateTransferRule
from .missing_mutation import MissingMutationRule
from .owner_match import OwnerMatchRule
from .parcel_overflow import ParcelAreaOverflowRule

RULES = [
    OwnerMatchRule(),
    AreaMatchRule(),
    DeedMutationAreaMatchRule(),
    ParcelAreaOverflowRule(),
    DuplicateTransferRule(),
    MissingMutationRule(),
    DocumentIntegrityRule(),
]

__all__ = [r.__class__.__name__ for r in RULES]