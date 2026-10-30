"""Hapus baris MILIK SATU SESI — reset demo tanpa menyentuh sesi lain.

Kenapa modul terpisah dari `demo_session.kosongkan_*` (Fase 2 MG): fungsi lama
bekerja dengan dua asumsi yang tidak lagi benar begitu ada lebih dari satu sesi:

- `kosongkan_bertanda()` menghapus **semua** baris ber-stempel (termasuk milik
  sesi lain) — itu dulu benar karena hanya ada satu sesi; sekarang berarti reset
  sesi pertama menghapus data sesi kedua.
- `kosongkan_kecuali(None)` menghapus **seluruh** baris operasional tanpa
  melihat pemilik, dan pernah terbukti memusnahkan template kanonik saat boot.

Aturan modul ini:

1. Kriteria hapus SELALU `demo_session_id = <sesi yang diminta>`. Tidak ada
   `WHERE origin='demo'` yang luas, tidak ada `DELETE FROM <tabel>`.
2. Sesi sentinel `cetakan` dan baris kanonik (`origin='seed'`) tidak pernah
   ikut: template beku bukan milik sesi yang sedang direset.
3. Anak dulu, induk kemudian (FK, urutan sama dengan `demo_session._urutan_hapus`).
4. Ledger TIDAK dihapus; generasi dinaikkan supaya blok generasi lama menjadi
   arsip (rantai hash tetap utuh — aturan yang sama dengan reset lain).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Base
from app.services import demo_session as sesi

__all__ = ["purge_session", "hitung_milik_sesi"]


def _kriteria_sesi(model: type[Base], sesi_id: uuid.UUID):
    """Predikat hapus: milik sesi ini, bukan cetakan, bukan baris kanonik."""
    kolom = model.__table__.columns
    kriteria = kolom["demo_session_id"] == sesi_id
    kriteria = kriteria & (kolom["demo_session_id"] != sesi.CETAKAN_ID)
    if "origin" in kolom:
        kriteria = kriteria & (kolom.origin != "seed")
    return kriteria


async def hitung_milik_sesi(db: AsyncSession, sesi_id: uuid.UUID) -> dict[str, int]:
    """Berapa baris yang akan terhapus — dipakai tes & laporan, tanpa menulis."""
    from sqlalchemy import func, select

    hasil: dict[str, int] = {}
    for model in sesi.model_bersesi():
        jumlah = await db.scalar(
            select(func.count()).select_from(model).where(_kriteria_sesi(model, sesi_id))
        )
        if jumlah:
            hasil[model.__tablename__] = int(jumlah)
    return hasil


async def purge_session(db: AsyncSession, sesi_id: uuid.UUID) -> dict[str, Any]:
    """Hapus seluruh baris milik `sesi_id` (dan HANYA miliknya).

    Mengembalikan `{"decisions": n, ...}` berisi jumlah baris terhapus per
    tabel. Tidak memanggil `commit`: pemanggil yang menentukan transaksi.
    """
    dihapus: dict[str, int] = {}
    # Anak keputusan yang TIDAK punya `demo_session_id` (approvals,
    # decision_evidence, agent_traces) tidak bisa disapu oleh
    # `_kriteria_sesi`, sehingga DELETE decisions menabrak
    # ForeignKeyViolationError ("still referenced from table approvals" —
    # terukur 30 Okt 2026 saat "Muat kasus" dijalankan ulang). Hapus lebih dulu
    # lewat subquery keputusan milik sesi ini.
    from sqlalchemy import select as _select

    from app.models import AgentTrace, Approval, Decision, DecisionEvidence

    id_keputusan = _select(Decision.id).where(_kriteria_sesi(Decision, sesi_id))
    for model_anak, kolom in (
        (AgentTrace, AgentTrace.decision_id),
        (Approval, Approval.decision_id),
        (DecisionEvidence, DecisionEvidence.decision_id),
    ):
        hasil_anak = await db.execute(
            delete(model_anak)
            .where(kolom.in_(id_keputusan))
            .execution_options(synchronize_session=False)
        )
        jumlah_anak = int(hasil_anak.rowcount or 0)
        if jumlah_anak:
            dihapus[model_anak.__tablename__] = (
                dihapus.get(model_anak.__tablename__, 0) + jumlah_anak
            )
    for model in sorted(sesi.model_bersesi(), key=sesi._urutan_hapus):
        hasil = await db.execute(
            delete(model)
            .where(_kriteria_sesi(model, sesi_id))
            .execution_options(synchronize_session=False)
        )
        jumlah = int(hasil.rowcount or 0)
        if jumlah:
            dihapus[model.__tablename__] = jumlah
    if dihapus:
        from app.services.ledger_service import bump_generation

        await bump_generation(db)
    return dihapus
