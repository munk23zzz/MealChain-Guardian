"""Fase 2 (permintaan pemilik proyek 2026-10-14): pemasok bisa ditampilkan di peta.

TDD RED dulu — endpoint read-only `GET /suppliers`:
- Read-only: `get_current_user` (JWT) — semua peran login boleh baca; 401 unauth.
- Pemasok = data sisi SUMBER (Ruling 2026-10-14 §4), jadi daftar TIDAK dikunci
  per lokasi — sama seperti `GET /batches`. Yang lokal-cakupan adalah eksklusi:
  tiap baris membawa `excluded_scope_locations`, dan UI tidak boleh
  menyebutnya nasional.
- Filter komoditas/lokasi memakai NAMA (bukan id) supaya bisa dipakai UI
  langsung; lokasi tak dikenal → 0 baris (bukan 404).
- `limit` dijaga 1..200 (422 di luar itu) supaya satu permintaan tidak bisa
  menarik tabel penuh tanpa batas.
"""

import json
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.seed.seed_data import DEMO_USERS
from app.seed.suppliers_demo import load_demo_rows

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

# dari data/seed/sprint1_seed.json (diverifikasi utuh di test_suppliers_data.py)
CANONICAL_SUPPLIERS = 17  # 14 semula + 3 pemasok beras (komoditas ke-4)
DEMO_SUPPLIERS = len(load_demo_rows())
# Tiga baris demo beras memakai nama pemasok kanonik yang sama: berkas demo
# berperan sebagai overlay koordinat, seeder mencocokkan lewat nama dan
# MENG-UPDATE baris kanonik, bukan menambah baris baru.
DEMO_OVERLAY = 3
TOTAL_SUPPLIERS = CANONICAL_SUPPLIERS + DEMO_SUPPLIERS - DEMO_OVERLAY


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def tokens():
    """Token nyata untuk ketiga peran demo (password diambil dari SEED, bukan ditulis di tes).

    Fixture ini punya TestClient sendiri: ia module-scope sedangkan `client`
    function-scope, jadi meminjam `client` di sini = ScopeMismatch. Pola
    "fixture scope sendiri" juga dipakai `tests/conftest.py`.
    """
    with TestClient(app) as c:
        out = {}
        for user in DEMO_USERS:
            resp = c.post(
                "/auth/login", json={"email": user["email"], "password": user["password"]}
            )
            assert resp.status_code == 200, resp.text
            headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
            out[user["email"]] = headers
            # Sejak 2026-10-18 ada TIGA user per peran (Jakarta/Bandung/Surabaya).
            # Kunci per peran harus tetap menunjuk user JAKARTA — tes lama memakai
            # peran saja dan memverifikasi jarak/rujukan Jakarta. User lain bisa
            # diakses lewat kunci emailnya.
            if user["email"] in (
                "sppg.head@demo.local",
                "sppg.nutritionist@demo.local",
                "bgn.monitor@demo.local",
            ):
                out[user["role"]] = headers
            else:
                out.setdefault(user["role"], headers)
        yield out


def test_suppliers_unauth_401(client):
    assert client.get("/suppliers").status_code == 401


@pytest.mark.parametrize("role", ["sppg_head", "sppg_nutritionist", "bgn_monitor"])
def test_suppliers_readable_by_every_role(client, tokens, role):
    """Daftar pemasok = data sisi sumber → dibaca semua peran, termasuk kepala SPPG.

    Ini keputusan sadar (Ruling 2026-10-14 §4): yang dibatasi per lokasi adalah
    keputusan/eksklusi, bukan profil pemasok. Tes ini mengunci keputusan itu
    supaya perubahan cakupan di masa depan tidak menyempit tanpa disadari.
    """
    resp = client.get("/suppliers", headers=tokens[role])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == TOTAL_SUPPLIERS
    assert body["count"] == TOTAL_SUPPLIERS


