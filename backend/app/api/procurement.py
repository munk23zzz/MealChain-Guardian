"""GET /procurement/summary — angka pengadaan untuk tile Overview (read-only).

Kenapa endpoint ini ada (laporan pemilik 27 Okt 2026: "setelah pengadaan
dieksekusi, Overview tidak berubah"). Pengukuran sebelum/sesudah satu siklus
approve+execute pada basis data demo menunjukkan eksekusi memang mengubah tiga
tabel — `decisions.status='executed'`, satu baris `sap_mock_purchase_orders`
(Rp 9.750.000), satu jejak `agent_traces` step `ACT`, dan blok ledger — TETAPI
Overview tidak punya satu pun kartu yang membaca ketiganya. Tiga kartu yang ada
membaca pasokan/kebutuhan, yang memang TIDAK berubah saat execute: stok baru
bertambah ketika penerimaan disetujui (`POST /receipts/{id}/approve`). Satu-
satunya angka Overview yang bergerak adalah hitungan antrean keputusan.

Jadi endpoint ini menjawab satu pertanyaan yang bisa diaudit: "pada periode ini,
berapa PO yang benar-benar terbit, berapa nilainya, berapa keputusan yang
dieksekusi, dan berapa batch yang diberangkatkan?" — dihitung dari tabelnya
langsung, bukan proksi, dan dengan periode yang dihitung server.

Kontrak:
- Pilih SALAH SATU: `periode=today|7d|1bulan` (hari kalender Asia/Jakarta, sama
  persis dengan `GET /kpi`) ATAU `start`+`end` RFC3339 eksplisit.
- Optional `location_id` UUID (hanya `bgn_monitor` yang boleh lintas lokasi).
- Omit scope = own location untuk SPPG, global untuk bgn_monitor.
- PO/ACT/batch dihitung pada `[start, end]` inklusif, memakai waktu kejadian
  masing-masing: `po.created_at`, `agent_traces.step_at` (step ACT),
  `batches.dispatched_at`.
- Cakupan PO mengikuti `decisions.target_location_id` (sasaran pengadaan);
  cakupan batch mengikuti `batches.location_id` (sisi tujuan kiriman).
- TIDAK menyaring `sap_mock_purchase_orders.origin`: baris yang ditulis jalur
  eksekusi memakai default `seed` (CHECK hanya mengizinkan seed|demo), jadi
  filter origin akan menyembunyikan PO yang justru baru terbit.
"""

import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.kpi_period import LABEL_PERIODE, PERIODE_KPI, ZONA_KPI, resolve_periode
from app.db import get_db
from app.models import User

router = APIRouter(prefix="", tags=["procurement"])

MAX_RANGE_DAYS = 366

_SQL_PO = (
    "SELECT po.status AS status, COUNT(*) AS jumlah, "
    "COALESCE(SUM(po.price * po.ordered_quantity), 0) AS nilai "
    "FROM sap_mock_purchase_orders po "
    "LEFT JOIN decisions d ON d.id = po.decision_id "
    "WHERE po.created_at >= :start AND po.created_at <= :end "
)

_SQL_PO_LAST = (
    "SELECT po.po_number, po.status, po.created_at, "
    "(po.price * po.ordered_quantity) AS nilai "
    "FROM sap_mock_purchase_orders po "
    "LEFT JOIN decisions d ON d.id = po.decision_id "
    "WHERE po.created_at >= :start AND po.created_at <= :end "
)

_SQL_ACT = (
    "SELECT COUNT(DISTINCT t.decision_id) AS jumlah, MAX(t.step_at) AS terakhir "
    "FROM agent_traces t "
    "JOIN decisions d ON d.id = t.decision_id "
    "WHERE t.step_name = 'ACT' AND t.step_at >= :start AND t.step_at <= :end "
)

_SQL_BATCH = (
    "SELECT COUNT(*) AS jumlah, MAX(b.dispatched_at) AS terakhir "
    "FROM batches b "
    "WHERE b.dispatched_at IS NOT NULL "
    "AND b.dispatched_at >= :start AND b.dispatched_at <= :end "
)

