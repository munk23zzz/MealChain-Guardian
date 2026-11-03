"""Orkestrasi review tujuh worker + verifier — satu putaran advisory.

Tujuh worker membaca API, bukan menulis. Lane pertama Supply+Demand, lane
kedua Safety+Freshness, lane ketiga Price+Logistics; Evidence Fusion berjalan
setelah lane selesai. Kegagalan satu worker tidak menghentikan worker lain:
temuan error dilaporkan apa adanya dan status run menjadi `partial`/`timeout`.

Tidak ada approval, eksekusi, atau perubahan status decision di sini.
"""

from __future__ import annotations

import re
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import replace
from time import monotonic
from typing import Any
from uuid import uuid4

from .api_client import AgentApiError, MealChainClient
from .contracts import AgentFinding, AgentName, AgentRun, RunStatus, VerifyResult, WorkerStatus
from .registry import get_spec
from .telemetry import build_trace_rows
from .validation import GUARDIANS, detect_contradictions, run_status, safety_veto
from .verifier_facts import AUDIT_FACTS_PATH
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


def _alasan_blokir(finding: AgentFinding) -> str:
    """Satu kalimat pemblokir dari FAKTA temuan — tanpa angka turunan.

    Narasi tidak boleh menyebut angka yang tidak ada di fakta (verifier akan
    menandainya), jadi alasan di sini hanya menyebut keadaan: field fakta yang
    null atau daftar id yang kosong/tidak.
    """
    facts = finding.facts or {}
    if finding.status is WorkerStatus.ERROR:
        return "worker gagal menjalankan pemeriksaan"
    if facts.get("batch_count") is None:
        return "batch sumber tidak teridentifikasi"
    if facts.get("expired_batch_ids"):
        return "ada batch sumber yang sudah kedaluwarsa"
    if facts.get("failed_batch_ids"):
        return "ada batch sumber berstatus fail"
    if facts.get("quarantined_batch_ids"):
        return "ada batch sumber dikarantina"
    if facts.get("active_exclusion_ids"):
        return "ada exclusion aktif yang berlaku"
    if facts.get("blocking_reason"):
        return str(facts["blocking_reason"])
    return "fakta pemblokir tidak tersedia lengkap (fail-closed)"


def _klausa_kesegaran(run: AgentRun) -> str:
    """Status kesegaran VERBATIM dari fakta worker freshness (bukan kesimpulan)."""
    temuan = next(
        (f for f in run.findings if f.agent is AgentName.FRESHNESS), None
    )
    if temuan is None:
        return ""
    facts = temuan.facts or {}
    if facts.get("batch_count") is None:
        return "Status kesegaran batch sumber tidak tersedia. "
    status = facts.get("freshness_status")
    if status == "needs_verification":
        return (
            "Kesegaran batch sumber belum certified (status needs_verification): "
            "butuh verifikasi manusia. "
        )
    if status == "fail":
        return "Kesegaran batch sumber tidak memenuhi ambang (status fail). "
    if status:
        return f"Status kesegaran batch sumber: {status}. "
    return "Status kesegaran batch sumber tidak tersedia. "


def narasi_dari_fakta(run: AgentRun) -> str:
    """Narasi deterministik: HANYA fakta yang benar-benar ada di `run`.

    Narasi supervisor bukan tempat mengarang verdict. Setiap klaim di bawah
    berasal dari `status`, `safety_veto`, `contradictions`, atau `findings`
    pada run ini — sehingga verifier bisa membandingkannya dengan fakta run
    yang sama, bukan dengan status keputusan di DB (objek yang berbeda).
    """
    status = run.status.value
    if run.safety_veto:
        pemblokir = [
            finding
            for finding in run.findings
            if finding.blocking and finding.agent in GUARDIANS
        ]
        bukti = "; ".join(
            f"{finding.agent.value}: {_alasan_blokir(finding)}" for finding in pemblokir
        ) or "guardian melaporkan blocking tanpa fakta pendukung"
        return (
            f"Status run: {status}; safety_veto=true. Guardian yang memblokir — "
            f"{bukti}. JANGAN EKSEKUSI keputusan ini sebelum bukti diperbaiki; "
            "keputusan tetap advisory dan menunggu review manusia."
        )
    if run.status is RunStatus.TIMEOUT:
        return (
            f"Status run: {status}; safety_veto=false. Sebagian temuan tidak "
            "tersedia; jangan menyimpulkan aman dan jangan eksekusi otomatis."
        )
    if run.status is RunStatus.PARTIAL:
        return (
            f"Status run: {status}; safety_veto=false; "
            f"kontradiksi={len(run.contradictions)}. Ada temuan degraded/error "
            "atau kontradiksi; keputusan tetap menunggu review manusia. "
            + _klausa_kesegaran(run)
        ).strip()
    if run.status is RunStatus.COMPLETED:
        return (
            f"Status run: {status}; safety_veto=false; "
            f"kontradiksi={len(run.contradictions)}. "
            + _klausa_kesegaran(run)
            + "Ini review advisory, bukan approval; keputusan tetap menunggu "
            "keputusan manusia."
        )
    return (
        f"Status run: {status}; safety_veto=false. Review tidak dapat "
        "diselesaikan; tidak ada klaim aman."
    )


