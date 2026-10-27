"""Jalur review IN-PROCESS dari repo ini (`AGENT_REVIEW_MODE=local`).

Kenapa modul ini ada: review delapan agent dulu HANYA lewat runtime AgentCore
(`AGENTCORE_RUNTIME_ARN`). Kalau image runtime yang ter-deploy tertinggal dari
repo, backend menjalankan kode LAMA tanpa terlihat: verifier melaporkan
`unavailable`/`degraded`, `duration_ms = 0`, dan status run `completed` walau
guardian memblokir — bug yang tidak bisa diperbaiki dari sisi backend.

Mode `local` menjalankan orkestrator YANG ADA DI REPO (`agent/orchestrator.py`)
di dalam proses backend. Itu pilihan penempatan **A (in-process client)** dari
skill `verifier-agent-adapter`: satu aplikasi, satu auditor, ctx dibangun
server-side, provider palsu mudah disuntik di tes. Opsi C (agent penuh dengan
tool) hanya untuk audit investigatif dan sengaja tidak dipakai di sini.

Batas yang dijaga (skill `verifier-agent-adapter`):

- **Angka lahir dari kode.** Verifier membaca `/decisions/{id}/audit-facts`
  lewat `agent/verifier_facts.py`; model hanya menilai konsistensi.
- **Model tidak berkuasa menaikkan status.** `agent/verifier_checks.jaga_verdict`
  menahan `consistent` menjadi `flagged` bila cek deterministik gagal; `blocking`
  tetap milik guardian.
- **Ketiadaan model = fail-closed.** Tanpa model yang bisa dipanggil, audit
  tetap jalan deterministik dan verdict TIDAK PERNAH dikarang menjadi
  `consistent` (`unavailable`, atau `flagged` bila cek deterministik gagal).

Model verifier (dipilih berurutan, eksplisit → cadangan):

1. `VERIFIER_AGENT_MODEL` — id model khusus verifier (mis. `sap-ai-core:llm`).
2. `VERIFIER_MODEL_PRIMARY` — rantai model verifier yang sudah ada di repo.
3. `SUPERVISOR_MODEL_PRIMARY` — cadangan terakhir; runtime/model boleh sama
   dengan supervisor (keputusan owner), yang wajib terpisah adalah SYSTEM
   PROMPT dan sumber fakta, dan itu sudah begitu di `agent/workers/verifier.py`.

Slot `agentcore` (ARN runtime review) DITOLAK sebagai model verifier: mengirim
prompt audit ke agent supervisor membuat auditor memakai prompt supervisor —
independensi yang justru dijaga jadi hilang. Slot itu membuat audit
fail-closed, bukan lolos.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, Callable

from app.services.agent_review_client import AgentReviewResult

#: Nilai `AGENT_REVIEW_MODE` yang memilih jalur in-process. Nilai lain
#: (`advisory`, `predecision`, `agentcore`, kosong) tetap memakai runtime
#: AgentCore — default AMAN: perilaku produksi tidak berubah diam-diam.
LOCAL_MODE = "local"

ENV_API_URL = "AGENT_LOCAL_API_URL"
#: API yang dipanggil worker saat review berjalan DI DALAM backend. Jangan pakai
#: `MEALCHAIN_API_URL` (itu alamat publik/tunnel milik runtime AgentCore): review
#: lokal harus membaca backend yang sedang melayani request ini.
DEFAULT_API_URL = "http://127.0.0.1:8000"

#: Urutan pencarian model verifier; nama env ikut dilaporkan supaya jejak audit
#: menyebut sumber konfigurasinya, bukan menebak.
MODEL_ENV_KEYS: tuple[str, ...] = (
    "VERIFIER_AGENT_MODEL",
    "VERIFIER_MODEL_PRIMARY",
    "SUPERVISOR_MODEL_PRIMARY",
)

TIMEOUT_MIN_SECONDS = 10.0
TIMEOUT_MAX_SECONDS = 120.0


def transport(mode: str | None) -> str:
    """`local` hanya bila diminta EKSPLISIT; selain itu `agentcore`.

    Default sengaja `agentcore`: nilai lama (`advisory`, `predecision`) dan
    nilai kosong/tidak dikenal tidak boleh memindahkan review ke proses
    backend tanpa keputusan operator.
    """
    return LOCAL_MODE if (mode or "").strip().lower() == LOCAL_MODE else "agentcore"


def mode_orkestrator(mode: str | None) -> str:
    """Mode yang dikenal `agent.orchestrator.run_review` (bukan `local`)."""
    return "predecision" if (mode or "").strip().lower() == "predecision" else "advisory"


def model_id_dari_env() -> tuple[str, str] | None:
    """(id model, nama env) pertama yang terisi; None bila semuanya kosong."""
    for kunci in MODEL_ENV_KEYS:
        nilai = (os.environ.get(kunci) or "").strip()
        if nilai:
            return nilai, kunci
    return None


def build_model() -> tuple[Callable[[str], str] | None, str | None]:
    """Callable model verifier dari env, atau (None, alasan) — tidak melempar.

    Alasan dikembalikan APA ADANYA supaya `agent_traces` menyebut mengapa
    audit tidak bisa menyimpulkan, bukan menyembunyikannya.
    """
    if model_id_dari_env() is None:
        return None, (
            "model verifier tidak dikonfigurasi ("
            + "/".join(MODEL_ENV_KEYS)
            + " kosong)"
        )
    model_id, sumber = model_id_dari_env()  # type: ignore[misc]

    from app.ai_providers.ai_provider_chain import build_caller_for_ref
    from app.ai_providers.model_registry import parse_model_ref

    ref = parse_model_ref(model_id)
    if ref is None:
        return None, f"model verifier dari {sumber} kosong"
    if ref.kind == "agentcore":
        # Lihat docstring modul: auditor tidak boleh memakai runtime supervisor.
        return None, (
            f"model verifier dari {sumber} menunjuk runtime AgentCore "
            "(slot agent), bukan model — audit fail-closed"
        )
    try:
        return build_caller_for_ref(ref), None
    except Exception as exc:  # noqa: BLE001 - env rusak ≠ audit gagal
        return None, (
            f"model verifier dari {sumber} gagal dibangun: "
            f"{type(exc).__name__}: {exc}"
        )


def _api_url(explicit: str | None) -> str:
    nilai = (explicit or os.environ.get(ENV_API_URL) or "").strip()
    return (nilai or DEFAULT_API_URL).rstrip("/")


def _jalankan(
    decision_id: str,
    *,
    token: str,
    api_url: str,
    model: Callable[[str], str] | None,
    mode: str,
    timeout_seconds: float,
) -> AgentReviewResult:
    """Satu putaran review in-process; kegagalan dilaporkan, tidak ditebak."""
    try:
        from agent.api_client import MealChainClient
        from agent.orchestrator import run_review
        from agent.telemetry import build_trace_rows
        from agent.workers import build_workers
        from agent.workers.verifier import VerifierWorker
    except Exception as exc:  # noqa: BLE001 - paket agent tidak terpasang
        return AgentReviewResult(
            status="unavailable",
            error=(
                "paket agent tidak dapat diimpor dari proses backend: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    if not (token or "").strip():
        return AgentReviewResult(
            status="unavailable",
            error="token internal tidak tersedia; worker tidak boleh mengarang data",
        )

    try:
        api = MealChainClient(
            base_url=api_url,
            token=token,
            timeout=min(20.0, max(5.0, timeout_seconds)),
        )
        workers = {
            worker.name: (
                VerifierWorker(model=model)
                if isinstance(worker, VerifierWorker)
                else worker
            )
            for worker in build_workers()
        }
        run = run_review(
            decision_id,
            api=api,
            workers=workers,
            timeout_seconds=timeout_seconds,
            mode=mode,
        )
        payload: dict[str, Any] = run.model_dump(mode="json")
        payload["trace_rows"] = build_trace_rows(run)
    except Exception as exc:  # noqa: BLE001 - review gagal ≠ request gagal
        return AgentReviewResult(
            status="failed", error=f"{type(exc).__name__}: {exc}"
        )

    return AgentReviewResult(
        status=run.status.value,
        run_id=str(run.run_id),
        payload=payload,
    )


def review_decision_local(
    decision_id: str,
    *,
    token: str,
    api_url: str | None = None,
    mode: str = "advisory",
    timeout_seconds: float = 60.0,
    model: Callable[[str], str] | None = None,
) -> AgentReviewResult:
    """Jalankan review delapan agent dari repo (bukan runtime AgentCore).

    `model` hanya untuk tes: produksi memakai `build_model()` dari env. Bila
    env tidak menyediakan model, audit tetap jalan dan hasilnya fail-closed.
    """
    if not isinstance(decision_id, str) or not decision_id.strip():
        return AgentReviewResult(status="failed", error="decision_id wajib diisi")

    batas = max(TIMEOUT_MIN_SECONDS, min(TIMEOUT_MAX_SECONDS, float(timeout_seconds)))
    if model is None:
        model, _alasan_model = build_model()

    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-local")
    future = executor.submit(
        _jalankan,
        decision_id.strip(),
        token=token,
        api_url=_api_url(api_url),
        model=model,
        mode=mode_orkestrator(mode),
        timeout_seconds=batas,
    )
    try:
        return future.result(timeout=batas + 15.0)
    except FutureTimeout:
        future.cancel()
        return AgentReviewResult(
            status="timeout",
            error=f"review lokal melewati batas {batas + 15.0:g} detik",
        )
    except Exception as exc:  # noqa: BLE001
        return AgentReviewResult(status="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


__all__ = [
    "DEFAULT_API_URL",
    "ENV_API_URL",
    "LOCAL_MODE",
    "MODEL_ENV_KEYS",
    "build_model",
    "mode_orkestrator",
    "model_id_dari_env",
    "review_decision_local",
    "transport",
]