def test_supplier_item_carries_map_profile(client, tokens):
    """Tiap baris wajib membawa profil yang dibutuhkan peta/halaman pemasok."""
    resp = client.get("/suppliers?q=Wortel%20Lestari%20Cianjur", headers=tokens["bgn_monitor"])
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["name"] == "Wortel Lestari Cianjur"
    assert item["location"] == "Cianjur"
    assert item["commodity"] == "wortel"
    assert item["reliability_score"] == pytest.approx(0.93)
    assert item["capacity_kg_per_week"] == pytest.approx(3000)
    assert item["certification_status"] == "haccp"
    assert item["address"] and item["contact_name"]
    assert -7.0 < item["latitude"] < -6.0  # sekitar Cianjur
    assert 106.0 < item["longitude"] < 108.0
    assert item["excluded_at_hub"] is False
    assert item["excluded_scope_locations"] == []


def test_supplier_without_profile_reports_null_not_zero(client, tokens):
    """Yang TIDAK punya sumber tetap NULL, bukan 0.

    NULL berarti "tidak diketahui"; 0 akan berbohong (seolah kapasitasnya nol)
    dan bisa memicu perhitungan yang salah di UI.

    Perubahan sadar 2026-10-16 (keputusan pemilik): profil yang BISA diturunkan
    dari batch kiriman kini terisi — `Supplier A Cianjur` (3 batch telur) jadi
    `commodity=telur`, `certification_status=haccp`. Yang tidak punya batch
    (mis. `Supplier Medan-1`) tetap kosong, dan `capacity_kg_per_week` selalu
    kosong karena tidak ada satu pun sumber datanya.
    """
    telur = client.get(
        "/suppliers?q=Supplier%20A%20Cianjur", headers=tokens["bgn_monitor"]
    ).json()["items"][0]
    assert telur["commodity"] == "telur"
    assert telur["certification_status"] == "haccp"
    assert telur["capacity_kg_per_week"] is None
    assert telur["latitude"] is not None  # koordinat di-backfill migrasi 012

    tanpa_batch = client.get(
        "/suppliers?q=Supplier%20Medan-1", headers=tokens["bgn_monitor"]
    ).json()["items"][0]
    assert tanpa_batch["commodity"] is None
    assert tanpa_batch["certification_status"] is None
    assert tanpa_batch["capacity_kg_per_week"] is None


def test_suppliers_filter_by_commodity(client, tokens):
    """Telur: 4 pemasok klaster Jakarta + 2 pemasok hub lain (Surabaya, Medan).

    Angka ini sadar berubah dua kali: Fase 7 (2026-10-15) 10 → 6; lalu
    2026-10-16 profil kanonik A/B/C Cianjur terisi dari batch kiriman telur
    → 6 + 3 = 9.
    """
    resp = client.get("/suppliers?commodity=telur", headers=tokens["bgn_monitor"])
    body = resp.json()
    assert body["count"] == 9
    assert {i["commodity"] for i in body["items"]} == {"telur"}
    # Kanonik yang kini ikut tersaring membuktikan profilnya memang terisi.
    assert "Supplier A Cianjur" in {i["name"] for i in body["items"]}


def test_suppliers_filter_by_location(client, tokens):
    """Cianjur: 5 pemasok kanonik (termasuk beras) + 1 pemasok demo."""
    resp = client.get("/suppliers?location=cianjur", headers=tokens["bgn_monitor"])
    body = resp.json()
    assert body["count"] == 6
    assert {i["location"] for i in body["items"]} == {"Cianjur"}


def test_suppliers_unknown_filter_returns_empty_not_404(client, tokens):
    resp = client.get("/suppliers?location=Atlantis", headers=tokens["bgn_monitor"])
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_suppliers_search_and_pagination(client, tokens):
    one = client.get("/suppliers?q=BANDUNGAN", headers=tokens["bgn_monitor"]).json()
    assert one["count"] == 1 and one["items"][0]["name"] == "Wortel Bandungan"

    page = client.get("/suppliers?limit=5&offset=30", headers=tokens["bgn_monitor"]).json()
    assert page["total"] == TOTAL_SUPPLIERS
    # Jumlah baris halaman = min(limit, sisa baris) — bukan "total − offset",
    # yang hanya kebetulan sama ketika sisa baris <= limit (41 pemasok kini
    # menyisakan 11 baris untuk halaman ini, jadi yang benar 5).
    assert page["count"] == min(page["limit"], TOTAL_SUPPLIERS - 30)
    assert page["limit"] == 5 and page["offset"] == 30

    first = client.get("/suppliers?limit=5", headers=tokens["bgn_monitor"]).json()
    names_first = [i["name"] for i in first["items"]]
    names_page = [i["name"] for i in page["items"]]
    assert not set(names_first) & set(names_page)  # halaman tidak tumpang tindih


