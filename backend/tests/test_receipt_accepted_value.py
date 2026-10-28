"""Nilai penerimaan memakai HARGA INVOICE PO (Fase 5 butir 4b).

Kontrak yang dikunci:

1. PO yang mendanai sebuah batch dirujuk lewat bukti `human_inspection` hasil
   `persist_supplier_binding` (`decision_evidence.payload.batch_ids`) — bukan
   tebakan dari pasangan (pemasok, komoditas, lokasi). Batch tanpa bukti itu
   TIDAK diatribusikan.
2. `accepted_value_idr = kg diterima x po.price`, dan `po.price` sejak Fase 5
   adalah harga satuan INVOICE (bahan + transportasi + penanganan) — penalti
   risiko internal tidak ikut.
3. Tanpa ikatan/PO, nilainya `null`. Bukan 0, bukan harga pasar, bukan
   `sdc / qty`: pembaca harus melihat absennya.

CATATAN KEBERSIHAN GERBANG (29 Okt 2026). Versi pertama berkas ini mencari
"batch demo yang kebetulan layak dan terikat PO". Itu lulus saat dijalankan
sendiri, lalu GAGAL di suite penuh dengan `NoResultFound` — sebabnya bukan kode
yang salah, melainkan suite lain di repo yang sama memakai/menerima/mengarantina
batch demo, sehingga kandidatnya habis. Data uji sekarang DIBUAT SENDIRI
(lokasi, pemasok, dua batch, keputusan, bukti ikatan, PO, akun) dan dibersihkan
lagi setelah tes: hasilnya tidak lagi bergantung pada urutan suite.
"""

from __future__ import annotations

import json
import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from tests.dsn import DSN_SYNC

PW = "Uji#Nilai2026"


def _client():
    from app.main import app

    return TestClient(app)


def _db():
    return create_engine(DSN_SYNC)


def _one(conn, sql: str, params: dict | None = None):
    return conn.execute(text(sql), params or {}).scalar_one()


def _exec(conn, sql: str, params: dict | None = None) -> None:
    conn.execute(text(sql), params or {})


def _akun(conn, akhiran: str, role: str, lokasi: str | None) -> str:
    email = f"nilai.{role}-{akhiran}@uji-nilai.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    _exec(
        conn,
        "INSERT INTO users (id, name, email, password_hash, role, location_id) "
        "VALUES (gen_random_uuid(), :n, :e, :h, :r, :l)",
        {"n": f"Uji Nilai {role}", "e": email, "h": digest, "r": role, "l": lokasi},
    )
    return email


