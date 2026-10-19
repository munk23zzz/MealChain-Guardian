"""Dokumen PO sebagai PDF — pagar, isi, dan kejujuran angkanya.

Permintaan pemilik (20 Okt 2026): pada tab Decision & Evidence, PO yang sudah
disetujui harus bisa diunduh sebagai PDF. Berkas ini memaku empat hal:

1. **Pagar persetujuan.** PDF hanya terbit untuk PO yang lahir dari keputusan
   `approved`/`executed`. PO impor tanpa keputusan → 409, keputusan yang masih
   menunggu → 409, nomor tak dikenal → 404. Tidak pernah dokumen kosong.
2. **Cakupan sama dengan daftar.** PO lokasi lain tidak bisa diunduh peran
   SPPG (404 — sama seperti daftar yang tidak memuatnya), dan PO tanpa
   keputusan tidak pernah terlihat oleh peran SPPG.
3. **Isi = angka DB.** Nomor PO, jumlah, harga, total (harga × jumlah), nama
   pemasok/bahan, dan baris persetujuan diambil dari DB saat tes berjalan; teks
   PDF diekstrak ulang untuk membuktikan angkanya benar-benar tercetak.
4. **Label simulasi.** Setiap dokumen menyebut "SAP simulasi" (Rules.md §4) dan
   tidak pernah mengaku sebagai dokumen SAP S/4HANA produksi.

Catatan: pembanding diambil dari DB, bukan angka mati, karena tabel PO dipakai
bersama suite lain (eksekusi keputusan menambah baris).
"""

import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine, text

from app.main import app
from app.services import po_document

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"


# ── Pembantu: angka gaya Indonesia, ditulis ulang di sini (bukan diimpor) ────
# Supaya tes tidak "membuktikan" format dengan fungsi yang sedang diuji.
def _ribu(nilai: float, desimal: int) -> str:
    utuh, _, pecahan = f"{nilai:.{desimal}f}".partition(".")
    negatif = utuh.startswith("-")
    utuh = utuh.lstrip("-")
    kelompok = []
    while len(utuh) > 3:
        kelompok.insert(0, utuh[-3:])
        utuh = utuh[:-3]
    kelompok.insert(0, utuh)
    hasil = ".".join(kelompok)
    if desimal:
        hasil += "," + pecahan
    return ("-" if negatif else "") + hasil


def _rupiah_tes(nilai: float) -> str:
    return f"Rp {_ribu(nilai, 2)}"


def _kg_tes(nilai: float) -> str:
    teks = _ribu(nilai, 1)
    return f"{(teks[:-2] if teks.endswith(',0') else teks)} kg"


def _teks_pdf(isi: bytes) -> str:
    reader = PdfReader(io.BytesIO(isi))
    return "\n".join((halaman.extract_text() or "") for halaman in reader.pages)


def _koneksi():
    return create_engine(DB_URL)


def _po_disertifikasi() -> dict | None:
    """Satu PO yang lahir dari keputusan approved/executed, lengkap dengan
    ground truth kolomnya (nasional — dipakai bersama monitor_headers)."""
    engine = _koneksi()
    try:
        with engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT po.po_number, po.status, po.ordered_quantity, po.price, "
                        "po.material_number, d.id AS decision_id, d.status AS decision_status, "
                        "s.name AS supplier_name, c.name AS commodity_name, "
                        "l.name AS location_name "
                        "FROM sap_mock_purchase_orders po "
                        "JOIN decisions d ON d.id = po.decision_id "
                        "LEFT JOIN suppliers s ON s.id = po.supplier_id "
                        "LEFT JOIN commodities c ON c.id = d.commodity_id "
                        "LEFT JOIN locations l ON l.id = d.target_location_id "
                        "WHERE d.status IN ('approved','executed') "
                        "ORDER BY po.created_at DESC, po.po_number ASC LIMIT 1"
                    )
                )
                .mappings()
                .first()
            )
            return dict(row) if row else None
    finally:
        engine.dispose()


def _po_tanpa_keputusan() -> str | None:
    engine = _koneksi()
    try:
        with engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT po_number FROM sap_mock_purchase_orders "
                    "WHERE decision_id IS NULL ORDER BY po_number LIMIT 1"
                )
            ).scalar_one_or_none()
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ── 1. Logika murni ─────────────────────────────────────────────────────────


