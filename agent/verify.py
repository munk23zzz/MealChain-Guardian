"""Gerbang verifikasi deterministik atas hasil supervisor.

Kenapa ada: supervisor merangkum tujuh worker, dan rangkuman itu bisa lebih
halus daripada buktinya (mis. ada worker `degraded` tetapi status run ditulis
`completed`). Gerbang ini memeriksa KONSISTENSI, bukan menilai kualitas model,
dan hanya boleh menandai (`flag`) — tidak memveto. Keputusan tetap `proposed`
dan eksekusi tetap menunggu manusia.

Semua pemeriksaan deterministik: tidak ada panggilan model, tidak ada tulisan.
"""

from __future__ import annotations

from .contracts import AgentRun, RunStatus, VerifyResult, WorkerStatus
from .validation import run_status


def verify_run(run: AgentRun) -> VerifyResult:
    """Periksa satu AgentRun; kembalikan verdict beserta alasan yang terbaca."""
    reasons: list[str] = []

    bukti = run_status(run.findings, run.contradictions)
    if run.status is not bukti:
        reasons.append(
            f"status_tidak_konsisten: supervisor={run.status.value}, "
            f"bukti_worker={bukti.value}"
        )

    # Veto keamanan yang aktif berarti keputusan tidak boleh dilaporkan sebagai
    # putaran selesai; manusia harus melihatnya.
    if run.safety_veto and run.status is RunStatus.COMPLETED:
        reasons.append(
            "safety_veto_aktif: ada temuan blocking, tetapi status run dilaporkan completed"
        )

    # Heuristik kata kunci, bukan penilaian semantik: bila ada worker yang tidak
    # utuh, narasi tidak boleh berbunyi seolah semuanya aman. Flag-only, jadi
    # salah tuduh di sini hanya meminta manusia membaca ulang.
    menurun = [
        finding.agent.value
        for finding in run.findings
        if finding.status
        in {WorkerStatus.DEGRADED, WorkerStatus.ERROR, WorkerStatus.SKIPPED}
    ]
    if menurun and run.narrative:
        teks = run.narrative.lower()
        jujur = any(
            kata in teks
            for kata in (
                "degraded",
                "sebagian",
                "error",
                "gagal",
                "tidak tersedia",
                "tidak lengkap",
                "partial",
            )
        )
        if not jujur:
            reasons.append(
                f"narasi_tidak_menyebut_penurunan: worker {', '.join(menurun)} "
                "tidak utuh tetapi narasi tidak menyebutnya"
            )

    return VerifyResult(verdict="flag" if reasons else "pass", reasons=reasons)


__all__ = ["VerifyResult", "verify_run"]
