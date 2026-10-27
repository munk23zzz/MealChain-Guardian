"""Pintu pemeliharaan ledger untuk tes (Fase 11 MG, migrasi 042).

Trigger `prevent_ledger_mutation()` menolak `UPDATE`/`DELETE`/`TRUNCATE` pada
`ledger_blocks` untuk SEMUA role — termasuk pemilik tabel. Itu perilaku produk
yang diinginkan, tetapi beberapa tes memang perlu memangkas blok yang ia buat
sendiri (membersihkan ekor rantai di DB bersama, atau sengaja merusak hash untuk
membuktikan deteksi manipulasi).

Tes semacam itu harus menyatakan niatnya secara eksplisit, dengan dua syarat
yang sama seperti prosedur admin yang disetujui:

1. `SET LOCAL mealchain.ledger_maintenance = 'on'` di dalam transaksi yang sama; dan
2. sesi berjalan sebagai anggota `mealchain_migrator` (role tes = pemilik tabel;

   role aplikasi `mealchain_app` TIDAK memenuhi syarat ini).

Tanpa pembukaan pintu, pernyataan itu gagal dengan pesan `ledger_append_only`.
Jangan menambahkan `TRUNCATE`/`DELETE` "diam-diam" tanpa memakai helper ini:
kalau sebuah tes butuh memutasi riwayat, alasannya harus tertulis di tesnya.
"""

from __future__ import annotations

from sqlalchemy import text

#: GUC yang harus dinyatakan sesi sebelum memutasi `ledger_blocks`.
GUC = "mealchain.ledger_maintenance"


def buka_pintu(conn) -> None:
    """Aktifkan pintu pemeliharaan pada transaksi SINKRON yang sedang berjalan."""
    conn.execute(text(f"SET LOCAL {GUC} = 'on'"))


async def buka_pintu_async(db) -> None:
    """Aktifkan pintu pemeliharaan pada sesi ASYNC yang sedang berjalan."""
    await db.execute(text(f"SET LOCAL {GUC} = 'on'"))
