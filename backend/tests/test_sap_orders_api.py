"""Purchase order mock SAP terbaca (W-5 · 2026-10-17) — kontrak + cakupan.

Latar: `sap_mock_purchase_orders` sudah lama DITULIS `api/actions.py` setiap kali
keputusan dieksekusi (saat ini 11 baris di DB demo), tetapi tidak ada satu rute
pun yang membacanya. Satu-satunya jejak di layar adalah toast sesaat
`DecisionActions.tsx`, dan `SAPDataProvider.get_purchase_orders()` hanya dipanggil
tes. Akibatnya klaim "dua approval → PO terbit" tidak bisa ditunjukkan.

Yang dipaku di berkas ini, dan alasannya:

1. Tanpa token → **401**. Read-only bukan berarti publik.
2. Kontrak kolom tetap: `po_number`, `status`, `created_at`, `decision_id`,
   `decision_status`, `location_id`, `location_name`, `supplier_id`,
   `supplier_name`, `material_number`, `ordered_quantity_kg`, `price_per_kg`,
   `total_value`, dan **`source == "mock_sap_table"`**.
   `source` wajib ada supaya panel bisa menyebut asalnya apa adanya: ini tabel
   transaksi mock di DB demo, BUKAN SAP S/4HANA nyata.
3. **Sumber data = tabel DB**, bukan `MockSAPProvider.get_purchase_orders()`
   yang mengembalikan dict `_POS` hardcoded. Kalau endpoint disambungkan ke
   adapter, jumlah barisnya tidak akan sama dengan isi tabel — tes 3 & 4 gagal.
4. **Cakupan** mengikuti `core/scope.py`: `sppg_head`/`sppg_nutritionist` hanya
   PO milik lokasi tujuannya; `bgn_monitor` lintas lokasi. PO tanpa keputusan
   (`decision_id IS NULL`, mis. baris seed/adapter) hanya terlihat monitor —
   PO tanpa lokasi tidak boleh bocor ke SPPG mana pun.
5. Nilai uang/kuantitas dibaca apa adanya dari kolom `price` dan
   `ordered_quantity` (tidak dihitung ulang); `total_value = price × qty`.
6. Read-only murni: tidak ada rute tulis (POST/PUT/PATCH/DELETE → 405).

Tabel PO dipakai bersama suite lain (eksekusi keputusan menambah baris), jadi
semua pembanding diambil dari DB saat tes berjalan, bukan angka mati.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

FIELDS = {
    "po_number",
    "status",
    "created_at",
    "decision_id",
    "decision_status",
    "location_id",
    "location_name",
    "supplier_id",
    "supplier_name",
    "material_number",
    # Nama komoditas dari relasi keputusan (bukan tebakan dari kode bahan:
    # seeder memakai `MAT-{nama[:4]}` sehingga `MAT-BERA` bukan kata yang layak
    # ditampilkan). NULL untuk baris impor tanpa keputusan.
    "commodity_name",
    "ordered_quantity_kg",
    "price_per_kg",
    "total_value",
    "source",
    # Asal baris: PO yang lahir dari eksekusi keputusan vs baris seed demo.
    # Dipakai panel untuk berhenti menyebut semua baris "terbit dari eksekusi".
    "origin",
}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _po_rows(location: str | None) -> list[dict]:
    """Ground truth dari DB untuk cakupan tertentu (None = nasional)."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            sql = (
                "SELECT po.po_number, po.status, l.name AS location_name "
                "FROM sap_mock_purchase_orders po "
                "LEFT JOIN decisions d ON d.id = po.decision_id "
                "LEFT JOIN locations l ON l.id = d.target_location_id "
            )
            if location is not None:
                sql += "WHERE l.name = :loc "
            sql += "ORDER BY po.created_at DESC"
            rows = conn.execute(
                text(sql), {"loc": location} if location else {}
            ).mappings().all()
            return [dict(r) for r in rows]
    finally:
        engine.dispose()


def _get(client, headers, path="/sap/purchase-orders", **params):
    return client.get(path, headers=headers, params=params)


def test_tanpa_token_401(client):
    resp = client.get("/sap/purchase-orders")
    assert resp.status_code == 401, resp.text
    assert client.get("/sap/purchase-orders/summary").status_code == 401


def test_kontrak_kolom_dan_label_sumber(client, monitor_headers):
    resp = _get(client, monitor_headers, limit=5)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"], "DB demo selalu punya PO (seed DEMO-PO-*)"
    row = body["items"][0]
    assert set(row) == FIELDS, sorted(set(row) ^ FIELDS)
    assert row["source"] == "mock_sap_table"
    assert row["origin"] in {"execution", "demo"}
    assert row["status"] in {"draft", "submitted", "confirmed"}
    assert row["ordered_quantity_kg"] > 0
    assert row["price_per_kg"] > 0
    # total dihitung dari kolom yang ada, bukan angka karangan
    assert row["total_value"] == pytest.approx(
        row["ordered_quantity_kg"] * row["price_per_kg"], rel=1e-6
    )
    assert body["count"] == len(body["items"])


