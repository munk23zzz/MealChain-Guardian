"""Alat baca-saja Verifier Agent: mengambil FAKTA sendiri, bukan narasi supervisor.

Verifier dulu hanya mewarisi verdict gerbang (`agent/verify.py`) — ia tidak
pernah membaca data, sehingga tidak mungkin menangkap klaim yang bertentangan
dengan kenyataan (AUD-9A-03). Modul ini adalah "toolset" verifier:

- `GET /decisions/{id}/audit-facts`  → fakta yang SUDAH dihitung kode
  (SDC vs rincian, batch sumber + gerbang kesegaran, bukti keputusan,
  exclusion, blok ledger);
- `GET /decisions/{id}/approval-summary` → status keputusan + approval.

Keduanya GET. Tidak ada jalur tulis, tidak ada POST, dan tidak ada aritmetika
di sini: modul ini hanya MEMBACA. Aturan "angka lahir dari kode" karena itu
dijaga di backend (`app/services/audit_facts.py`), bukan di agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .api_client import AgentApiError

AUDIT_FACTS_PATH = "/decisions/{decision_id}/audit-facts"
APPROVAL_SUMMARY_PATH = "/decisions/{decision_id}/approval-summary"

#: Himpunan jalur yang boleh dibaca verifier. Dipakai tes untuk mengunci bahwa
#: verifier tidak pernah menyentuh endpoint mutasi.
READ_ONLY_PATHS = (AUDIT_FACTS_PATH, APPROVAL_SUMMARY_PATH)


def _iter_angka(value: Any) -> Iterable[float]:
    """Semua angka di dalam fakta — dipakai mencocokkan angka klaim."""
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
        return
    if isinstance(value, str):
        teks = value.strip()
        try:
            yield float(teks)
        except ValueError:
            return
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_angka(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_angka(item)


@dataclass(frozen=True)
class FaktaVerifier:
    """Fakta yang dibaca verifier + jejak dari mana ia berasal."""

    data: dict[str, Any]
    approval: dict[str, Any] | None = None
    sumber: tuple[str, ...] = field(default_factory=tuple)

    @property
    def decision_id(self) -> str | None:
        nilai = self.data.get("decision_id")
        return str(nilai) if nilai else None

    def angka_dikenal(self) -> set[float]:
        angka = set(_iter_angka(self.data))
        if self.approval:
            angka.update(_iter_angka(self.approval))
        return angka

    def sitasi_id(self) -> list[dict[str, str]]:
        """Id yang boleh dipakai sebagai sitasi — hanya dari fakta."""
        blok = self.data.get("citations")
        hasil: list[dict[str, str]] = []
        if not isinstance(blok, dict):
            return hasil

        def tambah(jenis: str, nilai: Any) -> None:
            if nilai is None or str(nilai).strip() == "":
                return
            hasil.append({jenis: str(nilai)})

        for jenis in ("decision_id",):
            tambah(jenis, blok.get(jenis))
        for jenis, kunci in (
            ("batch_id", "batch_ids"),
            ("evidence_id", "evidence_ids"),
            ("ledger_block_id", "ledger_block_ids"),
        ):
            nilai = blok.get(kunci)
            if isinstance(nilai, (list, tuple)):
                for item in nilai:
                    tambah(jenis, item)
        return hasil

    def id_dikenal(self) -> set[str]:
        return {
            nilai
            for sitasi in self.sitasi_id()
            for nilai in sitasi.values()
        }


class VerifierFactsSource:
    """Pembaca fakta verifier: dua GET, tanpa tulis, tanpa hitung ulang."""

    def __init__(self, api: Any) -> None:
        self.api = api

    def baca(self, decision_id: str) -> FaktaVerifier:
        if not decision_id or not str(decision_id).strip():
            raise AgentApiError("decision_id wajib diisi untuk audit verifier")
        path = AUDIT_FACTS_PATH.format(decision_id=decision_id)
        data = self.api.get(path)
        if not isinstance(data, dict) or not data.get("decision_id"):
            raise AgentApiError(f"respons {path} tidak memuat faktanya", path=path)
        if str(data.get("decision_id")) != str(decision_id):
            raise AgentApiError(
                f"fakta {path} milik keputusan lain; audit ditolak", path=path
            )

        approval_path = APPROVAL_SUMMARY_PATH.format(decision_id=decision_id)
        approval: dict[str, Any] | None = None
        sumber = [path]
        try:
            ringkas = self.api.get(approval_path)
            if isinstance(ringkas, dict):
                approval = ringkas
                sumber.append(approval_path)
        except AgentApiError:
            # Approval-summary bukan sumber cek wajib; ketiadaannya dicatat
            # sebagai sumber yang tidak terbaca, bukan ditebak.
            pass
        return FaktaVerifier(data=data, approval=approval, sumber=tuple(sumber))


__all__ = [
    "APPROVAL_SUMMARY_PATH",
    "AUDIT_FACTS_PATH",
    "FaktaVerifier",
    "READ_ONLY_PATHS",
    "VerifierFactsSource",
]
