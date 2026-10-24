"""Bangun ulang template demo dari dalam aplikasi (tanpa shell).

Kenapa ada: `Siapkan data demo` hanya menyemai ketika sesi BELUM berjalan
(`POST /demo/session/start` menolak menyemai ulang sesi yang sama). Saat
geladi berulang, operator butuh cara mengembalikan data ke keadaan awal TANPA
menutup sesi dan TANPA membuka terminal. Itulah satu-satunya tugas modul ini.

Aturan yang dijaga:
- **Satu proses pada satu waktu.** Bangun ulang mem-purge seluruh baris
  operasional; dua permintaan bersamaan akan saling menghapus. Kunci dipegang
  di proses, dicoba tanpa menunggu, dan permintaan kedua ditolak `SibukError`
  (bukan diantrikan diam-diam sampai klien kehabisan waktu).
- **Sesi tidak disentuh.** Fungsi ini tidak memanggil `mulai/akhiri`; jendela
  waktu yang sedang berjalan tetap berjalan, hanya isinya yang dibangun ulang.
- **Tidak mengarang hasil.** Yang dikembalikan adalah hitungan yang dibaca
  ulang dari database sesudah commit (`hitung`), bukan angka yang disusun
  ulang dari parameter.
"""

from __future__ import annotations

import asyncio
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.seed.demo_template import build_into, pastikan_sesi


async def _bangun_deret() -> dict:
    """Deret waktu demo (dibangun ulang sesudah template)."""
    from app.seed.timeseries import generate_timeseries

    return await generate_timeseries()


async def _lengkapi_aktivitas(db: AsyncSession, sekarang) -> dict:
    """Aktivitas hari ini + keputusan selesai + harga harian."""
    from app.seed.demo_activity import (
        seed_demo_activity,
        seed_demo_completed_decisions,
        seed_demo_daily_prices,
    )

    hasil = {
        "aktivitas": await seed_demo_activity(db, sekarang),
        "keputusan_selesai": await seed_demo_completed_decisions(db, sekarang),
        "harga_harian": await seed_demo_daily_prices(db, sekarang),
    }
    return hasil


async def _lengkapi_cakupan(db: AsyncSession, sekarang) -> dict:
    """Pelengkap cakupan matriks (semua enum/status, kasus ekstrem)."""
    from app.seed.demo_extra import build_demo_extra

    return await build_demo_extra(db, sekarang)


class SibukError(RuntimeError):
    """Bangun ulang lain sedang berjalan di proses ini."""


_KUNCI = asyncio.Lock()


async def bangun_ulang(db: AsyncSession) -> dict:
    """Bangun ulang template demo; kembalikan ringkasan terukur.

    `asyncio.Lock.locked()` lalu `acquire()` tanpa `await` di antaranya aman:
    event loop tidak bisa menyisipkan tugas lain di antara keduanya, jadi tidak
    ada dua pemanggil yang sama-sama lolos.
    """
    if _KUNCI.locked():
        raise SibukError("bangun ulang sedang berjalan")
    await _KUNCI.acquire()
    mulai = time.monotonic()
    try:
        # Sesi aktif dulu: lihat komentar `pastikan_sesi` — tanpa itu penyapu di
        # proses aplikasi bisa menghapus baris demo yang baru lahir.
        await pastikan_sesi(db)
        laporan = await build_into(db, purge=True, freeze=True, bersihkan_sisa=False)
        await db.commit()
        # 22 Okt 2026: `build_into` mem-purge seluruh baris demo lalu membangun
        # ulang template. Tanpa langkah ini, data pelengkap cakupan (semua
        # decision_type/status, penerimaan menunggu, karantina, eksklusi, PO
        # dari keputusan) HILANG setiap kali tombol "Siapkan data demo" ditekan —
        # terukur: 20 PO demo -> 12, penerimaan 5 -> 0. Builder pelengkap
        # idempoten, jadi aman dipanggil sesudah template.
        # Deret waktu + aktivitas juga lahir dari jalur demo dan ikut ter-purge
        # oleh `build_into`. Tanpa langkah ini, setelah menekan "Siapkan data
        # demo" grafik dan KPI kosong (terukur: supply_records 5.200 -> 40,
        # PO demo 20 -> 12, penerimaan 5 -> 0). Tiap langkah dipisah sebagai
        # helper modul supaya tes bisa memalsukannya tanpa DB sungguhan.
        from datetime import datetime, timezone

        laporan["deret"] = await _bangun_deret()
        sekarang = datetime.now(timezone.utc)
        laporan.update(await _lengkapi_aktivitas(db, sekarang))
        laporan["pelengkap"] = await _lengkapi_cakupan(db, sekarang)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        _KUNCI.release()
    return {
        "durasi_detik": round(time.monotonic() - mulai, 1),
        "hitung": laporan.get("hitung") or {},
        "kasus": laporan.get("kasus") or {},
        "karantina": laporan.get("karantina") or {},
        "penerimaan": laporan.get("penerimaan") or {},
        "eksklusi": laporan.get("eksklusi") or {},
        "bukti": laporan.get("bukti") or {},
        # 22 Okt 2026: langkah pelengkap yang membuat tombol "Siapkan data demo"
        # tetap menghasilkan dataset lengkap (deret + aktivitas + cakupan).
        "deret": laporan.get("deret") or {},
        "aktivitas": laporan.get("aktivitas") or {},
        "keputusan_selesai": laporan.get("keputusan_selesai") or {},
        "harga_harian": laporan.get("harga_harian") or {},
        "pelengkap": laporan.get("pelengkap") or {},
    }