@pytest.mark.parametrize("query", ["limit=0", "limit=999", "offset=-1"])
def test_suppliers_rejects_out_of_range_window(client, tokens, query):
    assert client.get(f"/suppliers?{query}", headers=tokens["bgn_monitor"]).status_code == 422


def test_exclusion_flag_is_scope_local(client, tokens):
    """Eksklusi bersifat lokal-cakupan: dilaporkan BESERTA nama lokasinya.

    Pemasok demo "Telur Berkah Cianjur" dikecualikan di Cianjur (hub-nya) dan di
    Jakarta. Baris tetap muncul di daftar (daftar = data sumber, tidak
    disaring), tetapi membawa dua nama cakupan itu supaya UI bisa menyatakan
    "dikecualikan di ..." tanpa mengklaim eksklusi nasional.
    """
    supplier_id = None
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            supplier_id = conn.execute(
                text("SELECT id FROM suppliers WHERE name = 'Telur Berkah Cianjur'")
            ).scalar_one()
            scope_ids = dict(
                conn.execute(
                    text(
                        "SELECT name, id FROM locations WHERE name IN ('Cianjur','Jakarta')"
                    )
                ).all()
            )
            decision_id = conn.execute(text("SELECT id FROM decisions LIMIT 1")).scalar_one()
            user_id = conn.execute(text("SELECT id FROM users LIMIT 1")).scalar_one()
            for name in ("Cianjur", "Jakarta"):
                conn.execute(
                    text(
                        "INSERT INTO supplier_exclusions "
                        "(id, supplier_id, scope_location_id, status, reason, evidence_refs, "
                        " source_decision_id, proposed_by, activated_at) "
                        "VALUES (gen_random_uuid(), :s, :l, 'active', 'uji cakupan', "
                        " '[]'::jsonb, :d, :u, now())"
                    ),
                    {"s": supplier_id, "l": scope_ids[name], "d": decision_id, "u": user_id},
                )

        resp = client.get("/suppliers?q=Telur%20Berkah%20Cianjur", headers=tokens["bgn_monitor"])
        assert resp.status_code == 200, resp.text
        item = resp.json()["items"][0]
        assert item["excluded_at_hub"] is True
        assert item["excluded_scope_locations"] == ["Cianjur", "Jakarta"]

        # Pemasok lain di hub yang sama tidak ikut tertandai.
        other = client.get("/suppliers?q=Wortel%20Lestari%20Cianjur", headers=tokens["bgn_monitor"])
        assert other.json()["items"][0]["excluded_at_hub"] is False
    finally:
        if supplier_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM supplier_exclusions WHERE supplier_id = :s"),
                    {"s": supplier_id},
                )
        engine.dispose()


def test_suppliers_response_is_json_serializable_contract(client, tokens):
    """Kunci respons stabil — frontend memetakkannya langsung, jadi kunci hilang = bug."""
    body = client.get("/suppliers?limit=1", headers=tokens["bgn_monitor"]).json()
    assert set(body.keys()) == {
        "count",
        "total",
        "limit",
        "offset",
        "distance_reference",
        "reach",
        "items",
    }
    expected = {
        "id",
        "name",
        "location_id",
        "location",
        "latitude",
        "longitude",
        "commodity_id",
        "commodity",
        "reliability_score",
        "capacity_kg_per_week",
        "certification_status",
        "address",
        "contact_name",
        "distance_km",
        # Keputusan pemilik 2026-10-16: kunci `shipping` (ringkasan kiriman layak)
        # ikut ke kontrak JSON — null bila pemasok tidak sedang mengirim.
        "shipping",
        "excluded_at_hub",
        "excluded_scope_locations",
    }
    assert set(body["items"][0].keys()) == expected
    assert uuid.UUID(body["items"][0]["id"])  # id valid, bukan string bebas
    json.dumps(body)  # tidak ada tipe non-serializable


