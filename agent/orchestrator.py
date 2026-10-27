"""Orkestrasi review tujuh worker + verifier — satu putaran advisory.

Tujuh worker membaca API, bukan menulis. Lane pertama Supply+Demand, lane
kedua Safety+Freshness, lane ketiga Price+Logistics; Evidence Fusion berjalan
setelah lane selesai. Kegagalan satu worker tidak menghentikan worker lain:
temuan error dilaporkan apa adanya dan status run menjadi `partial`/`timeout`.

Tidak ada approval, eksekusi, atau perubahan status decision di sini.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import replace
from time import monotonic
from typing import Any
from uuid import uuid4

from .api_client import AgentApiError, MealChainClient
from .contracts import AgentFinding, AgentName, AgentRun, RunStatus, WorkerStatus
from .registry import get_spec
from .telemetry import build_trace_rows
from .validation import detect_contradictions, run_status, safety_veto
from .verify import verify_run
from .workers import build_workers
from .workers.base import WorkerContext, as_number

LANES: tuple[tuple[AgentName, ...], ...] = (
    (AgentName.SUPPLY, AgentName.DEMAND),
    (AgentName.SAFETY, AgentName.FRESHNESS),
    (AgentName.PRICE, AgentName.LOGISTICS),
)
EVIDENCE_AGENT = AgentName.EVIDENCE


def _id_teks(nilai: Any) -> str | None:
    """Identitas (UUID sebagai string) dari summary; kosong → None, tanpa menebak."""
    if not isinstance(nilai, str):
        return None
    teks = nilai.strip()
    return teks or None


def context_from_approval(
    decision_id: str, summary: dict[str, Any]
) -> WorkerContext:
    """Bangun context worker dari `approval-summary`; tidak menebak field.

    Sejak AUD-9B-29 context membawa identitas yang dipakai guardian untuk
    menilai batch SUMBER dan mencakupkan exclusion:

    - `target_location_id` + `supplier.id` → cakupan exclusion
      (`supplier_exclusions.supplier_id` + `scope_location_id`);
    - `safety.batch_ids` → himpunan batch sumber yang benar-benar dikirim
      (sumber yang sama dengan `batch_sumber_transfer` di backend).

    Field yang tidak ada dibiarkan None/kosong; worker lalu fail-closed,
    bukan menebak dari lokasi tujuan.
    """
    location = summary.get("target_location")
    commodity = summary.get("commodity")
    if not isinstance(location, str) or not location.strip():
        raise ValueError("approval-summary tidak memiliki target_location")
    if not isinstance(commodity, str) or not commodity.strip():
        raise ValueError("approval-summary tidak memiliki commodity")
    source = summary.get("source_location")
    source_location = source.strip() if isinstance(source, str) and source.strip() else None
    quantity = as_number(summary.get("quantity_kg"), allow_numeric_string=True)
    supplier = summary.get("supplier")
    supplier_id = _id_teks(supplier.get("id")) if isinstance(supplier, dict) else None
    safety = summary.get("safety")
    batch_ids: tuple[str, ...] = ()
    if isinstance(safety, dict) and isinstance(safety.get("batch_ids"), list):
        batch_ids = tuple(
            str(nilai) for nilai in safety["batch_ids"] if str(nilai).strip()
        )
    return WorkerContext(
        run_id=uuid4(),
        decision_id=decision_id,
        location=location.strip(),
        commodity=commodity.strip(),
        source_location=source_location,
        quantity_kg=quantity,
        target_location_id=_id_teks(summary.get("target_location_id")),
        source_location_id=_id_teks(summary.get("source_location_id")),
        supplier_id=supplier_id,
        source_batch_ids=batch_ids,
    )


def _error_finding(agent: AgentName, message: str) -> AgentFinding:
    return AgentFinding(
        agent=agent,
        stage=get_spec(agent).stage,
        status=WorkerStatus.ERROR,
        summary=f"{agent.value}: {message}",
        facts={},
        citations=[],
        warnings=[message],
    )


def _run_one(worker: Any, context: WorkerContext, *, retry_errors: bool) -> AgentFinding:
    """Jalankan satu worker; worker error boleh dicoba sekali lagi."""
    started = monotonic()
    try:
        finding = worker.run(context)
    except Exception as exc:  # worker contract: error tidak boleh menghentikan run
        return _error_finding(worker.name, f"{type(exc).__name__}: {exc}")

    if (
        retry_errors
        and finding.status is WorkerStatus.ERROR
        and monotonic() - started < 5
    ):
        try:
            finding = worker.run(context)
        except Exception as exc:
            return _error_finding(worker.name, f"{type(exc).__name__}: {exc}")
    return finding


def _run_lane(
    lane: tuple[AgentName, ...],
    workers: dict[AgentName, Any],
    context: WorkerContext,
    *,
    retry_errors: bool,
) -> list[AgentFinding]:
    results: list[AgentFinding] = []
    for name in lane:
        worker = workers.get(name)
        if worker is None:
            results.append(_error_finding(name, "worker tidak terdaftar"))
        else:
            results.append(_run_one(worker, context, retry_errors=retry_errors))
    return results


def _collect_lanes(
    workers: dict[AgentName, Any],
    context: WorkerContext,
    *,
    timeout_seconds: float,
    retry_errors: bool,
) -> tuple[list[AgentFinding], bool]:
    """Jalankan tiga lane paralel, lalu Evidence sesudah lane."""
    started = monotonic()
    deadline = started + max(0.1, timeout_seconds)
    executor = ThreadPoolExecutor(max_workers=len(LANES), thread_name_prefix="agent-lane")
    futures: dict[Future, tuple[AgentName, ...]] = {
        executor.submit(
            _run_lane,
            lane,
            workers,
            context,
            retry_errors=retry_errors,
        ): lane
        for lane in LANES
    }
    findings: list[AgentFinding] = []
    timed_out = False
    try:
        for future, lane in list(futures.items()):
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise FutureTimeout()
            try:
                findings.extend(future.result(timeout=remaining))
            except FutureTimeout:
                timed_out = True
                break
    except FutureTimeout:
        timed_out = True
    finally:
        for future in futures:
            if not future.done():
                future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)

    returned = {finding.agent for finding in findings}
    for lane in LANES:
        for name in lane:
            if name not in returned:
                findings.append(
                    _error_finding(
                        name,
                        "timeout: lane melewati batas waktu review"
                        if timed_out
                        else "worker tidak menghasilkan temuan",
                    )
                )
                returned.add(name)

    evidence = workers.get(EVIDENCE_AGENT)
    if timed_out or monotonic() >= deadline:
        findings.append(_error_finding(EVIDENCE_AGENT, "timeout: evidence tidak sempat berjalan"))
        timed_out = True
    elif evidence is None:
        findings.append(_error_finding(EVIDENCE_AGENT, "worker tidak terdaftar"))
    else:
        remaining = max(0.1, deadline - monotonic())
        evidence_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-evidence")
        future = evidence_executor.submit(
            _run_one, evidence, context, retry_errors=retry_errors
        )
        try:
            findings.append(future.result(timeout=remaining))
        except FutureTimeout:
            future.cancel()
            findings.append(_error_finding(EVIDENCE_AGENT, "timeout: evidence melewati batas"))
            timed_out = True
        finally:
            evidence_executor.shutdown(wait=False, cancel_futures=True)

    order = {name: index for index, name in enumerate(AgentName)}
    findings.sort(key=lambda finding: order[finding.agent])
    return findings, timed_out


def _narrative(run: AgentRun) -> str:
    if run.safety_veto:
        return (
            "Review 7 agen menemukan guardian yang memblokir. "
            "JANGAN EKSEKUSI keputusan ini sebelum bukti diperbaiki; "
            "keputusan tetap advisory dan menunggu review manusia."
        )
    if run.status is RunStatus.TIMEOUT:
        return (
            "Review 7 agen berhenti karena batas waktu. Sebagian temuan tidak "
            "tersedia; jangan menyimpulkan aman dan jangan eksekusi otomatis."
        )
    if run.status is RunStatus.PARTIAL:
        return (
            "Review 7 agen selesai sebagian. Ada temuan yang degraded/error atau "
            "kontradiksi; keputusan tetap menunggu review manusia."
        )
    if run.status is RunStatus.COMPLETED:
        return (
            "Review 7 agen selesai tanpa kontradiksi. Ini review advisory, bukan "
            "approval; keputusan tetap menunggu keputusan manusia."
        )
    return "Review 7 agen tidak dapat diselesaikan; tidak ada klaim aman."


def run_review(
    decision_id: str,
    *,
    api: Any | None = None,
    context: WorkerContext | None = None,
    workers: dict[AgentName, Any] | None = None,
    timeout_seconds: float = 45.0,
    mode: str = "advisory",
    retry_errors: bool = True,
) -> AgentRun:
    """Jalankan satu review tujuh worker (+ audit verifier) untuk satu decision.

    Context boleh diberikan oleh pemanggil (tes/probe); bila tidak, fungsi ini
    membaca `approval-summary` dan memakai field yang benar-benar ada. Tidak ada
    panggilan endpoint mutasi.
    """
    if mode not in ("advisory", "predecision"):
        mode = "advisory"

    if context is None:
        if api is None:
            try:
                api = MealChainClient.from_env()
            except AgentApiError as exc:
                raise RuntimeError(str(exc)) from exc
        summary = api.get(f"/decisions/{decision_id}/approval-summary")
        context = context_from_approval(decision_id, summary)
    else:
        if api is not None:
            context = replace(context, api=api)
        if context.decision_id != decision_id:
            context = replace(context, decision_id=decision_id)

    if api is None:
        api = context.api
    if api is None:
        raise RuntimeError("missing_config: API client tidak tersedia untuk review")

    selected: dict[AgentName, Any] = {}
    for worker in (list(workers.values()) if workers else build_workers()):
        name = getattr(worker, "name", None)
        if isinstance(name, AgentName):
            selected[name] = worker
    if len(selected) != len(AgentName):
        missing = sorted(name.value for name in set(AgentName) - set(selected))
        raise ValueError(f"worker belum lengkap: {', '.join(missing)}")

    run_id = uuid4()
    context = replace(context, run_id=run_id, api=api)
    started = monotonic()
    findings, timed_out = _collect_lanes(
        selected,
        context,
        timeout_seconds=timeout_seconds,
        retry_errors=retry_errors,
    )
    contradictions = detect_contradictions(findings)
    status = run_status(findings, contradictions)
    if timed_out:
        status = RunStatus.TIMEOUT
    run = AgentRun(
        run_id=run_id,
        decision_id=decision_id,
        mode=mode,
        status=status,
        findings=findings,
        contradictions=contradictions,
        safety_veto=safety_veto(findings),
        narrative=None,
        total_latency_ms=max(0, int((monotonic() - started) * 1000)),
    )
    run = run.model_copy(update={"narrative": _narrative(run)})
    # Gerbang verifikasi deterministik dijalankan SETELAH supervisor menyusun
    # rangkuman, dan hanya menandai — tidak mengubah status atau keputusan.
    run = run.model_copy(update={"verification": verify_run(run)})

    # Agent verifier (agent ke-8) mengaudit hasil yang sudah jadi. Ia TIDAK
    # masuk `findings` supaya status run, narasi, dan veto tetap milik tujuh
    # worker analitik; temuannya disimpan terpisah dan tampil sebagai baris
    # trace sendiri. Ketiadaannya tidak boleh menggagalkan review.
    verifier = selected.get(AgentName.VERIFIER)
    audit = getattr(verifier, "audit", None)
    if not callable(audit):
        # Worker pengganti (mis. fake di tes) tidak punya audit; audit tetap
        # harus ada supaya tidak ada putaran review tanpa jejak auditor.
        from .workers.verifier import VerifierWorker

        audit = VerifierWorker().audit
    # Verifier adalah RUN ANAK (AUD-9A-03): ia berjalan sesudah narasi, membaca
    # faktanya sendiri lewat context.api, dan meninggalkan jejak dengan
    # `run_id` sendiri + `parent_run_id` = run review ini.
    verifier_run_id = uuid4()
    try:
        temuan = audit(run, context=context, run_id=verifier_run_id)
    except TypeError as exc:
        # Hanya tanda tangan lama (fake auditor tanpa parameter) yang jatuh ke
        # sini; TypeError dari DALAM audit tidak boleh disamarkan.
        if "unexpected keyword argument" not in str(exc):
            temuan = None
        else:
            try:
                temuan = audit(run)
            except Exception:  # noqa: BLE001 - auditor gagal ≠ review gagal
                temuan = None
    except Exception:  # noqa: BLE001 - auditor gagal ≠ review gagal
        temuan = None
    if temuan is not None:
        run = run.model_copy(
            update={
                "verifier_finding": temuan,
                "verifier_run_id": verifier_run_id,
            }
        )
    return run


__all__ = [
    "LANES",
    "build_trace_rows",
    "context_from_approval",
    "run_review",
]
