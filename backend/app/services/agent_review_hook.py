"""Kait review agent setelah keputusan dibuat — satu tempat, dua jalur.

Kenapa modul ini ada
--------------------
Logikanya dulu tinggal di `api/demo.py` dan hanya dipanggil `POST /demo/event1`.
Keputusan yang lahir dari `POST /decisions` (jalur yang dipakai konsol operator
lewat `createDecision`) tidak pernah direview agent sama sekali. Modul ini
memindahkan logika itu ke lapisan service supaya kedua jalur memakai perilaku
yang sama.

Batas yang tetap berlaku
------------------------
- Review bersifat **advisory**: ia menambah baris jejak (7 worker + verifier +
  SUPERVISE) dan tidak pernah mengubah status, angka, atau keamanan keputusan.
- Kegagalan/timeout review **tidak** membatalkan keputusan. Kegagalan dicatat
  jujur sebagai satu baris SUPERVISE, bukan tujuh baris palsu.
- Mati secara default (`MULTI_AGENT_REVIEW`); menyalakannya berarti setiap
  keputusan memicu panggilan model — biaya dan latensi nyata.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import issue_token_for_user
from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.models import AgentTrace, Decision, User
from app.services import agent_review_local
from app.services.agent_review_client import AgentReviewResult, review_decision
from app.services.trace_persistence import persist_agent_review

#: Status yang dipakai saat review dijadwalkan di latar belakang.
STATUS_ANTRE = "queued"


async def jalankan_agent_review(
    db: AsyncSession, outcome: dict, *, user: User | None = None
) -> dict[str, Any]:
    """Review satu keputusan dan simpan jejaknya. Tidak pernah melempar.

    `outcome` memuat `decision_id` (kontrak lama dari `POST /demo/event1`).
    """
    disabled = {"status": "disabled", "run_id": None}
    if not settings.multi_agent_review:
        return disabled

    decision_id = outcome.get("decision_id")
    if not isinstance(decision_id, str) or not decision_id.strip():
        return {"status": "failed", "run_id": None}

    jalur = agent_review_local.transport(settings.agent_review_mode)
    if jalur == "local":
        # Review lokal membaca API dengan identitas PEMANGGIL (bukan token
        # layanan berumur panjang): cakupan peran tetap ditegakkan endpoint.
        if user is None:
            result = AgentReviewResult(
                status="unavailable",
                error="user pemanggil tidak tersedia untuk token review lokal",
            )
        else:
            try:
                token = issue_token_for_user(user)
            except Exception as exc:  # noqa: BLE001 - JWT_SECRET hilang dsb.
                result = AgentReviewResult(
                    status="unavailable",
                    error=f"token review lokal gagal dibuat: {type(exc).__name__}",
                )
            else:
                # Model berlatensi detik (verifier memanggilnya sekali); beri
                # anggaran lebih lega daripada jalur runtime, tetap berbatas.
                anggaran = float(min(max(settings.agent_review_timeout_seconds, 30), 120))
                result = await run_in_threadpool(
                    agent_review_local.review_decision_local,
                    decision_id,
                    token=token,
                    mode=settings.agent_review_mode,
                    timeout_seconds=anggaran,
                )
    else:
        timeout = float(min(max(settings.agent_review_timeout_seconds, 1), 45))
        try:
            result = await run_in_threadpool(
                review_decision, decision_id, timeout_seconds=timeout
            )
        except Exception:
            result = AgentReviewResult(status="failed", error="review client gagal")

    if not isinstance(result, AgentReviewResult):
        result = AgentReviewResult(status="failed", error="review client tidak valid")

    if result.completed:
        # P5: simpan 7 baris worker + verifier + SUPERVISE agar Agent Log bisa
        # menampilkan satu putaran review. Payload tidak lengkap → catat gagal,
        # jangan menulis baris yang tidak berasal dari runtime.
        await _catat_review_sukses(db, decision_id, result)
    else:
        # Kegagalan/timeout dicatat jujur sebagai SUPERVISE; tidak ada 7 row palsu.
        await _catat_review_gagal(db, decision_id, result)

    return {"status": result.status, "run_id": result.run_id}


async def _catat_review_sukses(
    db: AsyncSession, decision_id: str, result: AgentReviewResult
) -> None:
    """Persist 9 baris review (7 worker + verifier + SUPERVISE) atau 8 dari runtime lama.

    Kegagalan penyimpanan tidak membatalkan keputusan.
    """
    rows = (result.payload or {}).get("trace_rows")
    if not isinstance(rows, list) or len(rows) not in (8, 9):
        await _catat_review_gagal(
            db,
            decision_id,
            AgentReviewResult(
                status="failed",
                run_id=result.run_id,
                error="payload trace review tidak lengkap (wajib 9 baris)",
            ),
        )
        return
    try:
        await persist_agent_review(db, decision_id=decision_id, trace_rows=rows)
        await db.commit()
    except Exception as exc:
        try:
            await db.rollback()
        except Exception:
            pass
        await _catat_review_gagal(
            db,
            decision_id,
            AgentReviewResult(
                status="failed",
                run_id=result.run_id,
                error=f"trace review gagal disimpan: {type(exc).__name__}",
            ),
        )


async def _catat_review_gagal(
    db: AsyncSession, decision_id: str, result: AgentReviewResult
) -> None:
    """Tulis satu baris SUPERVISE best-effort; keputusan tetap ada."""
    try:
        decision_uuid = uuid.UUID(decision_id)
        if await db.get(Decision, decision_uuid) is None:
            return
        db.add(
            AgentTrace(
                decision_id=decision_uuid,
                step_name="SUPERVISE",
                tool_called="agent.review",
                input_summary={"task": "review_decision"},
                output_summary={
                    "status": result.status,
                    "run_id": result.run_id,
                    "error": result.error,
                },
            )
        )
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass


def jadwalkan_review_latar(
    background: BackgroundTasks, decision_id: str, user: User | None
) -> None:
    """Jadwalkan review SETELAH respons dikirim (agar 201 tidak menunggu model).

    Dipakai `POST /decisions`: konsol operator tidak boleh menggantung sampai
    puluhan detik hanya untuk jejak review. Tugas latar membuka sesi DB sendiri
    karena sesi permintaan sudah ditutup saat ia berjalan.
    """
    if not settings.multi_agent_review:
        return
    background.add_task(_review_latar, decision_id, user)


async def _review_latar(decision_id: str, user: User | None) -> None:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as sesi:
            await jalankan_agent_review(sesi, {"decision_id": decision_id}, user=user)
    except Exception:
        # Review latar tidak boleh menjatuhkan proses; kegagalannya sudah
        # dicatat (atau tidak ada keputusan untuk dicatat) di dalam.
        pass
    finally:
        await engine.dispose()
