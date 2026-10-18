"""Merkle ledger append-only (P1, keputusan Roy 2026-10-09).

Setiap aksi mutasi keputusan menambah block: payload_hash =
sha256(prev_hash + payload). Rantai diverifikasi ulang dari genesis.
Append-only secara konvensi aplikasi; DB user aplikasi TIDAK diberi
UPDATE/DELETE pada tabel ini di produksi (lihat Rules.md).
"""

import hashlib
import json
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

GENESIS = "0" * 64


def _canonical(payload: dict) -> str:
    def _default(o):
        if isinstance(o, (UUID, Decimal)):
            return str(o)
        if hasattr(o, "isoformat"):
            return o.isoformat()
        raise TypeError(repr(o))

    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=_default)


def payload_digest(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


async def append_block(
    db: AsyncSession,
    action: str,
    entity_id,
    actor_id,
    payload: dict,
) -> dict:
    """Tambah satu block ke ujung rantai (row-level lock anti race)."""
    last = (
        await db.execute(
            text(
                "SELECT height, payload_hash FROM ledger_blocks "
                "ORDER BY height DESC LIMIT 1 FOR UPDATE"
            )
        )
    ).fetchone()
    height = (last[0] + 1) if last else 1
    prev_hash = last[1] if last else GENESIS
    payload_str = _canonical(payload)
    payload_hash = hashlib.sha256((prev_hash + payload_str).encode()).hexdigest()
    row = (
        await db.execute(
            text(
                "INSERT INTO ledger_blocks "
                "(height, prev_hash, payload_hash, action, entity_id, actor_id, payload) "
                "VALUES (:h, :p, :ph, :a, :e, :act, :pl) "
                "RETURNING height, prev_hash, payload_hash"
            ),
            {
                "h": height, "p": prev_hash, "ph": payload_hash,
                "a": action, "e": entity_id, "act": actor_id,
                "pl": payload_str,
            },
        )
    ).fetchone()
    return {
        "height": row[0],
        "prev_hash": row[1],
        "payload_hash": row[2],
    }


async def verify_chain(db: AsyncSession) -> dict:
    """Verifikasi ulang seluruh rantai dari genesis (murni read).

    Sejak 18 Okt 2026 respons juga menyatakan KETERKAITAN blok, bukan hanya
    integritas hash (audit A4). `valid` tetap berarti "rantai tidak diputus" —
    itu kebenaran teknis yang tidak boleh dipalsukan — tetapi blok yang
    menunjuk keputusan/batch yang sudah dihapus dilaporkan terpisah supaya
    tidak terbaca sebagai "bukti lengkap".
    """
    linkage = await _linkage(db)
    rows = (
        await db.execute(
            text(
                "SELECT height, prev_hash, payload_hash, payload "
                "FROM ledger_blocks ORDER BY height"
            )
        )
    ).fetchall()
    prev = GENESIS
    for h, ph, expected, payload in rows:
        if h != 1 and ph != prev:
            return {"valid": False, "blocks": len(rows), "broken_at": h,
                    "reason": "prev_hash tidak nyambung", **linkage}
        actual = hashlib.sha256((ph + payload).encode()).hexdigest()
        if actual != expected:
            return {"valid": False, "blocks": len(rows), "broken_at": h,
                    "reason": "payload_hash tidak cocok dengan sha256(prev+payload)",
                    **linkage}
        prev = expected
    return {"valid": True, "blocks": len(rows), "head": prev if rows else None,
            **linkage}


async def _linkage(db: AsyncSession) -> dict:
    """Hitung blok yang entitasnya masih ada (keputusan atau batch).

    Blok tanpa `entity_id` (mis. catatan sistem) tidak dihitung sebagai yatim —
    ia memang tidak menunjuk entitas apa pun, jadi tidak bisa "hilang".
    """
    row = (
        await db.execute(
            text(
                """
                SELECT
                  count(*) FILTER (WHERE entity_id IS NOT NULL) AS entity_blocks,
                  count(*) FILTER (
                    WHERE entity_id IS NOT NULL
                      AND NOT EXISTS (SELECT 1 FROM decisions d WHERE d.id = lb.entity_id)
                      AND NOT EXISTS (SELECT 1 FROM batches b WHERE b.id = lb.entity_id)
                  ) AS orphan_blocks
                FROM ledger_blocks lb
                """
            )
        )
    ).one()
    entity_blocks, orphan_blocks = int(row[0]), int(row[1])
    linked_blocks = entity_blocks - orphan_blocks
    return {
        "entity_blocks": entity_blocks,
        "linked_blocks": linked_blocks,
        "orphan_blocks": orphan_blocks,
        "linked_ratio": (
            round(linked_blocks / entity_blocks, 3) if entity_blocks else None
        ),
        "coverage_warning": (
            f"rantai utuh, tetapi {orphan_blocks} blok menunjuk entitas yang sudah tidak ada"
            if orphan_blocks
            else None
        ),
    }
