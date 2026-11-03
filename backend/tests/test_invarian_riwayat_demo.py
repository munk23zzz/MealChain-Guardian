"""Dua invarian riwayat demo yang pernah bocor (audit 24 Okt 2026).

Keduanya tidak terlihat di UI sampai ada yang membuka panel Agent Log atau
bertanya "siapa yang menyetujui ini":

1. Jejak `ACT` pada keputusan yang tidak pernah dieksekusi. Penyebabnya dua
   penyemai yang menulis ACT untuk semua keputusan (`hari_ini.susun`) dan untuk
   `executed` + `approved` (`jakarta_lengkap.seed_decisions`).
2. Keputusan `executed` tanpa satu baris pun di `approvals`. Penyebabnya
   `jakarta_lengkap.seed_exclusions`, yang menulis status `executed` dan
   `SupplierExclusion.approved_at` tetapi tidak pernah menulis baris approval.

`verify/invariants.spec.json` memeriksa keduanya lewat SQL; tes ini menjaga
aturan yang sama tanpa perlu menjalankan gate.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

try:  # image backend memuat paket app; tes di host tanpa DB melewati berkas ini
    from sqlalchemy import text

    from app.core.config import settings
    from app.db import create_engine
except Exception:  # pragma: no cover - guard impor untuk lingkungan tanpa app
    text = None


def _url() -> str:
    return settings.database_url.replace("+asyncpg", "+psycopg")


@pytest.mark.skipif(text is None, reason="app/sqlalchemy tidak tersedia")
async def test_langkah_act_hanya_pada_keputusan_executed():
    eng = create_engine(_url())
    async with eng.connect() as conn:
        baris = (
            await conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM agent_traces t
                    JOIN decisions d ON d.id = t.decision_id
                    WHERE t.step_name = 'ACT' AND d.status <> 'executed'
                    """
                )
            )
        ).scalar_one()
        contoh = (
            await conn.execute(
                text(
                    """
                    SELECT left(d.id::text, 8) AS id, d.decision_type, d.status, t.tool_called
                    FROM agent_traces t
                    JOIN decisions d ON d.id = t.decision_id
                    WHERE t.step_name = 'ACT' AND d.status <> 'executed'
                    LIMIT 5
                    """
                )
            )
        ).fetchall()
    await eng.dispose()
    assert baris == 0, f"ada ACT pada keputusan yang belum dieksekusi: {contoh}"


@pytest.mark.skipif(text is None, reason="app/sqlalchemy tidak tersedia")
async def test_setiap_keputusan_executed_punya_persetujuan():
    eng = create_engine(_url())
    async with eng.connect() as conn:
        baris = (
            await conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM decisions d
                    WHERE d.status = 'executed'
                      AND NOT EXISTS (
                        SELECT 1 FROM approvals a
                        WHERE a.decision_id = d.id AND a.approved
                      )
                    """
                )
            )
        ).scalar_one()
        contoh = (
            await conn.execute(
                text(
                    """
                    SELECT left(d.id::text, 8) AS id, d.decision_type
                    FROM decisions d
                    WHERE d.status = 'executed'
                      AND NOT EXISTS (
                        SELECT 1 FROM approvals a
                        WHERE a.decision_id = d.id AND a.approved
                      )
                    LIMIT 5
                    """
                )
            )
        ).fetchall()
    await eng.dispose()
    assert baris == 0, f"keputusan executed tanpa approval: {contoh}"
