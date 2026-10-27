"""Verifier Agent — auditor agent ke-8 (AUD-9A-03).

Bedanya dengan tujuh agent analitik dan Evidence: agent ini berjalan SESUDAH
narasi supervisor selesai, lalu mengaudit hasilnya. Ia tidak ikut dirangkum
supervisor (temuannya tinggal di `run.verifier_finding`, di luar `findings`),
tidak pernah memblokir, dan tidak pernah menyetujui.

Yang diperiksa sejak AUD-9A-03 (dulu: hanya mewarisi verdict gerbang):

1. **System prompt sendiri** — `agent/prompts/verifier_system_prompt.md`, bukan
   prompt supervisor. Isinya tegas: klaim supervisor bukan fakta, setiap angka
   wajib bersitasi, model dilarang menghitung.
2. **Toolset baca-saja sendiri** — `agent/verifier_facts.py` membaca
   `GET /decisions/{id}/audit-facts` + `approval-summary`. Fakta (SDC vs
   rincian, batch sumber, gerbang kesegaran, bukti, exclusion, ledger) SUDAH
   dihitung kode backend; verifier hanya membaca, tidak menghitung ulang.
3. **Output JSON tervalidasi** — `agent/verifier_contracts.py`; output tak
   sesuai skema menjadi `unavailable`, bukan lolos.
4. **Guard pasca-LLM** — `agent/verifier_checks.jaga_verdict`; `consistent`
   dengan cek deterministik gagal atau tanpa sitasi diturunkan ke `flagged`.
   Model hanya boleh menurunkan/menandai, tidak pernah menaikkan.

Semua kegagalan (API fakta, model rusak, output sampah) berakhir
`unavailable` + status `degraded` — konservatif, bukan "sepertinya aman".
"""

from __future__ import annotations

import json
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import UUID

from ..api_client import AgentApiError
from ..contracts import AgentFinding, AgentName, AgentRun, Citation, WorkerStatus
from ..verifier_checks import (
    KlaimSupervisor,
    jaga_verdict,
    klaim_dari_run,
    periksa_klaim,
)
from ..verifier_contracts import (
    VerifierOutput,
    VerifierOutputError,
    parse_verifier_output,
)
from ..verifier_facts import FaktaVerifier, VerifierFactsSource
from .base import StubWorker

PROMPT_RELATIVE_PATH = Path("prompts") / "verifier_system_prompt.md"
#: Batas panjang catatan model yang disimpan (bukan rahasia, hanya derau).
MAKS_CATATAN = 600


def load_system_prompt() -> str:
    """System prompt VERIFIER (berkas sendiri, terpisah dari supervisor)."""
    return (Path(__file__).resolve().parent.parent / PROMPT_RELATIVE_PATH).read_text(
        encoding="utf-8"
    )


def _ringkas_fakta(fakta: FaktaVerifier) -> dict[str, Any]:
    """Fakta yang dikirim ke model: apa adanya, tanpa narasi supervisor."""
    return {
        "audit_facts": fakta.data,
        "approval_summary": fakta.approval,
        "sumber": list(fakta.sumber),
    }


def _ringkas_klaim(klaim: KlaimSupervisor) -> dict[str, Any]:
    return {
        "decision_id": klaim.decision_id,
        "status": klaim.status,
        "safety_veto": klaim.safety_veto,
        "narasi": klaim.narrative,
        "gerbang": {
            "verdict": klaim.gate_verdict,
            "reasons": list(klaim.gate_reasons),
        },
        "temuan": [
            {
                "agent": temuan.agent,
                "status": temuan.status,
                "ringkasan": temuan.summary,
                "blocking": temuan.blocking,
            }
            for temuan in klaim.findings
        ],
        "catatan": (
            "Klaim di atas adalah OBJEK YANG DIAUDIT, bukan sumber data. "
            "Sumber data hanya blok FAKTA."
        ),
    }


