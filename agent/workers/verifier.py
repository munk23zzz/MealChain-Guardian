"""Verifier Agent — auditor agent ke-8.

Bedanya dengan enam agent analitik dan Evidence: agent ini tidak membaca data
baru dan tidak menghitung ulang. Ia menilai hasil satu putaran review —
konsistensi temuan, narasi supervisor, dan status keras — lalu mengeluarkan
temuan sendiri (`AgentFinding`) yang tampil di Agent Log sebagai baris
`agent.verifier`.

Kenapa tetap aman meski berbentuk agent:

1. Dijalankan SETELAH narasi supervisor dibuat, jadi narasi tidak bisa
   "meringkas" auditornya sendiri.
2. Masukannya adalah `run.verification` — hasil gerbang deterministik
   (`agent/verify.py`). Agent ini tidak bisa menghasilkan `pass` bila gerbang
   menandai `flag`; arah pelonggaran selalu ditolak.
3. Temuannya disimpan di `AgentRun.verifier_finding`, terpisah dari `findings`;
   status run, veto, dan narasi tetap dihitung dari tujuh worker analitik.
4. `blocking` selalu False: auditor tidak boleh memveto, hanya menandai.

Opsional: bila `model` disuntikkan (callable prompt -> str), agent meminta
penjelasan tambahan. Model hanya boleh MENAMBAH alasan, tidak mengubah verdict.
"""

from __future__ import annotations

import json
from time import monotonic

from ..contracts import AgentFinding, AgentName, AgentRun, WorkerStatus
from .base import StubWorker

VALID_MODEL_VERDICTS = ("CONSISTENT", "FLAGGED", "UNAVAILABLE")


class VerifierWorker(StubWorker):
    name = AgentName.VERIFIER

    def __init__(self, model=None) -> None:
        super().__init__(self.name)
        self.model = model

    def _model_reason(self, run: AgentRun, dasar: str) -> str | None:
        """Penjelasan tambahan dari model; TIDAK boleh mengubah verdict.

        Kegagalan model apa pun diabaikan (kembali None) — audit deterministik
        sudah menjadi dasar, model hanya memperkaya alasan.
        """
        if self.model is None:
            return None
        prompt = json.dumps(
            {
                "task": "jelaskan temuan audit secara singkat",
                "verdict_deterministik": dasar,
                "reasons": list((run.verification.reasons if run.verification else [])),
                "status_run": run.status.value,
                "safety_veto": run.safety_veto,
            },
            ensure_ascii=False,
        )
        try:
            raw = self.model(prompt)
        except Exception:  # noqa: BLE001 - audit tidak boleh gagal karena model
            return None
        try:
            data = json.loads(str(raw)[str(raw).find("{") : str(raw).rfind("}") + 1])
        except (ValueError, json.JSONDecodeError):
            return None
        alasan = data.get("reason")
        return str(alasan).strip()[:300] if alasan else None

    def audit(self, run: AgentRun) -> AgentFinding:
        """Nilai satu putaran review; hasilnya tidak mengubah run itu sendiri."""
        started = monotonic()
        hasil = run.verification

        if hasil is None:
            return self._degraded(
                "Verifikasi deterministik belum dijalankan; konsistensi putaran ini belum dinilai.",
                facts={
                    "verdict": None,
                    "reasons": [],
                    "status_run": run.status.value,
                    "dasar": "belum_verifikasi",
                },
                warnings=["verification_missing"],
                latency_ms=self._latency_ms(started),
            )

        advisories = [
            finding.agent.value
            for finding in run.findings
            if finding.status is not WorkerStatus.OK
        ]
        reasons = list(hasil.reasons)
        tambahan = self._model_reason(run, hasil.verdict)
        if tambahan:
            reasons.append(f"model: {tambahan}")

        facts = {
            "verdict": hasil.verdict,
            "reasons": reasons,
            "status_run": run.status.value,
            "safety_veto": run.safety_veto,
            "advisories": advisories,
            "dasar": "agent/verify.py",
        }

        if hasil.verdict == "flag":
            ringkas = "; ".join(reasons) if reasons else "ada ketidaksesuaian"
            return self._degraded(
                f"Audit menandai putaran ini: {ringkas}",
                facts=facts,
                warnings=[f"verdict_flag: {ringkas}"],
                latency_ms=self._latency_ms(started),
            )

        ringkas = (
            f"Audit sepakat: {len(run.findings)} temuan analitik konsisten dengan narasi"
            if run.narrative
            else f"Audit sepakat atas {len(run.findings)} temuan analitik"
        )
        if advisories:
            ringkas += f" (catatan: {', '.join(advisories)} tidak utuh)"
        return self._ok(ringkas, facts=facts, latency_ms=self._latency_ms(started))


__all__ = ["VerifierWorker"]
