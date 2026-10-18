"""Worker Demand (stub P1)."""

from ..contracts import AgentName
from .base import StubWorker


class DemandWorker(StubWorker):
    name = AgentName.DEMAND
