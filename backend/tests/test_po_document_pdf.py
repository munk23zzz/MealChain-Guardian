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
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_SYNC


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


def _kuantitas_tes(nilai: float) -> str:
    """Angka kolom "Jumlah" saja (satuan punya kolomnya sendiri sejak template
    korporat 29 Okt 2026), tanpa ",0" yang dikarang."""
    teks = _ribu(nilai, 1)
    return teks[:-2] if teks.endswith(",0") else teks


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
    # Kolom "Jumlah" dan "Satuan" terpisah di template korporat (29 Okt 2026),
    # jadi kuantitas diperiksa sebagai angka + satuan, bukan "12,5 kg".
    assert _kuantitas_tes(12.5) in teks
    assert "kg" in teks
    assert "SAP simulasi" in teks
    assert "Kepala Uji" in teks
    # Template korporat: rincian pesanan + pengesahan ada, "Dasar persetujuan"
    # (dihapus atas permintaan pemilik 29 Okt 2026) tidak boleh muncul lagi.
    assert "Rincian pesanan" in teks
    assert "Pengesahan" in teks
    assert "Dasar persetujuan" not in teks
    assert "Safe Delivered Cost" not in teks
    # Seluruh keterangan di bawah tabel rincian dihapus 29 Okt 2026: catatan kaki
    # "*", kalimat arti status, blok "Syarat & ketentuan", kalimat "Sumber angka".
    assert "Syarat & ketentuan" not in teks
    assert "Sumber angka" not in teks
    assert "Status Draf berarti" not in teks
    assert "Status Terkirim berarti" not in teks


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
    assert _kuantitas_tes(qty) in teks
    # Harga satuan tersimpan (invoice unit price) = total ÷ jumlah, jadi ia
    # tercetak sebagai TOTAL, bukan baris "/kg" kedua di samping harga satuan
    # bahan. Asersi lama menuntut harga itu tercetak mentah; template korporat
    # 29 Okt 2026 menghapusnya supaya dokumen tidak memuat dua harga per kg.
    assert _rupiah_tes(round(harga * qty, 2)) in teks
    assert po["supplier_name"] in teks
    assert po["commodity_name"] in teks
    # Ref keputusan pindah ke meta PO (template korporat); id-nya tetap wajib
    # tercetak supaya dokumen bisa ditelusuri ke keputusannya.
    assert str(po["decision_id"]) in teks
    assert "SAP simulasi" in teks
    # Status PO tampil sebagai kata, bukan enum mentah. Status KEPUTUSAN tidak
    # lagi dicetak: blok "Dasar persetujuan" (yang memuatnya) dihapus 29 Okt
    # 2026; jejaknya kini hanya "Ref. keputusan" di meta + blok pengesahan.
    assert po_document.status_po_label(po["status"]) in teks
    assert "Dasar persetujuan" not in teks


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


