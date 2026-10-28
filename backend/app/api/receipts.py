"""Router catatan penerimaan barang (migrasi 016 + keputusan 026).

Dua lapis yang sengaja dipisah:

1. **Mencatat** (`POST /receipts`) — petugas dapur menulis apa yang benar-benar
   ia periksa saat barang datang, termasuk keadaan di luar daftar ("Lainnya").
   Catatan lahir berstatus `menunggu`: belum menambah stok apa pun.
2. **Memutuskan** (`POST /receipts/{id}/approve` / `.../reject`) — kepala SPPG
   menyetujui atau menolak. Persetujuan adalah satu-satunya jalur yang menulis
   `supply_records` (source `manual`), sehingga angka Overview/Hari Ini berubah
   karena keputusan itu — bukan karena layar menghitung sendiri.

Aturan yang ditegakkan di sini:
- hanya `sppg_head` yang memutuskan; pencatat boleh kepala maupun ahli gizi;
- batch harus di lokasi sendiri (scope, ruling 2026-10-14);
- kelayakan batch dinilai SATU evaluator (`app.core.batch_eligibility`), bukan
  aturan lokal berkas ini (Fase 4 MG poin 5). Pencatatan ditolak untuk batch
  `rejected`/`quarantined`; batch `on_hold` TETAP dicatat karena ceklis petugas
  adalah bukti untuk verifikasi lanjutan. Persetujuan hanya untuk `usable`,
  sehingga stok tidak pernah bertambah dari barang yang gagal/belum terbukti
  aman;
- status `batches.safety_status` TIDAK PERNAH diubah oleh endpoint di sini —
  tombol manusia bukan pengganti hasil uji laboratorium;
- satu batch paling banyak satu penerimaan disetujui (unique index parsial 026),
  jadi klik ganda tidak menggandakan stok.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.auth import MUTATING_ROLES, get_current_user, require_roles
from app.api.demo_session import butuh_sesi_aktif
from app.api.dependencies import get_db
from app.core.batch_eligibility import USABLE
from app.core.scope import assert_in_scope
from app.models import Batch, BatchReceipt, Commodity, Location, SupplyRecord, User
from app.services import receipt_value, settlement
from app.services.batch_eligibility_service import (
    BOLEH_DICATAT,
    evaluasi_batch,
    pesan_tolak,
)
from app.services.demo_session import sesi_sekarang

router = APIRouter()

#: Batas kewarasan untuk snapshot yang dikirim klien (id titik periksa hidup di
#: lapisan UI; backend menyimpannya apa adanya tetapi tidak mau menerima apa pun
#: tanpa batas).
MAX_CHECKED_KEYS = 20
MAX_KEY_LENGTH = 40
NOTE_MAX = 500
REJECT_MIN = 3


class ReceiptRequest(BaseModel):
    batch_id: uuid.UUID
    #: Snapshot titik periksa: {"kemasan": true, "suhu": false, ...}.
    checked: dict[str, bool] = Field(default_factory=dict)
    #: Isian "Lainnya" — keadaan yang tidak ada di daftar periksa.
    other_note: str | None = Field(default=None, max_length=NOTE_MAX)

    @field_validator("checked")
    @classmethod
    def _batas_kewarasan(cls, nilai: dict[str, bool]) -> dict[str, bool]:
        if len(nilai) > MAX_CHECKED_KEYS:
            raise ValueError(f"terlalu banyak titik periksa (maks {MAX_CHECKED_KEYS})")
        if any(len(kunci) > MAX_KEY_LENGTH for kunci in nilai):
            raise ValueError(f"nama titik periksa terlalu panjang (maks {MAX_KEY_LENGTH})")
        if any(not kunci.strip() for kunci in nilai):
            raise ValueError("nama titik periksa tidak boleh kosong")
        return nilai


class RejectRequest(BaseModel):
    #: Alasan penolakan — wajib, karena petugas harus tahu apa yang harus
    #: diperbaiki. Spasi saja tidak dianggap alasan.
    note: str = Field(min_length=REJECT_MIN, max_length=NOTE_MAX)


def _row(
    receipt: BatchReceipt,
    nama: str | None = None,
    pemeriksa: str | None = None,
    kg: float | None = None,
    nilai: float | None = None,
) -> dict:
    """Bentuk balasan yang stabil untuk UI (jumlah titik dihitung SERVER)."""
    dicek = receipt.checked or {}
    return {
        "id": str(receipt.id),
        "batch_id": str(receipt.batch_id),
        "checked": {str(k): bool(v) for k, v in dicek.items()},
        "checked_count": sum(1 for nilai in dicek.values() if nilai is True),
        "other_note": receipt.other_note,
        "recorded_by": str(receipt.recorded_by),
        "recorded_by_name": nama,
        "recorded_at": receipt.recorded_at.isoformat(),
        # ---- keputusan (026) ----
        "status": receipt.status,
        "reviewed_by": str(receipt.reviewed_by) if receipt.reviewed_by else None,
        "reviewed_by_name": pemeriksa,
        "reviewed_at": receipt.reviewed_at.isoformat() if receipt.reviewed_at else None,
        "review_note": receipt.review_note,
        "supply_record_id": (
            str(receipt.supply_record_id) if receipt.supply_record_id else None
        ),
        #: Nilai rupiah barang yang diterima menurut HARGA INVOICE PO (Fase 5).
        #: None = batch tanpa ikatan bukti/PO ("tidak tercatat"), beda dari 0.
        "accepted_value_idr": nilai if receipt.status == "disetujui" else None,
        #: Kg yang masuk stok karena persetujuan ini (None bila belum disetujui).
        "stock_kg": kg if receipt.status == "disetujui" else None,
    }


async def _nama(db: AsyncSession, user_id: uuid.UUID | None) -> str | None:
    if user_id is None:
        return None
    return (
        await db.execute(select(User.name).where(User.id == user_id))
    ).scalar_one_or_none()


async def _receipt_atau_404(db: AsyncSession, receipt_id: uuid.UUID) -> BatchReceipt:
    receipt = await db.get(BatchReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="catatan penerimaan tidak ditemukan")
    return receipt


async def _batch_atau_404(db: AsyncSession, batch_id: uuid.UUID) -> Batch:
    batch = await db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch tidak ditemukan")
    return batch


@router.post("/receipts", status_code=201)
async def create_receipt(
    payload: ReceiptRequest,
    _sesi: object = Depends(butuh_sesi_aktif),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*MUTATING_ROLES)),
) -> dict:
    """Catat satu penerimaan barang. 201 = tersimpan; 404 = batch tidak ada.

    Scope: barang hanya bisa diterima di dapur sendiri (ruling 2026-10-14) —
    peran SPPG yang mencoba mencatat batch milik lokasi lain dibalas 403.

    Kelayakan (Fase 4 MG poin 5): 409 bila evaluator menyatakan batch
    `rejected`/`quarantined`. Batch `on_hold` (safety `pending`/
    `needs_verification`, bukti suhu kurang) TETAP DITERIMA — ceklis petugas
    adalah bukti untuk verifikasi lanjutan, dan catatan `menunggu` tidak
    menambah stok. `batches.safety_status` tidak disentuh di sini.
    """
    batch = (
        await db.execute(select(Batch).where(Batch.id == payload.batch_id))
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="batch tidak ditemukan")

    assert_in_scope(user, batch.location_id, what="lokasi batch")

    # Fase 4 MG poin 5: revalidasi di PENERIMAAN. Batch yang sudah ditolak
    # evaluator (gagal uji, kedaluwarsa, masa layak tak tercatat, karantina,
    # kesegaran gagal) tidak boleh dicatat seolah tinggal menunggu persetujuan.
    # `on_hold` sengaja LOLOS: ceklis petugas adalah bukti untuk verifikasi
    # lanjutan, dan belum ada stok yang bertambah di titik ini.
    evaluasi = evaluasi_batch(batch)
    if evaluasi.status not in BOLEH_DICATAT:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{pesan_tolak(evaluasi)}"
                f" (kode: {', '.join(evaluasi.blocking_reasons)})"
            ),
        )

    # Catatan kosong/spasi = tidak ada catatan (NULL), bukan string kosong —
    # UI harus bisa membedakan "tidak menulis apa-apa" dari "menulis spasi".
    catatan = (payload.other_note or "").strip()

    receipt = BatchReceipt(
        batch_id=batch.id,
        checked=dict(payload.checked),
        other_note=catatan or None,
        recorded_by=user.id,
        status="menunggu",
        # Fase 2 MG: penerimaan milik SESI BATCH-nya, bukan sesi yang kebetulan
        # aktif. Tanpa ini, penerimaan atas barang sesi pertama tercatat milik
        # sesi kedua begitu operator membuka sesi baru, dan reset sesi pertama
        # tidak lagi bisa menemukan catatannya sendiri.
        demo_session_id=batch.demo_session_id,
    )
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)
    return _row(receipt, nama=user.name)


@router.post("/receipts/{receipt_id}/approve")
async def approve_receipt(
    receipt_id: uuid.UUID,
    _sesi: object = Depends(butuh_sesi_aktif),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("sppg_head")),
) -> dict:
    """Setujui penerimaan → barang masuk stok (idempoten).

    Persetujuan menulis SATU baris `supply_records` sebesar `batch.quantity_kg`
    untuk lokasi & komoditas batch. Overview membaca supply terbaru per lokasi,
    jadi angka pasokan/gap berubah setelah ini — bukan karena UI mengarang.

    Gerbang kelayakan (Fase 4 MG poin 5): hanya batch `usable` yang boleh
    disetujui. `on_hold` dan `rejected` sama-sama 409, tetapi pesannya menyebut
    sebab yang BERBEDA (`safety_pending` bukan `safety_fail`) supaya petugas
    tidak membuang barang yang masih bisa diverifikasi.

    Klik kedua tidak menambah stok: bila catatan sudah `disetujui`, balasan
    mengembalikan baris yang sama (`sudah: true`) tanpa menulis apa pun.
    """
    receipt = await _receipt_atau_404(db, receipt_id)
    batch = await _batch_atau_404(db, receipt.batch_id)
    assert_in_scope(user, batch.location_id, what="lokasi batch")

    if receipt.status == "disetujui":
        nama = await _nama(db, receipt.reviewed_by)
        kg = float(batch.quantity_kg)
        return {
            **_row(
                receipt,
                pemeriksa=nama,
                kg=kg,
                nilai=await receipt_value.nilai_diterima(db, batch.id, kg),
            ),
            "sudah": True,
        }
    if receipt.status == "ditolak":
        raise HTTPException(
            status_code=409,
            detail=(
                "penerimaan ini sudah ditolak — catat penerimaan baru bila"
                " barang diperiksa ulang"
            ),
        )
    # Hanya batch `usable` yang boleh menjadi stok. Evaluator yang sama dengan
    # `POST /receipts` dan `/actions/execute`, jadi `can_execute`, guard
    # eksekusi, dan penerimaan tidak bisa menyimpang (Fase 4 MG poin 4-5).
    # Alasan `on_hold` (pending/needs_verification/bukti suhu kurang) dijawab
    # dengan kalimatnya sendiri — bukan disamakan dengan kegagalan uji.
    evaluasi = evaluasi_batch(batch, datetime.now(UTC))
    if evaluasi.status != USABLE:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{pesan_tolak(evaluasi)}"
                f" (kode: {', '.join(evaluasi.blocking_reasons)})"
            ),
        )

    # Sudah ada penerimaan lain yang disetujui untuk batch ini?
    lain = (
        await db.execute(
            select(BatchReceipt.id).where(
                BatchReceipt.batch_id == batch.id,
                BatchReceipt.status == "disetujui",
                BatchReceipt.id != receipt.id,
            )
        )
    ).scalar_one_or_none()
    if lain is not None:
        raise HTTPException(
            status_code=409,
            detail="batch ini sudah punya penerimaan yang disetujui",
        )

    sekarang = datetime.now(UTC)
    # Stok on-hand = snapshot terakhir + barang yang baru diterima. Overview
    # membaca baris TERBARU (bukan jumlah seluruh riwayat), jadi menulis hanya
    # `batch.quantity_kg` akan MENURUNKAN pasokan bila stok sebelumnya lebih
    # besar — penerimaan harus menambah, bukan mengganti.
    stok_terakhir = (
        await db.execute(
            select(SupplyRecord)
            .where(
                SupplyRecord.location_id == batch.location_id,
                SupplyRecord.commodity_id == batch.commodity_id,
                # Samakan dengan pembaca stok (`balance.py`): hanya baris yang
                # SUDAH terjadi. Deret waktu demo memuat snapshot masa depan;
                # tanpa batas ini, approve menambah ke angka masa depan lalu
                # Overview hari ini tidak berubah (terukur 20 Okt 2026).
                SupplyRecord.recorded_at <= sekarang,
            )
            .order_by(SupplyRecord.recorded_at.desc(), SupplyRecord.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    dasar = Decimal(str(stok_terakhir.quantity_kg)) if stok_terakhir else Decimal("0")
    jumlah_baru = dasar + Decimal(str(batch.quantity_kg))
    stok = SupplyRecord(
        location_id=batch.location_id,
        commodity_id=batch.commodity_id,
        quantity_kg=jumlah_baru,
        recorded_at=sekarang,
        source="manual",
        origin="demo" if sesi_sekarang() is not None else "seed",
        generated_at=sekarang,
    )
    db.add(stok)
    receipt.status = "disetujui"
    receipt.reviewed_by = user.id
    receipt.reviewed_at = sekarang
    receipt.review_note = None
    await db.flush()
    receipt.supply_record_id = stok.id
    # Penulis KPI (migrasi 029): kg yang baru diterima menjadi porsi
    # tersampaikan pada rencana menu hari itu. Idempoten lewat
    # `source_ref=receipt:<id>`; tanpa ini Meal Continuity hanya bergerak
    # bila seeder dijalankan ulang.
    await settlement.catat_penerimaan(
        db, batch=batch, receipt=receipt, sekarang=sekarang
    )
    try:
        await db.commit()
    except IntegrityError as exc:  # balapan dua approve bersamaan
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="batch ini sudah punya penerimaan yang disetujui",
        ) from exc
    await db.refresh(receipt)
    return _row(
        receipt,
        pemeriksa=user.name,
        kg=float(batch.quantity_kg),
        nilai=await receipt_value.nilai_diterima(db, batch.id, float(batch.quantity_kg)),
    )


@router.post("/receipts/{receipt_id}/reject")
async def reject_receipt(
    receipt_id: uuid.UUID,
    payload: RejectRequest,
    _sesi: object = Depends(butuh_sesi_aktif),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("sppg_head")),
) -> dict:
    """Tolak penerimaan dengan alasan. Tidak menulis stok.

    Alasan wajib: tanpa itu petugas tidak tahu apa yang harus diperbaiki dan
    riwayat hanya menyimpan "ditolak" tanpa sebab.
    """
    receipt = await _receipt_atau_404(db, receipt_id)
    batch = await _batch_atau_404(db, receipt.batch_id)
    assert_in_scope(user, batch.location_id, what="lokasi batch")

    catatan = payload.note.strip()
    if len(catatan) < REJECT_MIN:
        raise HTTPException(status_code=422, detail="alasan penolakan wajib diisi")

    if receipt.status == "disetujui":
        raise HTTPException(
            status_code=409,
            detail="penerimaan sudah disetujui dan stoknya sudah tercatat — tidak bisa ditolak",
        )
    if receipt.status == "ditolak":
        nama = await _nama(db, receipt.reviewed_by)
        return {**_row(receipt, pemeriksa=nama), "sudah": True}

    receipt.status = "ditolak"
    receipt.reviewed_by = user.id
    receipt.reviewed_at = datetime.now(UTC)
    receipt.review_note = catatan
    await db.commit()
    await db.refresh(receipt)
    return _row(receipt, pemeriksa=user.name)


@router.get("/receipts/menunggu")
async def list_receipts_menunggu(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Catatan penerimaan yang SUDAH dicatat tetapi belum diputuskan.

    Dipisah dari daftar batch penerimaan (20 Okt 2026): layar "Penerimaan
    barang" hanya menawarkan barang yang BELUM dinilai/dicatat. Begitu catatan
    dibuat, batch itu keluar dari pilihan dan pindah ke antrean ini supaya
    kepala SPPG tetap bisa menyetujui/menolak tanpa mencari batch lagi.

    Satu baris per batch (catatan terbaru), di-scope ke lokasi pengguna bila
    pengguna punya lokasi; pemantau tanpa lokasi melihat seluruh jaringan.
    """
    pemeriksa = aliased(User)
    batas = []
    if user.location_id is not None:
        batas.append(Batch.location_id == user.location_id)

    baris = (
        await db.execute(
            select(
                BatchReceipt,
                User.name,
                Batch.quantity_kg,
                Commodity.name,
                Location.name,
                Batch.safety_status,
            )
            .join(User, User.id == BatchReceipt.recorded_by)
            .join(Batch, Batch.id == BatchReceipt.batch_id)
            .join(Commodity, Commodity.id == Batch.commodity_id)
            .join(Location, Location.id == Batch.location_id)
            .outerjoin(pemeriksa, pemeriksa.id == BatchReceipt.reviewed_by)
            .where(BatchReceipt.status == "menunggu", *batas)
            .order_by(BatchReceipt.recorded_at.desc(), BatchReceipt.id.desc())
        )
    ).all()

    terlihat: set[uuid.UUID] = set()
    items: list[dict] = []
    for receipt, nama, kg, komoditas, lokasi, safety in baris:
        if receipt.batch_id in terlihat:
            continue
        terlihat.add(receipt.batch_id)
        dicek = receipt.checked or {}
        items.append(
            {
                "id": str(receipt.id),
                "batch_id": str(receipt.batch_id),
                "commodity": komoditas,
                "quantity_kg": float(kg),
                "location": lokasi,
                "safety_status": safety,
                "checked_count": sum(1 for nilai in dicek.values() if nilai is True),
                "recorded_by_name": nama,
                "recorded_at": receipt.recorded_at.isoformat(),
                # Antrean ini hanya berisi catatan yang BELUM disetujui, jadi
                # nilai rupiah belum ada — kuncinya tetap dikirim (None) supaya
                # UI membaca satu bentuk payload saja.
                "accepted_value_idr": None,
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/receipts")
async def list_receipts(
    batch_id: uuid.UUID,
    limit: int = Query(default=5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Riwayat catatan penerimaan sebuah batch, terbaru dulu.

    Tidak dibatasi lokasi (pengawas nasional perlu bisa membacanya), tetapi
    hanya untuk batch yang diminta — bukan papan catatan seluruh jaringan.
    """
    pemeriksa = aliased(User)
    baris = (
        await db.execute(
            select(BatchReceipt, User.name, pemeriksa.name, Batch.quantity_kg)
            .join(User, User.id == BatchReceipt.recorded_by)
            .outerjoin(pemeriksa, pemeriksa.id == BatchReceipt.reviewed_by)
            .join(Batch, Batch.id == BatchReceipt.batch_id)
            .where(BatchReceipt.batch_id == batch_id)
            .order_by(BatchReceipt.recorded_at.desc(), BatchReceipt.id.desc())
            .limit(limit)
        )
    ).all()
    # Satu batch per permintaan → satu kueri harga, bukan satu per baris.
    kg_batch = float(baris[0][3]) if baris else None
    nilai = await receipt_value.nilai_diterima(db, batch_id, kg_batch)
    return {
        "items": [
            _row(receipt, nama=nama, pemeriksa=nama_pemeriksa, kg=float(kg), nilai=nilai)
            for receipt, nama, nama_pemeriksa, kg in baris
        ]
    }
