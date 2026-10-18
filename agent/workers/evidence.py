"""Worker Evidence Fusion (stub P1)."""

from ..contracts import AgentName
from .base import StubWorker


class EvidenceWorker(StubWorker):
    name = AgentName.EVIDENCE
