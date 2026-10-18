"""Worker Safety Guardian (stub P1)."""

from ..contracts import AgentName
from .base import StubWorker


class SafetyWorker(StubWorker):
    name = AgentName.SAFETY
