"""Siapa PEMILIK baris demo — resolusi sesi untuk penulis, bukan untuk tampilan.

Masalah yang ditutup modul ini (Fase 2 MG): sebelum ada sesi sebagai pemilik,
penulis demo memakai "sesi yang sedang aktif" (`demo_session.sesi_sekarang`,
diisi `aktif()`). Itu benar selama hanya ada satu sesi, dan salah begitu ada
dua: menyemai sesi kedua menstempel ulang baris sesi pertama, lalu reset sesi
pertama ikut menghapus data sesi kedua.

Aturan yang dipegang:

1. **Pemilik datang dari permintaan, bukan dari "sesi terbaru".** `POST
   /demo/seed` menerima `demo_session`; sesi itu yang memiliki semua baris yang
   lahir dari permintaan itu — termasuk baris `rejected` yang dibuat lebih dulu.
2. **Mode tidak boleh bertentangan.** Mode melekat pada sesi. Permintaan yang
   meminta `realtime` untuk sesi `replay` ditolak 422; yang tidak menyebut mode
   memakai mode sesi (default `replay` hanya untuk kompatibilitas UI lama).
3. **Sesi terbaru hanya untuk tampilan.** `GET /demo/session` boleh membaca
   sesi aktif terakhir; penulis TIDAK boleh memakainya sebagai pemilik baris.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.demo_sessions import DemoSession
from app.services import decision_time
from app.services import demo_session as sesi


class SesiTidakDitemukanError(LookupError):
    """`demo_session` yang diminta tidak ada di database."""


class ModeBertentanganError(ValueError):
    """Mode permintaan bertentangan dengan mode sesi pemilik."""


async def sesi_pemilik(
    db: AsyncSession,
    *,
    demo_session: uuid.UUID | None = None,
    mode: str | None = None,
) -> DemoSession | None:
    """Sesi pemilik untuk penulisan baris demo (atau `None` = jalur lama).

    `mode=None` berarti pemanggil tidak menyebut mode: nilai sesi yang dipakai.
    Sesi yang diminta eksplisit tetapi tidak ada → `SesiTidakDitemukan` (router
    membalas 404, bukan 500 dan bukan diam-diam memakai sesi lain).
    """
    if demo_session is not None:
        sesi_row = await db.get(DemoSession, demo_session)
        if sesi_row is None:
            raise SesiTidakDitemukanError(str(demo_session))
    else:
        # Tanpa permintaan eksplisit: sesi aktif adalah konteks yang wajar
        # (operator menekan "Muat kasus demo" di tengah sesi yang berjalan).
        sesi_row = await sesi.aktif(db)
        if sesi_row is None:
            return None

    if mode is not None:
        diminta = decision_time.mode_sah(mode)
        if diminta != sesi_row.mode:
            raise ModeBertentanganError(
                f"sesi {sesi_row.id} bermode {sesi_row.mode!r}, "
                f"permintaan meminta {diminta!r} — pilih sesi yang sesuai "
                "atau buka sesi baru dengan mode itu"
            )
    return sesi_row


def blok_sesi(sesi_row: DemoSession | None) -> dict | None:
    """Bentuk ringkas sesi untuk respons seed (id, mode, anchor, versi).

    Bentuk ini SAMA dengan `GET /demo/session` supaya klien tidak punya dua
    pembaca untuk satu konsep.
    """
    if sesi_row is None:
        return None
    return {
        "id": str(sesi_row.id),
        "mode": sesi_row.mode,
        "evaluation_anchor": sesi_row.evaluation_anchor.isoformat(),
        "dataset_version": sesi_row.dataset_version
        or decision_time.REPLAY_DATASET_VERSION,
    }


async def pastikan_identitas(sesi_row: DemoSession) -> None:
    """Lengkapi `dataset_version` sesi yang belum punya (baris lama/kosong).

    Tidak menulis ke DB: pemanggil (penulis sesi) yang commit. Fungsi terpisah
    supaya tidak ada dua definisi "versi dataset sesi ini".
    """
    if sesi_row.dataset_version:
        return
    sesi_row.dataset_version = decision_time.dataset_version_untuk(
        sesi_row.mode, sesi_row.evaluation_anchor
    )


__all__ = [
    "ModeBertentanganError",
    "SesiTidakDitemukanError",
    "blok_sesi",
    "pastikan_identitas",
    "sesi_pemilik",
]