def test_hanya_keputusan_disetujui_yang_punya_pdf():
    assert po_document.boleh_pdf("approved")
    assert po_document.boleh_pdf("executed")
    assert po_document.boleh_pdf("EXECUTED")
    belum = ("proposed", "pending_approval", "verifier_flagged", "rejected", "review_only", None)
    for status in belum + ("",):
        assert not po_document.boleh_pdf(status), status


def test_label_tidak_mengarang_status_asing():
    assert po_document.status_po_label("submitted") == "Terkirim"
    assert po_document.status_po_label("confirmed") == "Terkonfirmasi"
    assert po_document.status_po_label("dibatalkan") == "dibatalkan"
    assert po_document.status_keputusan_label("executed") == "Dieksekusi"
    assert po_document.jenis_keputusan_label("regional_balance") == "Penyeimbangan antarwilayah"
    assert po_document.jenis_keputusan_label("entah") == "entah"
    assert po_document.peran_label(None) == "—"


def test_format_angka_indonesia():
    assert po_document.rupiah(4639250) == "Rp 4.639.250,00"
    assert po_document.rupiah(0.5) == "Rp 0,50"
    assert po_document.rupiah(None) == "—"
    assert po_document.kg(120.5) == "120,5 kg"
    assert po_document.kg(1200) == "1.200 kg"
    assert po_document.kg(None) == "—"


def test_nama_berkas_aman():
    assert po_document.nama_berkas("MC-ABCDEF123456") == "PO-MC-ABCDEF123456.pdf"
    assert po_document.nama_berkas("4500000001") == "PO-4500000001.pdf"
    # Karakter aneh tidak boleh lolos ke header Content-Disposition.
    assert "/" not in po_document.nama_berkas("a/b c")


def test_pdf_dokumen_minimal_terbentuk():
    """Tanpa DB: pembangun dokumen tetap menghasilkan PDF yang bisa dibaca."""
    isi = po_document.bangun_pdf(
        {
            "po_number": "MC-TES",
            "status": "submitted",
            "created_at": datetime(2026, 10, 19, 3, 0, tzinfo=timezone.utc),
            "ordered_quantity": 12.5,
            "price": 20000,
            "total": 250000.0,
            "material_number": "MAT-BERA",
            "commodity_name": "Beras",
            "location_name": "Jakarta",
            "supplier_name": "CV Contoh",
            "keputusan": {
                "id": str(uuid.uuid4()),
                "jenis": "regional_balance",
                "status": "executed",
                "iteration": 1,
                "proposed_by": "supervisor_agent",
                "created_at": datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc),
                "expires_at": datetime(2026, 10, 19, 8, 0, tzinfo=timezone.utc),
            },
            "persetujuan": [
                {
                    "role": "sppg_head",
                    "name": "Kepala Uji",
                    "approved": True,
                    "comment": None,
                    "approved_at": datetime(2026, 10, 19, 2, 30, tzinfo=timezone.utc),
                }
            ],
            "syarat": {"min_approvals": 2, "required_roles": [["sppg_head"]], "satisfied": False},
            "dibuat_pada": datetime(2026, 10, 19, 4, 0, tzinfo=timezone.utc),
        }
    )
    assert isi.startswith(b"%PDF")
    assert len(isi) > 2000
    teks = _teks_pdf(isi)
    assert "MC-TES" in teks
    assert "Beras" in teks
    assert _rupiah_tes(250000) in teks
    assert _kg_tes(12.5) in teks
    assert "SAP simulasi" in teks
    assert "Kepala Uji" in teks


# ── 2. Route ────────────────────────────────────────────────────────────────


def test_tanpa_token_401(client):
    resp = client.get("/sap/purchase-orders/MC-APA-SAJA/pdf")
    assert resp.status_code == 401, resp.text


def test_nomor_tidak_dikenal_404(client, monitor_headers):
    resp = client.get("/sap/purchase-orders/PO-TIDAK-ADA/pdf", headers=monitor_headers)
    assert resp.status_code == 404, resp.text