#: Frasa yang MENGKLAIM veto/blokir. Bila fakta run tidak memblokir, narasi
#: dengan frasa ini adalah karangan — dan karangan itulah yang dulu memicu veto
#: verifier pada setiap putaran.
KATA_KLAIM_VETO = ("vetoed", "safety_veto=true", "memblokir", "diblokir")

#: "Status run: vetoed" — satu-satunya bentuk klaim status yang diaudit.
_STATUS_NARASI_RE = re.compile(r"status run:\s*([a-z_]+)")


def pelanggaran_narasi(teks: str | None, run: AgentRun) -> list[str]:
    """Selisih antara narasi dan fakta run; kosong = narasi boleh dipakai."""
    isi = (teks or "").strip()
    if not isi:
        return ["narasi kosong"]
    low = isi.lower()
    hasil: list[str] = []
    status_disebut = _STATUS_NARASI_RE.search(low)
    if status_disebut and status_disebut.group(1) != run.status.value:
        hasil.append(
            f"narasi menyebut status run '{status_disebut.group(1)}' padahal "
            f"fakta '{run.status.value}'"
        )
    if any(kata in low for kata in KATA_KLAIM_VETO) and not run.safety_veto:
        hasil.append("narasi menyebut veto/blokir padahal safety_veto=false")
    if "safety_veto=false" in low and run.safety_veto:
        hasil.append("narasi menyebut safety_veto=false padahal guardian memblokir")
    menyatakan_aman = any(
        kata in low for kata in ("tanpa kontradiksi", "semua aman", "aman untuk dieksekusi")
    )
    if menyatakan_aman and (run.safety_veto or run.status is not RunStatus.COMPLETED):
        hasil.append("narasi menyatakan aman padahal putaran tidak completed")
    return hasil


def fakta_narasi(run: AgentRun) -> dict[str, Any]:
    """Fakta run yang boleh dipakai narator — objek yang sama dengan narasi."""
    return {
        "status": run.status.value,
        "safety_veto": run.safety_veto,
        "kontradiksi": len(run.contradictions),
        "temuan": [
            {
                "agent": finding.agent.value,
                "status": finding.status.value,
                "blocking": finding.blocking,
                "fakta": finding.facts,
            }
            for finding in run.findings
        ],
    }