def test_cakupan_kepala_sppg_hanya_lokasinya(client, auth_headers):
    resp = _get(client, auth_headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert items, "seed punya PO untuk Jakarta (DEMO-PO-JAKA-AYAM)"
    for row in items:
        assert row["location_name"] == "Jakarta", row["po_number"]
        assert row["decision_id"], "PO tanpa keputusan = tanpa lokasi → bukan hak SPPG"
    nomor = {r["po_number"] for r in items}
    assert len(nomor) == len(items), "tidak boleh ada baris ganda"
    # ground truth: jumlahnya sama dengan baris ber-target Jakarta
    assert len(items) == len(_po_rows("Jakarta"))


def test_cakupan_monitor_lintas_lokasi(client, monitor_headers):
    resp = _get(client, monitor_headers, limit=200)
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    lokasi = {r["location_name"] for r in items if r["location_name"]}
    assert {"Jakarta", "Bandung", "Surabaya"} <= lokasi, lokasi
    # monitor melihat baris tanpa keputusan juga (seed/adapter), SPPG tidak
    assert any(r["decision_id"] is None for r in items)
    assert len(items) == len(_po_rows(None))


def test_ahli_gizi_lokasi_lain_dapat_daftar_kosong_bukan_403(
    client, far_nutritionist_headers
):
    resp = _get(client, far_nutritionist_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"] == []
    assert body["count"] == 0


def test_filter_status_dan_validasi(client, monitor_headers):
    resp = _get(client, monitor_headers, status="confirmed")
    assert resp.status_code == 200, resp.text
    assert {r["status"] for r in resp.json()["items"]} == {"confirmed"}
    assert _get(client, monitor_headers, status="hilang").status_code == 422


def test_nama_komoditas_dari_keputusan_bukan_tebakan_kode(client, monitor_headers):
    """Baris ber-keputusan membawa nama komoditas relasional; baris impor tidak.

    Panel tidak boleh menebak dari `material_number`: seeder memakai
    `MAT-{nama[:4]}` (`MAT-BERA`), sehingga tebakan menghasilkan kata rusak
    ("Bera") di layar.
    """
    items = _get(client, monitor_headers, limit=200).json()["items"]
    ber_keputusan = [r for r in items if r["decision_id"]]
    assert ber_keputusan, "seed demo punya PO ber-keputusan"
    for row in ber_keputusan:
        assert row["commodity_name"], row["po_number"]
        assert row["commodity_name"] != row["material_number"]
    # ground truth: nama itu memang nama komoditas keputusannya, bukan karangan
    contoh = ber_keputusan[0]
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            harap = conn.execute(
                text(
                    "SELECT c.name FROM decisions d JOIN commodities c "
                    "ON c.id = d.commodity_id WHERE d.id = :id"
                ),
                {"id": contoh["decision_id"]},
            ).scalar_one()
    finally:
        engine.dispose()
    assert contoh["commodity_name"] == harap
    # baris tanpa keputusan tidak punya komoditas — jangan dikarang
    for row in items:
        if row["decision_id"] is None:
            assert row["commodity_name"] is None, row["po_number"]


def test_filter_decision_id(client, monitor_headers):
    semua = _get(client, monitor_headers, limit=200).json()["items"]
    target = next(r for r in semua if r["decision_id"])
    resp = _get(client, monitor_headers, decision_id=target["decision_id"])
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert [r["po_number"] for r in items] == [target["po_number"]]
    assert _get(client, monitor_headers, decision_id="bukan-uuid").status_code == 422


def test_limit_dijepit(client, monitor_headers):
    assert len(_get(client, monitor_headers, limit=1).json()["items"]) == 1
    body = _get(client, monitor_headers, limit=10_000).json()
    assert len(body["items"]) <= 200
    assert body["limit"] <= 200


def test_summary_mengikuti_cakupan(client, auth_headers, monitor_headers):
    kepala = _get(client, auth_headers, path="/sap/purchase-orders/summary")
    assert kepala.status_code == 200, kepala.text
    ringkas = kepala.json()
    assert set(ringkas["by_status"]) == {"draft", "submitted", "confirmed"}
    items = _get(client, auth_headers).json()["items"]
    assert sum(ringkas["by_status"].values()) == len(items)
    assert ringkas["total_value"] == pytest.approx(
        sum(r["total_value"] for r in items), rel=1e-6
    )
    monitor = _get(client, monitor_headers, path="/sap/purchase-orders/summary").json()
    assert sum(monitor["by_status"].values()) >= sum(ringkas["by_status"].values())


def test_tidak_ada_rute_tulis(client, monitor_headers):
    for method in ("post", "put", "patch", "delete"):
        resp = getattr(client, method)("/sap/purchase-orders", headers=monitor_headers)
        assert resp.status_code == 405, f"{method} seharusnya 405, dapat {resp.status_code}"


def test_asal_po_mengikuti_ada_tidaknya_keputusan(client, monitor_headers):
    """`origin` adalah fakta turunan, bukan label seragam.

    Baris yang lahir dari eksekusi selalu punya `decision_id`; baris seed demo
    tidak. Kalau endpoint melabeli semua baris sama, panel akan mengklaim PO
    demo "terbit dari eksekusi" — persis yang dicegah tes ini.
    """
    body = _get(client, monitor_headers, limit=200).json()
    assert body["items"], "DB demo selalu punya PO"
    for row in body["items"]:
        harapan = "execution" if row["decision_id"] else "demo"
        assert row["origin"] == harapan, f"{row['po_number']}: {row['origin']} != {harapan}"
