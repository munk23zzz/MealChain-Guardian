"""S4-03 + periode server: GET /kpi — agregasi KPI read-only (plan §11 baris KPI).

Kontrak:
- Pilih SALAH SATU: `periode=today|7d|1bulan` (dihitung SERVER, hari kalender
  Asia/Jakarta) ATAU `start`+`end` RFC3339 eksplisit.
- Optional location_id UUID.
- Omit scope = own location untuk SPPG, global untuk bgn_monitor.
- Max range 366 hari; invalid range/naive time 422; foreign scope 403.
- 200 envelope: period (key/label/timezone/start/end), scope, computed_at,
  data_source, metrics (tepat tujuh entri dari kpi_service). Read murni.

Periode dihitung di sini, bukan di klien: satu tombol "hari ini" harus berarti
satu rentang yang sama untuk semua kartu. Client hanya mengirim kunci periode.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.kpi_period import LABEL_PERIODE, PERIODE_KPI, ZONA_KPI, resolve_periode
from app.db import get_db
from app.models import User
from app.models.demo_sessions import DemoSession
from app.services.kpi_service import METHOD_VERSION, compute_kpis

router = APIRouter(prefix="", tags=["kpi"])

MAX_RANGE_DAYS = 366


@router.get("/kpi")
async def get_kpi(
    periode: str | None = Query(
        None,
        description=(
            "Kunci periode yang dihitung server (Asia/Jakarta): "
            + " | ".join(PERIODE_KPI)
            + ". Tidak boleh dikirim bersama start/end."
        ),
    ),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    location_id: uuid.UUID | None = Query(None),
    include_demo: bool = Query(
        False,
        description=(
            "Cakupan data. false (bawaan) = fakta operasional saja "
            "(demo_session_id IS NULL). true = satu sesi demo, WAJIB disertai "
            "demo_session_id (tanpa itu 422)."
        ),
    ),
    demo_session_id: uuid.UUID | None = Query(
        None,
        description="Sesi demo eksplisit yang diminta. Tidak ada jalur 'sesi terbaru'.",
    ),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """KPI tujuh metrik, state available/no_data/unavailable + reason.

    SPPG hanya scope lokasinya (403 foreign); bgn_monitor global atau
    lokasi mana pun (read-only). Naive timestamp ditolak 422 (kontrak
    RFC3339 dengan offset eksplisit).

    Cakupan (Fase 8): angka operasional dan angka sesi demo TIDAK boleh
    tercampur. `include_demo=false` menyaring `demo_session_id IS NULL`;
    `include_demo=true` menyaring SATU sesi yang disebut pemanggil. Kombinasi
    yang tidak masuk akal (demo tanpa sesi, atau sesi tanpa include_demo)
    ditolak 422 — menebak berarti menyajikan angka milik sesi lain.
    """
    kunci: str | None = None
    label: str | None = None

    if periode is not None:
        if start is not None or end is not None:
            raise HTTPException(
                status_code=422,
                detail="kirim periode ATAU start+end, bukan keduanya",
            )
        if periode not in PERIODE_KPI:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"periode tidak dikenal: {periode!r}; pilihan: "
                    + ", ".join(PERIODE_KPI)
                ),
            )
        start, end = resolve_periode(periode, datetime.now(timezone.utc))
        kunci, label = periode, LABEL_PERIODE[periode]
    else:
        if start is None or end is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "wajib mengirim periode=("
                    + "|".join(PERIODE_KPI)
                    + "), atau start dan end sekaligus"
                ),
            )
        if start.tzinfo is None or end.tzinfo is None:
            raise HTTPException(
                status_code=422,
                detail="start/end wajib RFC3339 dengan offset zona waktu",
            )
        if start >= end:
            raise HTTPException(status_code=422, detail="start harus < end")
        if (end - start).days > MAX_RANGE_DAYS:
            raise HTTPException(
                status_code=422,
                detail=f"rentang maksimum {MAX_RANGE_DAYS} hari",
            )

    # Cakupan data (Fase 8): dua kombinasi tidak masuk akal dan ditolak di sini,
    # bukan dibiarkan lolos. `compute_kpis` sudah menolak demo tanpa sesi dengan
    # ValueError, tetapi tanpa penjagaan ini nilainya keluar sebagai 500 (galat
    # server) — bukan penolakan yang bisa diperbaiki pemanggil. Sesi tanpa
    # `include_demo` dulu diabaikan diam-diam dan dijawab 200 cakupan
    # operasional: pemanggil mengira ia melihat sesi yang ia sebut.
    if include_demo and demo_session_id is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "include_demo=true wajib menyertakan demo_session_id eksplisit; "
                "tidak ada jalur 'sesi terbaru'"
            ),
        )
    if demo_session_id is not None and not include_demo:
        raise HTTPException(
            status_code=422,
            detail=(
                "demo_session_id hanya berlaku bersama include_demo=true; "
                "tanpa itu jawabannya cakupan operasional"
            ),
        )

    scope = str(user.location_id) if user.location_id else None
    if user.role == "bgn_monitor":
        scope = str(location_id) if location_id else None  # global bila omit
    else:
        if location_id is not None and str(location_id) != scope:
            raise HTTPException(
                status_code=403, detail="scope lokasi di luar otoritas Anda"
            )
        if scope is None:
            raise HTTPException(
                status_code=403,
                detail="user belum terikat lokasi — tidak bisa membaca KPI",
            )
        location_id = user.location_id

    metrics = await compute_kpis(
        db,
        start,
        end,
        location_id,
        include_demo=include_demo,
        demo_session_id=demo_session_id,
    )
    # Fase 10 MG: jawaban ini WAJIB menyebut waktu acuan dataset yang dipakai.
    # Tanpa jangkar, "hari ini" pada angka simulasi tidak bisa dibedakan dari
    # "hari ini" pada data lapangan — dan Joule akan menuliskannya sebagai satu
    # kalimat sumber yang menyesatkan.
    sesi = None
    if include_demo and demo_session_id is not None:
        baris = await db.get(DemoSession, demo_session_id)
        if baris is not None:
            sesi = {
                "id": str(baris.id),
                "mode": baris.mode,
                "evaluation_anchor": baris.evaluation_anchor.isoformat(),
                "dataset_version": baris.dataset_version,
            }
    return {
        "period": {
            "key": kunci,
            "label": label,
            "timezone": str(ZONA_KPI),
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "scope": {
            "location_id": str(location_id) if location_id else None,
            "role": user.role,
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "data_source": "live_aggregate",
        # Cakupan yang BENAR-BENAR dipakai jawaban ini (bukan yang diminta UI):
        # tanpa ini, layar tidak bisa membedakan angka operasional dari angka
        # sesi demo hanya dengan melihat nilainya.
        "data_mode": "demo" if include_demo else "operational",
        "demo_session_id": str(demo_session_id) if include_demo and demo_session_id else None,
        # Sesi yang BENAR-BENAR dipakai: mode + jangkar evaluasi (Fase 10 MG).
        "demo_session": sesi,
        "method_version": METHOD_VERSION,
        "metrics": metrics,
    }
