"""Kasus demo WAJIB punya binding pemasok eksplisit (audit 19 Okt 2026).

Kenapa ada: dataset kanonik 19 Okt memperluas kiriman, sehingga satu pasangan
(lokasi, komoditas) bisa punya lebih dari satu pemasok — Cianjur×telur punya
dua batch dari dua pemasok. `resolve_binding` sengaja TIDAK menebak pada
pasangan seperti itu, jadi keempat kasus demo (yang dibuat `POST /demo/seed`
tanpa bukti binding) langsung tertahan dengan alasan
"pemasok tidak dikenal: keputusan lama perlu binding batch eksplisit" —
kartu unggulan demo tidak bisa dieksekusi.

Aturan yang dikunci tes ini: seeder menulis bukti `allocation_binding` untuk
setiap kasus yang masih BISA ditindaklanjuti, dan binding itu menunjuk batch
nyata di lokasi asal + komoditas keputusan (bukan karangan), sehingga
`GET /decisions/{id}/approval-summary` melaporkan nama pemasok.
"""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
EMAIL = "sppg.head@demo.local"
PASSWORD = "Demo#SPPG2026"

# Status yang akan DIEKSEKUSI setelah persetujuan: hanya ini yang butuh binding.
# Kasus `verifier_flagged` (supplier-janggal) SENGAJA tidak diikat: tuduhannya
# tentang harga sebuah kutipan pemasok, dan pemasok itu bukan selalu pemilik
# batch terbesar — mengikat batch terbesar berarti menampilkan pemasok yang
# bukan subjek tuduhan. Di sana alasan "pemasok tidak dikenal" memang jujur.
AKTIF = ("pending_approval",)


def _db():
    return create_engine(DB_URL)


def _bindings(conn, decision_id: str) -> list[dict]:
    rows = conn.execute(
        text(
            "SELECT payload FROM decision_evidence "
            "WHERE decision_id = :d AND payload->>'allocation_binding' = 'true'"
        ),
        {"d": decision_id},
    ).scalars().all()
    return [row if isinstance(row, dict) else dict(row) for row in rows]


def test_kasus_demo_punya_binding_pemasok_yang_cocok_dengan_batch() -> None:
    engine = _db()
    try:
        with TestClient(app) as c:
            tok = c.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
            assert tok.status_code == 200, tok.text
            headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}

            seed = c.post("/demo/seed", json={"force": True}, headers=headers)
            assert seed.status_code == 200, seed.text
            assert seed.json()["seeded"] is True

            with engine.begin() as conn:
                kasus = conn.execute(
                    text(
                        "SELECT d.id, d.demo_case, d.status, d.source_location_id, "
                        "       d.commodity_id "
                        "FROM decisions d JOIN locations l ON l.id = d.target_location_id "
                        "WHERE d.demo_case IS NOT NULL AND l.name = 'Jakarta' "
                        "AND d.status = ANY(:aktif)"
                    ),
                    {"aktif": list(AKTIF)},
                ).all()
            assert kasus, "seed demo tidak membuat keputusan yang bisa ditindaklanjuti"

            for decision_id, case, status, sumber, komoditas in kasus:
                with engine.begin() as conn:
                    binding = _bindings(conn, str(decision_id))
                assert len(binding) == 1, (
                    f"{case} ({status}) punya {len(binding)} binding; harus tepat 1 "
                    "supaya resolve_binding tidak menebak"
                )
                payload = binding[0]
                batch_ids = payload["batch_ids"]
                assert batch_ids, f"{case}: binding tanpa batch"
                with engine.begin() as conn:
                    batch = conn.execute(
                        text(
                            "SELECT supplier_id, location_id, commodity_id "
                            "FROM batches WHERE id = :b"
                        ),
                        {"b": batch_ids[0]},
                    ).one()
                assert str(batch[0]) == payload["supplier_id"], f"{case}: supplier tidak cocok"
                assert batch[1] == sumber, f"{case}: batch bukan dari lokasi asal keputusan"
                assert batch[2] == komoditas, f"{case}: batch komoditas lain"

                ringkas = c.get(
                    f"/decisions/{decision_id}/approval-summary", headers=headers
                )
                assert ringkas.status_code == 200, ringkas.text
                data = ringkas.json()
                assert data["supplier"], (
                    f"{case}: approval-summary masih tanpa pemasok — "
                    f"blocking={data.get('blocking_reasons')}"
                )
    finally:
        engine.dispose()
