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


async def current_generation(db: AsyncSession) -> int:
    """Generasi data demo yang sedang aktif (1 bila tabel penanda belum ada)."""
    row = (
        await db.execute(text("SELECT generation FROM ledger_meta WHERE id = 1"))
    ).fetchone()
    return int(row[0]) if row else 1


async def bump_generation(db: AsyncSession) -> int:
    """Naikkan generasi: dipanggil setiap data demo direset.

    Blok generasi lama TIDAK dihapus maupun ditulis ulang — rantai hash harus
    tetap bisa diverifikasi. Yang berubah hanya cara cakupan dilaporkan:
    `linked_ratio` menghitung generasi aktif, blok lama masuk `archived_blocks`.
    """
    row = (
        await db.execute(
            text(
                # UPSERT: DB yang dibuat dari model (bukan migrasi) mungkin belum
                # punya baris penanda; generasi tetap harus bisa naik.
                "INSERT INTO ledger_meta (id, generation, updated_at) "
                "VALUES (1, 2, now()) "
                "ON CONFLICT (id) DO UPDATE "
                "SET generation = ledger_meta.generation + 1, updated_at = now() "
                "RETURNING generation"
            )
        )
    ).fetchone()
    return int(row[0]) if row else 1


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
    generation = await current_generation(db)
    payload_str = _canonical(payload)
    payload_hash = hashlib.sha256((prev_hash + payload_str).encode()).hexdigest()
    row = (
        await db.execute(
            text(
                "INSERT INTO ledger_blocks "
                "(height, prev_hash, payload_hash, action, entity_id, actor_id, "
                "payload, generation) "
                "VALUES (:h, :p, :ph, :a, :e, :act, :pl, :g) "
                "RETURNING height, prev_hash, payload_hash"
            ),
            {
                "h": height, "p": prev_hash, "ph": payload_hash,
                "a": action, "e": entity_id, "act": actor_id,
                "pl": payload_str, "g": generation,
            },
        )
    ).fetchone()
    return {
        "height": row[0],
        "prev_hash": row[1],
        "payload_hash": row[2],
        "generation": generation,
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
    """Cakupan blok GENERASI AKTIF (audit N3, 24 Okt 2026).

    Blok tanpa `entity_id` (mis. catatan sistem) tidak dihitung sebagai yatim —
    ia memang tidak menunjuk entitas apa pun, jadi tidak bisa "hilang".

    Blok dari generasi sebelumnya TIDAK ikut dinilai: entitasnya memang sudah
    dibersihkan oleh reset data demo (itu tujuannya), dan bloknya sengaja tidak
    dihapus supaya rantai hash tetap utuh. Mereka dilaporkan sebagai
    `archived_blocks`, bukan sebagai kerusakan.
    """
    generation = await current_generation(db)
    row = (
        await db.execute(
            text(
                """
                SELECT
                  count(*) FILTER (
                    WHERE generation = :g AND entity_id IS NOT NULL
                  ) AS entity_blocks,
                  count(*) FILTER (
                    WHERE generation = :g
                      AND entity_id IS NOT NULL
                      AND NOT EXISTS (SELECT 1 FROM decisions d WHERE d.id = lb.entity_id)
                      AND NOT EXISTS (SELECT 1 FROM batches b WHERE b.id = lb.entity_id)
                      -- Sejak AUTH-01, perubahan pengguna/lokasi juga berblok
                      -- (`admin.user.update` / `admin.location.update`), jadi
                      -- users & locations adalah entitas yang sah — bukan yatim.
                      AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id = lb.entity_id)
                      AND NOT EXISTS (SELECT 1 FROM locations lc WHERE lc.id = lb.entity_id)
                  ) AS orphan_blocks,
                  count(*) FILTER (WHERE generation < :g) AS archived_blocks
                FROM ledger_blocks lb
                """
            ),
            {"g": generation},
        )
    ).one()
    entity_blocks, orphan_blocks, archived = int(row[0]), int(row[1]), int(row[2])
    linked_blocks = entity_blocks - orphan_blocks
    return {
        "generation": generation,
        "entity_blocks": entity_blocks,
        "linked_blocks": linked_blocks,
        "orphan_blocks": orphan_blocks,
        "archived_blocks": archived,
        "linked_ratio": (
            round(linked_blocks / entity_blocks, 3) if entity_blocks else None
        ),
        "coverage_warning": (
            f"{orphan_blocks} blok generasi aktif menunjuk entitas yang sudah tidak ada"
            if orphan_blocks
            else None
        ),
    }
