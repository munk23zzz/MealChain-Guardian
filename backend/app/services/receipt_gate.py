"""Gerbang penerimaan & karantina satu keputusan — dihitung SERVER.

Fase 9 MG poin 4: UI tidak boleh menyimpulkan sendiri kapan barang boleh
diterima atau ditahan. Kontrak `GET /decisions/{id}/approval-summary` sudah
membawa `can_approve`/`can_reject`/`can_execute`; modul ini menambah
`can_receive`/`can_quarantine` untuk batch yang SAMA-SAMA dinilai endpoint
penerimaan dan karantina.

Keputusan kontrak (pemilik produk, 27 Okt 2026): batch acuan = batch di lokasi
**TUJUAN** keputusan — barang diterima di dapur penerima, jadi batch sumber yang
dipakai `can_execute` bukan acuannya.

Tidak ada kebijakan baru di sini. Setiap alasan diturunkan dari pagar yang sudah
ditegakkan endpoint:

`can_receive` mencerminkan `POST /receipts/{id}/approve`: peran `sppg_head`,
batch di lokasi user, evaluator `usable`, ada catatan penerimaan `menunggu`.

`can_quarantine` mencerminkan `POST /batches/{id}/quarantine` (`aksi=tahan`):
peran SPPG (kepala/ahli gizi), lokasi batch = lokasi user, `boleh_ditahan`,
dan transisi `tahan` sah dari status karantina sekarang.

Alasan memakai KODE stabil (bukan kalimat) supaya UI bisa menerjemahkan satu
kali; kode evaluator (`safety_pending`, `quarantined`, …) dipakai apa adanya
dari `app.core.batch_eligibility` — bukan disalin.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.batch_eligibility import USABLE
from app.core.quarantine import AKSI_TAHAN, boleh_ditahan, status_setelah
from app.models import Batch, BatchReceipt, Decision
from app.services.batch_eligibility_service import evaluasi_batch, next_step

__all__ = [
    "KODE",
    "ROLE_PENERIMA",
    "ROLE_SPPG",
    "gerbang_penerimaan",
]

#: Satu-satunya peran yang boleh menyetujui penerimaan (`POST /receipts/{id}/approve`).
ROLE_PENERIMA = "sppg_head"

#: Peran SPPG pemilik lokasi batch yang boleh menahan/melepas karantina.
ROLE_SPPG = frozenset({"sppg_head", "sppg_nutritionist"})

#: Kode alasan gerbang ini. Kode evaluator batch TIDAK didaftar di sini —
#: nilainya dipakai langsung dari `app.core.batch_eligibility`.
KODE = {
    "viewer_unknown": "viewer_unknown",
    "role_not_head": "role_not_head",
    "role_not_sppg": "role_not_sppg",
    "out_of_scope": "out_of_scope",
    "receipt_missing": "receipt_missing",
    "receipt_already_decided": "receipt_already_decided",
    "safety_fail_not_quarantinable": "safety_fail_not_quarantinable",
    "safety_status_unknown": "safety_status_unknown",
    "quarantine_transition_invalid": "quarantine_transition_invalid",
    "no_batch": "no_batch",
}

#: Langkah berikutnya saat penerimaan hanya tertahan oleh catatan yang belum ada.
_LANGKAH_CATAT = "catat hasil terima petugas lalu setujui penerimaan"


def _alasan_karantina(batch: Batch, role: str | None, location_id) -> list[str]:
    """Alasan `POST /batches/{id}/quarantine (tahan)` akan menolak batch ini."""
    alasan: list[str] = []
    if role not in ROLE_SPPG:
        alasan.append(KODE["role_not_sppg"])
    if role in ROLE_SPPG and (not location_id or location_id != batch.location_id):
        alasan.append(KODE["out_of_scope"])
    try:
        boleh, _sebab = boleh_ditahan(batch.safety_status or "")
    except ValueError:
        # Status keamanan di luar daftar: karantina tidak boleh ditebak.
        alasan.append(KODE["safety_status_unknown"])
    else:
        if not boleh:
            alasan.append(KODE["safety_fail_not_quarantinable"])
    try:
        status_setelah(batch.quarantine_status or "none", AKSI_TAHAN)
    except ValueError:
        # Sudah `quarantined` atau `failed`: menahan lagi bukan transisi sah.
        alasan.append(KODE["quarantine_transition_invalid"])
    return alasan


def _alasan_penerimaan(
    batch: Batch,
    role: str | None,
    location_id,
    status_catatan: str | None,
    evaluasi,
) -> list[str]:
    """Alasan `POST /receipts/{id}/approve` akan menolak batch ini."""
    alasan: list[str] = []
    if role != ROLE_PENERIMA:
        alasan.append(KODE["role_not_head"])
    elif not location_id or location_id != batch.location_id:
        alasan.append(KODE["out_of_scope"])
    if evaluasi.status != USABLE:
        # `on_hold` dan `rejected` berbeda sebab — kode evaluator dipakai apa
        # adanya supaya UI membedakan "belum diuji" dari "gagal uji".
        alasan.extend(evaluasi.blocking_reasons or [])
    if status_catatan is None:
        alasan.append(KODE["receipt_missing"])
    elif status_catatan != "menunggu":
        alasan.append(KODE["receipt_already_decided"])
    return alasan


def _unik(daftar: list[str]) -> list[str]:
    """Urutan dipertahankan: alasan peran/cakupan lebih dulu, lalu sebab batch."""
    keluaran: list[str] = []
    for kode in daftar:
        if kode not in keluaran:
            keluaran.append(kode)
    return keluaran


async def gerbang_penerimaan(
    db: AsyncSession,
    decision: Decision,
    viewer_role: str | None,
    viewer_location_id: uuid.UUID | None,
    sekarang: datetime | None = None,
) -> dict:
    """Nilai satu keputusan: boleh diterima? boleh ditahan?

    `viewer_role=None` (pemanggil internal tanpa pembaca) menghasilkan
    `None` — bukan `False` — supaya laporan agent tidak mengklaim "tidak boleh"
    padahal perannya tidak diketahui.
    """
    kosong = {
        "location_id": None,
        "location_name": None,
        "batches": [],
        "can_receive": None if viewer_role is None else False,
        "can_quarantine": None if viewer_role is None else False,
        "receive_reasons": [KODE["viewer_unknown"]]
        if viewer_role is None
        else [KODE["no_batch"]],
        "quarantine_reasons": [KODE["viewer_unknown"]]
        if viewer_role is None
        else [KODE["no_batch"]],
        "next_step": None,
    }
    if decision.target_location_id is None or decision.commodity_id is None:
        return kosong

    batches = (
        (
            await db.execute(
                select(Batch).where(
                    Batch.location_id == decision.target_location_id,
                    Batch.commodity_id == decision.commodity_id,
                )
            )
        )
        .scalars()
        .all()
    )
    if not batches:
        # Barang belum ada di dapur penerima: tidak ada yang bisa diterima
        # maupun ditahan. Ini BUKAN kegagalan aplikasi.
        return kosong

    id_batch = [b.id for b in batches]
    status_catatan = {
        str(baris[0]): str(baris[1])
        for baris in (
            await db.execute(
                select(BatchReceipt.batch_id, BatchReceipt.status).where(
                    BatchReceipt.batch_id.in_(id_batch)
                )
            )
        ).all()
    }
    # Satu batch bisa punya beberapa catatan (riwayat); yang menentukan adalah
    # ada-tidaknya catatan `menunggu`. `_catatan` di bawah memilih yang itu.
    menunggu = {
        str(baris[0])
        for baris in (
            await db.execute(
                select(BatchReceipt.batch_id).where(
                    BatchReceipt.batch_id.in_(id_batch),
                    BatchReceipt.status == "menunggu",
                )
            )
        ).all()
    }
    saat = sekarang or datetime.now(UTC)

    baris_batch: list[dict] = []
    for batch in batches:
        kunci = str(batch.id)
        catatan = "menunggu" if kunci in menunggu else status_catatan.get(kunci)
        evaluasi = evaluasi_batch(batch, saat)
        terima_alasan = _alasan_penerimaan(
            batch, viewer_role, viewer_location_id, catatan, evaluasi
        )
        tahan_alasan = _alasan_karantina(batch, viewer_role, viewer_location_id)
        baris_batch.append(
            {
                "batch_id": kunci,
                "status": evaluasi.status,
                "can_receive": not terima_alasan if viewer_role else None,
                "can_quarantine": not tahan_alasan if viewer_role else None,
                "receive_reasons": _unik(terima_alasan),
                "quarantine_reasons": _unik(tahan_alasan),
            }
        )

    terima_semua = [k for b in baris_batch for k in b["receive_reasons"]]
    tahan_semua = [k for b in baris_batch for k in b["quarantine_reasons"]]

    langkah = next_step(evaluasi_batch(batches[0], saat))
    if langkah is None and any(
        KODE["receipt_missing"] in b["receive_reasons"] for b in baris_batch
    ):
        langkah = _LANGKAH_CATAT

    return {
        "location_id": str(decision.target_location_id),
        "location_name": None,  # nama lokasi bukan urusan gerbang ini (UI punya sendiri)
        "batches": baris_batch,
        "can_receive": None if viewer_role is None else any(
            b["can_receive"] for b in baris_batch
        ),
        "can_quarantine": None
        if viewer_role is None
        else any(b["can_quarantine"] for b in baris_batch),
        "receive_reasons": _unik(terima_semua)
        if viewer_role is not None
        else [KODE["viewer_unknown"]],
        "quarantine_reasons": _unik(tahan_semua)
        if viewer_role is not None
        else [KODE["viewer_unknown"]],
        "next_step": langkah,
    }
