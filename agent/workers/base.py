"""Dasar worker agent dan stub P1.

Stub tidak memanggil model/API. Ia hanya menghasilkan `AgentFinding` yang
valid dengan status `skipped`, supaya orkestrasi dan UI bisa diuji sebelum
worker nyata diimplementasikan.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from time import monotonic
from typing import Any
from uuid import UUID

from ..api_client import AgentApiError
from ..contracts import AgentFinding, AgentName, Citation, WorkerStatus
from ..registry import AgentSpec, get_spec


@dataclass(frozen=True)
class WorkerContext:
    run_id: UUID
    decision_id: str
    location: str | None = None
    commodity: str | None = None
    source_location: str | None = None
    quantity_kg: float | None = None
    api: Any = None
    #: Identitas untuk mencakupkan exclusion & memilih batch sumber
    #: (AUD-9B-29). `location` tetap lokasi TUJUAN; batch yang dinilai guardian
    #: adalah batch SUMBER (`source_location` / `source_batch_ids`).
    target_location_id: str | None = None
    source_location_id: str | None = None
    supplier_id: str | None = None
    #: `batch_ids` binding keputusan (himpunan yang sama dengan
    #: `batch_sumber_transfer` di backend). Kosong = tidak ada binding.
    source_batch_ids: tuple[str, ...] = ()


class StubWorker:
    name: AgentName

    def __init__(self, name: AgentName | None = None) -> None:
        selected = name or getattr(type(self), "name", None)
        if selected is None:
            raise ValueError("worker harus punya name")
        self.name = selected if isinstance(selected, AgentName) else AgentName(selected)
        self.spec: AgentSpec = get_spec(self.name)

    def _target(self, context: WorkerContext) -> tuple[str, str]:
        if not context.location or not context.location.strip():
            raise ValueError("location wajib diisi untuk worker ini")
        if not context.commodity or not context.commodity.strip():
            raise ValueError("commodity wajib diisi untuk worker ini")
        return context.location.strip(), context.commodity.strip()

    def _api(self, context: WorkerContext) -> Any:
        if context.api is None:
            raise AgentApiError(
                "missing_config: WorkerContext.api belum diisi; "
                "worker tidak boleh mengarang data"
            )
        return context.api

    @staticmethod
    def _latency_ms(started: float) -> int:
        """Durasi kerja terukur, dibulatkan ke atas minimal 1 ms.

        `0` dipakai UI sebagai "tidak ada pekerjaan berjalan" (kartu bukti Demo
        Control menulis "Durasi: 0 md"), padahal jalur cepat — model tidak
        dikonfigurasi, fakta gagal terbaca — selesai di bawah satu milidetik.
        Karena itu hasil pengukuran tidak pernah 0; "tidak diukur" tetap `None`.
        """
        return max(1, round((monotonic() - started) * 1000))

    @staticmethod
    def _citation(
        claim: str,
        source_path: str,
        source_field: str,
        source_value: object,
    ) -> Citation:
        return Citation(
            claim=claim,
            source_path=source_path,
            source_field=source_field,
            source_value=source_value,
        )

    def _finding(
        self,
        status: WorkerStatus,
        summary: str,
        *,
        facts: dict[str, Any] | None = None,
        citations: list[Citation] | None = None,
        warnings: list[str] | None = None,
        blocking: bool = False,
        latency_ms: int | None = None,
    ) -> AgentFinding:
        return AgentFinding(
            agent=self.name,
            stage=self.spec.stage,
            status=status,
            summary=summary,
            facts=facts or {},
            citations=citations or [],
            confidence=None,
            warnings=warnings or [],
            blocking=blocking,
            latency_ms=latency_ms,
        )

    def _error(
        self,
        message: str,
        *,
        latency_ms: int | None = None,
    ) -> AgentFinding:
        return self._finding(
            WorkerStatus.ERROR,
            f"{self.spec.role} gagal: {message}",
            warnings=[f"worker_error: {message}"],
            latency_ms=latency_ms,
        )

    def _degraded(
        self,
        summary: str,
        *,
        facts: dict[str, Any] | None = None,
        citations: list[Citation] | None = None,
        warnings: list[str] | None = None,
        blocking: bool = False,
        latency_ms: int | None = None,
    ) -> AgentFinding:
        return self._finding(
            WorkerStatus.DEGRADED,
            summary,
            facts=facts,
            citations=citations,
            warnings=warnings,
            blocking=blocking,
            latency_ms=latency_ms,
        )

    def _ok(
        self,
        summary: str,
        *,
        facts: dict[str, Any] | None = None,
        citations: list[Citation] | None = None,
        warnings: list[str] | None = None,
        blocking: bool = False,
        latency_ms: int | None = None,
    ) -> AgentFinding:
        return self._finding(
            WorkerStatus.OK,
            summary,
            facts=facts,
            citations=citations,
            warnings=warnings,
            blocking=blocking,
            latency_ms=latency_ms,
        )

    def run(self, context: WorkerContext) -> AgentFinding:
        if not context.decision_id.strip():
            raise ValueError("decision_id wajib diisi")
        return AgentFinding(
            agent=self.name,
            stage=self.spec.stage,
            status=WorkerStatus.SKIPPED,
            summary=f"{self.spec.role} belum dijalankan pada P1 (stub).",
            facts={},
            citations=[],
            confidence=None,
            warnings=["Stub P1: belum ada pembacaan API atau panggilan model."],
            blocking=False,
            latency_ms=None,
        )


class ReadOnlyWorker(StubWorker):
    """Marker base untuk worker P2+; hanya membaca API."""


def as_number(value: object, *, allow_numeric_string: bool = False) -> int | float | None:
    """Ambil angka apa adanya; bool dan None bukan angka fakta.

    `allow_numeric_string` hanya dipakai untuk field DB yang diserialisasi
    sebagai string desimal (mis. `quantity_kg` di dossier). String non-angka
    tetap dikembalikan None, bukan dikarang menjadi 0.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if allow_numeric_string and isinstance(value, str):
        try:
            return float(Decimal(value.strip()))
        except (InvalidOperation, ValueError):
            return None
    return None