#: Kg yang benar-benar masuk gudang: penerimaan `disetujui` pada periode itu.
#: Kg diambil dari `batches.quantity_kg` — `batch_receipts` tidak menyimpan kg.
_SQL_RECEIPT = (
    "SELECT COUNT(*) AS jumlah, COALESCE(SUM(b.quantity_kg), 0) AS kg, "
    "MAX(r.reviewed_at) AS terakhir "
    "FROM batch_receipts r "
    "JOIN batches b ON b.id = r.batch_id "
    "WHERE r.status = 'disetujui' "
    "AND r.reviewed_at >= :start AND r.reviewed_at <= :end "
)

_SQL_RECEIPT_LAST = (
    "SELECT b.quantity_kg AS kg, r.reviewed_at "
    "FROM batch_receipts r "
    "JOIN batches b ON b.id = r.batch_id "
    "WHERE r.status = 'disetujui' "
    "AND r.reviewed_at >= :start AND r.reviewed_at <= :end "
)


def _periode(
    periode: str | None, start: datetime | None, end: datetime | None
) -> tuple[datetime, datetime, str | None, str | None]:
    """Rentang [start, end] + kunci/label — satu aturan dengan `GET /kpi`."""
    if periode is not None:
        if start is not None or end is not None:
            raise HTTPException(
                status_code=422, detail="kirim periode ATAU start+end, bukan keduanya"
            )
        if periode not in PERIODE_KPI:
            raise HTTPException(
                status_code=422,
                detail=f"periode tidak dikenal: {periode!r}; pilihan: "
                + ", ".join(PERIODE_KPI),
            )
        start, end = resolve_periode(periode, datetime.now(timezone.utc))
        return start, end, periode, LABEL_PERIODE[periode]

    if start is None or end is None:
        raise HTTPException(
            status_code=422,
            detail="wajib mengirim periode=(" + "|".join(PERIODE_KPI) + "), "
            "atau start dan end sekaligus",
        )
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(
            status_code=422, detail="start/end wajib RFC3339 dengan offset zona waktu"
        )
    if start >= end:
        raise HTTPException(status_code=422, detail="start harus < end")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=422, detail=f"rentang maksimum {MAX_RANGE_DAYS} hari"
        )
    return start, end, None, None


def _cakupan(user: User, location_id: uuid.UUID | None) -> str | None:
    """Lokasi yang boleh dibaca; 403 bila SPPG meminta lokasi lain."""
    scope = str(user.location_id) if user.location_id else None
    if user.role == "bgn_monitor":
        return str(location_id) if location_id else None
    if location_id is not None and str(location_id) != scope:
        raise HTTPException(status_code=403, detail="scope lokasi di luar otoritas Anda")
    if scope is None:
        raise HTTPException(
            status_code=403, detail="user belum terikat lokasi — tidak bisa membaca"
        )
    return scope


