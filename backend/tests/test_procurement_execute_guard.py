"""Eksekusi keputusan PENGADAAN (`supplier_procurement`, `source_location_id` NULL).

Konteks cacat terukur (27 Okt 2026, keputusan `943e662c…` di DB demo):

- approval SUKSES (status `approved`), tetapi tombol "Eksekusi" menerima
  `409 binding batch/supplier berubah`;
- sebabnya `supplier_eligibility.resolve_binding` membandingkan
  `batch.location_id` dengan `decision.source_location_id`, sedangkan pengadaan
  memang TIDAK punya lokasi asal (`demo_procurement_orchestrator.py`: "Pengadaan
  tidak memindahkan stok SPPG lain: sisi asal = NULL") dan binding-nya ditulis
  oleh `persist_supplier_binding` terhadap `target_location_id`;
- `approval_summary._supplier_for` sudah punya cabang pengadaan, jadi read model
  menyatakan `can_execute=True` sementara endpoint pasti 409 — janji yang tidak
  ditepati (audit M5).

Berkas ini mengunci perbaikan itu: pengadaan divalidasi terhadap lokasi TUJUAN,
dan `source_location_id` NULL untuk jenis lain TETAP fail-closed.
"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_ASYNC.replace("+asyncpg", "+psycopg")
PW = "TestPass#2026"


def _exec(sql: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            res = conn.execute(text(sql), params or {})
            try:
                return res.fetchall()
            except Exception:
                return []
    finally:
        engine.dispose()


def _mk_user(role: str, kota: str) -> dict:
    email = f"{role}-{uuid.uuid4().hex[:8]}@uji-pengadaan.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    _exec(
        "INSERT INTO users (id, name, email, password_hash, role, location_id) "
        "SELECT gen_random_uuid(), 'Uji pengadaan', :e, :h, :r, l.id "
        "FROM locations l WHERE l.name = :k",
        {"e": email, "h": digest, "r": role, "k": kota},
    )
    return {"email": email, "password": PW}


def _login(client: TestClient, user: dict) -> dict:
    resp = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _batch_pemasok_di_sppg() -> dict:
    """Batch milik pemasok DI SPPG tujuan (definisi "memasok SPPG ini").

    Keadaan batch DIPAKSA layak (safety `pass`, masa layak jauh di depan)
    sebelum dipakai. Tanpa ini fixture bergantung pada urutan suite: tes lain
    boleh menandai batch yang sama `fail` atau kedaluwarsa, dan guard lalu
    menolak dengan alasan yang benar tetapi bukan yang sedang diuji
    (terukur: `safety revalidation gagal: batch sumber kedaluwarsa` di suite
    penuh, padahal lulus saat berkas dijalankan sendiri).
    """
    row = _exec(
        "SELECT b.id, b.supplier_id, b.location_id, b.commodity_id, l.name "
        "FROM batches b "
        "JOIN suppliers s ON s.id = b.supplier_id "
        "JOIN locations l ON l.id = b.location_id "
        "WHERE b.location_id = s.location_id "
        "ORDER BY b.created_at DESC LIMIT 1"
    )
    assert row, "butuh batch pemasok-di-SPPG untuk fixture"
    _exec(
        "UPDATE batches SET safety_status = 'pass', "
        "usable_until = now() + interval '30 days' WHERE id = :b",
        {"b": str(row[0][0])},
    )
    return {
        "batch_id": str(row[0][0]),
        "supplier_id": str(row[0][1]),
        "location_id": str(row[0][2]),
        "commodity_id": str(row[0][3]),
        "kota": row[0][4],
    }


def _nama_lokasi(location_id: str) -> str:
    row = _exec("SELECT name FROM locations WHERE id = CAST(:l AS uuid)", {"l": location_id})
    assert row, f"lokasi {location_id} tidak ada"
    return row[0][0]


def _batch_lokasi_lain(location_id: str, commodity_id: str) -> dict:
    """Batch komoditas SAMA di lokasi LAIN (untuk kasus negatif lokasi)."""
    row = _exec(
        "SELECT b.id, b.supplier_id, b.location_id FROM batches b "
        "WHERE b.location_id <> CAST(:l AS uuid) "
        "AND b.commodity_id = CAST(:k AS uuid) "
        "AND b.safety_status = 'pass' LIMIT 1",
        {"l": location_id, "k": commodity_id},
    )
    assert row, "butuh batch komoditas sama di lokasi lain untuk fixture negatif"
    return {
        "batch_id": str(row[0][0]),
        "supplier_id": str(row[0][1]),
        "location_id": str(row[0][2]),
        "commodity_id": commodity_id,
    }


def _siapkan(
    *,
    jenis: str = "supplier_procurement",
    target: dict | None = None,
    binding_batch: dict | None = None,
    supplier_binding: str | None = None,
    source_null: bool = True,
    approver_kota: str | None = None,
) -> dict:
    """Keputusan pending + binding + dua approval (head & ahli gizi) lokasi TUJUAN.

    `target` menentukan SPPG tujuan + komoditas; `binding_batch` menentukan batch
    yang ditulis ke bukti (boleh sengaja tidak cocok untuk kasus negatif).
    """
    dasar = _batch_pemasok_di_sppg()
    target = target or dasar
    binding_batch = binding_batch or target
    supplier_binding = supplier_binding or binding_batch["supplier_id"]
    did = str(uuid.uuid4())
    _exec(
        "INSERT INTO decisions (id, decision_type, status, proposed_by, "
        "source_location_id, target_location_id, commodity_id, quantity_kg, "
        "safe_delivered_cost, expires_at, cost_breakdown, iteration, "
        "verified_by, verifier_note, supplier_id) "
        "VALUES (:id, :jenis, 'pending_approval', 'supervisor_agent', "
        "CASE WHEN :src_null THEN NULL ELSE CAST(:src AS uuid) END, "
        "CAST(:target AS uuid), CAST(:kom AS uuid), 300, "
        "9000000, now() + interval '45 minutes', "
        "'{\"purchase\": \"9000000\", \"candidate_score\": \"0.4\"}'::jsonb, 1, "
        "'verifier_agent', 'consistent', CAST(:sup AS uuid))",
        {
            "id": did,
            "jenis": jenis,
            "src_null": source_null,
            "src": target["location_id"],
            "target": target["location_id"],
            "kom": target["commodity_id"],
            "sup": supplier_binding if jenis == "supplier_procurement" else None,
        },
    )
    _exec(
        "INSERT INTO decision_evidence (decision_id, evidence_type, payload) "
        "VALUES (:d, 'human_inspection', CAST(:p AS jsonb))",
        {
            "d": did,
            "p": (
                '{"allocation_binding": true, "procurement": true, '
                '"supplier_id": "' + supplier_binding + '", '
                '"target_location_id": "' + target["location_id"] + '", '
                '"batch_ids": ["' + binding_batch["batch_id"] + '"]}'
            ),
        },
    )
    kota = approver_kota or _nama_lokasi(target["location_id"])
    kepala = _mk_user("sppg_head", kota)
    gizi = _mk_user("sppg_nutritionist", kota)
    for u in (kepala, gizi):
        _exec(
            "INSERT INTO approvals (decision_id, approved_by, approved, comment) "
            "SELECT :d, u.id, true, 'fixture' FROM users u WHERE u.email = :e",
            {"d": did, "e": u["email"]},
        )
    return {"decision_id": did, "kepala": kepala, "gizi": gizi, "batch": target}


def _bersihkan(hasil: dict) -> None:
    did = hasil["decision_id"]
    for sql in (
        "DELETE FROM sap_mock_purchase_orders WHERE decision_id = :d",
        "DELETE FROM approvals WHERE decision_id = :d",
        "DELETE FROM decision_evidence WHERE decision_id = :d",
        "DELETE FROM decisions WHERE id = :d",
    ):
        _exec(sql, {"d": did})
    for u in (hasil["kepala"], hasil["gizi"]):
        _exec("DELETE FROM users WHERE email = :e", {"e": u["email"]})


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_pengadaan_tanpa_lokasi_asal_bisa_dieksekusi(client):
    """Cacat utama: 409 'binding batch/supplier berubah' padahal data konsisten."""
    hasil = _siapkan()
    try:
        headers = _login(client, hasil["kepala"])
        resp = client.post(
            "/actions/execute", json={"decision_id": hasil["decision_id"]}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "executed"
        assert body["po_number"]
        baris = _exec(
            "SELECT (SELECT status FROM decisions WHERE id = :d), "
            "(SELECT count(*) FROM sap_mock_purchase_orders WHERE decision_id = :d) ",
            {"d": hasil["decision_id"]},
        )
        assert baris[0][0] == "executed"
        assert int(baris[0][1]) == 1
    finally:
        _bersihkan(hasil)


def test_binding_pengadaan_batch_lokasi_lain_ditolak(client):
    """Batch bukan di SPPG tujuan tetap 409 dengan pesan yang sama (bukan dilonggarkan)."""
    dasar = _batch_pemasok_di_sppg()
    lain = _batch_lokasi_lain(dasar["location_id"], dasar["commodity_id"])
    hasil = _siapkan(binding_batch=lain)
    try:
        headers = _login(client, hasil["kepala"])
        resp = client.post(
            "/actions/execute", json={"decision_id": hasil["decision_id"]}, headers=headers
        )
        assert resp.status_code == 409, resp.text
        assert "binding batch/supplier berubah" in resp.text
    finally:
        _bersihkan(hasil)


def test_binding_pengadaan_supplier_lain_ditolak(client):
    """Supplier di binding bukan pemilik batch → 409."""
    dasar = _batch_pemasok_di_sppg()
    lain = _batch_lokasi_lain(dasar["location_id"], dasar["commodity_id"])
    hasil = _siapkan(supplier_binding=lain["supplier_id"])
    try:
        headers = _login(client, hasil["kepala"])
        resp = client.post(
            "/actions/execute", json={"decision_id": hasil["decision_id"]}, headers=headers
        )
        assert resp.status_code == 409, resp.text
        assert "binding batch/supplier berubah" in resp.text
    finally:
        _bersihkan(hasil)


def test_pengadaan_batch_fail_tetap_diblokir_safety(client):
    """Membuka lokasi asal NULL tidak boleh meloloskan safety gate."""
    hasil = _siapkan()
    try:
        _exec(
            "UPDATE batches SET safety_status = 'fail' WHERE id = :b",
            {"b": hasil["batch"]["batch_id"]},
        )
        headers = _login(client, hasil["kepala"])
        resp = client.post(
            "/actions/execute", json={"decision_id": hasil["decision_id"]}, headers=headers
        )
        assert resp.status_code == 409, resp.text
        assert "safety revalidation gagal" in resp.text
        sisa = _exec(
            "SELECT status FROM decisions WHERE id = :d", {"d": hasil["decision_id"]}
        )
        assert sisa[0][0] != "executed"
    finally:
        _exec(
            "UPDATE batches SET safety_status = 'pass' WHERE id = :b",
            {"b": hasil["batch"]["batch_id"]},
        )
        _bersihkan(hasil)


def test_non_pengadaan_tanpa_lokasi_asal_tetap_ditolak(client):
    """Fail-closed dipertahankan: hanya pengadaan yang boleh tanpa lokasi asal."""
    hasil = _siapkan(jenis="regional_balance")
    try:
        headers = _login(client, hasil["kepala"])
        resp = client.post(
            "/actions/execute", json={"decision_id": hasil["decision_id"]}, headers=headers
        )
        assert resp.status_code == 409, resp.text
        assert "binding batch/supplier berubah" in resp.text
    finally:
        _bersihkan(hasil)


def test_can_execute_paritas_pengadaan(client):
    """Read model tidak boleh menjanjikan eksekusi yang pasti 409 (audit M5)."""
    hasil = _siapkan()
    try:
        headers = _login(client, hasil["kepala"])
        ringkas = client.get(
            f"/decisions/{hasil['decision_id']}/approval-summary", headers=headers
        )
        assert ringkas.status_code == 200, ringkas.text
        data = ringkas.json()
        assert data["can_execute"] is True, data.get("blocking_reasons")
        assert not [
            r for r in data.get("blocking_reasons", []) if "binding" in r
        ], data.get("blocking_reasons")

        _exec(
            "UPDATE batches SET safety_status = 'fail' WHERE id = :b",
            {"b": hasil["batch"]["batch_id"]},
        )
        ringkas = client.get(
            f"/decisions/{hasil['decision_id']}/approval-summary", headers=headers
        )
        assert ringkas.status_code == 200, ringkas.text
        assert ringkas.json()["can_execute"] is False
    finally:
        _exec(
            "UPDATE batches SET safety_status = 'pass' WHERE id = :b",
            {"b": hasil["batch"]["batch_id"]},
        )
        _bersihkan(hasil)
