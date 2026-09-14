"""Structured evidence storage for PCB Copilot projects."""

from pcb_copilot.evidence.index import (
    EvidenceFormatError,
    load_evidence_index,
    save_evidence_index,
)
from pcb_copilot.evidence.models import (
    EvidenceIndex,
    EvidenceRecord,
    EvidenceRole,
    TrustTier,
)

__all__ = [
    "EvidenceFormatError",
    "EvidenceIndex",
    "EvidenceRecord",
    "EvidenceRole",
    "TrustTier",
    "load_evidence_index",
    "save_evidence_index",
]
