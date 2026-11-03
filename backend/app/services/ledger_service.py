"""Merkle ledger append-only (P1, keputusan Roy 2026-10-09).

Setiap aksi mutasi keputusan menambah block: payload_hash =
sha256(prev_hash + payload). Rantai diverifikasi ulang dari genesis.
Append-only secara konvensi aplikasi; DB user aplikasi TIDAK diberi
UPDATE/DELETE pada tabel ini di produksi (lihat Rules.md).
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

GENESIS = "0" * 64


def baca_checkpoint(jalur: str | None = None) -> dict | None:
    """Baca checkpoint ledger dari LUAR database (Fase 11 butir 2).

    Berkas ini ditulis role migrasi dari host (`scripts/ledger_anchor.py`) dan
    hanya bisa DIBACA aplikasi (mount `./data:/data:ro`). Karena itu hash di
    dalamnya tidak dapat dipalsukan oleh kode aplikasi — berbeda dari
    `payload_hash` di database, yang bisa ditulis ulang oleh siapa pun yang
    memegang hak tulis tabel.

    Mengembalikan `None` bila path kosong, berkas tidak ada, atau isinya tidak
    berbentuk checkpoint yang sah. Tidak ada nilai karangan: pemanggil harus
    melaporkan "belum ada anchor", bukan "cocok".
    """
    path = jalur if jalur is not None else settings.ledger_anchor_path
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as berkas:
            data = json.load(berkas)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if "height" not in data or "payload_hash" not in data:
        return None
    return data


async def _laporan_anchor(db: AsyncSession, jalur: str | None = None) -> dict:
    """Bandingkan rantai di database dengan checkpoint eksternal.

    `match` sengaja TIDAK ikut menentukan `valid`: `valid` berarti integritas
    rantai menurut database itu sendiri, sedangkan `anchor.match` berarti
    "sama dengan salinan yang disimpan di luar database". Dua pertanyaan
    berbeda; menggabungkannya akan menyembunyikan kasus paling berbahaya —
    rantai yang ditulis ulang rapi (valid=true) tetapi tidak sama dengan
    checkpoint.
    """
    path = jalur if jalur is not None else settings.ledger_anchor_path
    checkpoint = baca_checkpoint(path)
    if checkpoint is None:
        return {
            "configured": bool(path),
            "path": path or None,
            "match": None,
            "reason": (
                "checkpoint belum dibuat (jalankan scripts/ledger_anchor.py)"
                if path
                else "LEDGER_ANCHOR_PATH kosong — anchor eksternal dimatikan"
            ),
            "height": None,
            "payload_hash": None,
            "created_at": None,
        }

    tinggi = int(checkpoint["height"])
    hash_anchor = str(checkpoint["payload_hash"])
    baris = (
        await db.execute(
            text("SELECT payload_hash FROM ledger_blocks WHERE height = :h"),
            {"h": tinggi},
        )
    ).fetchone()

    dasar = {
        "configured": True,
        "path": path,
        "height": tinggi,
        "payload_hash": hash_anchor,
        "created_at": checkpoint.get("created_at"),
    }
    if baris is None:
        return {
            **dasar,
            "match": False,
            "reason": (
                f"blok setinggi {tinggi} tidak ada di database — checkpoint lebih "
                "tinggi dari rantai (riwayat dipangkas, atau DB dipulihkan dari "
                "salinan yang lebih lama)"
            ),
        }
    if str(baris[0]) != hash_anchor:
        return {
            **dasar,
            "match": False,
            "reason": (
                f"hash blok {tinggi} di database berbeda dari anchor — riwayat "
                "ditulis ulang setelah checkpoint"
            ),
        }
    return {**dasar, "match": True, "reason": None}


async def tulis_checkpoint(db: AsyncSession, jalur: str | None = None) -> dict:
    """Tulis checkpoint anchor dari keadaan rantai SEKARANG (role migrasi).

    Dipanggil `scripts/ledger_anchor.py` dari host, bukan dari jalur kerja
    aplikasi: yang menandatangani riwayat harus pihak yang berwenang, dan
    berkasnya harus berada di tempat aplikasi tidak bisa menulis (mount :ro).

    Tulis atomik (`tmp` lalu `os.replace`) supaya verifikasi yang membaca
    berkas di tengah penulisan tidak melihat JSON separuh.
    """
    path = jalur if jalur is not None else settings.ledger_anchor_path
    if not path:
        raise ValueError("LEDGER_ANCHOR_PATH kosong — tidak ada tempat menulis anchor")

    jumlah = int(
        (await db.execute(text("SELECT count(*) FROM ledger_blocks"))).scalar_one()
    )
    kepala = (
        await db.execute(
            text(
                "SELECT height, payload_hash, generation, created_at "
                "FROM ledger_blocks ORDER BY height DESC LIMIT 1"
            )
        )
    ).fetchone()
    if kepala is None:
        raise ValueError("ledger kosong — tidak ada blok untuk dijadikan anchor")

    data = {
        "height": int(kepala[0]),
        "payload_hash": str(kepala[1]),
        "generation": int(kepala[2]) if kepala[2] is not None else None,
        "blocks": jumlah,
        "block_created_at": (
            kepala[3].isoformat() if hasattr(kepala[3], "isoformat") else None
        ),
        "created_at": datetime.now(UTC).isoformat(),
        "written_by": "scripts/ledger_anchor.py",
    }

    direktori = os.path.dirname(path)
    if direktori:
        os.makedirs(direktori, exist_ok=True)
    sementara = f"{path}.tmp"
    with open(sementara, "w", encoding="utf-8") as berkas:
        json.dump(data, berkas, indent=2, sort_keys=True)
        berkas.write("\n")
    os.replace(sementara, path)
    return data


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


async def bump_bila_berblok(db: AsyncSession, entity_ids) -> int | None:
    """Naikkan generasi bila blok generasi aktif menunjuk `entity_ids`.

    Kenapa perlu (audit integritas database 26 Okt 2026, D-02): `ledger_blocks`
    tidak punya FK ke `decisions`, jadi menghapus keputusan tidak meninggalkan
    jejak apa pun. Kalau bloknya berada di generasi AKTIF, `/ledger/verify`
    melaporkan `orphan_blocks > 0`: jejak audit menunjuk entitas hantu.

    Kontrak: blok TIDAK dihapus (rantai hash harus utuh dan bisa diverifikasi);
    yang berubah hanya cara cakupan dilaporkan — blok generasi lama menjadi
    `archived_blocks`. Mengembalikan generasi baru, atau None bila tidak ada
    blok yang menyentuh entitas tersebut (tidak perlu naik).
    """
    ids = [i for i in dict.fromkeys(entity_ids) if i is not None]
    if not ids:
        return None
    jumlah = (
        await db.execute(
            text(
                "SELECT count(*) FROM ledger_blocks "
                "WHERE generation = :g AND entity_id = ANY(:ids)"
            ),
            {"g": await current_generation(db), "ids": ids},
        )
    ).scalar_one()
    if not int(jumlah):
        return None
    return await bump_generation(db)


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
    """Tambah satu block ke ujung rantai (kunci antrean anti race).

    Kunci memakai `pg_advisory_xact_lock`, bukan `SELECT ... FOR UPDATE`:
    `FOR UPDATE` menuntut hak `UPDATE` pada tabel, sehingga role aplikasi yang
    hanya memegang `SELECT` + `INSERT` (Fase 11, migrasi 042) GAGAL menambah
    blok dengan `permission denied for table ledger_blocks`. Advisory lock
    memberi serialisasi yang sama tanpa hak tulis.
    """
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext('ledger_blocks_append')::bigint)")
    )
    last = (
        await db.execute(
            text(
                "SELECT height, payload_hash FROM ledger_blocks "
                "ORDER BY height DESC LIMIT 1"
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


async def verify_chain(db: AsyncSession, *, anchor_path: str | None = None) -> dict:
    """Verifikasi ulang seluruh rantai dari genesis (murni read).

    Sejak 18 Okt 2026 respons juga menyatakan KETERKAITAN blok, bukan hanya
    integritas hash (audit A4). `valid` tetap berarti "rantai tidak diputus" —
    itu kebenaran teknis yang tidak boleh dipalsukan — tetapi blok yang
    menunjuk keputusan/batch yang sudah dihapus dilaporkan terpisah supaya
    tidak terbaca sebagai "bukti lengkap".

    Sejak Fase 11 butir 2 respons memuat `anchor`: perbandingan dengan
    checkpoint di LUAR database. `valid=true` pada database yang sama TIDAK
    cukup — penulis yang memegang hak tulis bisa menghitung ulang seluruh hash.
    `anchor.match=false` adalah bukti bahwa riwayat ditulis ulang.
    """
    linkage = await _linkage(db)
    anchor = await _laporan_anchor(db, anchor_path)
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
                    "reason": "prev_hash tidak nyambung", "anchor": anchor,
                    **linkage}
        actual = hashlib.sha256((ph + payload).encode()).hexdigest()
        if actual != expected:
            return {"valid": False, "blocks": len(rows), "broken_at": h,
                    "reason": "payload_hash tidak cocok dengan sha256(prev+payload)",
                    "anchor": anchor, **linkage}
        prev = expected
    return {"valid": True, "blocks": len(rows), "head": prev if rows else None,
            "anchor": anchor, **linkage}


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