def _siapkan() -> dict:
    """Buat seluruh rantai yang dibutuhkan tes, milik tes ini sendiri.

    Satu lokasi + pemasok + dua batch (satu terikat PO lewat bukti
    `human_inspection`, satu tidak) + akun kepala SPPG di lokasi itu.
    """
    akhiran = uuid.uuid4().hex[:8]
    log = [
        {"timestamp": "2026-10-27T06:00:00+00:00", "temperature_c": 4.1},
        {"timestamp": "2026-10-27T07:00:00+00:00", "temperature_c": 4.3},
    ]
    kg = 150.00
    harga = 41500.00
    po_number = f"UJI-NILAI-{akhiran.upper()}"
    sql_batch = (
        "INSERT INTO batches (commodity_id, location_id, supplier_id, quantity_kg, "
        "harvested_at, temperature_log, freshness_score, safety_status, usable_until, "
        "origin) SELECT c.id, :l, :s, :kg, now() - interval '6 hours', "
        "CAST(:tl AS jsonb), 0.94, 'pass', now() + interval '2 days', 'seed' "
        "FROM commodities c ORDER BY c.name LIMIT 1 RETURNING id"
    )
    engine = _db()
    try:
        with engine.begin() as conn:
            lokasi = str(
                _one(
                    conn,
                    "INSERT INTO locations (name, region, latitude, longitude) "
                    "VALUES (:n, 'Uji Nilai', -6.2, 106.8) RETURNING id",
                    {"n": f"Nilai-{akhiran}"},
                )
            )
            pemasok = str(
                _one(
                    conn,
                    "INSERT INTO suppliers (name, location_id, reliability_score) "
                    "VALUES (:n, :l, 0.8) RETURNING id",
                    {"n": f"Pemasok Nilai {akhiran}", "l": lokasi},
                )
            )
            batch_terikat = str(
                _one(
                    conn,
                    sql_batch,
                    {"l": lokasi, "s": pemasok, "kg": kg, "tl": json.dumps(log)},
                )
            )
            batch_bebas = str(
                _one(
                    conn,
                    sql_batch,
                    {"l": lokasi, "s": pemasok, "kg": 60.00, "tl": json.dumps(log)},
                )
            )
            keputusan = str(
                _one(
                    conn,
                    "INSERT INTO decisions (id, decision_type, status, proposed_by, "
                    "target_location_id, commodity_id, quantity_kg, safe_delivered_cost, "
                    "expires_at, created_at, origin) "
                    "SELECT :id, 'supplier_procurement', 'executed', 'supervisor_agent', "
                    ":l, c.id, :kg, 2500000, now() + interval '1 hour', now(), 'demo' "
                    "FROM commodities c ORDER BY c.name LIMIT 1 RETURNING id",
                    {"id": str(uuid.uuid4()), "l": lokasi, "kg": kg},
                )
            )
            # Bukti ikatan: satu-satunya jalur atribusi batch -> PO yang diakui.
            _exec(
                conn,
                "INSERT INTO decision_evidence (id, decision_id, evidence_type, payload) "
                "VALUES (gen_random_uuid(), :d, 'human_inspection', CAST(:p AS jsonb))",
                {
                    "d": keputusan,
                    "p": json.dumps({"batch_ids": [batch_terikat], "inspeksi": "uji"}),
                },
            )
            _exec(
                conn,
                "INSERT INTO sap_mock_purchase_orders (id, po_number, supplier_id, "
                "material_number, ordered_quantity, price, status, decision_id, created_at) "
                "VALUES (gen_random_uuid(), :n, :s, 'MAT-UJI', :kg, :h, 'confirmed', "
                ":d, now())",
                {"n": po_number, "s": pemasok, "kg": kg, "h": harga, "d": keputusan},
            )
            email = _akun(conn, akhiran, "sppg_head", lokasi)
        return {
            "akhiran": akhiran,
            "location_id": lokasi,
            "supplier_id": pemasok,
            "batch_terikat": batch_terikat,
            "batch_bebas": batch_bebas,
            "decision_id": keputusan,
            "po_number": po_number,
            "kg": kg,
            "harga": harga,
            "email": email,
        }
    finally:
        engine.dispose()


def _bersihkan(data: dict) -> None:
    """Hapus semua yang dibuat `_siapkan`, urut dari anak ke induk."""
    engine = _db()
    try:
        with engine.begin() as conn:
            _exec(
                conn,
                "DELETE FROM batch_receipts WHERE batch_id IN (:a, :b)",
                {"a": data["batch_terikat"], "b": data["batch_bebas"]},
            )
            _exec(
                conn,
                "DELETE FROM supply_records WHERE location_id = :l",
                {"l": data["location_id"]},
            )
            _exec(
                conn,
                "DELETE FROM decision_evidence WHERE decision_id = :d",
                {"d": data["decision_id"]},
            )
            _exec(
                conn,
                "DELETE FROM sap_mock_purchase_orders WHERE decision_id = :d",
                {"d": data["decision_id"]},
            )
            _exec(conn, "DELETE FROM decisions WHERE id = :d", {"d": data["decision_id"]})
            _exec(
                conn,
                "DELETE FROM batches WHERE location_id = :l",
                {"l": data["location_id"]},
            )
            _exec(
                conn,
                "DELETE FROM users WHERE location_id = :l",
                {"l": data["location_id"]},
            )
            _exec(
                conn,
                "DELETE FROM suppliers WHERE location_id = :l",
                {"l": data["location_id"]},
            )
            _exec(conn, "DELETE FROM locations WHERE id = :l", {"l": data["location_id"]})
    finally:
        engine.dispose()


@pytest.fixture()
def ikatan():
    data = _siapkan()
    try:
        yield data
    finally:
        _bersihkan(data)


