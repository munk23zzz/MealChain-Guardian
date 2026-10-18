"""Worker Price (stub P1)."""

from ..contracts import AgentName
from .base import StubWorker


class PriceWorker(StubWorker):
    name = AgentName.PRICE