# --------------------------------------------------------------------------
# Fase 7b (2026-10-15) — jarak & "terjangkau" sebagai RELEVANSI, bukan scope
# --------------------------------------------------------------------------


def test_distance_is_measured_from_the_users_own_location(client, tokens):
    """Peran SPPG: jaraknya diukur dari SPPG-nya, dan rujukannya dinyatakan."""
    body = client.get("/suppliers?limit=200", headers=tokens["sppg_head"]).json()
    assert body["distance_reference"]["location"] == "Jakarta"
    assert body["distance_reference"]["latitude"] == pytest.approx(-6.2088, abs=0.01)

    by_name = {i["name"]: i["distance_km"] for i in body["items"]}
    # Angka-angka ini berasal dari koordinat di data/seed/suppliers_demo.json
    # (diuji terpisah di test_suppliers_data.py) — di sini yang diperiksa:
    # endpoint mengembalikan jarak yang bisa dicocokkan akal sehat.
    assert by_name["Sayur Segar Kramat Jati"] < 10
    assert 40 < by_name["Telur Berkah Bogor"] < 50
    assert 100 < by_name["Wortel Lestari Subang"] < 120
    assert by_name["Wortel Bandungan"] > 300  # Semarang, memang jauh


def test_monitor_has_no_reference_without_location_filter(client, tokens):
    """Nasional = tanpa rujukan tunggal, jadi jaraknya null (bukan 0, bukan ditebak)."""
    body = client.get("/suppliers?limit=5", headers=tokens["bgn_monitor"]).json()
    assert body["distance_reference"] is None
    assert all(i["distance_km"] is None for i in body["items"])
    assert body["reach"]["excluded_out_of_reach"] == 0


def test_monitor_can_use_location_filter_as_reference(client, tokens):
    """Monitor boleh memakai hub pada filter `location=` sebagai rujukan."""
    body = client.get(
        "/suppliers?location=Jakarta&limit=200", headers=tokens["bgn_monitor"]
    ).json()
    assert body["distance_reference"]["location"] == "Jakarta"
    jakarta = next(i for i in body["items"] if i["name"] == "Telur Berkah Jakarta")
    assert jakarta["distance_km"] < 15


def test_max_distance_filters_and_reports_what_it_hid(client, tokens):
    """Penyaring relevansi: baris jauh dikeluarkan, jumlahnya DIUMUMKAN."""
    full = client.get("/suppliers?limit=200", headers=tokens["sppg_head"]).json()
    near = client.get(
        "/suppliers?max_distance_km=150&limit=200", headers=tokens["sppg_head"]
    ).json()

    assert near["total"] < full["total"]
    assert near["reach"]["max_distance_km"] == 150.0
    assert near["reach"]["excluded_out_of_reach"] == full["total"] - near["total"]
    assert near["reach"]["excluded_unknown_distance"] == 0
    assert all(i["distance_km"] <= 150 for i in near["items"])

    names = {i["name"] for i in near["items"]}
    assert "Prima Ayam Sejahtera Jakarta" in names  # 13,4 km
    assert "Telur Berkah Bogor" in names  # 43,4 km
    assert "Wortel Lestari Subang" in names  # 108,6 km
    assert "Wortel Bandungan" not in names  # Semarang, ~400 km

    wide = client.get(
        "/suppliers?max_distance_km=2000&limit=5", headers=tokens["sppg_head"]
    ).json()
    assert wide["total"] == full["total"]  # penyaring longgar tidak menghilangkan apa pun


def test_max_distance_requires_a_reference_point(client, tokens):
    """Tanpa rujukan: 422 — bukan mengembalikan seluruh tabel seolah tersaring."""
    resp = client.get("/suppliers?max_distance_km=150", headers=tokens["bgn_monitor"])
    assert resp.status_code == 422
    assert "rujukan" in resp.json()["detail"]

    ok = client.get(
        "/suppliers?location=Jakarta&max_distance_km=150", headers=tokens["bgn_monitor"]
    )
    assert ok.status_code == 200


