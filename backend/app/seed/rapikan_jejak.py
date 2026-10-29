"""Rapikan data jejak agent supaya Agent Activity Log masuk akal.

Kenapa ada (audit 29 Okt 2026). Tiga cacat nyata di data hasil penyemai:

1. **Langkah mendahului keputusan.** 81 dari 109 baris `agent_traces` punya
   `step_at` sebelum `created_at` keputusannya; 39 dari 48 keputusan terkena
   seluruh langkahnya, paling jauh 25 jam. Di layar ini terbaca sebagai jejak
   yang baru saja terjadi, padahal kejadiannya "sebelum keputusan ada" — mustahil.
2. **Kedaluwarsa sebelum lahir.** 6 keputusan `rejected` punya
   `expires_at < created_at` (30–60 menit lebih awal).
3. Keputusan tanpa langkah awal (LEARN saja) TIDAK diperbaiki di sini: menambah
   baris berarti mengarang jejak. Yang dilakukan halaman: menyebutnya apa adanya.

Aturan perbaikan bersifat deterministik dan tidak menghapus baris: urutan langkah
dipertahankan, hanya waktunya digeser ke setelah keputusan dibuat.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Jarak antar langkah sesudah dirapikan (detik) — cukup rapat agar tetap
#: terbaca sebagai satu rangkaian, cukup lebar agar urutannya stabil.
JEDA_DETIK = 120


def jadwal_ulang_jejak(
    langkah: list[tuple[str, datetime]],
    lahir: datetime,
    jeda_detik: int = JEDA_DETIK,
) -> dict[str, datetime] | None:
    """Peta `id → step_at baru`, atau `None` bila tidak ada yang perlu diubah.

    `langkah` = daftar (id, step_at) yang SUDAH urut menurut step_at. Semua
    langkah diletakkan sesudah `lahir` dengan jarak tetap, sehingga urutan
    aslinya tetap terbaca dan tidak ada langkah yang mendahului keputusan.
    """
    if not langkah:
        return None
    if all(step >= lahir for _, step in langkah):
        return None
    return {
        kunci: lahir + timedelta(seconds=jeda_detik * (i + 1))
        for i, (kunci, _) in enumerate(langkah)
    }


async def rapikan_jejak(session: AsyncSession) -> dict:
    """Jalankan perbaikan (1) dan (2). Aman dijalankan berulang."""
    baris = (
        await session.execute(
            text(
                "SELECT t.id, t.decision_id, t.step_at, d.created_at "
                "FROM agent_traces t JOIN decisions d ON d.id = t.decision_id "
                "ORDER BY t.decision_id, t.step_at, t.id"
            )
        )
    ).all()

    per_keputusan: dict = {}
    for id_, decision_id, step_at, created_at in baris:
        per_keputusan.setdefault(decision_id, {"lahir": created_at, "langkah": []})
        per_keputusan[decision_id]["langkah"].append((id_, step_at))

    digeser = 0
    for data in per_keputusan.values():
        baru = jadwal_ulang_jejak(data["langkah"], data["lahir"])
        if not baru:
            continue
        for kunci, waktu in baru.items():
            await session.execute(
                text("UPDATE agent_traces SET step_at = :w WHERE id = :i"),
                {"w": waktu, "i": kunci},
            )
            digeser += 1

    # Kedaluwarsa sebelum lahir: pertahankan keadaan "sudah lewat" dengan
    # memundurkan created_at, bukan memajukan expires_at — status `rejected`
    # pada baris-baris ini memang berarti tenggatnya sudah lewat.
    hasil_kedaluwarsa = await session.execute(
        text(
            "UPDATE decisions SET created_at = expires_at - interval '60 minutes' "
            "WHERE expires_at < created_at"
        )
    )
    await session.commit()
    return {
        "langkah_digeser": digeser,
        "keputusan_kedaluwarsa_diperbaiki": int(getattr(hasil_kedaluwarsa, "rowcount", 0) or 0),
        "keputusan_diperiksa": len(per_keputusan),
    }


async def _main() -> None:
    from app.db import create_engine, create_session_maker
    from app.seed.seed_data import _seed_database_url

    engine = create_engine(_seed_database_url())
    try:
        maker = create_session_maker(engine)
        async with maker() as session:
            hasil = await rapikan_jejak(session)
        print(f"rapikan_jejak: {hasil}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
