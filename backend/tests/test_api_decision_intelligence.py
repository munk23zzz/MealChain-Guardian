"""Task 10 Sprint 2: API decision intelligence (4 endpoint).

- GET  /balance/{location}/{commodity}
- POST /balance/recommend
- POST /decisions
- GET  /decisions/{decision_id}

Routers tipis; formulas tetap di core/service. Expiry contract:
now < expires_at → valid, else expired (Task 11 tumpang tindih di sini
untuk GET validity).
"""

import uuid as uuidlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_SYNC


@pytest.fixture()
def client(auth_headers):
    with TestClient(app) as c:
        c.headers.update(auth_headers)
        yield c


def _db():
    return create_engine(DB_URL)


def _cleanup(decision_id):
    with _db().begin() as conn:
        conn.execute(
            text("DELETE FROM decisions WHERE id = :id"),
            {"id": decision_id},
        )


_QUANTITY_TABLE = {"supply": "supply_records", "demand": "demand_records"}


def _db_latest_quantity_kg(kind: str, location: str, commodity: str):
    """Quantity_kg baris TERBARU (supply|demand) untuk (lokasi, komoditas).

    Sengaja diturunkan dari DB supaya tes tidak pecah saat deret aktual
    diperluas: pasokan & harga demo kini berjalan sampai 5 Nov (ACTUAL_REF),
    sedangkan demand tetap berhenti di baris kanonik 8 Okt. Jadi 'record
    terbaru' bergerak untuk supply tapi tidak untuk demand — angka panel
    demo lama (300/1400) tidak lagi berlaku.

    Sejak audit angka 18 Okt 2026 endpoint hanya memakai baris yang SUDAH
    terjadi (`recorded_at <= now()`, parameter `as_of`), jadi acuan di sini
    memakai batas yang sama — baris masa depan bukan 'kondisi kini'.
    """
    table = _QUANTITY_TABLE[kind]
    with _db().connect() as conn:
        return conn.execute(
            text(
                f"SELECT r.quantity_kg FROM {table} r "
                "JOIN locations l ON l.id = r.location_id "
                "JOIN commodities c ON c.id = r.commodity_id "
                "WHERE l.name = :loc AND c.name = :com "
                "AND r.recorded_at <= now() "
                "ORDER BY r.recorded_at DESC, r.id DESC LIMIT 1"
            ),
            {"loc": location, "com": commodity},
        ).scalar_one_or_none()


def _gap_from_refs(supply_ref, demand_ref):
    """(surplus, shortage, status) dengan aritmetika Decimal yang sama
    seperti core.gaps (max(x, 0), status turunan relasi)."""
    from decimal import Decimal

    supply = supply_ref if supply_ref is not None else Decimal("0")
    demand = demand_ref if demand_ref is not None else Decimal("0")
    surplus = supply - demand if supply > demand else Decimal("0")
    deficit = demand - supply if demand > supply else Decimal("0")
    if surplus > 0:
        status = "surplus"
    elif deficit > 0:
        status = "shortage"
    else:
        status = "balanced"
    return surplus, deficit, status


def test_balance_endpoint_returns_gap_facts(client):
    # Angka acuan sengaja diturunkan dari DB, bukan dipaku ke nilai panel demo
    # lama (300/1080/780): deret aktual diperluas sampai 5 Nov sehingga baris
    # supply terbaru Jakarta/telur bergerak, sementara demand tetap baris
    # kanonik 8 Okt. Tes jadi tahan-snapshot terhadap perluasan deret.
    supply_ref = _db_latest_quantity_kg("supply", "Jakarta", "telur")
    demand_ref = _db_latest_quantity_kg("demand", "Jakarta", "telur")
    assert supply_ref is not None, "seed wajib punya supply Jakarta/telur"
    assert demand_ref is not None, "seed wajib punya demand Jakarta/telur"
    expected_surplus, expected_shortage, expected_status = _gap_from_refs(
        supply_ref, demand_ref
    )

    resp = client.get("/balance/Jakarta/telur")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["supply_kg"] == float(supply_ref)
    assert body["demand_kg"] == float(demand_ref)
    assert body["shortage_kg"] == float(expected_shortage)
    assert body["surplus_kg"] == float(expected_surplus)
    # status konsisten: shortage bila supply < demand
    assert body["status"] == expected_status


def _pasangan_tanpa_demand() -> tuple[str, str] | None:
    """Pasangan (lokasi, komoditas) yang punya PASOKAN tetapi belum ada demand."""
    with _db().connect() as conn:
        row = conn.execute(
            text(
                "SELECT l.name, c.name FROM supply_records s "
                "JOIN locations l ON l.id = s.location_id "
                "JOIN commodities c ON c.id = s.commodity_id "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM demand_records d "
                "  WHERE d.location_id = s.location_id "
                "  AND d.commodity_id = s.commodity_id"
                ") ORDER BY l.name, c.name LIMIT 1"
            )
        ).first()
    return (row[0], row[1]) if row else None