def _masuk(client, email: str) -> dict:
    resp = client.post("/auth/login", json={"email": email, "password": PW})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _catat(client, headers, batch_id: str) -> dict:
    resp = client.post(
        "/receipts",
        headers=headers,
        json={
            "batch_id": batch_id,
            "checked": {"kemasan": True},
            "other_note": "uji nilai",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_nilai_diterima_memakai_harga_invoice_po(ikatan):
    with _client() as c:
        headers = _masuk(c, ikatan["email"])
        badan = _catat(c, headers, ikatan["batch_terikat"])
        assert badan["accepted_value_idr"] is None, "belum disetujui = belum ada nilai"

        setuju = c.post(f"/receipts/{badan['id']}/approve", headers=headers)
        assert setuju.status_code == 200, setuju.text
        hasil = setuju.json()
        assert hasil["status"] == "disetujui"
        assert hasil["stock_kg"] == ikatan["kg"]
        assert hasil["accepted_value_idr"] == pytest.approx(
            ikatan["kg"] * ikatan["harga"], abs=0.01
        )


def test_tanpa_ikatan_bukti_nilai_null_bukan_nol(ikatan):
    with _client() as c:
        headers = _masuk(c, ikatan["email"])
        badan = _catat(c, headers, ikatan["batch_bebas"])
        setuju = c.post(f"/receipts/{badan['id']}/approve", headers=headers)
        assert setuju.status_code == 200, setuju.text
        assert setuju.json()["accepted_value_idr"] is None


def test_antrean_menunggu_membawa_kunci_nilai_kosong(ikatan):
    """Kunci harus SELALU ada supaya UI tidak membedakan dua bentuk payload."""
    with _client() as c:
        headers = _masuk(c, ikatan["email"])
        badan = _catat(c, headers, ikatan["batch_terikat"])
        antrean = c.get("/receipts/menunggu", headers=headers)
        assert antrean.status_code == 200, antrean.text
        baris = [i for i in antrean.json()["items"] if i["id"] == badan["id"]]
        assert baris, "catatan menunggu harus muncul di antrean"
        assert "accepted_value_idr" in baris[0]
        assert baris[0]["accepted_value_idr"] is None


# --- Dokumen 05 S8.2-S8.3 -------------------------------------------------
# Tiga angka (kuantitas batch / masuk stok / nilai) dan asal harga satuannya
# harus bisa dibaca SEBELUM keputusan, tanpa klien mengalikan kg x harga sendiri.


def test_pratinjau_nilai_dan_asal_harga_sebelum_disetujui(ikatan):
    with _client() as c:
        headers = _masuk(c, ikatan["email"])
        badan = _catat(c, headers, ikatan["batch_terikat"])
        # Angka pratinjau: dihitung server, bukan UI.
        assert badan["batch_quantity_kg"] == ikatan["kg"]
        assert badan["unit_price_idr"] == pytest.approx(ikatan["harga"], abs=0.01)
        assert badan["estimated_value_idr"] == pytest.approx(
            ikatan["kg"] * ikatan["harga"], abs=0.01
        )
        # Belum disetujui -> nilai pembukuan dan stok masih kosong.
        assert badan["accepted_value_idr"] is None
        assert badan["stock_kg"] is None
        # Asal harga: nomor PO ikut supaya UI bisa menulis "... dari PO <nomor>".
        assert badan["po_number"] == ikatan["po_number"]


def test_baca_ulang_membawa_angka_yang_sama(ikatan):
    """GET tidak boleh menampilkan angka berbeda dari POST (satu sumber hitung)."""
    with _client() as c:
        headers = _masuk(c, ikatan["email"])
        badan = _catat(c, headers, ikatan["batch_terikat"])
        baca = c.get(f"/receipts?batch_id={ikatan['batch_terikat']}", headers=headers)
        assert baca.status_code == 200, baca.text
        baris = [i for i in baca.json()["items"] if i["id"] == badan["id"]][0]
        for kunci in (
            "batch_quantity_kg",
            "unit_price_idr",
            "estimated_value_idr",
            "po_number",
        ):
            assert baris[kunci] == badan[kunci], kunci


def test_setelah_disetujui_nilai_perkiraan_menjadi_pembukuan(ikatan):
    with _client() as c:
        headers = _masuk(c, ikatan["email"])
        badan = _catat(c, headers, ikatan["batch_terikat"])
        perkiraan = badan["estimated_value_idr"]
        setuju = c.post(f"/receipts/{badan['id']}/approve", headers=headers)
        assert setuju.status_code == 200, setuju.text
        hasil = setuju.json()
        assert hasil["accepted_value_idr"] == pytest.approx(perkiraan, abs=0.01)
        assert hasil["stock_kg"] == hasil["batch_quantity_kg"]