def test_pdf_untuk_po_yang_sudah_disetujui(client, monitor_headers):
    po = _po_disertifikasi()
    assert po is not None, "DB demo tidak punya PO dari keputusan approved/executed"

    resp = client.get(
        f"/sap/purchase-orders/{po['po_number']}/pdf", headers=monitor_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert (
        resp.headers["content-disposition"]
        == f'attachment; filename="PO-{po["po_number"]}.pdf"'
    )
    assert resp.headers.get("cache-control") == "no-store"
    assert resp.content.startswith(b"%PDF")

    teks = _teks_pdf(resp.content)
    qty = float(po["ordered_quantity"])
    harga = float(po["price"])
    # Setiap angka yang tercetak harus bisa dilacak ke kolomnya.
    assert po["po_number"] in teks
    assert _kg_tes(qty) in teks
    assert _rupiah_tes(harga) in teks
    assert _rupiah_tes(round(harga * qty, 2)) in teks
    assert po["supplier_name"] in teks
    assert po["commodity_name"] in teks
    assert str(po["decision_id"]) in teks
    assert "SAP simulasi" in teks
    # Status keputusan tampil sebagai kata, bukan enum mentah.
    assert po_document.status_keputusan_label(po["decision_status"]) in teks


def test_po_tanpa_keputusan_tidak_punya_pdf(client, monitor_headers):
    nomor = _po_tanpa_keputusan()
    assert nomor is not None, "DB demo tidak punya PO impor tanpa keputusan"
    resp = client.get(f"/sap/purchase-orders/{nomor}/pdf", headers=monitor_headers)
    assert resp.status_code == 409, resp.text
    assert "tidak lahir dari keputusan" in resp.json()["detail"]


def test_po_dari_keputusan_belum_disetujui_ditolak(client, monitor_headers):
    """Baris buatan: keputusan `pending_approval` + PO-nya. Dibersihkan di akhir."""
    nomor = f"PYTEST-PO-{uuid.uuid4().hex[:10].upper()}"
    engine = _koneksi()
    decision_id = None
    try:
        with engine.begin() as conn:
            location_id = conn.execute(
                text("SELECT id FROM locations ORDER BY name LIMIT 1")
            ).scalar_one()
            supplier_id = conn.execute(
                text("SELECT id FROM suppliers ORDER BY name LIMIT 1")
            ).scalar_one()
            commodity_id = conn.execute(
                text("SELECT id FROM commodities ORDER BY name LIMIT 1")
            ).scalar_one()
            decision_id = conn.execute(
                text(
                    "INSERT INTO decisions (id, decision_type, status, proposed_by, "
                    "target_location_id, commodity_id, quantity_kg, expires_at, origin) "
                    "VALUES (gen_random_uuid(), 'regional_balance', 'pending_approval', "
                    "'supervisor_agent', :loc, :kom, 100, :exp, 'seed') RETURNING id"
                ),
                {
                    "loc": str(location_id),
                    "kom": str(commodity_id),
                    "exp": datetime.now(timezone.utc) + timedelta(hours=6),
                },
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO sap_mock_purchase_orders (po_number, supplier_id, "
                    "material_number, ordered_quantity, price, decision_id, status) "
                    "VALUES (:nomor, :sup, 'MAT-TES', 100, 15000, :dec, 'submitted')"
                ),
                {"nomor": nomor, "sup": str(supplier_id), "dec": str(decision_id)},
            )

        resp = client.get(f"/sap/purchase-orders/{nomor}/pdf", headers=monitor_headers)
        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"]
        assert "menunggu persetujuan" in detail
        assert "setelah keputusan disetujui" in detail
        assert not resp.content.startswith(b"%PDF")
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM sap_mock_purchase_orders WHERE po_number = :n"),
                {"n": nomor},
            )
            if decision_id is not None:
                conn.execute(
                    text("DELETE FROM decisions WHERE id = :d"), {"d": str(decision_id)}
                )
        engine.dispose()


def test_cakupan_sppg_tidak_bisa_unduh_po_lokasi_lain(client, auth_headers):
    """Peran Kepala SPPG Jakarta: PO lokasi lain = 404, bukan PDF lokasi orang."""
    engine = _koneksi()
    try:
        with engine.connect() as conn:
            nomor = conn.execute(
                text(
                    "SELECT po.po_number FROM sap_mock_purchase_orders po "
                    "JOIN decisions d ON d.id = po.decision_id "
                    "JOIN locations l ON l.id = d.target_location_id "
                    "WHERE d.status IN ('approved','executed') AND l.name <> 'Jakarta' "
                    "ORDER BY po.created_at DESC LIMIT 1"
                )
            ).scalar_one_or_none()
    finally:
        engine.dispose()
    if nomor is None:
        pytest.skip("DB demo tidak punya PO lokasi lain yang sudah dieksekusi")

    resp = client.get(f"/sap/purchase-orders/{nomor}/pdf", headers=auth_headers)
    assert resp.status_code == 404, resp.text
