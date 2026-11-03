"""Kontrak output Verifier Agent (AUD-9A-03) — JSON tervalidasi, bukan teks bebas.

Verifier adalah auditor, jadi keluarannya harus bisa diperiksa mesin: tiga
verdict yang sah, cek per klaim, dan sitasi id. Teks yang tidak sesuai kontrak
TIDAK dianggap "hampar" — ia menjadi `unavailable` (fail-closed), karena audit
yang tidak terbaca tidak boleh membuka jalan approval.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Kosakata verdict yang sah — dipakai juga oleh guard (`agent/verifier_checks`).
Verdict = Literal["consistent", "flagged", "unavailable"]
VERDICTS: tuple[str, ...] = ("consistent", "flagged", "unavailable")


class VerifierOutputError(ValueError):
    """Output model tidak sesuai kontrak verifier."""


class VerifierCheck(BaseModel):
    """Satu butir pemeriksaan: klaim supervisor vs fakta."""

    model_config = ConfigDict(extra="forbid")

    nama: str = Field(min_length=1)
    klaim: str
    aktual: str
    lulus: bool


class VerifierCitation(BaseModel):
    """Sitasi id yang benar-benar ada di fakta (bukan karangan model)."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str | None = None
    batch_id: str | None = None
    evidence_id: str | None = None
    ledger_block_id: str | None = None

    @model_validator(mode="after")
    def _wajib_satu_id(self) -> VerifierCitation:
        if not any(
            (self.decision_id, self.batch_id, self.evidence_id, self.ledger_block_id)
        ):
            raise ValueError("sitasi wajib memuat minimal satu id")
        return self

    def identitas(self) -> str:
        for jenis in ("decision_id", "batch_id", "evidence_id", "ledger_block_id"):
            nilai = getattr(self, jenis)
            if nilai:
                return f"{jenis}:{nilai}"
        return "?"


class VerifierOutput(BaseModel):
    """Bentuk jawaban verifier yang diterima sistem."""

    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    checks: list[VerifierCheck] = Field(default_factory=list)
    citations: list[VerifierCitation] = Field(default_factory=list)
    catatan: str = ""


def parse_verifier_output(raw: str) -> VerifierOutput:
    """Ekstrak JSON dari output model; gagal apa pun → `VerifierOutputError`.

    Toleran terhadap teks pembungkus (markdown/penjelasan) di sekitar satu
    objek JSON, tetapi TIDAK toleran terhadap skema: verdict di luar tiga nilai
    sah, kunci asing, atau sitasi tanpa id semuanya ditolak.
    """
    teks = str(raw or "").strip()
    if not teks:
        raise VerifierOutputError("output model kosong")
    start = teks.find("{")
    end = teks.rfind("}")
    if start == -1 or end <= start:
        raise VerifierOutputError("output model tidak memuat objek JSON")
    try:
        data: Any = json.loads(teks[start : end + 1])
    except (json.JSONDecodeError, ValueError) as exc:
        raise VerifierOutputError(f"JSON verifier tidak sah: {exc}") from exc
    if not isinstance(data, dict):
        raise VerifierOutputError("output verifier bukan objek JSON")
    try:
        return VerifierOutput.model_validate(data)
    except Exception as exc:  # pydantic ValidationError
        raise VerifierOutputError(f"skema verifier tidak cocok: {exc}") from exc


__all__ = [
    "VERDICTS",
    "Verdict",
    "VerifierCheck",
    "VerifierCitation",
    "VerifierOutput",
    "VerifierOutputError",
    "parse_verifier_output",
]
