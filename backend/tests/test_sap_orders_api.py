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
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.po_number import nomor_po
from app.main import app
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_SYNC

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
    # Fase 5: arti harga dinamai eksplisit, dan dua arti biaya dikirim terpisah.
    # `price_per_kg` dipertahankan sebagai alias (artinya sama: harga yang
    # ditagihkan), `cost_legacy` menyebut basis harganya, `sdc_total` adalah
    # pembanding analitis (bukan tagihan; NULL untuk PO tanpa keputusan).
    "invoice_unit_price",
    "invoice_total",
    "cost_legacy",
    "cost_legacy_label",
    "sdc_total",
    "source",
    # Asal baris: PO yang lahir dari eksekusi keputusan vs baris seed demo.
    # Dipakai panel untuk berhenti menyebut semua baris "terbit dari eksekusi".
    "origin",
    # Dok 05 §9 butir 3: nilai PO dan nilai barang yang masuk berdampingan.
    # Server menghitung sisi "masuk" dari ikatan bukti `human_inspection`
    # (`payload->'batch_ids'`), jalur yang sama dengan nilai penerimaan.
    # `None` = belum ada barang tercatat — BUKAN 0 kg dan BUKAN Rp 0.
    "received_kg",
    "received_value_idr",
    "variance_idr",
    "variance_pct",
    "received_batch_count",
    "received_basis",
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


def _realisasi_ground_truth() -> dict[str, float]:
    """kg terikat per PO, dihitung ulang dari DB (bukan angka mati).

    Dedupe `DISTINCT` penting: satu batch bisa tercatat di beberapa bukti untuk
    keputusan yang sama, dan tanpa dedupe jumlahnya akan berlipat.
    """
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "WITH ikatan AS ("
                    " SELECT DISTINCT po.po_number, b.id AS batch_id, b.quantity_kg"
                    " FROM sap_mock_purchase_orders po"
                    " JOIN decisions d ON d.id = po.decision_id"
                    " JOIN decision_evidence e ON e.decision_id = d.id"
                    "  AND e.evidence_type = 'human_inspection'"
                    " CROSS JOIN LATERAL jsonb_array_elements_text("
                    "  CASE WHEN jsonb_typeof(e.payload->'batch_ids') = 'array'"
                    "   THEN e.payload->'batch_ids' ELSE '[]'::jsonb END) AS t(batch_id)"
                    " JOIN batches b ON b.id::text = t.batch_id)"
                    " SELECT po_number, SUM(quantity_kg) AS kg FROM ikatan"
                    " GROUP BY po_number"
                )
            ).mappings().all()
            return {str(r["po_number"]): float(r["kg"]) for r in rows}
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


@pytest.fixture()
def po_ber_keputusan():
    """Pastikan ADA satu PO yang lahir dari keputusan selama tes ini berjalan.

    Dua tes di berkas ini butuh contoh PO ber-`decision_id`, dan dulu keduanya
    mengambil "sisa" baris milik suite lain: begitu tes lain membuang keputusan
    demo (FK `ON DELETE CASCADE`), baris itu ikut hilang dan `next(...)` melempar
    StopIteration — merah yang tidak ada hubungannya dengan endpoint.

    Fixture ini membuat pasangan keputusan+PO sendiri bila DB tidak punya, lalu
    menghapusnya kembali; bila sudah ada baris milik tes lain, fixture tidak
    menyentuhnya.
    """
    kunci = uuid.uuid5(uuid.NAMESPACE_URL, "mealchain:uji-po-filter")
    nomor = nomor_po(kunci)
    engine = create_engine(DB_URL)
    dibuat = False
    try:
        with engine.begin() as conn:
            ada = conn.execute(
                text(
                    "SELECT decision_id FROM sap_mock_purchase_orders "
                    "WHERE decision_id IS NOT NULL LIMIT 1"
                )
            ).scalar_one_or_none()
            if ada is None:
                komoditas = conn.execute(
                    text("SELECT id FROM commodities ORDER BY name LIMIT 1")
                ).scalar_one()
                pemasok = conn.execute(
                    text("SELECT id FROM suppliers ORDER BY name LIMIT 1")
                ).scalar_one()
                # Sisa percobaan sebelumnya (bila tes pernah terhenti) dibersihkan
                # lewat NOMOR + id tetap, bukan tebakan.
                conn.execute(
                    text("DELETE FROM sap_mock_purchase_orders WHERE po_number = :n"),
                    {"n": nomor},
                )
                conn.execute(
                    text("DELETE FROM decisions WHERE id = CAST(:id AS uuid)"),
                    {"id": str(kunci)},
                )
                conn.execute(
                    text(
                        "INSERT INTO decisions (id, decision_type, status, proposed_by, "
                        "commodity_id, supplier_id, quantity_kg, safe_delivered_cost, "
                        "expires_at, created_at, origin) VALUES (CAST(:id AS uuid), "
                        "'supplier_procurement', 'executed', 'supervisor_agent', "
                        ":komoditas, :pemasok, 100, 2500000, now() + interval '1 hour', "
                        "now(), 'demo')"
                    ),
                    {"id": str(kunci), "komoditas": komoditas, "pemasok": pemasok},
                )
                conn.execute(
                    text(
                        "INSERT INTO sap_mock_purchase_orders (id, po_number, supplier_id, "
                        "material_number, ordered_quantity, price, status, decision_id, "
                        "created_at) VALUES (CAST(:id AS uuid), :n, :pemasok, 'MAT-UJI', "
                        "100, 25000, 'confirmed', CAST(:dec AS uuid), now())"
                    ),
                    {
                        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "mealchain:uji-po-filter:po")),
                        "n": nomor,
                        "pemasok": pemasok,
                        "dec": str(kunci),
                    },
                )
                dibuat = True
        yield str(kunci) if dibuat else str(ada)
    finally:
        if dibuat:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM sap_mock_purchase_orders WHERE po_number = :n"),
                    {"n": nomor},
                )
                conn.execute(
                    text("DELETE FROM decisions WHERE id = CAST(:id AS uuid)"),
                    {"id": str(kunci)},
                )
        engine.dispose()


