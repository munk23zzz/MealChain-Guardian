"""Pengelola mode database: DEFAULT (referensi saja) vs DEMO (data lengkap).

Dipakai dari akar repo:

    bash scripts/db-mode.sh status
    bash scripts/db-mode.sh init-default
    bash scripts/db-mode.sh init-demo [--refresh]
    bash scripts/db-mode.sh reset-demo --yes

Atau langsung di kontainer:

    docker compose exec -T backend python -m app.seed.db_mode status

Definisi mode (dibaca dari ISI database, bukan dari ingatan operator):

* **DEFAULT** — schema lengkap + data referensi/master saja (komoditas, lokasi
  SPPG, akun RBAC). Tabel bisnis kosong, jadi *empty state* frontend benar.
* **DEMO** — DEFAULT + dataset demo penuh (kanonik + deret waktu + aktivitas +
  kasus lengkap). Semua baris bisnis bertanda `origin='demo'`.

Pemilihan lewat environment `DB_MODE` (default|demo) untuk keputusan aplikasi,
tetapi perintah di bawah yang benar-benar MENGISI database. `status` melaporkan
bila keduanya tidak cocok.

Pengaman:
* `reset-demo` menolak jalan bila host database bukan lokal (allowlist) atau
  `DB_MODE_ENV=production`; tanpa `--yes` ia hanya menampilkan rencana.
* Semua perintah idempoten: `init-*` memakai id deterministik (`stable_uuid`),
  `reset-demo` menghapus berdasarkan penanda demo, bukan menebak.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db import create_session_maker
from app.models import (
    AgentTrace,
    Approval,
    Batch,
    BatchReceipt,
    Commodity,
    Decision,
    DecisionEvidence,
    DeliveryEvent,
    DemandRecord,
    DemoSession,
    DisposalEvent,
    Location,
    MenuPlan,
    PriceSignal,
    RoadRoute,
    SapMockMaterialStock,
    SapMockPurchaseOrder,
    Supplier,
    SupplierExclusion,
    SupplyRecord,
    User,
)

HOST_LOKAL = {"postgres", "localhost", "127.0.0.1", "::1", "db"}
# Tabel referensi: TIDAK pernah disentuh reset-demo.
TABEL_REFERENSI = ("commodities", "locations", "users")

# Urutan hapus: anak dulu, induk belakangan (FK tanpa CASCADE ikut aman).
URUTAN_HAPUS = (
    BatchReceipt,
    DecisionEvidence,
    AgentTrace,
    Approval,
    SapMockPurchaseOrder,
    SapMockMaterialStock,
    SupplierExclusion,
    DeliveryEvent,
    DisposalEvent,
    MenuPlan,
    PriceSignal,
    DemandRecord,
    SupplyRecord,
    RoadRoute,
    Batch,
    Decision,
    Supplier,
    DemoSession,
)

# Tabel yang dihitung untuk laporan status (referensi + bisnis).
TABEL_LAPORAN = (
    Commodity,
    Location,
    User,
    Supplier,
    Batch,
    BatchReceipt,
    Decision,
    Approval,
    DecisionEvidence,
    AgentTrace,
    SupplyRecord,
    DemandRecord,
    PriceSignal,
    MenuPlan,
    DeliveryEvent,
    DisposalEvent,
    SupplierExclusion,
    SapMockPurchaseOrder,
    SapMockMaterialStock,
    RoadRoute,
    DemoSession,
)

REFERENSI_KANONIK = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------- bantuan
def _host_db() -> str:
    return (urlparse(settings.database_url).hostname or "").lower()


def _pengaman_demo(aksi: str, konfirmasi: bool) -> None:
    host = _host_db()
    if host not in HOST_LOKAL:
        raise SystemExit(
            f"DITOLAK: {aksi} hanya boleh di database lokal/demo, host terbaca '{host}'."
        )
    if os.environ.get("DB_MODE_ENV", "").lower() == "production":
        raise SystemExit(f"DITOLAK: DB_MODE_ENV=production, {aksi} tidak dijalankan.")
    if not konfirmasi:
        raise SystemExit(
            f"{aksi} akan menghapus SELURUH baris bisnis di {settings.database_url.split('@')[-1]} "
            "(tabel referensi tetap). Jalankan ulang dengan --yes."
        )


async def _hitung(session) -> dict[str, int]:
    hasil: dict[str, int] = {}
    for model in TABEL_LAPORAN:
        jumlah = await session.scalar(select(func.count()).select_from(model))
        hasil[model.__tablename__] = int(jumlah or 0)
    return hasil


async def _hitung_demo(session) -> dict[str, int]:
    """Baris bertanda demo per tabel (kolom `origin` atau `demo_session_id`)."""
    hasil: dict[str, int] = {}
    for model in TABEL_LAPORAN:
        kolom = model.__table__.columns
        kriteria = None
        if "origin" in kolom:
            kriteria = kolom["origin"] == "demo"
        elif "demo_session_id" in kolom:
            kriteria = kolom["demo_session_id"].isnot(None)
        if kriteria is None:
            continue
        jumlah = await session.scalar(select(func.count()).select_from(model).where(kriteria))
        hasil[model.__tablename__] = int(jumlah or 0)
    return hasil


def _mode_dari_isi(jumlah: dict[str, int]) -> str:
    bisnis = [t for t in jumlah if t not in TABEL_REFERENSI]
    return "demo" if any(jumlah[t] for t in bisnis) else "default"


# ------------------------------------------------------------------- perintah
async def cmd_status(session) -> dict:
    jumlah = await _hitung(session)
    demo = await _hitung_demo(session)
    isi = _mode_dari_isi(jumlah)
    # `mode_env` hanya dilaporkan bila operator MEMANG menyetel DB_MODE.
    # Tanpa itu, membandingkan dengan nilai bawaan "default" membuat database
    # DEMO yang sehat terbaca "cocok: false" hanya karena skrip dijalankan
    # tanpa variabel — peringatan palsu yang melatih orang mengabaikan status.
    env = (os.environ.get("DB_MODE") or "").strip().lower() or None
    from sqlalchemy import text

    alembic = await session.scalar(text("select version_num from alembic_version"))
    return {
        "mode_isi": isi,
        "mode_env": env,
        "cocok": (None if env is None else isi == env),
        "alembic": alembic,
        "host": _host_db(),
        "jumlah": jumlah,
        "bertanda_demo": demo,
    }


async def _alembic_upgrade_head() -> None:
    from alembic import command
    from alembic.config import Config

    akar = Path(__file__).resolve().parents[2]  # backend/
    cfg = Config(str(akar / "alembic.ini"))
    cfg.set_main_option("script_location", str(akar / "alembic"))
    await asyncio.to_thread(command.upgrade, cfg, "head")


async def _tabel_bisnis() -> list[str]:
    """Semua tabel bisnis menurut metadata (bukan daftar laporan yang mungkin bolong)."""
    from app.db import Base

    return sorted(
        t
        for t in Base.metadata.tables
        if t not in TABEL_REFERENSI and t != "alembic_version"
    )


async def _normalisasi_referensi(session) -> bool:
    """Samakan id referensi ke `stable_uuid(nama)` bila database hanya referensi.

    Ditemukan 22 Okt 2026: database demo lama menyimpan komoditas/lokasi dengan
    UUID acak dari versi awal, sehingga `load_seed` gagal
    (`duplicate key value violates unique constraint "commodities_name_key"`).
    Karena mode DEFAULT tidak punya baris bisnis, baris referensi aman dibuang
    dan ditanam ulang dengan id kanonik. Bila ada baris bisnis, jangan menyentuh
    apa pun — laporkan agar operator membangun ulang database demo.
    """
    # Deteksi "database hanya referensi" HARUS memakai seluruh tabel bisnis.
    # Versi pertama memakai `_hitung` (subset tabel laporan); tabel yang tidak
    # terdaftar lolos dari pemeriksaan, penghapusan referensi berjalan, dan FK
    # CASCADE ikut menghapus data bisnis — persis kejadian 22 Okt 2026.
    from sqlalchemy import text as _text

    for tabel in await _tabel_bisnis():
        ada = await session.scalar(_text(f'select count(*) from "{tabel}"'))
        if int(ada or 0) > 0:
            return False
    await session.execute(delete(User))
    await session.execute(delete(Location))
    await session.execute(delete(Commodity))
    await session.commit()
    return True


async def cmd_init_default(session) -> dict:
    from app.seed.reference import seed_reference

    dinormalisasi = await _normalisasi_referensi(session)
    jumlah = await seed_reference(session)
    return {
        "langkah": "init-default",
        "referensi_dinormalisasi": dinormalisasi,
        "ditambah": jumlah,
    }


async def cmd_init_demo(session, refresh: bool = False) -> dict:
    """Bangun dataset DEMO penuh. Idempoten (aman dijalankan berulang)."""
    from app.seed.demo_activity import (
        seed_demo_activity,
        seed_demo_completed_decisions,
        seed_demo_daily_prices,
    )
    from app.seed.demo_extra import build_demo_extra
    from app.seed.reference import seed_reference
    from app.seed.seed_data import load_seed
    from app.seed.timeseries import generate_timeseries

    hasil: dict[str, object] = {"langkah": "init-demo", "refresh": refresh}

    # 22 Okt 2026: baris demo yang menempati kunci alami baris kanonik harus
    # dibuang lebih dulu. `load_seed` memakai `merge()` per ID, jadi setelah
    # jalur tombol "Siapkan data demo" (kunci alami sama, ID berbeda) merge
    # jatuh ke INSERT dan menabrak `uq_supply_records_loc_com_time_source —
    # init-demo berhenti exit 1 di tengah jalan. Hanya baris BERTANDA demo pada
    # detik referensi kanonik yang dibuang; sisa data demo tidak disentuh dan
    # deret waktunya dibangun ulang di langkah 2.
    from app.models import DemandRecord, PriceSignal, SupplyRecord

    bentrok = {}
    for model in (SupplyRecord, DemandRecord, PriceSignal):
        # supply/demand: cukup baris ber-stempel demo. price_signals: SEMUA baris
        # pada detik referensi (kunci uniknya tidak memuat `origin`, jadi baris
        # kanonik versi template pun menabrak `uq_price_signals_reference`).
        kondisi = [model.recorded_at == REFERENSI_KANONIK]
        if model is not PriceSignal:
            kondisi.append(model.origin == "demo")
        r = await session.execute(delete(model).where(*kondisi))
        bentrok[model.__tablename__] = int(r.rowcount or 0)
    await session.commit()
    hasil["bentrok_kanonik_dibuang"] = {k: v for k, v in bentrok.items() if v}

    hasil["referensi_dinormalisasi"] = await _normalisasi_referensi(session)
    hasil["referensi"] = await seed_reference(session)
    await session.commit()

    # 1. Dataset kanonik (supplier, batch, PO impor, fakta P6). Reference time
    #    tetap 8 Okt 2026 supaya isi kanonik deterministik; deret waktu di
    #    langkah 2 yang membuat data terasa "hari ini".
    # Akun demo sudah ditanam `seed_reference` (password yang sama dengan seed
    # kanonik); `ensure_demo_users()` tidak dipakai karena memanggil asyncio.run
    # di dalam event loop yang sedang berjalan.
    hasil["kanonik"] = await load_seed(REFERENSI_KANONIK)
    # 22 Okt 2026: init-demo sempat menghasilkan tabel kosong tanpa pesan apa pun
    # (supply 5.200 -> 0 setelah run kedua). Tanpa jejak angka per langkah,
    # penyebabnya hanya bisa ditebak. Simpan hitungan sesudah tiap langkah.
    jejak: dict[str, dict[str, int]] = {}

    async def _jejak(nama: str) -> None:
        j = await _hitung(session)
        jejak[nama] = {
            k: j.get(k, 0)
            for k in ("supply_records", "demand_records", "batches", "decisions")
        }

    await _jejak("sesudah_kanonik")

    # 2. Deret waktu relatif hari ini + aktivitas demo.
    hasil["deret"] = await generate_timeseries()
    await _jejak("sesudah_deret")
    now = datetime.now(timezone.utc)
    hasil["aktivitas"] = await seed_demo_activity(session, now)
    hasil["keputusan_selesai"] = await seed_demo_completed_decisions(session, now)
    hasil["harga_harian"] = await seed_demo_daily_prices(session, now)

    # 3. Pelengkap cakupan matriks (semua enum, semua status, kasus ekstrem).
    await _jejak("sesudah_aktivitas")
    hasil["pelengkap"] = await build_demo_extra(session, now)
    await _jejak("sesudah_pelengkap")

    # 4. TIDAK menandai ulang baris kanonik menjadi `origin='demo'`.
    #    Alasan (22 Okt 2026): `_collect_baselines()` di generator membaca baris
    #    `origin='seed'` sebagai jangkar. Menandai ulang semuanya membuat run
    #    KEDUA melihat "tidak ada jangkar" -> planned=0, dan itu sudah terbukti
    #    membuat deret waktu runtuh tanpa pesan galat. Reset tetap tepat sasaran
    #    karena `reset-demo` hanya jalan di DB demo (dijaga) dan menghapus seluruh
    #    tabel bisnis; sampah penanda tidak sepadan dengan risikonya.
    hasil["ditandai_demo"] = {"dilewati": True, "alasan": "jangkar seed dipertahankan"}
    hasil["jejak"] = jejak
    await session.commit()
    hasil["status"] = await cmd_status(session)
    return hasil


async def _tandai_demo(session) -> dict[str, int]:
    """`origin='seed'` -> `'demo'` untuk tabel bisnis yang punya kolom origin.

    Baris kanonik memang data bisnis tiruan; di mode DEMO ia ikut harus bisa
    dibersihkan. Tabel referensi tidak punya kolom origin dan tidak disentuh.
    """
    from sqlalchemy import update

    hasil: dict[str, int] = {}
    for model in URUTAN_HAPUS:
        if "origin" not in model.__table__.columns:
            continue
        r = await session.execute(
            update(model)
            .where(model.__table__.c.origin == "seed")
            .values(origin="demo")
        )
        hasil[model.__tablename__] = int(r.rowcount or 0)
    return hasil


async def cmd_reset_demo(session, konfirmasi: bool = False) -> dict:
    _pengaman_demo("reset-demo", konfirmasi)
    # Kutipan harga yang lahir dari PO demo ikut hilang bersama PO-nya; kalau
    # tidak, metrik Price Deviation memuat angka yang tidak bisa ditelusuri.
    from app.services.settlement import bersihkan_kutipan_tanpa_po

    await bersihkan_kutipan_tanpa_po(session)
    sebelum = await _hitung(session)
    dihapus: dict[str, int] = {}
    for model in URUTAN_HAPUS:
        r = await session.execute(delete(model))
        dihapus[model.__tablename__] = int(r.rowcount or 0)
    await session.commit()
    sesudah = await _hitung(session)
    return {
        "langkah": "reset-demo",
        "dihapus": dihapus,
        "sebelum": sebelum,
        "sesudah": sesudah,
        "mode_isi": _mode_dari_isi(sesudah),
    }


# ----------------------------------------------------------------------- main
PERINTAH = {
    "status": "tampilkan mode aktif, revisi alembic, dan jumlah baris",
    "init-default": "schema + data referensi saja (tanpa data bisnis)",
    "init-demo": "schema + referensi + dataset demo penuh",
    "reset-demo": "hapus baris demo, kembali ke mode DEFAULT",
}


async def _jalankan(args) -> dict:
    engine = create_async_engine(settings.database_url)
    try:
        maker = create_session_maker(engine)
        if args.perintah in {"init-default", "init-demo"}:
            await _alembic_upgrade_head()
        async with maker() as session:
            if args.perintah == "status":
                return await cmd_status(session)
            if args.perintah == "init-default":
                hasil = await cmd_init_default(session)
                hasil["status"] = await cmd_status(session)
                return hasil
            if args.perintah == "init-demo":
                return await cmd_init_demo(session, refresh=args.refresh)
            if args.perintah == "reset-demo":
                return await cmd_reset_demo(session, konfirmasi=args.yes)
        raise SystemExit(f"perintah tidak dikenal: {args.perintah}")
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="db-mode",
        description="Kelola mode database MealChain Guardian (DEFAULT / DEMO).",
    )
    parser.add_argument("perintah", choices=sorted(PERINTAH))
    parser.add_argument(
        "--yes", action="store_true", help="konfirmasi untuk reset-demo"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="bangun ulang deret demo relatif hari ini (default: tetap idempoten)",
    )
    args = parser.parse_args(argv)
    hasil = asyncio.run(_jalankan(args))
    print(json.dumps(hasil, default=str, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
