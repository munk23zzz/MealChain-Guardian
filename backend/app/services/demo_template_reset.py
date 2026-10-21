"""Bangun ulang template demo dari dalam aplikasi (tanpa shell).

Kenapa ada: `Siapkan data demo` hanya menyemai ketika sesi BELUM berjalan
(`POST /demo/session/start` menolak menyemai ulang sesi yang sama). Saat
geladi berulang, operator butuh cara mengembalikan data ke keadaan awal TANPA
menutup sesi dan TANPA membuka terminal. Itulah satu-satunya tugas modul ini.

Aturan yang dijaga:
- **Satu proses pada satu waktu.** Bangun ulang mem-purge seluruh baris
  operasional; dua permintaan bersamaan akan saling menghapus. Kunci dipegang
  di proses, dicoba tanpa menunggu, dan permintaan kedua ditolak `Sibuk`
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


class Sibuk(RuntimeError):
    """Bangun ulang lain sedang berjalan di proses ini."""


_KUNCI = asyncio.Lock()


async def bangun_ulang(db: AsyncSession) -> dict:
    """Bangun ulang template demo; kembalikan ringkasan terukur.

    `asyncio.Lock.locked()` lalu `acquire()` tanpa `await` di antaranya aman:
    event loop tidak bisa menyisipkan tugas lain di antara keduanya, jadi tidak
    ada dua pemanggil yang sama-sama lolos.
    """
    if _KUNCI.locked():
        raise Sibuk("bangun ulang sedang berjalan")
    await _KUNCI.acquire()
    mulai = time.monotonic()
    try:
        # Sesi aktif dulu: lihat komentar `pastikan_sesi` — tanpa itu penyapu di
        # proses aplikasi bisa menghapus baris demo yang baru lahir.
        await pastikan_sesi(db)
        laporan = await build_into(db, purge=True, freeze=True, bersihkan_sisa=False)
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
    }
