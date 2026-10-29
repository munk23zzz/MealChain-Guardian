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
from app.core.receipt_scoring import (
    CHECKLIST_VERSION,
    checklist_untuk,
    opsi_jumlah,
    putusan,
    saran,
    skor,
    validasi_berat,
)
from app.core.scope import assert_in_scope
from app.models import (
    Batch,
    BatchReceipt,
    Commodity,
    Location,
    Supplier,
    SupplyRecord,
    User,
)
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

#: Label putusan ceklis untuk layar (Dok 05 §4). Diterjemahkan di SERVER supaya
#: UI tidak pernah menampilkan enum mentah (`pass`, `needs_verification`) dan
#: tidak bisa menebak artinya sendiri-sendiri.
VERDICT_LABEL = {
    "pass": "Layak diterima",
    "needs_verification": "Perlu keputusan manual",
    "fail": "Tidak boleh diterima",
}

#: Pesan galat berat yang tidak wajar (kode → kalimat).
BERAT_PESAN = {
    "berat_nol": "berat diterima harus lebih dari 0 kg — timbang dulu barangnya",
    "berat_minus": "berat diterima tidak boleh negatif",
    "berat_lebih": (
        "berat diterima lebih dari 110% berat pesanan — periksa ulang timbangan "
        "atau jumlah yang dikirim"
    ),
}


