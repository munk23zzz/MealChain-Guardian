"""Sesi demo — data operasional hanya hidup selama sesi (20 Okt 2026).

Permintaan pemilik: tampilan default KOSONG; tombol "Siapkan data demo" memanggil
data dan mengaktifkannya selama satu jam (bisa diperpanjang), ada hitungan
mundur, dan sesudah sesi habis data kembali kosong (perubahan selama sesi ikut
hilang). Aturan yang dipegang modul ini:

- Sesi TIDAK menghapus bukti secara membabi buta: yang dihapus hanya baris yang
  ber-stempel `demo_session_id` sesi itu. Baris lain (data kerja orang lain,
  referensi users/locations/commodities) tidak disentuh.
- Jam tidak digeser: `anchor_now` mencatat waktu server saat sesi dibuat, lalu
  berjalan normal. Tidak ada pembekuan waktu yang membuat log suhu mustahil.
- Kedaluwarsa dinilai malas (saat ada yang bertanya), bukan oleh cron: satu
  sumber kebenaran, tidak ada proses latar yang bisa mati diam-diam.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, event, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import Base
from app.models.demo_sessions import DemoSession

#: Sesi yang sedang dipakai request ini. Diisi `get_db` (lihat dependencies.py).
_current: ContextVar[uuid.UUID | None] = ContextVar("mealchain_demo_session", default=None)

#: Model yang ikut aturan sesi. Ditambah bertahap; setiap model WAJIB punya
#: kolom `demo_session_id` dan dipasang di migrasi yang sama.
MODEL_BERSESI: tuple[type[Base], ...] = ()


_model_cache: tuple[type[Base], ...] | None = None
_model_ukuran = -1


def model_bersesi() -> tuple[type[Base], ...]:
    """Model yang punya kolom `demo_session_id` — dicari, bukan didaftar manual.

    Cache dihitung ulang bila jumlah mapper berubah. Ini bukan optimasi gaya:
    `pasang_penjaga()` berjalan saat modul diimpor, ketika `app.models` mungkin
    BELUM lengkap. Cache yang "sekali jadi" membuat supplier_exclusions (dan
    tabel lain yang diimpor belakangan) tidak pernah ikut disaring/dihapus —
    terukur 20 Okt 2026 sebagai ForeignKeyViolationError saat menghapus decisions.
    """
    global _model_cache, _model_ukuran
    ukuran = len(Base.registry.mappers)
    if _model_cache is None or ukuran != _model_ukuran:
        _model_cache = tuple(
            mapper.class_
            for mapper in Base.registry.mappers
            if "demo_session_id" in mapper.columns
        )
        _model_ukuran = ukuran
    return _model_cache


def sekarang() -> datetime:
    return datetime.now(timezone.utc)


#: Sesi sentinel "cetakan" (template beku).
#:
#: Kenapa ada (audit integritas database 26 Okt 2026, D-04): template demo dulu
#: "dibekukan" dengan menulis `origin='seed'`, sehingga provenance baris demo
#: hilang dan cek kanonik (`origin='demo'`) lulus secara vakum. Penanda beku
#: sekarang BUKAN perubahan origin, melainkan stempel ke sesi sentinel ini:
#: ia tidak pernah `active` (jadi tidak muncul di /demo/session, tidak bisa
#: diperpanjang/diakhiri) dan penyapu sesi tidak menghapus barisnya.
CETAKAN_ID = uuid.UUID("ce7a0000-0000-4000-8000-000000000001")


async def cetakan(db: AsyncSession) -> uuid.UUID:
    """Pastikan baris sesi sentinel `cetakan` ada; kembalikan id-nya.

    Idempoten: baris dibuat sekali, sesudah itu hanya dibaca.
    """
    ada = await db.get(DemoSession, CETAKAN_ID)
    if ada is None:
        jangkar = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db.add(
            DemoSession(
                id=CETAKAN_ID,
                status="expired",
                started_at=jangkar,
                expires_at=jangkar,
                anchor_now=jangkar,
                ended_at=jangkar,
                template_version="cetakan",
                # Sesi sentinel tidak pernah dievaluasi; mode `replay` + jangkar
                # kanon menjaga kontrak kolom (bukan jangkar Jan 2026 yang akan
                # membuat template beku tampak "lebih tua" dari dataset kanon).
                mode="replay",
                evaluation_anchor=datetime(
                    2026, 10, 8, 12, 0, tzinfo=timezone.utc
                ),
                dataset_version="cetakan",
            )
        )
        await db.flush()
    return CETAKAN_ID



def set_sesi(sesi_id: uuid.UUID | None) -> None:
    _current.set(sesi_id)


def sesi_sekarang() -> uuid.UUID | None:
    return _current.get()


#: Serialisasi operasi sesi (mulai/akhiri). Tanpa ini, penyemaian yang masih
#: berjalan bisa menulis baris SETELAH pembersihan, sehingga "Akhiri sesi"
#: meninggalkan data (terukur 20 Okt 2026: 30 keputusan + 82 batch sisa).
#: Satu worker uvicorn — bila kelak multi-worker, ganti dengan advisory lock DB.
_kunci = asyncio.Lock()


@asynccontextmanager
async def kunci_sesi():
    async with _kunci:
        yield


def _menit_valid(menit: int | None, bawaan: int) -> int:
    """Batasi durasi ke rentang wajar: minimal 1 menit, maksimal `settings`."""
    maks = max(1, int(settings.demo_session_max_minutes))
    if menit is None:
        return max(1, min(int(bawaan), maks))
    try:
        nilai = int(menit)
    except (TypeError, ValueError):
        return max(1, min(int(bawaan), maks))
    return max(1, min(nilai, maks))


def _batas_akhir(started_at: datetime) -> datetime:
    """Plafon absolut satu sesi: `DEMO_SESSION_MAX_MINUTES` menit (2 jam).

    Satu sumber untuk START dan EXTEND. Sebelumnya hanya `extend` yang memakai
    plafon ini sementara durasi awal masih menerima nilai apa pun dari payload,
    sehingga "sesi 2 jam" bisa dimulai sebagai 4 jam. Perpanjangan hanya boleh
    MENAMBAL sampai plafon — meminta 240 menit pada sesi 110 menit tetap
    berhenti di 120 menit.
    """
    return started_at + timedelta(minutes=max(1, int(settings.demo_session_max_minutes)))



def status_payload(sesi: DemoSession | None, saat: datetime | None = None) -> dict[str, Any]:
    """Bentuk balasan stabil untuk UI (hitungan mundur dihitung SERVER).

    Sejak Fase 2 MG payload membawa `mode`, `evaluation_anchor`, dan
    `dataset_version`: klien tidak boleh menebak mode dari "sesi terbaru", dan
    `GET /demo/session` memakai bentuk yang SAMA dengan blok `session` pada
    respons seed (`demo_ownership.blok_sesi`).
    """
    saat = saat or sekarang()
    if sesi is None:
        return {
            "active": False,
            "enforced": bool(settings.demo_session_enforce),
            "session_id": None,
            "status": "kosong",
            "mode": None,
            "evaluation_anchor": None,
            "dataset_version": None,
            # Jumlah kasus milik sesi; `None` = tidak ada sesi (bukan nol kasus).
            "cases": None,
            "expires_at": None,
            "anchor_now": None,
            "server_now": saat.isoformat(),
            "remaining_seconds": 0,
        }
    sisa = int((sesi.expires_at - saat).total_seconds())
    from app.services import decision_time

    return {
        "active": sesi.status == "active" and sisa > 0,
        "enforced": bool(settings.demo_session_enforce),
        "session_id": str(sesi.id),
        "status": sesi.status,
        # Mode/anchor adalah sifat SESI (bukan data sesi terbaru).
        "mode": sesi.mode,
        "evaluation_anchor": sesi.evaluation_anchor.isoformat(),
        "dataset_version": (
            sesi.dataset_version
            or decision_time.dataset_version_untuk(
                sesi.mode, sesi.evaluation_anchor
            )
        ),
        # Diisi pemanggil yang punya DB (`GET /demo/session`): jumlah KASUS milik
        # sesi ini. `None` = belum dihitung, bukan nol.
        "cases": None,
        "expires_at": sesi.expires_at.isoformat(),
        "anchor_now": sesi.anchor_now.isoformat(),
        "server_now": saat.isoformat(),
        "remaining_seconds": max(0, sisa),
    }


async def _sesi_aktif_terakhir(db: AsyncSession) -> DemoSession | None:
    hasil = await db.execute(
        select(DemoSession)
        .where(DemoSession.status == "active")
        .order_by(DemoSession.started_at.desc())
        .limit(1)
    )
    return hasil.scalar_one_or_none()


#: Kapan terakhir kali sisa demo tanpa sesi disapu (monotonic detik). Sapu ini
#: dipanggil dari jalur baca (`aktif()`), jadi ia dibatasi supaya tidak menjadi
#: DELETE di setiap request.
_sapu_terakhir = 0.0
SAPU_JEDA_DETIK = 10.0


async def sapu_tanpa_sesi(db: AsyncSession, *, jeda: float | None = None) -> int:
    """Hapus baris `origin='demo'` TANPA stempel saat tidak ada sesi aktif.

    Kenapa perlu: `kosongkan_bertanda()` hanya berjalan kalau ADA sesi yang
    ditutup. Baris demo yang lahir di luar sesi (jalur lama `/demo/seed`,
    `/demo/refresh`, seeder skrip) tidak punya stempel dan tidak ada sesi untuk
    ditutup — jadi ia hidup selamanya. Terukur 21 Okt 2026: 25 keputusan demo
    tanpa stempel masih tampil padahal semua sesi sudah `expired`, sehingga
    "tampilan default kosong" tidak terpenuhi.

    Batas aman: hanya `origin='demo'`. Baris kanonik (`origin='seed'`) tidak
    pernah disentuh — itu data kerja yang dipakai peta, KPI, dan suite backend.

    `jeda` (detik) menahan pemanggilan berulang dari jalur baca; `0` memaksa.
    Mengembalikan jumlah baris yang dihapus.
    """
    global _sapu_terakhir
    if not settings.demo_session_enforce:
        return 0
    sekarang_mono = time.monotonic()
    ambang = SAPU_JEDA_DETIK if jeda is None else jeda
    if ambang > 0 and sekarang_mono - _sapu_terakhir < ambang:
        return 0
    if await _sesi_aktif_terakhir(db) is not None:
        return 0
    _sapu_terakhir = sekarang_mono
    dihapus = 0
    for model in sorted(model_bersesi(), key=_urutan_hapus):
        if "origin" not in model.__table__.columns:
            continue
        hasil = await db.execute(
            delete(model).where(
                model.demo_session_id.is_(None),
                model.__table__.c.origin == "demo",
            )
        )
        dihapus += int(hasil.rowcount or 0)
    if dihapus:
        await db.commit()
    return dihapus


async def aktif(db: AsyncSession) -> DemoSession | None:
    """Sesi aktif, atau None. Sesi yang lewat waktu diakhiri di sini juga.

    Saat tidak ada sesi aktif, sisa baris demo tanpa stempel ikut disapu
    (`sapu_tanpa_sesi`, dijeda 10 detik) — ini yang membuat tampilan kembali
    kosong tanpa harus ada sesi yang ditutup lebih dulu.
    """
    sesi = await _sesi_aktif_terakhir(db)
    if sesi is None:
        await sapu_tanpa_sesi(db)
        return None
    if sesi.expires_at <= sekarang():
        await akhiri(db, sesi)
        return None
    set_sesi(sesi.id)
    return sesi


async def mulai(
    db: AsyncSession,
    *,
    menit: int | None = None,
    created_by: uuid.UUID | None = None,
    template_version: str | None = None,
    kosongkan: bool = True,
    mode: str = "replay",
    anchor: datetime | None = None,
) -> DemoSession:
    """Mulai sesi baru. Sesi lama (kalau ada) diakhiri lebih dulu — satu sesi aktif.

    `kosongkan=False` dipakai oleh `mulai_dengan_template`: template dibangun lebih
    dulu, jadi pengosongan di sini akan menghapus hasil build itu sendiri.

    `mode`/`anchor` (Fase 2 MG) menentukan jangkar EVALUASI sesi: `replay`
    memakai jangkar kanon historis (reproducible), `realtime` memakai waktu sesi
    dibuka. `dataset_version` diturunkan dari keduanya, bukan dikarang klien.
    """
    from app.services import decision_time

    mode_final = decision_time.mode_sah(mode)
    lama = await _sesi_aktif_terakhir(db)
    if lama is not None:
        await akhiri(db, lama)
    if settings.demo_session_enforce and kosongkan:
        # Sesi baru = data mulai dari nol. Ini juga mencegah tabrakan id
        # deterministik seed dengan sisa sesi lama (duplicate key batches_pkey).
        await kosongkan_kecuali(db, None)
    saat = sekarang()
    durasi = _menit_valid(menit, settings.demo_session_minutes)
    jangkar = anchor or decision_time.anchor_untuk(mode_final, saat=saat)
    sesi = DemoSession(
        status="active",
        started_at=saat,
        expires_at=saat + timedelta(minutes=durasi),
        anchor_now=saat,
        template_version=template_version,
        created_by=created_by,
        mode=mode_final,
        evaluation_anchor=jangkar,
        dataset_version=decision_time.dataset_version_untuk(mode_final, jangkar),
    )
    db.add(sesi)
    await db.commit()
    await db.refresh(sesi)
    set_sesi(sesi.id)
    return sesi


async def mulai_dengan_template(
    db: AsyncSession,
    *,
    menit: int | None = None,
    created_by: uuid.UUID | None = None,
    mode: str = "replay",
    anchor: datetime | None = None,
) -> tuple[DemoSession, dict[str, Any]]:
    """Bangun template demo DULU, buka sesi BELAKANGAN.

    Alasan (audit 21 Okt 2026, dua kali terukur): urutan lama — buat sesi, kosongkan
    semua tabel operasional, lalu bangun template — membuat kegagalan build
    meninggalkan sesi `active` dengan 15 tabel kosong. Klik berikutnya dibalas
    `created=false` (idempoten), jadi template tidak pernah dibangun ulang dan
    sistem tidak bisa pulih tanpa "Akhiri sesi".

    Dengan urutan ini: build gagal → tidak ada sesi baru, baris lama utuh, dan
    pemanggil menerima galat (router membalas 503 dengan pesan jujur). Klik ulang
    akan mencoba membangun lagi.
    """
    lama = await _sesi_aktif_terakhir(db)
    if lama is not None:
        await akhiri(db, lama)

    # Fase 7 MG: jangkar dihitung SEKALI di sini, lalu dipakai dua kali — untuk
    # membangun kasus (ID + waktu kejadian) dan untuk baris sesi. Kalau keduanya
    # menghitung sendiri (`anchor_untuk` dipanggil di dua tempat), sesi realtime
    # bisa berjangkar satu menit setelah data, dan `needed_by`/masa layak yang
    # dihitung dari jangkar itu tidak lagi cocok dengan sesi yang tampil di UI.
    from app.services import decision_time

    mode_final = decision_time.mode_sah(mode)
    jangkar = anchor or decision_time.anchor_untuk(mode_final)

    # Impor di dalam fungsi: hindari siklus services <-> seed saat modul dimuat.
    from app.seed.demo_template import build_into

    laporan = await build_into(
        db,
        purge=True,
        freeze=True,
        bersihkan_sisa=False,
        mode=mode_final,
        anchor=jangkar,
    )
    # Fase 10 MG: mode/anchor diteruskan ke pembuat sesi. Tanpa ini tombol
    # "Muat Demo Real-time" membangun template yang sama tetapi sesinya lahir
    # `replay` — dataset realtime dilaporkan sebagai kanon, dan tidak ada galat
    # yang menunjukkan kekeliruan itu.
    sesi = await mulai(
        db,
        menit=menit,
        created_by=created_by,
        kosongkan=False,
        mode=mode_final,
        anchor=jangkar,
    )
    return sesi, laporan


async def perpanjang(db: AsyncSession, *, menit: int = 30) -> DemoSession | None:
    """Tambah waktu sesi berjalan. ID sesi TIDAK berubah, data tidak disentuh."""
    sesi = await _sesi_aktif_terakhir(db)
    if sesi is None:
        return None
    if sesi.expires_at <= sekarang():
        await akhiri(db, sesi)
        return None
    batas = _batas_akhir(sesi.started_at)
    baru = min(sesi.expires_at + timedelta(minutes=_menit_valid(menit, 30)), batas)
    sesi.expires_at = baru
    await db.commit()
    await db.refresh(sesi)
    set_sesi(sesi.id)
    return sesi


async def akhiri(db: AsyncSession, sesi: DemoSession | None = None) -> DemoSession | None:
    """Tutup sesi + hapus baris ber-stempel sesi itu (perubahan hilang, sesuai permintaan)."""
    sesi = sesi or await _sesi_aktif_terakhir(db)
    if sesi is None:
        set_sesi(None)
        return None
    await kosongkan_bertanda(db)
    sesi.status = "expired"
    sesi.ended_at = sekarang()
    await db.commit()
    # Sisa demo yang lahir di luar sesi (tanpa stempel) juga dibersihkan, supaya
    # "Akhiri sesi" benar-benar kembali ke 0 baris demo. Dipanggil SESUDAH sesi
    # ditandai expired: penyapu itu menolak bekerja selama masih ada sesi aktif.
    await sapu_tanpa_sesi(db, jeda=0)
    await db.refresh(sesi)
    set_sesi(None)
    return sesi


async def tandai_sesi(db: AsyncSession, sesi_id: uuid.UUID) -> int:
    """Stempel SEMUA baris operasional tanpa sesi ke sesi ini.

    Diperlukan karena penyemai memakai `insert()` Core/bulk yang tidak melewati
    event flush. Dipanggil sekali sesudah penyemaian selesai.
    """
    ditandai = 0
    for model in model_bersesi():
        kriteria = model.demo_session_id.is_(None)
        # 21 Okt 2026: hanya baris DEMO yang boleh distempel. Sebelum ini
        # stempel massal ikut mengenai baris kanonik (`origin='seed'`) yang
        # lahir di tengah sesi, sehingga "Akhiri sesi" menghapus data kerja
        # (terukur: 78 batch + 2 keputusan kanonik). Model tanpa kolom origin
        # (tabel jembatan) tetap distempel karena barisnya memang lahir dari sesi.
        if "origin" in model.__table__.columns:
            kriteria = kriteria & (model.__table__.c.origin == "demo")
        hasil = await db.execute(
            update(model)
            .where(kriteria)
            .values(demo_session_id=sesi_id)
            .execution_options(synchronize_session=False)
        )
        ditandai += int(hasil.rowcount or 0)
    await db.commit()
    return ditandai


async def kosongkan_bertanda(db: AsyncSession) -> int:
    """Hapus baris milik sesi + baris DEMO tanpa stempel (mode sesi menyala).

    Dipakai saat sesi ditutup (tombol "Akhiri sesi") maupun saat sesi
    kedaluwarsa. Dua golongan yang dihapus:

    1. `demo_session_id IS NOT NULL` DAN `origin='demo'` — semua baris demo
       ber-stempel, termasuk sisa sesi lain. Ini yang menutup bug "sisa sesi
       lama" tanpa menyentuh template kanonik.
    2. `origin='demo'` DAN `demo_session_id IS NULL` — hanya saat
       `demo_session_enforce` menyala. Tanpa poin ini, data dari jalur lama
       (`POST /demo/seed`, `POST /demo/refresh`) yang lahir di luar sesi tidak
       pernah ikut terhapus: terukur 21 Okt 2026 — 25 keputusan demo tanpa
       stempel masih tampil padahal tidak ada sesi aktif, sehingga "akhiri sesi"
       tidak kembali ke 0 seperti aturan pemilik.

    Kenapa TIDAK menghapus semua baris tanpa stempel: baris kanonik `seed`
    (`origin='seed'`, bawaan kolom) adalah data kerja yang tidak pernah lahir
    dari sesi; menghapusnya membuat peta, KPI, dan 58 tes backend kehilangan
    data. Batas `origin='demo'` itulah yang membuat pembersihan ini aman.
    """
    dihapus = 0
    for model in sorted(model_bersesi(), key=_urutan_hapus):
        kriteria = model.demo_session_id.isnot(None)
        # Baris CETAKAN (template beku) sengaja TIDAK ikut dihapus: ia tidak
        # lahir dari sesi ini, dan provenance-nya (`origin='demo'`) justru harus
        # tetap ada setelah sesi berakhir (audit D-04).
        kriteria = kriteria & (model.demo_session_id != CETAKAN_ID)
        # Baris kanonik yang (karena data lama) terlanjur berstempel tidak ikut
        # dihapus: template `origin='seed'` harus selamat dari siklus demo.
        if "origin" in model.__table__.columns:
            kriteria = kriteria & (model.__table__.c.origin == "demo")
        hasil = await db.execute(delete(model).where(kriteria))
        dihapus += int(hasil.rowcount or 0)
        # Model tanpa kolom `origin` (mis. tabel jembatan) hanya kena aturan (1).
        if settings.demo_session_enforce and "origin" in model.__table__.columns:
            sisa = await db.execute(
                delete(model).where(
                    model.demo_session_id.is_(None),
                    model.__table__.c.origin == "demo",
                )
            )
            dihapus += int(sisa.rowcount or 0)
    await db.commit()
    return dihapus


async def kosongkan_kecuali(db: AsyncSession, simpan: uuid.UUID | None) -> int:
    """Hapus SEMUA baris operasional kecuali milik sesi `simpan` (None = semua).

    Kenapa "semua kecuali", bukan "yang tanpa stempel": sesi bisa saling
    menimpa (dua tab, klik ganda, penyemaian yang masih berjalan saat sesi
    diganti). Kalau pembersihan hanya menyasar stempel tertentu, sisa sesi lain
    tertinggal dan tetap terlihat — terukur 20 Okt 2026: 40 batch + 4 keputusan
    milik sesi yang sudah `expired` masih muncul setelah "Akhiri sesi".
    """
    dihapus = 0
    for model in sorted(model_bersesi(), key=_urutan_hapus):
        if simpan is None:
            hasil = await db.execute(delete(model))
        else:
            hasil = await db.execute(
                delete(model).where(
                    model.demo_session_id.is_(None)
                    | (model.demo_session_id != simpan)
                )
            )
        dihapus += int(hasil.rowcount or 0)
    if dihapus:
        # Data demo direset -> blok ledger lama menjadi arsip generasi sebelumnya.
        # Bloknya TIDAK dihapus (rantai hash harus tetap utuh); cakupan dihitung
        # per generasi. Lihat `ledger_service.bump_generation` (audit N3).
        from app.services.ledger_service import bump_generation

        await bump_generation(db)
    await db.commit()
    return dihapus


async def bersihkan_warisan(db: AsyncSession) -> int:
    """Alias lama: kosongkan semua baris operasional (default kosong)."""
    return await kosongkan_kecuali(db, None)


async def bersihkan(db: AsyncSession, sesi_id: uuid.UUID) -> int:
    """Hapus baris milik sesi ini, urut aman terhadap foreign key.

    Hanya baris ber-stempel yang dihapus — pemeriksaan "data lain aman" ada di
    tes (`test_demo_session.py`), bukan sekadar niat di komentar.
    """
    dihapus = 0
    for model in sorted(model_bersesi(), key=_urutan_hapus):
        hasil = await db.execute(
            delete(model).where(model.demo_session_id == sesi_id)
        )
        dihapus += int(hasil.rowcount or 0)
    if dihapus:
        # Data demo direset -> blok ledger lama menjadi arsip generasi sebelumnya.
        # Bloknya TIDAK dihapus (rantai hash harus tetap utuh); cakupan dihitung
        # per generasi. Lihat `ledger_service.bump_generation` (audit N3).
        from app.services.ledger_service import bump_generation

        await bump_generation(db)
    await db.commit()
    return dihapus


def _urutan_hapus(model: type[Base]) -> int:
    """Anak dulu, induk kemudian (receipts → batches, evidence → decisions)."""
    nama = model.__tablename__
    # Anak dulu: penerimaan & pengecualian pemasok merujuk decisions/batches
    # tanpa cascade (`supplier_exclusions.source_decision_id`), jadi harus
    # dihapus sebelum induknya — terukur 20 Okt 2026 (ForeignKeyViolationError).
    if nama in {
        "decision_evidence",
        "approvals",
        "agent_traces",
        "batch_receipts",
        "supplier_exclusions",
    }:
        return 0
    if nama in {"decisions", "batches"}:
        return 1
    return 2


# ── Penjaga ORM: stempel saat insert + saring saat baca ─────────────────────
# Dua-duanya HANYA aktif bila `settings.demo_session_enforce` menyala. Bawaan
# mati supaya 1.200+ tes backend yang menyemai tanpa sesi tetap sah.

_terpasang = False


def boleh_distempel(obj: Any) -> bool:
    """True bila `obj` adalah baris DEMO yang boleh menerima stempel sesi.

    Kenapa perlu (regresi 27 Okt 2026): penjaga `before_flush` dulu menstempel
    SETIAP objek baru, termasuk baris kanonik `origin='seed'` yang lahir di
    tengah sesi aktif. Jalur "Siapkan data demo" (`bangun_ulang`, dipanggil
    tombol refresh) membangun ulang template SAAT sesi berjalan, dan `load_seed`
    menulis snapshot kanonik lewat `merge()` (ORM) — terukur: 78 batch + 40 fakta
    pasokan + 7 keputusan ber-`origin='seed'` ikut berstempel sesi aktif.
    Invarian `verify/invariants.spec.json` ("baris kanonik tidak boleh
    berstempel") menolak keadaan itu, dan baris kanonik tampak seperti milik
    sesi padahal ia data kerja.

    Aturan: model TANPA kolom `origin` (tabel jembatan) tetap distempel karena
    barisnya memang lahir dari sesi. Model BER-kolom `origin` hanya distempel
    bila `origin == 'demo'`; `origin` kosong berarti default DB `'seed'`
    (kanonik) — kesimpulannya TIDAK distempel.
    """
    tabel = getattr(obj, "__table__", None)
    if tabel is None or "origin" not in tabel.columns:
        return True
    return getattr(obj, "origin", None) == "demo"


def pasang_penjaga() -> None:
    """Pasang stempel `before_flush` sekali per proses (idempoten).

    Catatan penting (20 Okt 2026): penyaringan baca lewat
    `with_loader_criteria` DIHAPUS. Alasannya empiris: banyak endpoint memilih
    kolom (`select(Batch.id, ...)`) atau memakai Core/bulk, sehingga kriteria
    ORM tidak konsisten — `/batches` menjawab 0 baris padahal 118 batch ada.
    Kosong-secara-default sekarang dijaga oleh SIKLUS DATA: baris tanpa stempel
    dibersihkan saat sesi mulai (dan saat startup), baris ber-stempel dihapus
    saat sesi berakhir. Itu juga yang diminta pemilik, dan tidak bergantung
    pada bentuk kueri masing-masing endpoint.
    """
    global _terpasang
    if _terpasang:
        return

    @event.listens_for(Session, "before_flush")
    def _stempel(session, _flush_context, _instances):  # type: ignore[no-untyped-def]
        # Dipasang di flush — bukan per model — supaya model yang ditambahkan
        # pada iterasi berikutnya otomatis ikut tanpa didaftar ulang.
        if not settings.demo_session_enforce:
            return
        sesi_id = sesi_sekarang()
        if sesi_id is None:
            return
        for obj in session.new:
            if not hasattr(obj, "demo_session_id") or obj.demo_session_id is not None:
                continue
            # Hanya baris DEMO. Lihat `boleh_distempel`: baris kanonik
            # (`origin='seed'` atau default DB) tidak boleh berstempel sesi.
            if not boleh_distempel(obj):
                continue
            obj.demo_session_id = sesi_id

    _terpasang = True


# Dipasang saat modul diimpor: event hanya bekerja bila flag menyala, jadi
# biayanya nol untuk tes/produksi, tetapi tidak bisa "lupa dipasang" di tes.
pasang_penjaga()


__all__ = [
    "akhiri",
    "aktif",
    "bersihkan",
    "boleh_distempel",
    "kosongkan_kecuali",
    "kunci_sesi",
    "bersihkan_warisan",
    "model_bersesi",
    "mulai",
    "pasang_penjaga",
    "perpanjang",
    "sekarang",
    "sesi_sekarang",
    "set_sesi",
    "status_payload",
    "tandai_sesi",
]
