"""Detail satu PO sebagai JSON — bahan yang sama dengan PDF PO (29 Okt 2026).

Permintaan pemilik: "latih Joule chat supaya dapat membaca lebih detail seperti
PDF PO". PDF-nya sudah ada (`GET /sap/purchase-orders/{nomor}/pdf`) tetapi
jembatan A2A hanya menerima JSON, dan daftar PO tidak memuat isi dokumen:
rincian biaya, siapa menyetujui dan komentarnya, syarat persetujuan, serta
keputusan yang melahirkannya.

Kontrak berkas ini:

1. `GET /sap/purchase-orders/{nomor}/detail` mengembalikan isi dokumen dalam
   JSON: identitas PO, kuantitas/harga/total, nama material, komoditas, lokasi,
   pemasok, rincian biaya komersial, keputusan asal, daftar persetujuan, syarat.
2. Angka berasal dari kolom DB: `total = price × ordered_quantity`.
3. `boleh_pdf` mengikuti aturan dokumen (`po_document.boleh_pdf`), sehingga
   Joule bisa menjawab "PDF-nya sudah bisa diunduh?" tanpa menebak.
4. PO tanpa keputusan tetap terbaca (keputusan `null`, `boleh_pdf` false) —
   baris seed tidak boleh disembunyikan, tetapi tidak boleh diklaim punya PDF.
5. Cakupan sama dengan daftar/PDF: SPPG hanya PO lokasi tujuannya (404, bukan
   403 — keberadaan PO lokasi lain tidak bocor).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC

DB_URL = DSN_SYNC


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c

FIELDS = {
    "po_number",
    "status",
    "created_at",
    "material_number",
    "commodity_name",
    "location_name",
    "supplier_name",
    "ordered_quantity",
    "price",
    "total",
    "commercial_cost",
    "keputusan",
    "persetujuan",
    "syarat",
    "boleh_pdf",
    "source",
}


def _rows(sql: str, params: dict | None = None) -> list[dict]:
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return [dict(r) for r in conn.execute(text(sql), params or {}).mappings().all()]
    finally:
        engine.dispose()


def _po_berkeputusan(statuses: tuple[str, ...] = ("approved", "executed")) -> dict:
    rows = _rows(
        "SELECT po.po_number, d.status AS status_keputusan, d.id AS decision_id, "
        "l.name AS location_name "
        "FROM sap_mock_purchase_orders po JOIN decisions d ON d.id = po.decision_id "
        "JOIN locations l ON l.id = d.target_location_id "
        "ORDER BY po.created_at DESC"
    )
    assert rows, "DB demo harus punya PO yang lahir dari keputusan"
    cocok = [r for r in rows if r["status_keputusan"] in statuses]
    assert cocok, f"tidak ada PO dengan keputusan {statuses}"
    return cocok[0]


def test_tanpa_token_401(client):
    assert client.get("/sap/purchase-orders/MC-000000000000/detail").status_code == 401


def test_detail_memuat_isi_dokumen(client, monitor_headers):
    po = _po_berkeputusan()
    resp = client.get(
        f"/sap/purchase-orders/{po['po_number']}/detail", headers=monitor_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == FIELDS, sorted(set(body) ^ FIELDS)
    assert body["po_number"] == po["po_number"]
    assert body["source"] == "mock_sap_table"
    assert body["location_name"] == po["location_name"]
    assert body["ordered_quantity"] > 0 and body["price"] > 0
    assert body["total"] == pytest.approx(body["ordered_quantity"] * body["price"], rel=1e-6)
    assert body["boleh_pdf"] is True
    keputusan = body["keputusan"]
    assert keputusan and keputusan["id"] == str(po["decision_id"])
    assert keputusan["status"] == po["status_keputusan"]
    assert "jenis" in keputusan and "iteration" in keputusan and "proposed_by" in keputusan
    assert isinstance(body["persetujuan"], list) and body["persetujuan"]
    for baris in body["persetujuan"]:
        assert set(baris) >= {"role", "name", "approved", "comment", "approved_at"}
    assert set(body["syarat"]) >= {"min_approvals", "required_roles", "satisfied"}


def test_persetujuan_sama_dengan_tabel(client, monitor_headers):
    po = _po_berkeputusan()
    resp = client.get(
        f"/sap/purchase-orders/{po['po_number']}/detail", headers=monitor_headers
    )
    body = resp.json()
    db = _rows(
        "SELECT u.name, u.role, a.approved FROM approvals a "
        "JOIN users u ON u.id = a.approved_by WHERE a.decision_id = :d "
        "ORDER BY a.approved_at ASC, a.id ASC",
        {"d": po["decision_id"]},
    )
    assert [(b["name"], b["role"], b["approved"]) for b in body["persetujuan"]] == [
        (d["name"], d["role"], bool(d["approved"])) for d in db
    ]


def test_po_tanpa_keputusan_tetap_terbaca_tanpa_pdf(client, monitor_headers):
    rows = _rows(
        "SELECT po_number FROM sap_mock_purchase_orders "
        "WHERE decision_id IS NULL ORDER BY created_at DESC LIMIT 1"
    )
    if not rows:
        pytest.skip("seed tidak punya PO tanpa keputusan")
    nomor = rows[0]["po_number"]
    resp = client.get(f"/sap/purchase-orders/{nomor}/detail", headers=monitor_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["keputusan"] is None
    assert body["boleh_pdf"] is False
    assert body["persetujuan"] == []
    assert body["ordered_quantity"] > 0


def test_cakupan_sppg_menolak_po_lokasi_lain(client, auth_headers, monitor_headers):
    semua = client.get(
        "/sap/purchase-orders", headers=monitor_headers, params={"limit": 200}
    ).json()["items"]
    asing = [r for r in semua if r["location_name"] and r["location_name"] != "Jakarta"]
    if not asing:
        pytest.skip("tidak ada PO di luar Jakarta")
    resp = client.get(
        f"/sap/purchase-orders/{asing[0]['po_number']}/detail", headers=auth_headers
    )
    assert resp.status_code == 404, resp.text


def test_nomor_tidak_ada_404(client, monitor_headers):
    resp = client.get("/sap/purchase-orders/MC-FFFFFFFFFFFF/detail", headers=monitor_headers)
    assert resp.status_code == 404, resp.text