def test_balance_endpoint_surplus_city_without_demand(client, monitor_headers):
    """Pasokan tanpa baris permintaan → demand 0, surplus murni.

    Dulu kasus ini dipaku ke Cianjur/telur ("Cianjur sengaja tanpa demand").
    Sejak deret permintaan 19 Okt 2026 mencakup SEMUA pasangan lokasi×komoditas,
    keadaan itu tidak ada lagi di dataset — jadi pasangannya DICARI saat tes
    berjalan, dan tes SKIP bila memang mustahil dibentuk. Melonggarkan asersinya
    (mis. "demand 0 itu opsional") akan menghapus arti tes ini.
    """
    pasangan = _pasangan_tanpa_demand()
    if pasangan is None:
        pytest.skip("semua lokasi×komoditas punya baris demand; kasus ini mustahil")

    lokasi, komoditas = pasangan
    supply_ref = _db_latest_quantity_kg("supply", lokasi, komoditas)
    demand_ref = _db_latest_quantity_kg("demand", lokasi, komoditas)
    assert supply_ref is not None, f"seed wajib punya supply {lokasi}/{komoditas}"
    assert demand_ref is None, f"{lokasi}/{komoditas} harus tanpa baris demand"
    expected_surplus, expected_shortage, _ = _gap_from_refs(supply_ref, 0)

    resp = client.get(f"/balance/{lokasi}/{komoditas}", headers=monitor_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["supply_kg"] == float(supply_ref)
    assert body["demand_kg"] == 0.0
    assert body["surplus_kg"] == float(expected_surplus)
    assert body["shortage_kg"] == 0.0
    assert body["status"] == "surplus"


def test_balance_endpoint_unknown_location_404(client):
    resp = client.get("/balance/Narnia/telur")
    assert resp.status_code == 404


def test_recommend_endpoint_ranks_candidates(client):
    resp = client.post("/balance/recommend", json={})
    assert resp.status_code == 200, resp.text
    items = resp.json()["recommendations"]
    assert items, "seed wajib menghasilkan kandidat"
    ranks = [r["rank"] for r in items]
    assert ranks == sorted(ranks)
    telur = [r for r in items
             if r["candidate"]["source_location"] == "Cianjur"
             and r["candidate"]["destination_location"] == "Jakarta"]
    assert telur, "Cianjur→Jakarta telur wajib ada"


def test_decisions_persist_and_get_validity(client):
    rec = client.post("/balance/recommend", json={}).json()
    # Keputusan hanya boleh menyasar lokasi milik SPPG pengguna (Jakarta), jadi
    # pilih kandidat TERATAS yang tujuannya Jakarta — bukan rank 1 global, yang
    # bisa saja menuju kota lain dan memang ditolak 403 oleh aturan scope.
    items = rec["recommendations"]
    top = next(
        (r for r in items if r["candidate"]["destination_location"] == "Jakarta"),
        None,
    )
    assert top is not None, "seed wajib punya kandidat menuju Jakarta"

    payload = {
        "recommendation": top,
        "ttl_minutes": 30,
    }
    resp = client.post("/decisions", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    decision_id = body["decision_id"]
    assert body["status"] == "proposed"  # CHECK enum Schema.md, initial
    assert body["valid"] is True

    got = client.get(f"/decisions/{decision_id}").json()
    assert got["decision_id"] == decision_id
    assert got["valid"] is True
    assert got["expires_at"] > got["created_at"]

    _cleanup(decision_id)


def test_decision_persistence_without_expires_at_impossible(client):
    """Kontrak: expires_at NOT NULL — POST tanpa ttl tetap sukses (default),
    kolom di DB tidak boleh nullable. Verifikasi via information_schema."""
    with _db().connect() as conn:
        nullable = conn.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name='decisions' AND column_name='expires_at'"
            )
        ).scalar()
    assert nullable == "NO"


def test_decision_get_unknown_id_404(client):
    resp = client.get(f"/decisions/{uuidlib.uuid4()}")
    assert resp.status_code == 404


def test_recommend_deterministic(client):
    """Determinisme API = urutan ranking & identitas kandidat stabil
    antar panggilan. (Bit-identik penuh diuji di level service dengan
    as_of tetap — endpoint live menghitung freshness pada now().)"""
    a = client.post("/balance/recommend", json={}).json()
    b = client.post("/balance/recommend", json={}).json()
    ids_a = [r["candidate_id"] for r in a["recommendations"]]
    ids_b = [r["candidate_id"] for r in b["recommendations"]]
    assert ids_a == ids_b
    assert len(ids_a) == len(set(ids_a))  # tanpa duplikat