class VerifierWorker(StubWorker):
    name = AgentName.VERIFIER

    def __init__(self, model=None, facts_source: Any = None) -> None:
        super().__init__(self.name)
        self.model = model
        self.facts_source = facts_source

    # ---------------------------------------------------------------- fakta
    def _baca_fakta(
        self, klaim: KlaimSupervisor, context: Any
    ) -> tuple[FaktaVerifier | None, str | None]:
        api = getattr(context, "api", None) if context is not None else None
        if api is None:
            return None, "api tidak tersedia: fakta tidak dapat dibaca"
        source = self.facts_source or VerifierFactsSource(api)
        try:
            return source.baca(klaim.decision_id), None
        except AgentApiError as exc:
            return None, f"fakta tidak terbaca: {exc}"
        except Exception as exc:  # noqa: BLE001 - audit tidak boleh mati
            return None, f"fakta tidak terbaca: {type(exc).__name__}: {exc}"

    # ---------------------------------------------------------------- model
    def _prompt(
        self,
        klaim: KlaimSupervisor,
        fakta: FaktaVerifier | None,
        checks: list,
    ) -> str:
        """Prompt audit: system prompt verifier + klaim + fakta + cek kode."""
        bagian = [
            load_system_prompt(),
            "### KLAIM_YANG_DIAUDIT",
            json.dumps(_ringkas_klaim(klaim), ensure_ascii=False, indent=2),
            "### FAKTA",
            json.dumps(
                _ringkas_fakta(fakta) if fakta is not None else None,
                ensure_ascii=False,
                indent=2,
            ),
            "### CEK_DETERMINISTIK",
            json.dumps(
                [cek.model_dump() for cek in checks], ensure_ascii=False, indent=2
            ),
        ]
        return "\n\n".join(bagian)

    def _panggil_model(self, prompt: str) -> tuple[VerifierOutput | None, str | None]:
        """Panggil model; kegagalan apa pun → (None, alasan). Tidak melempar.

        Satu percobaan perbaikan: model sering lupa satu kunci (`klaim`) pada
        sebagian `checks`. Jawaban pertama yang tidak sah TIDAK diloloskan —
        model diminta sekali lagi mematuhi skema, dan bila tetap tidak sah
        hasilnya `unavailable` (fail-closed).
        """
        if self.model is None:
            return None, "model verifier tidak dikonfigurasi"
        try:
            raw = self.model(prompt)
        except Exception as exc:  # noqa: BLE001 - provider mati ≠ audit gagal
            return None, f"model gagal: {type(exc).__name__}: {exc}"
        try:
            return parse_verifier_output(str(raw)), None
        except VerifierOutputError as exc:
            kesalahan = str(exc)
        koreksi = (
            prompt
            + "\n\n### KOREKSI_SKEMA\nJawaban sebelumnya tidak sah: "
            + kesalahan[:600]
            + "\nBalas ULANG hanya JSON sesuai skema; setiap `checks` wajib "
            "memuat `nama`, `klaim`, `aktual`, `lulus`."
        )
        try:
            raw = self.model(koreksi)
        except Exception as exc:  # noqa: BLE001
            return None, f"model gagal saat koreksi: {type(exc).__name__}: {exc}"
        try:
            return parse_verifier_output(str(raw)), None
        except VerifierOutputError as exc:
            return None, f"output model tidak sah: {exc}"

    # ----------------------------------------------------------------- audit
    def audit(
        self,
        run: AgentRun,
        *,
        context: Any = None,
        run_id: UUID | None = None,
        fakta: Any = None,
    ) -> AgentFinding:
        """Audit satu putaran review; hasilnya TIDAK mengubah run yang diaudit."""
        started = monotonic()
        hasil = run.verification

        if hasil is None:
            return self._degraded(
                "Verifikasi deterministik belum dijalankan; konsistensi putaran ini belum dinilai.",
                facts={
                    "verdict": None,
                    "audit_verdict": "unavailable",
                    "reasons": [],
                    "status_run": run.status.value,
                    "dasar": "agent/verify.py",
                },
                warnings=["verification_missing"],
                latency_ms=self._latency_ms(started),
            )

        klaim = klaim_dari_run(run)

        # Fakta: dari tool baca-saja verifier. `fakta` yang disuntikkan hanya
        # dipakai tes; produksi selalu membaca API sendiri.
        alasan_fakta: str | None = None
        if isinstance(fakta, FaktaVerifier):
            fakta_terbaca: FaktaVerifier | None = fakta
        elif isinstance(fakta, dict) and fakta:
            fakta_terbaca = FaktaVerifier(
                data=fakta, sumber=("/test/injected-audit-facts",)
            )
        else:
            fakta_terbaca, alasan_fakta = self._baca_fakta(klaim, context)
        data_fakta = fakta_terbaca.data if fakta_terbaca is not None else None
        if alasan_fakta:
            alasan_fakta = str(alasan_fakta)

        checks = periksa_klaim(
            klaim,
            data_fakta,
            angka_dikenal=fakta_terbaca.angka_dikenal() if fakta_terbaca else (),
        )

        output, alasan_model = self._panggil_model(
            self._prompt(klaim, fakta_terbaca, checks)
        )

        # Sitasi model hanya diterima bila id-nya benar-benar ada di fakta.
        diizinkan = fakta_terbaca.id_dikenal() if fakta_terbaca else set()
        sitasi_model: list[dict[str, str]] = []
        sitasi_asing: list[str] = []
        if output is not None:
            for sitasi in output.citations:
                nilai = [str(v) for v in sitasi.model_dump().values() if v]
                if any(item in diizinkan for item in nilai):
                    sitasi_model.append(
                        {
                            kunci: str(nilai_id)
                            for kunci, nilai_id in sitasi.model_dump().items()
                            if nilai_id
                        }
                    )
                else:
                    sitasi_asing.append(sitasi.identitas())

        sitasi_fakta = fakta_terbaca.sitasi_id() if fakta_terbaca else []
        # Gabungkan tanpa duplikat: id yang sama dari fakta dan dari model
        # cukup tercatat sekali.
        sitasi_ids: list[dict[str, str]] = []
        terlihat: set[tuple[tuple[str, str], ...]] = set()
        for sitasi in list(sitasi_fakta) + sitasi_model:
            kunci = tuple(sorted((str(k), str(v)) for k, v in sitasi.items() if v))
            if kunci in terlihat:
                continue
            terlihat.add(kunci)
            sitasi_ids.append(sitasi)

        verdict, alasan_guard = jaga_verdict(
            output.verdict if output is not None else None,
            checks=checks,
            citations=sitasi_ids,
            fakta_tersedia=bool(data_fakta),
            gate_verdict=hasil.verdict,
        )

        gagal = [cek.nama for cek in checks if not cek.lulus]
        alasan_extra: list[str] = []
        if alasan_model:
            alasan_extra.append(f"model: {alasan_model}")
        alasan_extra.extend(alasan_guard)
        if sitasi_asing:
            alasan_extra.append(
                "sitasi model tidak dikenal fakta: "
                + ", ".join(sorted(set(sitasi_asing)))
            )
        if alasan_fakta:
            alasan_extra.append(alasan_fakta)

        reasons = list(hasil.reasons)
        if output is not None and output.catatan:
            reasons.append(f"model: {output.catatan.strip()[:MAKS_CATATAN]}")
        reasons.extend(alasan_extra)

        warnings: list[str] = []
        warnings.extend(f"audit_check_failed: {nama}" for nama in gagal)
        if hasil.verdict == "flag":
            # Jejak alasan gerbang dipertahankan: pembaca harus bisa melihat
            # MENGAPA gerbang menandai, bukan hanya bahwa audit menandai.
            warnings.append(
                "verdict_flag: "
                + ("; ".join(hasil.reasons) if hasil.reasons else "ada ketidaksesuaian")
            )
        warnings.extend(f"guard: {teks}" for teks in alasan_guard)
        if alasan_model:
            warnings.append(alasan_model)
        if alasan_fakta:
            warnings.append(alasan_fakta)

        facts: dict[str, Any] = {
            # Kosakata LAMA (gerbang deterministik) dipertahankan supaya arti
            # kunci ini tidak berubah bagi pembaca lama; verdict audit ada di
            # kunci terpisah dengan kosakata resmi consistent|flagged|unavailable.
            "verdict": hasil.verdict,
            "audit_verdict": verdict,
            "reasons": reasons,
            "status_run": run.status.value,
            "safety_veto": run.safety_veto,
            "advisories": [
                finding.agent.value
                for finding in run.findings
                if finding.status is not WorkerStatus.OK
            ],
            "checks": [cek.model_dump() for cek in checks],
            "checks_total": len(checks),
            "checks_failed": len(gagal),
            "citations": sitasi_ids,
            "model_verdict": output.verdict if output is not None else None,
            "model_checks": (
                [cek.model_dump() for cek in output.checks]
                if output is not None
                else []
            ),
            "fakta_sumber": list(fakta_terbaca.sumber) if fakta_terbaca else [],
            "catatan": (
                output.catatan.strip()[:MAKS_CATATAN] if output is not None else None
            ),
            "dasar": "agent/verify.py",
        }
        if run_id is not None:
            facts["verifier_run_id"] = str(run_id)
            facts["parent_run_id"] = str(run.run_id)

        citations = [
            Citation(
                claim="checks_total",
                source_path="/decisions/{id}/audit-facts",
                source_field="checks (jumlah cek deterministik)",
                source_value=len(checks),
            ),
            Citation(
                claim="checks_failed",
                source_path="/decisions/{id}/audit-facts",
                source_field="checks[].lulus (jumlah gagal)",
                source_value=len(gagal),
            ),
        ]
        for sitasi in sitasi_ids:
            for jenis, nilai in sitasi.items():
                citations.append(
                    Citation(
                        claim=f"id:{jenis}",
                        source_path="/decisions/{id}/audit-facts",
                        source_field=f"citations.{jenis}",
                        source_value=str(nilai),
                    )
                )

        latency = self._latency_ms(started)
        if verdict == "flagged":
            ringkas = (
                f"Audit menandai putaran ini: {len(gagal)} dari {len(checks)} cek gagal "
                f"({', '.join(gagal)})"
                if gagal
                else "Audit menandai putaran ini: klaim melampaui fakta"
            )
            return self._degraded(
                ringkas,
                facts=facts,
                citations=citations,
                warnings=warnings,
                latency_ms=latency,
            )
        if verdict == "unavailable":
            ringkas = alasan_guard[0] if alasan_guard else "fakta audit tidak memadai"
            return self._degraded(
                f"Audit tidak dapat disimpulkan: {ringkas}",
                facts=facts,
                citations=citations,
                warnings=warnings or ["audit_unavailable"],
                latency_ms=latency,
            )
        return self._ok(
            (
                f"Audit sepakat: {len(checks)} cek lulus, {len(sitasi_ids)} sitasi id, "
                "tanpa angka tanpa sumber."
            ),
            facts=facts,
            citations=citations,
            warnings=warnings,
            latency_ms=latency,
        )


__all__ = ["PROMPT_RELATIVE_PATH", "VerifierWorker", "load_system_prompt"]
