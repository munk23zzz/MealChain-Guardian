"""Orchestrator pengadaan pemasok untuk Demo Control (19 Okt 2026).

Alur tujuh langkah yang sama dengan `event1_orchestrator`, tetapi objek yang
dinilai adalah PEMASOK yang sudah memasok SPPG target (bukan surplus SPPG
lain):

DETECT → VERIFY → TRACE → PREDICT → OPTIMIZE → ANALYZE → DECIDE → SUPERVISE

Semua angka berasal dari `supplier_procurement.evaluate_suppliers`
(pemasok, stok batch di SPPG itu, penawaran harga, jarak pemasok→SPPG) dan
`run_forecast` untuk histori demand. Tidak ada approval otomatis dan tidak ada
eksekusi: keputusan lahir `proposed`.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from time import monotonic
from typing import Callable

from sqlalchemy import select

from app.ai_providers.verifier_client import run_verifier
from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.models import Commodity, Decision, Location
from app.services.forecast_service import forecast_kebutuhan
from app.services.hypothesis_client import narasi_tahap, run_hypothesis
from app.services.supervisor_client import run_supervisor
from app.services.supplier_procurement import (
    evaluate_suppliers,
    persist_supplier_binding,
)
from app.services.trace_persistence import persist_trace_steps

DEFAULT_TTL_MINUTES = 30
FORECAST_HORIZON_DAYS = 7


@dataclass
class _TraceStep:
    step_name: str
    tool_called: str | None
    input_summary: dict | None
    output_summary: dict | None
    # 29 Okt 2026: durasi nyata per langkah. Tanpa ini Agent Log hanya bisa
    # menampilkan urutan kedatangan baris (semua `step_at` = waktu simpan), sehingga
    # putaran yang memanggil model terbaca seperti skrip instan.
    duration_ms: int | None = None


def _narasi(tahap: str, fakta: dict) -> dict:
    """Narasi model untuk satu tahap; gagal apa pun dicatat, putaran tetap jalan.

    Angka di `fakta` sudah dihitung kode. `narasi_tahap` menandai angka yang
    tidak ada di fakta (`ungrounded`) alih-alih menerimanya.
    """
    mulai = monotonic()
    try:
        hasil = narasi_tahap(tahap, fakta)
    except Exception as exc:  # noqa: BLE001 — narasi opsional, tahap tetap tercatat
        return {
            "status": "error",
            "teks": None,
            "provider": None,
            "error": f"{type(exc).__name__}: {exc}",
            "duration_ms": int((monotonic() - mulai) * 1000),
        }
    return {
        "status": hasil.status,
        "teks": hasil.hypothesis,
        "provider": hasil.provider,
        "fallback_used": hasil.fallback_used,
        "ungrounded_numbers": list(hasil.ungrounded_numbers),
        "duration_ms": int((monotonic() - mulai) * 1000),
    }


def _attempt_dicts(attempts) -> list[dict]:
    return [
        {
            "name": getattr(a, "name", None),
            "outcome": getattr(a, "outcome", None),
            "category": getattr(a, "category", None),
        }
        for a in (attempts or [])
    ]


def _ringkas_tolak(kandidat: list[dict]) -> list[dict]:
    """Alasan pemasok tidak layak — dibawa ke pesan 409 supaya bisa dibuktikan."""
    return [
        {
            "supplier": k["supplier"],
            "excluded": k["excluded"],
            "reasons": k["reasons"],
        }
        for k in kandidat
        if not k["eligible"]
    ]


def _kalimat_tolak(ditolak: list[dict], batas_alasan: int = 2) -> str:
    """Alasan dalam kalimat yang bisa dibaca manusia (bukan repr list Python).

    Tetap menyebut sebab per pemasok: tanpa itu, pesan 409 hanya bilang
    "tidak ada" dan tidak bisa dibuktikan dari data.
    """
    bagian = []
    for baris in ditolak:
        alasan = "; ".join(baris["reasons"][:batas_alasan]) or "tidak tercatat"
        bagian.append(f"{baris['supplier']}: {alasan}")
    return "; ".join(bagian) if bagian else "tidak ada pemasok terdaftar"


async def _run_supplier_procurement(
    *,
    commodity: str,
    target_location: str,
    verifier_bedrock,
    ttl_minutes: int,
    demo_session_id: uuid.UUID | None = None,
    on_step: Callable[[_TraceStep], None] | None = None,
) -> dict:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    traces: list[_TraceStep] = []

    def _tambah(langkah: _TraceStep) -> None:
        """Simpan langkah DAN siarkan ke kanal kemajuan (29 Okt 2026).

        Langkah tetap dikumpulkan seperti sebelumnya; siaran hanya tambahan
        untuk log langsung di Demo Control. Kegagalan siaran tidak pernah
        menggagalkan putaran.
        """
        traces.append(langkah)
        if on_step is not None:
            try:
                on_step(langkah)
            except Exception:  # noqa: BLE001 — telemetri, bukan jalur data
                pass

    async with maker() as session:
        target = (
            await session.execute(
                select(Location).where(Location.name == target_location)
            )
        ).scalar_one_or_none()
        if target is None:
            raise ValueError(f"lokasi SPPG {target_location!r} tidak ada di database")

        komoditas = (
            await session.execute(
                select(Commodity).where(Commodity.name == commodity)
            )
        ).scalar_one_or_none()
        if komoditas is None:
            raise ValueError(f"komoditas {commodity!r} tidak ada di database")

        penilaian = await evaluate_suppliers(
            session, target=target, commodity=commodity
        )
        kandidat = penilaian["candidates"]
        chosen = penilaian["chosen"]
        if chosen is None:
            ditolak = _ringkas_tolak(kandidat)
            raise ValueError(
                "tidak ada pemasok yang memasok "
                f"{target_location} untuk {commodity} yang bisa dikirim sekarang "
                f"({len(kandidat)} pemasok dinilai, 0 layak). "
                f"Alasan: {_kalimat_tolak(ditolak)}"
            )

        # DETECT -----------------------------------------------------------
        detect = {
            "commodity": commodity,
            "target_location": target_location,
            "supply_kg": penilaian["supply_kg"],
            "demand_kg": penilaian["demand_kg"],
            "gap_kg": penilaian["gap_kg"],
            "suppliers_total": penilaian["suppliers_total"],
            "suppliers_eligible": len(penilaian["ranked"]),
            "suppliers_rejected": _ringkas_tolak(kandidat),
        }
        detect["narasi"] = _narasi("DETECT", dict(detect))
        _tambah(
            _TraceStep(
                "DETECT",
                "supply.get+demand.get+supplier.get",
                {"commodity": commodity, "target_location": target_location},
                detect,
                duration_ms=detect["narasi"]["duration_ms"],
            )
        )

        # VERIFY -----------------------------------------------------------
        ctx = {
            "decision_id": None,
            "commodity": commodity,
            "safety_status": chosen["safety_status"],
            "freshness_score": chosen["freshness_score"],
            "candidates": kandidat,
            "evidence": {
                "batch_ids": chosen["batch_ids"],
                "price_sources": ["pihps_reference", "supplier_quote"],
            },
            "logistics": {
                "distance_km": chosen["leg_km"],
                "time_min": None,
                "feasible": chosen["leg_km"] is not None,
            },
            "cost": {
                "safe_delivered_cost": chosen["safe_delivered_cost"],
                "breakdown": chosen["cost_breakdown"],
            },
            "rationale": (
                f"Pengadaan dari pemasok {chosen['supplier']} yang memasok "
                f"{target_location}: kekurangan {penilaian['gap_kg']} kg, "
                f"dipasok {chosen['quantity_kg']} kg"
            ),
        }
        verifier_result = run_verifier(ctx, bedrock=verifier_bedrock)
        verifier_payload = {
            "verdict": verifier_result.verdict,
            "reason": verifier_result.reason,
            "provider": verifier_result.provider,
            "fallback_used": verifier_result.fallback_used,
            "attempts": _attempt_dicts(verifier_result.attempts),
        }
        verifier_payload["narasi"] = _narasi("VERIFY", dict(verifier_payload))
        _tambah(
            _TraceStep(
                "VERIFY",
                "verifier.rest",
                {
                    "commodity": commodity,
                    "supplier": chosen["supplier"],
                    "safety_status": ctx["safety_status"],
                    "freshness_score": ctx["freshness_score"],
                },
                verifier_payload,
                duration_ms=verifier_payload["narasi"]["duration_ms"],
            )
        )

        # DECIDE: baris keputusan (id dipakai FK trace) ---------------------
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=ttl_minutes)
        # Status awal DITURUNKAN dari verdict verifier yang baru dihitung di
        # langkah VERIFY — bukan dari model, dan bukan `proposed` buta.
        #
        # Kenapa (regresi 28 Okt 2026): keputusan lahir `proposed` sementara
        # `verified_by`/`verifier_note` sudah terisi. Akibatnya `/actions/approve`
        # menolak ("status proposed tidak dapat di-approve") DAN `/actions/execute`
        # menolak ("status proposed tidak dapat dieksekusi") — satu-satunya jalan
        # keluar adalah memanggil `/actions/propose` lebih dulu, yang tidak
        # ditawarkan UI. Pemilik melihat "agent jalan tapi keputusannya tidak bisa
        # di-approve/execute".
        #
        # Aturannya sama dengan `/actions/verify` + `/actions/propose`:
        #   CONSISTENT → `pending_approval` (terverifikasi, siap disetujui)
        #   FLAGGED    → `verifier_flagged` (tetap boleh disetujui, dengan catatan)
        #   UNAVAILABLE→ tetap `proposed` (belum dinilai; verify masih boleh diulang)
        verdict = (verifier_result.verdict or "").upper()
        status_awal = {
            "CONSISTENT": "pending_approval",
            "FLAGGED": "verifier_flagged",
        }.get(verdict, "proposed")
        decision = Decision(
            id=uuid.uuid4(),
            decision_type="supplier_procurement",
            status=status_awal,
            proposed_by="supervisor_agent",
            verified_by="verifier_agent",
            verifier_note=verifier_result.verdict.lower(),
            # Baris ini lahir dari DEMO, bukan data kanonik: `origin='demo'`
            # adalah syarat yang membuat penjaga sesi (`boleh_distempel`,
            # `tandai_sesi`, `kosongkan_bertanda`) mau menghapusnya saat jendela
            # demo berakhir. Dengan default DB `'seed'`, keputusan hasil agent
            # hidup selamanya dan "data hilang saat demo habis" tidak terjadi.
            origin="demo",
            # Pengadaan tidak memindahkan stok SPPG lain: sisi asal = NULL.
            source_location_id=None,
            target_location_id=target.id,
            commodity_id=komoditas.id,
            supplier_id=uuid.UUID(chosen["supplier_id"]),
            quantity_kg=Decimal(str(chosen["quantity_kg"])),
            safe_delivered_cost=Decimal(str(chosen["safe_delivered_cost"])),
            cost_breakdown=chosen["cost_breakdown"],
            expires_at=expires_at,
            # Fase 2 MG: pemilik baris disebut pemanggil, bukan ditebak dari
            # "sesi aktif" oleh penjaga `before_flush`.
            demo_session_id=demo_session_id,
        )
        session.add(decision)
        await session.flush()

        await persist_supplier_binding(
            session,
            decision,
            supplier_id=chosen["supplier_id"],
            batch_ids=chosen["batch_ids"],
        )

        trace_out = {"steps_recorded": 6, "decision_id": str(decision.id)}
        trace_out["narasi"] = _narasi(
            "TRACE", {k: v for k, v in trace_out.items() if k != "decision_id"}
        )
        _tambah(
            _TraceStep(
                "TRACE",
                None,
                {"decision_id": str(decision.id)},
                trace_out,
                duration_ms=trace_out["narasi"]["duration_ms"],
            )
        )

        # PREDICT: satu pintu peramalan (jendela 28 hari, ambang minimum, cache).
        forecast = await forecast_kebutuhan(
            session,
            location_id=target.id,
            commodity_id=komoditas.id,
            horizon_days=FORECAST_HORIZON_DAYS,
        )
        predict_out = {
            "forecast_qty_kg": forecast.qty_kg,
            "method": forecast.method,
            "provider": forecast.source,
            "source": forecast.source,
            "fallback_used": forecast.fallback_used,
            "sample_count": forecast.sample_count,
            "cache_hit": forecast.cache_hit,
            "attempts": _attempt_dicts(forecast.attempts),
        }
        if forecast.qty_kg is None:
            predict_out["note"] = forecast.reason or "histori demand kosong; tanpa panggilan model"
        predict_out["narasi"] = _narasi("PREDICT", dict(predict_out))
        _tambah(
            _TraceStep(
                "PREDICT",
                "forecast.provider",
                {
                    "history_points": forecast.sample_count,
                    "horizon_days": FORECAST_HORIZON_DAYS,
                },
                predict_out,
                duration_ms=predict_out["narasi"]["duration_ms"],
            )
        )

        # OPTIMIZE (rekaman pemeringkatan pemasok deterministik) -----------
        optimize_out = {
            "chosen_supplier": chosen["supplier"],
            "chosen_supplier_id": chosen["supplier_id"],
            "rank": chosen["rank"],
            "score": chosen["score"],
            "safe_delivered_cost": chosen["safe_delivered_cost"],
            "leg_km": chosen["leg_km"],
            "available_kg": chosen["available_kg"],
            "quote_price_per_kg": chosen["quote_price_per_kg"],
            # Deviasi harga ikut dicatat sebagai fakta putaran supaya
            # angka yang dikutip narasi supervisor ("harga deviasi
            # -1,92%") punya sumber primer. Tanpa ini cek
            # `angka_bersitasi` menandainya tanpa sumber dan verdict
            # verifier jatuh ke `flagged` pada putaran yang sehat.
            "reference_price_per_kg": chosen.get("reference_price_per_kg"),
            "price_deviation_pct": chosen.get("price_deviation_pct"),
            "price_classification": chosen.get("price_classification"),
            "reliability": chosen["reliability"],
            "capacity_kg_per_week": chosen["capacity_kg_per_week"],
            "candidates_total": len(kandidat),
            "ranked": [
                {
                    "rank": r["rank"],
                    "supplier": r["supplier"],
                    "score": r["score"],
                    "safe_delivered_cost": r["safe_delivered_cost"],
                }
                for r in penilaian["ranked"]
            ],
        }
        optimize_out["narasi"] = _narasi(
            "OPTIMIZE", {k: v for k, v in optimize_out.items() if k != "chosen_supplier_id"}
        )
        _tambah(
            _TraceStep(
                "OPTIMIZE",
                "supplier.evaluate",
                {"commodity": commodity, "target_location": target_location},
                optimize_out,
                duration_ms=optimize_out["narasi"]["duration_ms"],
            )
        )

        # ANALYZE: hipotesis sebab + rekomendasi dari LLM ------------------
        # Fakta di bawah SUDAH dihitung kode (supply/demand/evaluate/forecast).
        # Model hanya menafsirkan: tidak diminta menghitung, dan angka baru yang
        # muncul ditandai `ungrounded` oleh `run_hypothesis` — bukan diterima.
        # Langkah ini advisory: verdict, status keputusan, dan angka tidak berubah.
        fakta_analisis = {
            "commodity": commodity,
            "target_location": target_location,
            "supply_kg": penilaian["supply_kg"],
            "demand_kg": penilaian["demand_kg"],
            "gap_kg": penilaian["gap_kg"],
            "chosen": {
                "supplier": chosen["supplier"],
                "available_kg": chosen["available_kg"],
                "quantity_kg": chosen["quantity_kg"],
                "leg_km": chosen["leg_km"],
                "quote_price_per_kg": chosen["quote_price_per_kg"],
                "reference_price_per_kg": chosen.get("reference_price_per_kg"),
                "price_deviation_pct": chosen.get("price_deviation_pct"),
                "safety_status": chosen["safety_status"],
                "freshness_score": chosen["freshness_score"],
            },
            "verifier_verdict": verifier_result.verdict,
            "forecast": {
                "forecast_qty_kg": predict_out.get("forecast_qty_kg"),
                "method": predict_out.get("method"),
                "horizon_days": FORECAST_HORIZON_DAYS,
            },
        }
        mulai_analisis = monotonic()
        try:
            hipotesis = run_hypothesis(fakta_analisis)
        except Exception as exc:  # noqa: BLE001 - analisis opsional, putaran tetap jalan
            hipotesis = None
            analisis_error = f"{type(exc).__name__}: {exc}"
        else:
            analisis_error = None
        durasi_analisis = int((monotonic() - mulai_analisis) * 1000)

        analisis_out = {
            "status": "error" if hipotesis is None else hipotesis.status,
            "hypothesis": None if hipotesis is None else hipotesis.hypothesis,
            "recommendation": None if hipotesis is None else hipotesis.recommendation,
            "confidence": None if hipotesis is None else hipotesis.confidence,
            "provider": None if hipotesis is None else hipotesis.provider,
            "fallback_used": None if hipotesis is None else hipotesis.fallback_used,
            "attempts": [] if hipotesis is None else _attempt_dicts(hipotesis.attempts),
            "ungrounded_numbers": (
                [] if hipotesis is None else list(hipotesis.ungrounded_numbers)
            ),
            "advisory": True,
        }
        if analisis_error:
            analisis_out["error"] = analisis_error
        _tambah(
            _TraceStep(
                "ANALYZE",
                "hypothesis.llm",
                {
                    "commodity": commodity,
                    "target_location": target_location,
                    "gap_kg": penilaian["gap_kg"],
                },
                analisis_out,
                duration_ms=durasi_analisis,
            )
        )

        # DECIDE (rekaman persist) -----------------------------------------
        decide_out = {
            "decision_id": str(decision.id),
            "expires_at": expires_at.isoformat(),
            "approved": False,
            "status": decision.status,
        }
        decide_out["narasi"] = _narasi(
            "DECIDE", {k: v for k, v in decide_out.items() if k != "decision_id"}
        )
        _tambah(
            _TraceStep(
                "DECIDE",
                "POST /decisions",
                {"status": decision.status, "ttl_minutes": ttl_minutes},
                decide_out,
                duration_ms=decide_out["narasi"]["duration_ms"],
            )
        )

        # SUPERVISE --------------------------------------------------------
        supervise_out = run_supervisor(
            {
                # Id keputusan WAJIB ikut: tool supervisor (`get_cost_eligibility`,
                # `get_evidence_digest`) hanya bisa dipanggil dengan id ini. Tanpa
                # id, agen menjawab "saya memerlukan decision_id" (terukur
                # 29 Okt 2026) sehingga tahap pengawasan tampak tidak membaca data.
                "decision_id": str(decision.id),
                "supplier_id": chosen["supplier_id"],
                "batch_ids": chosen["batch_ids"],
                "commodity": commodity,
                "target_location": target_location,
                "supplier": chosen["supplier"],
                "supplier_leg_km": chosen["leg_km"],
                "supplier_quote_per_kg": chosen["quote_price_per_kg"],
                "supplier_available_kg": chosen["available_kg"],
                "gap_kg": penilaian["gap_kg"],
                "verifier_verdict": verifier_result.verdict,
                "forecast": predict_out,
                "chosen": chosen,
            }
        )
        supervisor_payload = {
            "status": supervise_out.status,
            "summary": supervise_out.summary,
            "provider": supervise_out.provider,
            "fallback_used": supervise_out.fallback_used,
            "attempts": _attempt_dicts(supervise_out.attempts),
            "decision_id": str(decision.id),
        }
        # Tahap SUPERVISE SELALU dicatat. Dulu baris ini hanya ditulis bila
        # `status == "narrated"`, sehingga panel 10 tahap kehilangan satu tahap
        # tanpa jejak apa pun saat provider mati — pembaca tidak bisa membedakan
        # "tidak diawasi" dari "tidak pernah jalan". Kegagalan adalah fakta yang
        # harus tercatat, dan `status` di payload menyebutnya apa adanya.
        if supervise_out.status != "narrated":
            supervisor_payload["note"] = (
                "narasi tidak tersedia; tahap dicatat apa adanya tanpa mengarang "
                "ringkasan"
            )
        _tambah(
            _TraceStep(
                "SUPERVISE",
                (
                    "supervisor.narration"
                    if supervise_out.status == "narrated"
                    else f"supervisor.{supervise_out.status}"
                ),
                {"decision_id": str(decision.id)},
                supervisor_payload,
            )
        )

        # Jumlah langkah NYATA pada baris TRACE. Sebelumnya angka 6 ditulis
        # tangan padahal putaran ini menulis 9 langkah — angka jejak yang
        # dikarang membuat audit tidak bisa mempercayai kolom mana pun.
        for step in traces:
            if step.step_name == "TRACE" and isinstance(step.output_summary, dict):
                step.output_summary["steps_recorded"] = len(traces)

        for step in traces:
            persist_trace_steps(
                session,
                decision_id=str(decision.id),
                steps=[
                    {
                        "step_name": step.step_name,
                        "tool_called": step.tool_called,
                        "input_summary": step.input_summary,
                        "output_summary": step.output_summary,
                        "duration_ms": step.duration_ms,
                    }
                ],
            )

        await session.commit()

    return {
        "decision_id": str(decision.id),
        "mode": "supplier_procurement",
        "detect": detect,
        "verifier": verifier_payload,
        "forecast": predict_out,
        "supervisor": supervisor_payload,
        "suppliers": penilaian,
        "decision_snapshot": {
            "decision_id": str(decision.id),
            "status": decision.status,
            "approved": False,
            "expires_at": expires_at.isoformat(),
            "supplier": chosen["supplier"],
            "recommendation": chosen,
        },
        "trace_steps": [t.step_name for t in traces],
    }


def run_supplier_procurement(
    commodity: str,
    target_location: str,
    *,
    verifier_bedrock=None,
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
    demo_session_id: uuid.UUID | None = None,
    on_step: Callable[[_TraceStep], None] | None = None,
) -> dict:
    """Jalankan pengadaan pemasok penuh; sync wrapper di atas sesi async.

    `demo_session_id` (Fase 2 MG) = sesi PEMILIK keputusan yang lahir di sini.
    """
    return asyncio.run(
        _run_supplier_procurement(
            commodity=commodity,
            target_location=target_location,
            verifier_bedrock=verifier_bedrock,
            ttl_minutes=ttl_minutes,
            demo_session_id=demo_session_id,
            on_step=on_step,
        )
    )