def test_nama_komoditas_dari_keputusan_bukan_tebakan_kode(
    client, monitor_headers, po_ber_keputusan
):
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


def test_filter_decision_id(client, monitor_headers, po_ber_keputusan):
    semua = _get(client, monitor_headers, limit=200).json()["items"]
    target = next(r for r in semua if r["decision_id"])
    resp = _get(client, monitor_headers, decision_id=target["decision_id"])
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert [r["po_number"] for r in items] == [target["po_number"]]
    assert _get(client, monitor_headers, decision_id="bukan-uuid").status_code == 422


def test_tidak_ada_po_artefak_tanpa_keputusan():
    """PO bernomor `MC-...` wajib punya keputusan induk (S4-37).

    Nomor `MC-` hanya lahir dari `nomor_po(decision_id)`, jadi baris `MC-`
    dengan `decision_id IS NULL` pasti artefak penghapusan keputusan (FK lama
    `ON DELETE SET NULL`), bukan data. Baris impor SAP bernomor numerik
    (`4500000xxx`) memang tanpa keputusan — itu sah dan dibiarkan.
    """
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            yatim = (
                conn.execute(
                    text(
                        "SELECT po_number FROM sap_mock_purchase_orders "
                        "WHERE decision_id IS NULL AND po_number LIKE 'MC-%' "
                        "ORDER BY po_number"
                    )
                )
                .scalars()
                .all()
            )
    finally:
        engine.dispose()
    assert not yatim, "PO artefak tanpa keputusan: " + ", ".join(yatim)


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


def test_realisasi_po_cocok_dengan_db(client, auth_headers):
    """Nilai barang masuk = harga satuan × kg terikat, dihitung dari DB.

    Angkanya dibandingkan dengan kueri pembanding saat tes berjalan: kalau
    agregasi server menggandakan batch atau salah harga, tes ini gagal.
    """
    rows = _get(client, auth_headers).json()["items"]
    truth = _realisasi_ground_truth()
    berangka = [r for r in rows if r["po_number"] in truth]
    assert berangka, "tidak ada PO berikatan bukti di cakupan ini"

    for r in berangka:
        kg = truth[r["po_number"]]
        assert r["received_kg"] == pytest.approx(kg), r["po_number"]
        assert r["received_value_idr"] == pytest.approx(
            round(r["price_per_kg"] * kg, 2)
        ), r["po_number"]
        assert r["variance_idr"] == pytest.approx(
            round(r["received_value_idr"] - r["total_value"], 2)
        ), r["po_number"]
        assert r["received_batch_count"] >= 1, r["po_number"]
        assert r["received_basis"] == "inspection_binding"


def test_po_tanpa_ikatan_none_bukan_nol(client, auth_headers):
    """PO tanpa bukti penerimaan tidak boleh tampil sebagai "Rp 0".

    0 adalah klaim ("tidak ada barang masuk"); None adalah fakta ("belum ada
    catatan"). Panel menampilkan keduanya dengan kalimat berbeda, jadi kontrak
    ini dipaku di API.
    """
    rows = _get(client, auth_headers).json()["items"]
    truth = _realisasi_ground_truth()
    kosong = [r for r in rows if r["po_number"] not in truth]
    assert kosong, "cakupan ini tidak punya PO tanpa ikatan — tes tidak bermakna"

    for r in kosong:
        assert r["received_kg"] is None, r["po_number"]
        assert r["received_value_idr"] is None, r["po_number"]
        assert r["variance_idr"] is None, r["po_number"]
        assert r["variance_pct"] is None, r["po_number"]
        assert r["received_batch_count"] == 0, r["po_number"]
        assert r["received_basis"] is None, r["po_number"]
