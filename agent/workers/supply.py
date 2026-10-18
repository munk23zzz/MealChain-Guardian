"""Worker Supply (stub P1)."""

from ..contracts import AgentName
from .base import StubWorker


class SupplyWorker(StubWorker):
    name = AgentName.SUPPLY