def narasi_terjaga(
    run: AgentRun,
    narrator: Any | None = None,
    *,
    lineage: dict[str, Any] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Narasi final + catatan bila narator (model) mengarang.

    Narator hanya boleh MENGULANG fakta run. Bila narasinya bertentangan dengan
    fakta (mis. mengklaim veto saat `safety_veto=false`), narasi itu dibuang dan
    diganti narasi deterministik dari fakta — bukan diloloskan, karena veto
    verifier atas narasi karangan itulah bug yang sedang diperbaiki.

    `lineage` (28 Okt 2026) = out-param opsional yang diisi APA ADANYA:
    `{"source": "model"|"template", "latency_ms": int, "note": str|None}`.
    Sebelum ini jejak SUPERVISE tidak membedakan narasi model dari narasi
    template, sehingga pemeriksa menyimpulkan supervisor "deterministik" —
    padahal modelnya bisa saja dipanggil lalu narasinya ditolak gerbang.
    """
    mulai = monotonic()

    def _catat(sumber: str, catatan: str | None) -> None:
        if lineage is None:
            return
        lineage.update(
            {
                "source": sumber,
                "latency_ms": max(0, int((monotonic() - mulai) * 1000)),
                "note": catatan,
            }
        )

    template = narasi_dari_fakta(run)
    if narrator is None:
        _catat("template", "narator tidak dipasang (tanpa model)")
        return template, ()
    try:
        kandidat = str(narrator(fakta_narasi(run)) or "").strip()
    except Exception as exc:  # noqa: BLE001 - narator gagal ≠ review gagal
        catatan = f"narator gagal ({type(exc).__name__}); narasi fakta dipakai"
        _catat("template", catatan)
        return template, (catatan,)
    if not kandidat:
        catatan = "narator mengembalikan narasi kosong; narasi fakta dipakai"
        _catat("template", catatan)
        return template, (catatan,)
    masalah = pelanggaran_narasi(kandidat, run)
    if masalah:
        catatan = (
            "narasi narator bertentangan dengan fakta, diganti narasi fakta: "
            + "; ".join(masalah)
        )
        _catat("template", catatan)
        return template, (catatan,)
    _catat("model", None)
    return kandidat, ()


def batch_sumber_dari_audit_facts(api: Any, decision_id: str) -> tuple[str, ...]:
    """`batch_ids` batch SUMBER dari fakta backend; `()` bila tidak terbaca.

    `approval-summary` untuk keputusan pengadaan pemasok tidak membawa
    `safety.batch_ids` (dan `source_location` null), sehingga guardian
    Safety/Freshness tidak bisa mengidentifikasi batch dan fail-closed →
    memblokir setiap putaran. Fakta `audit-facts` SUDAH menghitung himpunan
    batch sumber (sumber yang sama dengan `batch_sumber_transfer`), jadi yang
    dilengkapi di sini adalah FAKTA — bukan tebakan. Bila fakta itu tidak ada,
    context tetap kosong (fail-closed) dan guardian tetap memblokir.
    """
    path = AUDIT_FACTS_PATH.format(decision_id=decision_id)
    try:
        data = api.get(path)
    except Exception:  # noqa: BLE001 - fakta opsional; ketiadaannya bukan tebakan
        return ()
    if not isinstance(data, dict) or str(data.get("decision_id") or "") != str(
        decision_id
    ):
        return ()
    batch = data.get("batch_sumber")
    ids = batch.get("batch_ids") if isinstance(batch, dict) else None
    if not isinstance(ids, (list, tuple)):
        return ()
    return tuple(str(nilai) for nilai in ids if str(nilai).strip())


def run_review(
    decision_id: str,
    *,
    api: Any | None = None,
    context: WorkerContext | None = None,
    workers: dict[AgentName, Any] | None = None,
    timeout_seconds: float = 45.0,
    mode: str = "advisory",
    retry_errors: bool = True,
    narrator: Any | None = None,
) -> AgentRun:
    """Jalankan satu review tujuh worker (+ audit verifier) untuk satu decision.

    Context boleh diberikan oleh pemanggil (tes/probe); bila tidak, fungsi ini
    membaca `approval-summary` dan memakai field yang benar-benar ada. Tidak ada
    panggilan endpoint mutasi.

    `narrator` adalah seam opsional `(fakta_run) -> teks`: narasi yang ia
    hasilkan HANYA dipakai bila konsisten dengan fakta run (lihat
    `narasi_terjaga`); selain itu narasi deterministik dari fakta yang dipakai.
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
        if not context.source_batch_ids:
            batch_ids = batch_sumber_dari_audit_facts(api, decision_id)
            if batch_ids:
                context = replace(context, source_batch_ids=batch_ids)
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
    run = run.model_copy(update={"narrative": None})
    lineage_narasi: dict[str, Any] = {}
    narasi, catatan_narasi = narasi_terjaga(run, narrator, lineage=lineage_narasi)
    run = run.model_copy(
        update={"narrative": narasi, "narration": lineage_narasi or None}
    )
    # Gerbang verifikasi deterministik dijalankan SETELAH supervisor menyusun
    # rangkuman, dan hanya menandai — tidak mengubah status atau keputusan.
    gerbang = verify_run(run)
    run = run.model_copy(update={"verification": gerbang})
    if catatan_narasi:
        # Jejak mengapa narasi narator dibuang — pembaca harus bisa melihatnya
        # di gerbang, bukan menyimpulkan sendiri.
        run = run.model_copy(
            update={
                "verification": VerifyResult(
                    verdict=gerbang.verdict,
                    reasons=[*gerbang.reasons, *catatan_narasi],
                )
            }
        )

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
    "batch_sumber_dari_audit_facts",
    "build_trace_rows",
    "context_from_approval",
    "fakta_narasi",
    "narasi_dari_fakta",
    "narasi_terjaga",
    "pelanggaran_narasi",
    "run_review",
]