class ReceiptRequest(BaseModel):
    batch_id: uuid.UUID
    #: Snapshot titik periksa: {"kemasan": true, "suhu": false, ...}.
    checked: dict[str, bool] = Field(default_factory=dict)
    #: Isian "Lainnya" — keadaan yang tidak ada di daftar periksa.
    other_note: str | None = Field(default=None, max_length=NOTE_MAX)
    #: Jawaban tujuh butir berbobot (Dok 05 §3): {"suhu": "sesuai", ...}.
    #: Bila diisi, server MENILAI dan menyimpan skor + putusan. Bila kosong,
    #: jalur lama (cek boolean) tetap jalan — baris lama tidak dipaksa berubah.
    answers: dict[str, str] | None = Field(default=None)
    #: Berat yang benar-benar ditimbang saat barang tiba (kg). Wajib bersama
    #: `answers`: angka ini yang dipakai menilai butir "kesesuaian jumlah" dan
    #: menghitung nilai rupiah (Dok 05 §5.1), bukan berat batch.
    accepted_kg: float | None = Field(default=None, ge=0, le=1_000_000)

    @field_validator("answers")
    @classmethod
    def _batas_jawaban(cls, nilai: dict[str, str] | None) -> dict[str, str] | None:
        if nilai is None:
            return None
        if len(nilai) > MAX_CHECKED_KEYS:
            raise ValueError(f"terlalu banyak butir (maks {MAX_CHECKED_KEYS})")
        if any(not kunci.strip() or len(kunci) > MAX_KEY_LENGTH for kunci in nilai):
            raise ValueError("nama butir tidak boleh kosong atau terlalu panjang")
        return nilai

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
    po_number: str | None = None,
    unit_price: float | None = None,
    nilai_diterima: float | None = None,
) -> dict:
    """Bentuk balasan yang stabil untuk UI (jumlah titik dihitung SERVER)."""
    dicek = receipt.checked or {}
    # Berat yang dipakai menghitung nilai: hasil timbangan bila ada, kalau tidak
    # berat batch (perilaku baris lama). Dok 05 §5.1: nilai = kg DITERIMA × harga.
    kg_terima = (
        float(receipt.accepted_kg)
        if receipt.accepted_kg is not None
        else kg
    )
    if nilai_diterima is None and kg_terima is not None and unit_price is not None:
        nilai_diterima = round(kg_terima * unit_price, 2)
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
        #: Sejak migrasi 044 angkanya memakai kg DITERIMA (Dok 05 §5.1), bukan
        #: berat batch: susut sortir langsung mengurangi nilai.
        "accepted_value_idr": (
            (nilai_diterima if nilai_diterima is not None else nilai)
            if receipt.status == "disetujui"
            else None
        ),
        #: Kg yang masuk stok karena persetujuan ini (None bila belum disetujui).
        "stock_kg": kg_terima if receipt.status == "disetujui" else None,
        # ---- konteks nilai (Dok 05 §8.2–§8.3) ------------------------------
        # Ketiganya dikirim juga untuk catatan 'menunggu', supaya layar bisa
        # menampilkan tiga angka dan asal harganya SEBELUM keputusan diambil.
        #: Kuantitas batch yang akan masuk stok bila disetujui.
        "batch_quantity_kg": kg,
        #: Nomor PO invoice yang mendanai batch. None = tidak ada ikatan bukti.
        "po_number": po_number,
        #: Harga satuan invoice (Rp/kg) — dasar kalimat "kg × Rp/kg dari PO …".
        "unit_price_idr": unit_price,
        #: Perkiraan nilai bila disetujui (kg × harga satuan). BUKAN nilai
        #: tersimpan: `accepted_value_idr` tetap satu-satunya angka pembukuan.
        "estimated_value_idr": nilai,
        # ---- skor ceklis (migrasi 044, Dok 05 §3–§5) -----------------------
        #: Nilai 0–100 dari tujuh butir berbobot. None = baris lama/belum dinilai.
        "score": receipt.score,
        #: 'pass' | 'needs_verification' | 'fail' — putusan SERVER, bukan UI.
        "verdict": receipt.verdict,
        "verdict_label": VERDICT_LABEL.get(receipt.verdict or "", None),
        #: Kalimat alasan (Dok 05 §7). Wajib tampil di rentang 65–85.
        "advice": receipt.advice,
        #: Rincian poin per butir: [{kunci,label,opsi_label,bobot,faktor,poin,…}].
        "points": (receipt.points or {}).get("per_butir"),
        #: Jawaban apa adanya: {"suhu": "sesuai", ...}.
        "answers": receipt.answers,
        #: Berat pesanan (batch) & berat yang benar-benar ditimbang.
        "ordered_kg": float(receipt.ordered_kg) if receipt.ordered_kg is not None else kg,
        "accepted_kg": kg_terima,
        #: Nilai rupiah dari kg DITERIMA (bukan kg batch) — beda dari
        #: `estimated_value_idr` yang memakai berat batch.
        "nilai_diterima_idr": nilai_diterima,
        "checklist_version": receipt.checklist_version,
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

    # ---- Penilaian ceklis (migrasi 044, Dok 05 §3–§4) ----------------------
    # Jawaban tujuh butir dinilai SERVER di sini dan hasilnya disimpan; layar
    # hanya menampilkan `score`/`points`/`verdict` apa adanya.
    dinilai: dict = {}
    kg_pesan = float(batch.quantity_kg)
    if payload.answers is not None:
        if payload.accepted_kg is None:
            raise HTTPException(
                status_code=422,
                detail="berat diterima wajib diisi bersama jawaban ceklis",
            )
        kg_terima = float(payload.accepted_kg)
        kode_berat = validasi_berat(kg_pesan, kg_terima)
        if kode_berat is not None:
            raise HTTPException(
                status_code=422,
                detail=f"{BERAT_PESAN[kode_berat]} (kode: {kode_berat})",
            )
        jawaban = {str(k): str(v) for k, v in payload.answers.items()}
        # Butir "kesesuaian jumlah" TIDAK dijawab petugas: nilainya diturunkan
        # dari timbangan (§5.1) supaya jawaban tidak bisa bertentangan dengan kg
        # yang benar-benar masuk. Jawaban kiriman klien untuk butir ini dibuang.
        jawaban["jumlah"] = opsi_jumlah(kg_pesan, kg_terima)
        try:
            hasil = skor(jawaban)
        except KeyError as exc:
            raise HTTPException(
                status_code=422,
                detail=(
                    "jawaban ceklis belum lengkap atau pilihannya tidak dikenal: "
                    f"{exc.args[0] if exc.args else ''}"
                ),
            ) from exc
        keputusan = putusan(hasil, kg_pesan, kg_terima)
        dinilai = {
            "answers": jawaban,
            "points": {"per_butir": list(hasil.per_butir)},
            "score": hasil.score,
            "verdict": keputusan,
            "advice": saran(hasil, keputusan, kg_pesan, kg_terima),
            "ordered_kg": kg_pesan,
            "accepted_kg": kg_terima,
            "checklist_version": CHECKLIST_VERSION,
            # Snapshot boolean lama tetap diisi (butir yang dijawab dengan
            # pilihan penuh) supaya pembaca lama tidak melihat ceklis kosong.
            "checked": {
                b["kunci"]: b["faktor"] == 100 for b in hasil.per_butir
            },
        }

    receipt = BatchReceipt(
        batch_id=batch.id,
        checked=dict(dinilai.pop("checked", payload.checked)),
        other_note=catatan or None,
        recorded_by=user.id,
        status="menunggu",
        # Fase 2 MG: penerimaan milik SESI BATCH-nya, bukan sesi yang kebetulan
        # aktif. Tanpa ini, penerimaan atas barang sesi pertama tercatat milik
        # sesi kedua begitu operator membuka sesi baru, dan reset sesi pertama
        # tidak lagi bisa menemukan catatannya sendiri.
        demo_session_id=batch.demo_session_id,
        **dinilai,
    )
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)
    # Dok 05 §8.2–§8.3: catatan yang baru dibuat langsung membawa konteks nilai
    # (kg batch, harga satuan PO, perkiraan nilai) supaya layar bisa menampilkan
    # tiga angka tanpa menunggu keputusan — dan tanpa menghitung sendiri.
    kg_batch = float(batch.quantity_kg)
    po_number, harga = await receipt_value.po_dan_harga(db, batch.id)
    # §5.1: putusan `fail` membuat jumlah efektif 0 — barangnya ada di truk,
    # tetapi tidak boleh masuk dapur, jadi tidak ada nilai yang dibukukan.
    kg_efektif = (
        0.0
        if receipt.verdict == "fail"
        else (float(receipt.accepted_kg) if receipt.accepted_kg is not None else kg_batch)
    )
    return _row(
        receipt,
        nama=user.name,
        kg=kg_batch,
        nilai=receipt_value.nilai_dari(kg_batch, harga),
        po_number=po_number,
        unit_price=float(harga) if harga is not None else None,
        nilai_diterima=receipt_value.nilai_dari(kg_efektif, harga),
    )


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
        kg_terima = (
            float(receipt.accepted_kg) if receipt.accepted_kg is not None else kg
        )
        po_number, harga = await receipt_value.po_dan_harga(db, batch.id)
        return {
            **_row(
                receipt,
                pemeriksa=nama,
                kg=kg,
                nilai=receipt_value.nilai_dari(kg_terima, harga),
                po_number=po_number,
                unit_price=float(harga) if harga is not None else None,
                nilai_diterima=receipt_value.nilai_dari(kg_terima, harga),
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
    # Gerbang putusan ceklis (Dok 05 §6): nilai di bawah ambang atau ada butir
    # kritis berarti barang tidak boleh masuk dapur, sebesar apa pun jumlah
    # fisiknya. Kalau hanya UI yang menyembunyikan tombolnya, panggilan langsung
    # ke endpoint ini tetap menambah stok — jadi gerbangnya di sini.
    if receipt.verdict == "fail":
        raise HTTPException(
            status_code=409,
            detail=(
                "putusan ceklis penerimaan: tidak boleh diterima"
                + (f" — {receipt.advice}" if receipt.advice else "")
                + " (kode: receipt_verdict_fail)"
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
    # Dok 05 §5.1: yang masuk stok adalah BERAT DITERIMA (timbangan), bukan
    # berat batch. Selisihnya susut sortir — kalau memakai berat batch, stok
    # bertambah dari barang yang tidak pernah sampai di dapur.
    kg_masuk = (
        Decimal(str(receipt.accepted_kg))
        if receipt.accepted_kg is not None
        else Decimal(str(batch.quantity_kg))
    )
    jumlah_baru = dasar + kg_masuk
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
    kg = float(batch.quantity_kg)
    kg_terima = float(receipt.accepted_kg) if receipt.accepted_kg is not None else kg
    po_number, harga = await receipt_value.po_dan_harga(db, batch.id)
    return _row(
        receipt,
        pemeriksa=user.name,
        kg=kg,
        nilai=receipt_value.nilai_dari(kg_terima, harga),
        po_number=po_number,
        unit_price=float(harga) if harga is not None else None,
        nilai_diterima=receipt_value.nilai_dari(kg_terima, harga),
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
        po_number, harga = await receipt_value.po_dan_harga(db, batch.id)
        kg = float(batch.quantity_kg)
        return {
            **_row(
                receipt,
                pemeriksa=nama,
                kg=kg,
                nilai=receipt_value.nilai_dari(kg, harga),
                po_number=po_number,
                unit_price=float(harga) if harga is not None else None,
            ),
            "sudah": True,
        }

    receipt.status = "ditolak"
    receipt.reviewed_by = user.id
    receipt.reviewed_at = datetime.now(UTC)
    receipt.review_note = catatan
    await db.commit()
    await db.refresh(receipt)
    # Konteks nilai tetap dikirim pada penolakan: layar menampilkan berapa
    # rupiah yang TIDAK masuk stok, dan dari PO mana angka itu berasal.
    kg = float(batch.quantity_kg)
    po_number, harga = await receipt_value.po_dan_harga(db, batch.id)
    return _row(
        receipt,
        pemeriksa=user.name,
        kg=kg,
        nilai=receipt_value.nilai_dari(kg, harga),
        po_number=po_number,
        unit_price=float(harga) if harga is not None else None,
    )


@router.get("/receipts/checklist")
async def receipt_checklist(
    commodity: str | None = Query(default=None, max_length=60),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Daftar butir ceklis + bobot + tiga pilihan untuk satu komoditas.

    Dok 05 §3: bobot dan faktor hidup di SERVER. Layar tidak menyimpan salinan
    angka itu, supaya perubahan bobot tidak membuat layar lama menghitung
    berbeda. Petunjuk suhu diambil dari profil komoditas (`commodity_limits`),
    jadi telur/ayam/wortel (rantai dingin) dan beras (suhu ruang) tidak
    dipaksa memakai satu rentang yang sama.

    `commodity` dicocokkan lewat nama komoditas di tabel `commodities`; nama
    yang tidak dikenal tetap mengembalikan daftar butir tanpa petunjuk suhu
    (bukan galat — layar masih bisa menilai butir lain).
    """
    nama = (commodity or "").strip() or None
    if nama:
        ada = (
            await db.execute(select(Commodity.name).where(Commodity.name == nama))
        ).scalar_one_or_none()
        if ada is None:
            nama = None
    return checklist_untuk(nama)


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

    Antrean ini hanya memuat batch yang SUDAH AMAN secukupnya untuk diputuskan
    (evaluator `usable`) dan yang masa layaknya belum lewat (29 Okt 2026).
    Kepala SPPG tinggal menyetujui atau menolak; barang yang buktinya belum
    lengkap tetap terlihat di kartu "Batch perlu perhatian" — bukan di sini.
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
                Batch,
                Commodity.name,
                Location.name,
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

    # Hanya batch yang SUDAH dinyatakan aman (permintaan pemilik, 29 Okt 2026):
    # antrean ini adalah tempat memutuskan, bukan tempat menindaklanjuti bukti
    # yang belum lengkap. Kriterianya memakai evaluator yang SAMA dengan
    # `/approve` — kalau baris muncul di sini, tombol Setujui pasti diterima
    # server; batch `on_hold`/`rejected`/`quarantined` tidak ditawarkan.
    baris = [b for b in baris if evaluasi_batch(b[2]).status == USABLE]

    terlihat: set[uuid.UUID] = set()
    # Konteks nilai (Dok 05 §8.2–§8.3): antrean harus bisa menulis tiga angka
    # dan asal harganya SEBELUM kepala SPPG memutuskan. Satu kueri peta untuk
    # semua batch di antrean — bukan satu kueri harga per baris.
    peta_po = await receipt_value.peta_po_dan_harga(
        db, {str(baris_[0].batch_id) for baris_ in baris if baris_}
    )
    items: list[dict] = []
    for receipt, nama, batch, komoditas, lokasi in baris:
        if receipt.batch_id in terlihat:
            continue
        terlihat.add(receipt.batch_id)
        kg = float(batch.quantity_kg)
        safety = batch.safety_status
        dicek = receipt.checked or {}
        po_number, harga = peta_po.get(str(receipt.batch_id), (None, None))
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
                # nilai pembukuan belum ada — kuncinya tetap dikirim (None)
                # supaya UI membaca satu bentuk payload saja.
                "accepted_value_idr": None,
                # ---- konteks nilai (Dok 05 §8.2–§8.3) ----
                # Dikirim untuk catatan 'menunggu' supaya baris antrean bisa
                # menampilkan "bila disetujui" + asal harga, tanpa layar
                # mengalikan kg x harga sendiri.
                "batch_quantity_kg": float(kg),
                "po_number": po_number,
                "unit_price_idr": float(harga) if harga is not None else None,
                "estimated_value_idr": receipt_value.nilai_dari(float(kg), harga),
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
    po_number, harga = await receipt_value.po_dan_harga(db, batch_id)
    nilai = receipt_value.nilai_dari(kg_batch, harga)
    return {
        "items": [
            _row(
                receipt,
                nama=nama,
                pemeriksa=nama_pemeriksa,
                kg=float(kg),
                nilai=nilai,
                po_number=po_number,
                unit_price=float(harga) if harga is not None else None,
            )
            for receipt, nama, nama_pemeriksa, kg in baris
        ]
    }


#: Batas kewarasan riwayat penerimaan: cukup untuk layar audit satu tahun demo,
#: cukup kecil untuk dihitung ulang seluruhnya di server (ringkasan dihitung
#: dari SELURUH baris dalam cakupan, bukan hanya halaman yang dikirim).
RIWAYAT_MAKS = 500


@router.get("/receipts/riwayat")
async def list_receipts_riwayat(
    supplier_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(menunggu|disetujui|ditolak)$"),
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Riwayat penerimaan barang per pemasok (Dok 05 §8.5, layar Pemasok).

    Kenapa endpoint ini ada: `GET /receipts` hanya menjawab per BATCH, dan
    `GET /receipts/menunggu` hanya memuat catatan yang belum diputuskan. Layar
    audit pemasok butuh ketiganya sekaligus — yang sudah disetujui, yang
    ditolak, dan yang menunggu — dalam satu tabel berurut waktu.

    Yang dijanjikan bentuk balasannya:

    - satu baris per catatan penerimaan, terbaru dulu;
    - kg DIPESAN (`ordered_kg`, kuantitas batch) dan kg DITERIMA
      (`received_kg`, hanya terisi bila disetujui) dua kolom terpisah — klien
      tidak pernah mengurangkannya sendiri;
    - nilai rupiah dari `receipt_value` (harga satuan invoice PO), dan `None`
      untuk batch tanpa ikatan PO ("tidak tercatat", bukan Rp 0);
    - `ringkasan` dihitung server dari SELURUH baris dalam cakupan, supaya
      angka di kepala tabel tidak berubah saat pengguna memindah halaman.

    Cakupannya sama dengan antrean `menunggu`: pengguna yang punya lokasi hanya
    melihat penerimaan lokasinya; pemantau tanpa lokasi melihat seluruh jaringan.
    """
    pemeriksa = aliased(User)
    batas = []
    if user.location_id is not None:
        batas.append(Batch.location_id == user.location_id)
    if supplier_id is not None:
        batas.append(Batch.supplier_id == supplier_id)
    if status is not None:
        batas.append(BatchReceipt.status == status)

    baris = (
        await db.execute(
            select(
                BatchReceipt,
                User.name,
                pemeriksa.name,
                Batch.quantity_kg,
                Batch.id,
                Commodity.name,
                Supplier.id,
                Supplier.name,
                Location.name,
            )
            .join(User, User.id == BatchReceipt.recorded_by)
            .join(Batch, Batch.id == BatchReceipt.batch_id)
            .join(Commodity, Commodity.id == Batch.commodity_id)
            .join(Supplier, Supplier.id == Batch.supplier_id)
            .join(Location, Location.id == Batch.location_id)
            .outerjoin(pemeriksa, pemeriksa.id == BatchReceipt.reviewed_by)
            .where(*batas)
            .order_by(BatchReceipt.recorded_at.desc(), BatchReceipt.id.desc())
            .limit(RIWAYAT_MAKS)
        )
    ).all()

    # Satu kueri harga untuk semua batch di halaman ini — bukan satu per baris.
    peta = await receipt_value.peta_po_dan_harga(
        db, {str(r[4]) for r in baris}
    )

    items: list[dict] = []
    for (
        receipt,
        nama,
        nama_pemeriksa,
        kg,
        batch_id,
        komoditas,
        supplier_uuid,
        supplier_nama,
        lokasi,
    ) in baris:
        kg_float = float(kg) if kg is not None else None
        # Dok 05 §5.1 (perbaikan 29 Okt 2026): kolom "diterima" adalah hasil
        # TIMBANGAN. Dulu dua kolom ini sama-sama memakai `batches.quantity_kg`,
        # sehingga ringkasan Pemasok menulis "kg diterima 900" padahal yang
        # masuk stok (dan yang dibayar) 855 kg — berbeda dari KPI "Effective
        # Price per Accepted Kg" yang sudah memakai timbangan. Baris lama tanpa
        # timbangan tetap sah: jatuh ke berat batch.
        pesanan = (
            float(receipt.ordered_kg) if receipt.ordered_kg is not None else kg_float
        )
        timbangan = (
            float(receipt.accepted_kg) if receipt.accepted_kg is not None else kg_float
        )
        po_number, harga_satuan = peta.get(str(batch_id), (None, None))
        row = _row(
            receipt,
            nama=nama,
            pemeriksa=nama_pemeriksa,
            kg=kg_float,
            nilai=receipt_value.nilai_dari(kg_float, harga_satuan),
            po_number=po_number,
            unit_price=float(harga_satuan) if harga_satuan is not None else None,
        )
        row.update(
            {
                "batch_ref": str(batch_id)[:8],
                "commodity": komoditas,
                "supplier_id": str(supplier_uuid),
                "supplier": supplier_nama,
                "location": lokasi,
                # Dok 05 §8.2: dua angka kg berdiri sendiri. `received_kg`
                # kosong selama catatan belum disetujui — barang yang belum
                # masuk stok tidak boleh terbaca sebagai sudah diterima.
                "ordered_kg": pesanan,
                "received_kg": timbangan if receipt.status == "disetujui" else None,
            }
        )
        items.append(row)

    ringkasan = {
        "total": len(items),
        "menunggu": 0,
        "disetujui": 0,
        "ditolak": 0,
        "kg_dipesan": 0.0,
        "kg_diterima": 0.0,
        #: Nilai pembukuan dari penerimaan yang SUDAH disetujui.
        "nilai_diterima_idr": 0.0,
        #: Perkiraan nilai (kg × harga satuan) yang masih menunggu keputusan.
        "nilai_menunggu_idr": 0.0,
        #: Baris yang harganya tidak bisa ditentukan (tanpa ikatan PO).
        "tanpa_harga": 0,
        "supplier": len({row["supplier_id"] for row in items}),
    }
    for row in items:
        kunci = row["status"]
        if kunci in ("menunggu", "disetujui", "ditolak"):
            ringkasan[kunci] += 1
        if row["ordered_kg"] is not None:
            ringkasan["kg_dipesan"] += row["ordered_kg"]
        if row["received_kg"] is not None:
            ringkasan["kg_diterima"] += row["received_kg"]
        if row["accepted_value_idr"] is not None:
            ringkasan["nilai_diterima_idr"] += row["accepted_value_idr"]
        elif row["status"] == "menunggu" and row["estimated_value_idr"] is not None:
            # Hanya baris yang MASIH menunggu keputusan. Catatan yang ditolak
            # juga tidak punya nilai pembukuan, tetapi ia bukan "menunggu" —
            # memasukkan perkiraannya ke sini membuat angka "nilai menunggu"
            # memuat barang yang sudah jelas tidak diterima.
            ringkasan["nilai_menunggu_idr"] += row["estimated_value_idr"]
        if row["unit_price_idr"] is None:
            ringkasan["tanpa_harga"] += 1
    for nama_angka in ("kg_dipesan", "kg_diterima"):
        ringkasan[nama_angka] = round(ringkasan[nama_angka], 2)
    for nama_angka in ("nilai_diterima_idr", "nilai_menunggu_idr"):
        ringkasan[nama_angka] = round(ringkasan[nama_angka], 2)

    return {"items": items[:limit], "ringkasan": ringkasan}
