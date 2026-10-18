"""Worker Freshness Guardian (stub P1)."""

from ..contracts import AgentName
from .base import StubWorker


class FreshnessWorker(StubWorker):
    name = AgentName.FRESHNESS
