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
import json
import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Jarak antar langkah sesudah dirapikan (detik) — cukup rapat agar tetap
#: terbaca sebagai satu rangkaian, cukup lebar agar urutannya stabil.
JEDA_DETIK = 120

#: Langkah yang wajib ada karena keadaan keputusan itu sendiri.
LANGKAH_AWAL = "DETECT"
LANGKAH_EKSEKUSI = "ACT"
STATUS_EKSEKUSI = "executed"


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


def langkah_pelengkap(status: str, langkah_ada: Iterable[str]) -> list[str]:
    """Langkah wajib yang BELUM ada, menurut keadaan keputusan itu sendiri.

    Sebab ada (audit lanjutan 29 Okt 2026, terukur di data demo):

    - 10 keputusan tidak punya baris `DETECT`. Akibatnya panel jejak menulis
      "tidak ada langkah awal" dan Decision Time kehilangan titik kirinya —
      padahal keputusannya jelas ada dan punya langkah sesudahnya.
    - 1 keputusan berstatus `executed` tidak punya baris `ACT`. Statusnya
      mengklaim sudah dieksekusi (approval-nya juga ada), tetapi jejaknya
      tidak mencatat eksekusi sama sekali.

    Yang dilengkapi HANYA langkah yang implied oleh fakta yang sudah tercatat:
    keputusan yang lahir berarti pernah ada DETECT, dan status `executed`
    berarti eksekusi sudah terjadi. Langkah lain tidak pernah dikarang —
    keputusan yang belum dieksekusi tidak diberi ACT.
    """
    ada = {str(item) for item in langkah_ada}
    perlu: list[str] = []
    if LANGKAH_AWAL not in ada:
        perlu.append(LANGKAH_AWAL)
    if status == STATUS_EKSEKUSI and LANGKAH_EKSEKUSI not in ada:
        perlu.append(LANGKAH_EKSEKUSI)
    return perlu


async def lengkapi_jejak(session: AsyncSession) -> dict:
    """Tambal langkah yang hilang karena keadaan keputusannya (idempoten).

    Tidak menghapus dan tidak mengubah baris lama; setiap baris baru ditandai
    "dibuat oleh template demo" supaya asalnya terbaca di panel jejak.
    """
    baris = (
        await session.execute(
            text(
                "SELECT d.id, d.status, d.created_at, "
                "COALESCE(array_agg(t.step_name) FILTER (WHERE t.step_name IS NOT NULL), '{}') "
                "FROM decisions d LEFT JOIN agent_traces t ON t.decision_id = d.id "
                "GROUP BY d.id, d.status, d.created_at"
            )
        )
    ).all()

    ditambah: list[str] = []
    for decision_id, status, lahir, langkah_ada in baris:
        perlu = langkah_pelengkap(status, langkah_ada or [])
        if not perlu:
            continue
        # Langkah pelengkap diletakkan rapat setelah keputusan lahir, sebelum
        # langkah lain yang sudah ada (yang sudah dirapikan oleh fungsi di atas).
        for urutan, nama in enumerate(perlu):
            jejak_id = uuid.uuid5(uuid.UUID(str(decision_id)), f"pelengkap:{nama}")
            await session.execute(
                text(
                    "INSERT INTO agent_traces "
                    "(id, decision_id, step_name, agent_name, tool_called, "
                    " input_summary, output_summary, step_at) "
                    "VALUES (:id, :d, :step, NULL, NULL, "
                    "        CAST(:masuk AS jsonb), CAST(:keluar AS jsonb), :kapan) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": jejak_id,
                    "d": decision_id,
                    "step": nama,
                    "masuk": json.dumps({"pelengkap": True}),
                    "keluar": json.dumps(
                        {
                            "catatan": (
                                f"Langkah {nama} dilengkapi dari keadaan keputusan "
                                "(dibuat oleh template demo)."
                            )
                        }
                    ),
                    "kapan": (lahir or datetime.now(timezone.utc))
                    + timedelta(seconds=30 * (urutan + 1)),
                },
            )
            ditambah.append(nama)
    await session.commit()
    return {
        "langkah_ditambah": len(ditambah),
        "rincian": {
            "DETECT": ditambah.count("DETECT"),
            "ACT": ditambah.count("ACT"),
        },
    }


async def rapikan_jejak(session: AsyncSession) -> dict:
    """Jalankan perbaikan (1) dan (2), lalu lengkapi langkah wajib (3). Aman diulang."""
    pelengkap = await lengkapi_jejak(session)
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
        "langkah_pelengkap": pelengkap,
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