@router.get("/procurement/summary")
async def get_procurement_summary(
    periode: str | None = Query(
        None,
        description="today | 7d | 1bulan (hari kalender Asia/Jakarta). "
        "Tidak boleh dikirim bersama start/end.",
    ),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    location_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """PO terbit, keputusan dieksekusi, dan batch berangkat pada satu periode."""
    mulai, akhir, kunci, label = _periode(periode, start, end)
    lokasi = _cakupan(user, location_id)

    # Cakupan PO/ACT memakai `decisions.target_location_id`; cakupan batch
    # memakai `batches.location_id`. Keduanya NULL-able → parameter hanya
    # ditambahkan bila memang ada lokasi, supaya tidak ada perbandingan NULL.
    syarat_po = "AND d.target_location_id = :loc " if lokasi else ""
    syarat_batch = "AND b.location_id = :loc " if lokasi else ""
    params: dict = {"start": mulai, "end": akhir}
    if lokasi:
        params["loc"] = lokasi

    baris_po = (
        await db.execute(text(_SQL_PO + syarat_po + "GROUP BY po.status"), params)
    ).mappings().all()
    by_status = {"draft": 0, "submitted": 0, "confirmed": 0}
    jumlah_po = 0
    # Decimal, bukan float: audit 28 Okt 2026 menemukan /procurement/summary
    # menjumlah 5 PO yang sama menjadi 100.050.435.184,00 sementara
    # /sap/purchase-orders/summary (jalur yang memakai Decimal) memberi ,01.
    # Penyebabnya akumulasi float + pembulatan banker's pada f"{x:.2f}".
    nilai_po = Decimal("0")
    # "Terbit" = sudah dikirim ke SAP (submitted/confirmed). Draf belum terbit,
    # jadi tidak boleh ikut angka komitmen: audit 28 Okt 2026 menemukan tile
    # "PO terbit" menghitung 5 PO padahal 2 masih draf, dan 99,95% rupiahnya
    # satu fixture draf (MC-EXTREME01, sengaja dibuat untuk uji format angka).
    status_terbit = ("submitted", "confirmed")
    draf_jumlah = 0
    draf_nilai = Decimal("0")
    for row in baris_po:
        status = str(row["status"])
        by_status[status] = int(row["jumlah"])
        if status in status_terbit:
            jumlah_po += int(row["jumlah"])
            nilai_po += Decimal(str(row["nilai"] or 0))
        elif status == "draft":
            draf_jumlah += int(row["jumlah"])
            draf_nilai += Decimal(str(row["nilai"] or 0))

    po_terakhir = (
        await db.execute(
            text(
                _SQL_PO_LAST
                + syarat_po
                + "ORDER BY po.created_at DESC, po.po_number ASC LIMIT 1"
            ),
            params,
        )
    ).mappings().first()

    act = (
        await db.execute(
            text(
                _SQL_ACT
                + ("AND d.target_location_id = :loc " if lokasi else "")
            ),
            params,
        )
    ).mappings().first()

    batch = (
        await db.execute(text(_SQL_BATCH + syarat_batch), params)
    ).mappings().first()

    syarat_terima = "AND b.location_id = :loc " if lokasi else ""
    terima = (
        await db.execute(text(_SQL_RECEIPT + syarat_terima), params)
    ).mappings().first()
    terima_terakhir = (
        await db.execute(
            text(_SQL_RECEIPT_LAST + syarat_terima + "ORDER BY r.reviewed_at DESC LIMIT 1"),
            params,
        )
    ).mappings().first()

    def _angka(nilai) -> str:
        """Desimal apa adanya, dua angka di belakang koma — tanpa float.

        ROUND_HALF_UP dipilih agar angka di layar sama dengan
        `/sap/purchase-orders/summary` untuk baris yang sama (audit 28 Okt 2026:
        f"{x:.2f}" membulatkan 100.050.435.184,005 ke bawah).
        """
        return f"{Decimal(str(nilai)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"

    return {
        "period": {
            "key": kunci,
            "label": label,
            "timezone": str(ZONA_KPI),
            "start": mulai.isoformat(),
            "end": akhir.isoformat(),
        },
        "scope": {"location_id": lokasi, "role": user.role},
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "data_source": "live_aggregate",
        "purchase_orders": {
            "state": "available",
            "count": jumlah_po,
            "total_value": _angka(nilai_po),
            "currency": "IDR",
            "by_status": by_status,
            # Draf dilaporkan terpisah, bukan disembunyikan: operator tetap
            # melihat ada 2 PO menunggu kirim, tapi tidak dihitung sebagai
            # komitmen hari ini.
            "drafts": {"count": draf_jumlah, "total_value": _angka(draf_nilai)},
            "last": (
                {
                    "po_number": po_terakhir["po_number"],
                    "status": po_terakhir["status"],
                    "created_at": po_terakhir["created_at"].isoformat(),
                    "value": _angka(po_terakhir["nilai"]),
                }
                if po_terakhir
                else None
            ),
        },
        "decisions_executed": {
            "state": "available",
            "count": int(act["jumlah"]) if act else 0,
            "last_step_at": (
                act["terakhir"].isoformat() if act and act["terakhir"] else None
            ),
        },
        "batches_dispatched": {
            "state": "available",
            "count": int(batch["jumlah"]) if batch else 0,
            "last_dispatched_at": (
                batch["terakhir"].isoformat() if batch and batch["terakhir"] else None
            ),
        },
        # Kg yang benar-benar masuk gudang pada periode ini. Inilah angka yang
        # bergerak SETELAH penerimaan disetujui — eksekusi hanya menerbitkan PO.
        "receipts": {
            "state": "available",
            "count": int(terima["jumlah"]) if terima else 0,
            "kg": _angka(terima["kg"]) if terima else "0.00",
            "unit": "kg",
            "last": (
                {
                    "kg": _angka(terima_terakhir["kg"]),
                    "reviewed_at": terima_terakhir["reviewed_at"].isoformat(),
                }
                if terima_terakhir
                else None
            ),
        },
    }
