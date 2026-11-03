"""Residu N3: "Siapkan data demo" tidak boleh menghapus jejak audit.

Sebelum perbaikan (24 Okt 2026), `app/seed/demo_template.py` memanggil
`DELETE FROM ledger_blocks` sebelum membangun ulang rantai. Akibatnya setiap
reset demo membuang SELURUH ledger — termasuk arsip generasi lama yang justru
menjadi bukti bahwa data pernah ada. Generasi ledger (N3) jadi tidak ada artinya
pada jalur yang paling sering dipakai saat demo.

Kontrak baru: reset cukup menaikkan generasi. Blok lama tetap tersimpan dan
dilaporkan sebagai `archived_blocks`; blok baru menyambung rantai yang sama
(`prev_hash` tidak putus), dan cakupan generasi aktif tetap 100% tertaut.

Tes ini mengunci dua hal: mekanisme ledger-nya (bump + append) dan fakta bahwa
jalur reset memakai mekanisme itu, bukan `DELETE`.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import text

from app.services import ledger_service
from tests.ledger_pemeliharaan import buka_pintu_async
from tests.test_ledger_generasi import _jalankan, _kembalikan


def test_jalur_reset_tidak_menghapus_ledger():
    sumber = Path("app/seed/demo_template.py").read_text(encoding="utf-8")
    assert "DELETE FROM ledger_blocks" not in sumber, (
        "reset demo tidak boleh menghapus ledger; naikkan generasi saja"
    )
    assert "bump_generation" in sumber


def test_bump_lalu_append_menyisakan_arsip_dan_rantai_tetap_valid():
    """Meniru langkah reset: blok lama jadi arsip, blok baru menyambung rantai.

    Baseline sengaja dibuat di dalam tes, supaya kontrak ini juga terbukti di
    database yang baru dimigrasi (CI tidak punya blok dari demo).
    """

    async def _t(db):
        awal = await ledger_service.current_generation(db)
        puncak = int(
            (await db.execute(text("SELECT coalesce(max(height), 0) FROM ledger_blocks"))).scalar()
            or 0
        )
        try:
            lama = uuid.uuid4()
            await ledger_service.append_block(
                db,
                action="decision.created",
                entity_id=lama,
                actor_id=None,
                payload={"decision_id": str(lama), "uji": "sebelum-reset"},
            )
            await db.commit()

            generasi_baru = await ledger_service.bump_generation(db)
            baru = uuid.uuid4()
            await ledger_service.append_block(
                db,
                action="decision.created",
                entity_id=baru,
                actor_id=None,
                payload={"decision_id": str(baru), "uji": "sesudah-reset"},
            )
            await db.commit()

            assert generasi_baru == awal + 1
            total = int(
                (await db.execute(text("SELECT count(*) FROM ledger_blocks"))).scalar()
            )
            assert total == puncak + 2, "blok lama tidak boleh hilang"

            laporan = await ledger_service.verify_chain(db)
            assert laporan["valid"] is True
            assert laporan["generation"] == generasi_baru
            assert laporan["archived_blocks"] >= 1
            # Blok baru menunjuk entitas yang tidak ada -> yatim, dan itu jujur.
            assert laporan["orphan_blocks"] >= 1
        finally:
            await buka_pintu_async(db)
            await db.execute(
                text("DELETE FROM ledger_blocks WHERE height > :h"), {"h": puncak}
            )
            await _kembalikan(db, puncak, awal)

    _jalankan(_t)