def test_template_korporat_rincian_memuat_bahan_transportasi_penanganan():
    """Template PO korporat: satu tabel rincian berisi tiga komponen tagihan.

    Urutan baris (bahan -> transportasi -> penanganan -> total) adalah kontrak
    tampilan yang diminta pemilik 29 Okt 2026; kalau urutannya berubah, pembaca
    dokumen pembelian melihat komponen risiko/tambahan sebelum bahan.
    """
    isi = po_document.bangun_pdf(
        {
            "po_number": "MC-UJI-TEMPLATE",
            "status": "submitted",
            "created_at": datetime(2026, 10, 29, 3, 0, tzinfo=timezone.utc),
            "ordered_quantity": 200.0,
            "price": 29421.0,
            "total": 5884200.0,
            "material_number": "MAT-TELUR",
            "commodity_name": "Telur",
            "location_name": "Jakarta",
            "supplier_name": "CV Contoh",
            "commercial_cost": {
                "purchase_total": "5700000.00",
                "transport_total": "34200.00",
                "handling_total": "150000.00",
                "invoice_total": "5884200.00",
                "invoice_unit_price": "29421.00",
                "sdc_total": None,
                "sdc_unit_price": None,
                "expected_loss": None,
                "freshness_risk": None,
                "safety_penalty": None,
                "risk_method": {"kind": "simulated_policy", "version": "sdc-policy-1"},
            },
            "keputusan": {"id": "kep-1", "status": "executed"},
            "persetujuan": [],
            "dibuat_pada": datetime(2026, 10, 29, 4, 0, tzinfo=timezone.utc),
        }
    )
    teks = _teks_pdf(isi)
    posisi = [
        teks.index("Bahan — Telur"),
        teks.index("Transportasi"),
        teks.index("Penanganan"),
        teks.index("Total PO (bahan + transportasi + penanganan)"),
    ]
    assert posisi == sorted(posisi), "urutan komponen pada rincian pesanan berubah"
    # Nilai per komponen = angka yang tercatat, bukan angka baru.
    assert _rupiah_tes(5700000) in teks
    assert _rupiah_tes(34200) in teks
    assert _rupiah_tes(150000) in teks
    # Harga satuan bahan diturunkan (5.700.000 / 200) dan tetap tampil angkanya.
    assert _rupiah_tes(28500) in teks
    # Catatan kaki bertanda "*" (harga satuan TURUNAN, lumpsum/ls, selisih)
    # dihapus 29 Okt 2026 atas permintaan pemilik: rincian pesanan tidak lagi
    # ditemani keterangan apa pun di bawah tabel.
    assert "TURUNAN" not in teks
    assert "lumpsum" not in teks



# ── 4. Tautan PDF publik untuk Joule (29 Okt 2026) ──────────────────────────
#
# Joule hanya mengirim teks: tidak ada token login dan tidak ada lampiran. Satu
# tautan berumur pendek dipakai supaya juri bisa membuka dokumen yang sedang
# dibaca asisten — tanpa membuka akses lain.


def test_detail_po_mengirim_tautan_pdf_yang_bisa_dibuka_tanpa_token(client, monitor_headers):
    po = _po_disertifikasi()
    assert po is not None, "DB demo tidak punya PO dari keputusan approved/executed"

    resp = client.get(
        f"/sap/purchase-orders/{po['po_number']}/detail", headers=monitor_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["boleh_pdf"] is True
    tautan = body["pdf_url"]
    assert tautan and "/public/purchase-orders/" in tautan and "?t=" in tautan

    # Tautan yang sama, TANPA header Authorization.
    token = tautan.split("?t=", 1)[1]
    unduh = client.get(f"/public/purchase-orders/{po['po_number']}/pdf?t={token}")
    assert unduh.status_code == 200, unduh.text
    assert unduh.content.startswith(b"%PDF")
    assert unduh.headers["cache-control"] == "no-store"
    assert unduh.headers["referrer-policy"] == "no-referrer"


def test_tautan_pdf_menolak_token_palsu_nomor_lain_dan_kedaluwarsa(client, monitor_headers):
    po = _po_disertifikasi()
    assert po is not None
    nomor = po["po_number"]

    token_nomor_lain = po_document.token_pdf("MC-NOMOR-LAIN")
    assert (
        client.get(f"/public/purchase-orders/{nomor}/pdf?t={token_nomor_lain}").status_code
        == 401
    )
    assert client.get(f"/public/purchase-orders/{nomor}/pdf?t=bukan-token").status_code == 401
    assert client.get(f"/public/purchase-orders/{nomor}/pdf").status_code == 401

    lampau = datetime.now(timezone.utc) - timedelta(minutes=30)
    kedaluwarsa = po_document.token_pdf(nomor, sekarang=lampau)
    resp = client.get(f"/public/purchase-orders/{nomor}/pdf?t={kedaluwarsa}")
    assert resp.status_code == 401, resp.text
    assert not resp.content.startswith(b"%PDF")


def test_tautan_pdf_tetap_menolak_po_tanpa_keputusan(client):
    nomor = _po_tanpa_keputusan()
    if nomor is None:
        pytest.skip("DB demo tidak punya PO impor tanpa keputusan")
    token = po_document.token_pdf(nomor)
    resp = client.get(f"/public/purchase-orders/{nomor}/pdf?t={token}")
    assert resp.status_code == 409, resp.text
    assert not resp.content.startswith(b"%PDF")