@pytest.mark.parametrize("value", ["-1", "5000"])
def test_max_distance_is_range_checked(client, tokens, value):
    assert (
        client.get(
            f"/suppliers?max_distance_km={value}", headers=tokens["sppg_head"]
        ).status_code
        == 422
    )


# ---------------------------------------------------------------------------
# "Sedang mengirim" (keputusan pemilik 2026-10-16): pemasok yang batch kirimannya
# MASIH LAYAK hari ini. Endpoint yang menghitung - peta/daftar hanya menampilkan.
# ---------------------------------------------------------------------------


def _sql_shipping(supplier_name: str) -> dict:
    """Angka pembanding langsung dari DB (API vs SQL), tanpa lewat endpoint."""
    engine = create_engine(DB_URL)
    now = datetime.now(UTC)
    with engine.connect() as conn:
        total, kg, until, fails = conn.execute(
            text(
                """
                SELECT count(*), coalesce(sum(b.quantity_kg), 0), max(b.usable_until),
                       count(*) FILTER (WHERE b.safety_status = 'fail')
                FROM batches b
                JOIN suppliers s ON s.id = b.supplier_id
                WHERE s.name = :name AND b.usable_until >= :now
                """
            ),
            {"name": supplier_name, "now": now},
        ).one()
    return {"count": total, "total_kg": float(kg), "until": until, "fails": fails}


def test_item_carries_shipping_field(client, tokens):
    """Setiap baris membawa kunci `shipping` (null bila tidak sedang mengirim)."""
    body = client.get("/suppliers?limit=200", headers=tokens["sppg_head"]).json()

    assert all("shipping" in item for item in body["items"])
    no_batch = next(i for i in body["items"] if i["name"] == "Telur Berkah Jakarta")
    assert no_batch["shipping"] is None


def test_shipping_matches_sql_for_active_supplier(client, tokens):
    """Supplier A Cianjur: 4 kiriman layak, 2.200 kg, semuanya telur — sama dengan SQL.

    Sebelum Fase 10 angkanya 3 kiriman / 1.400 kg. Kiriman kanonik ke SPPG Jakarta
    (800 kg, keputusan pemilik 2026-10-16) menambah satu kiriman layak, jadi angka
    tes ini berubah SADAR karena data berubah — bukan karena aturannya dilonggarkan.
    """
    body = client.get(
        "/suppliers?q=Supplier%20A%20Cianjur", headers=tokens["sppg_head"]
    ).json()
    item = next(i for i in body["items"] if i["name"] == "Supplier A Cianjur")
    sql = _sql_shipping("Supplier A Cianjur")

    assert sql["count"] == 4, "prasyarat: seed kanonik utuh (Fase 10 menambah kiriman Jakarta)"
    assert item["shipping"]["count"] == sql["count"]
    assert item["shipping"]["total_kg"] == sql["total_kg"] == 2200.0
    assert item["shipping"]["commodities"] == ["telur"]
    assert item["shipping"]["safety_fail_count"] == 0
    assert datetime.fromisoformat(item["shipping"]["until"]) == sql["until"]


def test_shipping_reports_batch_that_failed_testing(client, tokens):
    """Supplier B Cianjur mengirim telur 600 kg yang gagal uji - dilaporkan, bukan disembunyikan."""
    body = client.get(
        "/suppliers?q=Supplier%20B%20Cianjur", headers=tokens["sppg_head"]
    ).json()
    item = next(i for i in body["items"] if i["name"] == "Supplier B Cianjur")

    assert item["shipping"]["count"] == 1
    assert item["shipping"]["safety_fail_count"] == 1


def test_expired_batch_is_not_counted(client, tokens):
    """Supplier C Cianjur: kirimannya layak sampai 10 Sep → tidak dihitung hari ini."""
    body = client.get(
        "/suppliers?q=Supplier%20C%20Cianjur", headers=tokens["sppg_head"]
    ).json()
    item = next(i for i in body["items"] if i["name"] == "Supplier C Cianjur")

    assert _sql_shipping("Supplier C Cianjur")["count"] == 0
    assert item["shipping"] is None
