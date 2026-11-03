"""Keterkaitan blok ledger (Fase 0 butir 4 / audit BLOCKER A4, 18 Okt 2026).

Masalah: `/ledger/verify` hanya memeriksa integritas hash. Di DB demo, SEMUA
blok menunjuk entitas yang sudah tidak ada (keputusan/batch dihapus), tetapi
responsnya tetap `{"valid": true}` — hijau yang menyesatkan: "rantai utuh"
terbaca sebagai "bukti lengkap".

Kontrak baru: `valid` tetap berarti integritas rantai (jangan diubah — itu
kebenaran teknis), dan respons WAJIB menyatakan berapa blok yang masih tertaut:
`entity_blocks`, `linked_blocks`, `orphan_blocks`, `linked_ratio`, plus
`coverage_warning` bila ada blok yatim — semuanya untuk generasi data demo
yang aktif (`generation`), sedangkan blok generasi lama dilaporkan sebagai
`archived_blocks` (lihat `tests/test_ledger_generasi.py`).

Tes ini tidak menyuntik blok baru (ledger append-only milik DB bersama); ia
membandingkan angka respons dengan hitungan langsung dari tabel.
"""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DB_URL = (
    DSN_ASYNC
).replace("+asyncpg", "+psycopg")

# Cakupan dihitung pada GENERASI AKTIF saja (N3, 24 Okt 2026): blok generasi
# lama tidak dihapus, tetapi entitasnya memang sudah dibersihkan reset demo,
# sehingga dinilai terpisah sebagai `archived_blocks`.
LINKAGE_SQL = """
SELECT
  count(*) FILTER (WHERE entity_id IS NOT NULL) AS entity_blocks,
  count(*) FILTER (
    WHERE entity_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM decisions d WHERE d.id = lb.entity_id)
      AND NOT EXISTS (SELECT 1 FROM batches b WHERE b.id = lb.entity_id)
      -- Entitas sah lainnya: pengguna & lokasi (blok `admin.*`, AUTH-01).
      AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id = lb.entity_id)
      AND NOT EXISTS (SELECT 1 FROM locations lc WHERE lc.id = lb.entity_id)
  ) AS orphan_blocks
FROM ledger_blocks lb,
     (SELECT coalesce((SELECT generation FROM ledger_meta WHERE id = 1), 1) AS g) gen
WHERE lb.generation = gen.g
"""


def _db_counts() -> dict:
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            row = conn.execute(text(LINKAGE_SQL)).one()
        return {"entity_blocks": row[0], "orphan_blocks": row[1]}
    finally:
        engine.dispose()


def _token(client: TestClient) -> dict:
    resp = client.post(
        "/auth/login",
        json={"email": "bgn.monitor@demo.local", "password": "Demo#BGN2026"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_ledger_verify_menyatakan_keterkaitan_blok():
    counts = _db_counts()
    with TestClient(app) as client:
        resp = client.get("/ledger/verify", headers=_token(client))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Integritas rantai tetap dilaporkan seperti sebelumnya.
    assert body["valid"] is True, body
    assert body["blocks"] >= body["entity_blocks"], body

    # Angka keterkaitan harus cocok dengan DB — bukan dikarang.
    assert body["entity_blocks"] == counts["entity_blocks"], body
    assert body["orphan_blocks"] == counts["orphan_blocks"], body
    assert body["linked_blocks"] == counts["entity_blocks"] - counts["orphan_blocks"], body

    if counts["entity_blocks"]:
        expected = round(
            (counts["entity_blocks"] - counts["orphan_blocks"]) / counts["entity_blocks"], 3
        )
        assert body["linked_ratio"] == expected, body
    else:
        assert body["linked_ratio"] is None, body

    # Jujur: rantai utuh TIDAK boleh tampil sebagai "semua bukti lengkap".
    if counts["orphan_blocks"]:
        assert body["coverage_warning"], body
        assert str(counts["orphan_blocks"]) in body["coverage_warning"]
    else:
        assert body["coverage_warning"] is None, body
