"""Gerbang penerimaan & karantina pada `GET /decisions/{id}/approval-summary`.

Fase 9 MG poin 4: tombol penerimaan/karantina tidak boleh dihitung klien.
Kontrak hari ini hanya membawa `can_approve`, `can_reject`, `can_execute`,
`blocking_reasons`; `can_receive` dan `can_quarantine` belum ada. Tes ini
mengunci tambahannya pada endpoint itu.

Keputusan kontrak (pemilik produk, 27 Okt 2026): batch acuan = batch di lokasi
**TUJUAN** keputusan (barang diterima di dapur penerima), bukan batch sumber
yang dipakai `can_execute`. Kedua flag adalah CERMINAN pagar endpoint yang sudah
ada — tidak ada aturan bisnis baru:

- `can_receive`   ← `POST /receipts/{id}/approve`: peran `sppg_head`, batch di
  cakupan lokasi user, evaluator batch `usable`, ada catatan penerimaan
  `menunggu` untuk batch itu;
- `can_quarantine` ← `POST /batches/{id}/quarantine` aksi `tahan`: peran SPPG
  (kepala/ahli gizi), lokasi batch = lokasi user, `boleh_ditahan(safety_status)`,
  dan transisi `tahan` sah dari status karantina sekarang.

Karena itu tes ini TIDAK menulis ekspektasi baru tentang kebijakan: setiap
harapan di bawah bisa diturunkan dari pesan 409/403 endpoint di atas.
"""

import json
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC

DB_URL = DSN_SYNC
NOW = datetime.now(timezone.utc)
PW = "UjiF9#2026"


# ---------------------------------------------------------------- utilitas DB


def _db_all(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(query), params or {}).fetchall()
            conn.commit()
            return rows
    finally:
        engine.dispose()


def _db_exec(query: str, params: dict | None = None) -> None:
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(text(query), params or {})
    finally:
        engine.dispose()


def _db_one(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            row = conn.execute(text(query), params or {}).fetchone()
            return row[0] if row else None
    finally:
        engine.dispose()


def _login(client: TestClient, email: str, password: str = PW) -> dict:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _head_demo(client: TestClient) -> dict:
    return _login(client, "sppg.head@demo.local", "Demo#SPPG2026")


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ------------------------------------------------------------------- panggung


@pytest.fixture()
def panggung():
    """Lokasi tujuan + batch + keputusan + catatan penerimaan `menunggu`.

    Sumber keputusan = Jakarta (demo), tujuan = lokasi baru supaya peran kepala
    di lokasi itu benar-benar satu-satunya yang berhak menerima.
    """
    akhiran = uuid.uuid4().hex[:8]
    log = [
        {"timestamp": "2026-10-27T06:00:00+00:00", "temperature_c": 4.1},
        {"timestamp": "2026-10-27T07:00:00+00:00", "temperature_c": 4.3},
    ]
    tgt = str(
        _db_one(
            "INSERT INTO locations (name, region, latitude, longitude) "
            "VALUES (:n, 'Uji F9', -6.2, 106.8) RETURNING id",
            {"n": f"F9-tgt-{akhiran}"},
        )
    )
    sup = str(
        _db_one(
            "INSERT INTO suppliers (name, location_id, reliability_score) "
            "VALUES (:n, :l, 0.8) RETURNING id",
            {"n": f"F9-sup-{akhiran}", "l": tgt},
        )
    )
    batch = str(
        _db_one(
            "INSERT INTO batches (commodity_id, location_id, supplier_id, quantity_kg, "
            "harvested_at, temperature_log, freshness_score, safety_status, usable_until) "
            "SELECT c.id, :l, :s, 150.00, now() - interval '10 hours', CAST(:tl AS jsonb), "
            "0.94, 'pass', now() + interval '8 hours' FROM commodities c "
            "WHERE c.name='telur' RETURNING id",
            {"l": tgt, "s": sup, "tl": json.dumps(log)},
        )
    )
    sumber = _db_one("SELECT id FROM locations WHERE name='Jakarta'")
    keputusan = str(
        _db_one(
            "INSERT INTO decisions (id, decision_type, status, proposed_by, "
            "source_location_id, target_location_id, commodity_id, quantity_kg, "
            "safe_delivered_cost, expires_at, cost_breakdown, iteration, "
            "verifier_note, verified_by) "
            "SELECT :id, 'regional_balance', 'executed', 'supervisor_agent', :src, :tgt, "
            "c.id, 150.00, 4050000.00, now() + interval '20 minutes', "
            "'{\"purchase\": \"3750000\", \"transport\": \"250000\","
            " \"handling\": \"50000\"}'::jsonb, "
            "1, 'consistent', 'verifier_agent' FROM commodities c "
            "WHERE c.name='telur' RETURNING id",
            {"id": str(uuid.uuid4()), "src": str(sumber), "tgt": tgt},
        )
    )

    def buat_akun(role: str, lokasi: str) -> str:
        email = f"f9.{role}-{akhiran}@uji-f9.local"
        digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
        _db_exec(
            "INSERT INTO users (id, name, email, password_hash, role, location_id) "
            "VALUES (gen_random_uuid(), :n, :e, :h, :r, :l)",
            {"n": f"Uji F9 {role}", "e": email, "h": digest, "r": role, "l": lokasi},
        )
        return email

    kepala = buat_akun("sppg_head", tgt)
    gizi = buat_akun("sppg_nutritionist", tgt)
    # Monitor nasional dibuat SENDIRI: akun demo `bgn.monitor@demo.local` dipakai
    # tes lain yang merotasi password-nya, dan tes ini tidak boleh bergantung
    # pada keadaan akun bersama (terukur: gagal hanya di suite penuh).
    monitor = buat_akun("bgn_monitor", None)
    pencatat = _db_one(
        "SELECT id FROM users WHERE email = :e", {"e": kepala}
    )
    catatan = str(
        _db_one(
            "INSERT INTO batch_receipts (batch_id, checked, recorded_by, status) "
            "VALUES (:b, '{\"suhu\": true}'::jsonb, :u, 'menunggu') RETURNING id",
            {"b": batch, "u": str(pencatat)},
        )
    )

    data = {
        "akhiran": akhiran,
        "location_id": tgt,
        "supplier_id": sup,
        "batch_id": batch,
        "decision_id": keputusan,
        "receipt_id": catatan,
        "kepala": kepala,
        "gizi": gizi,
        "monitor": monitor,
    }
    yield data

    _db_exec("DELETE FROM batch_receipts WHERE batch_id = :b", {"b": batch})
    _db_exec("DELETE FROM decision_evidence WHERE decision_id = :d", {"d": keputusan})
    _db_exec("DELETE FROM approvals WHERE decision_id = :d", {"d": keputusan})
    _db_exec("DELETE FROM decisions WHERE id = :d", {"d": keputusan})
    _db_exec("DELETE FROM batches WHERE id = :b", {"b": batch})
    _db_exec("DELETE FROM suppliers WHERE id = :s", {"s": sup})
    _db_exec("DELETE FROM users WHERE location_id = :l", {"l": tgt})
    _db_exec("DELETE FROM users WHERE email = :e", {"e": monitor})
    _db_exec("DELETE FROM locations WHERE id = :l", {"l": tgt})


def _ringkasan(client: TestClient, sppg: dict, headers: dict) -> dict:
    resp = client.get(
        f"/decisions/{sppg['decision_id']}/approval-summary", headers=headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _set_batch(sppg: dict, **kolom) -> None:
    bagian = ", ".join(f"{k} = :{k}" for k in kolom)
    _db_exec(
        f"UPDATE batches SET {bagian} WHERE id = :b",
        {**{k: v for k, v in kolom.items()}, "b": sppg["batch_id"]},
    )


# --------------------------------------------------- 1. bentuk kontrak payload


def test_ringkasan_membawa_can_receive_dan_can_quarantine(client, panggung):
    """Field baru tidak boleh hilang/null: klien tidak boleh menghitung sendiri."""
    body = _ringkasan(client, panggung, _login(client, panggung["kepala"]))
    assert isinstance(body.get("can_receive"), bool), body.get("can_receive")
    assert isinstance(body.get("can_quarantine"), bool), body.get("can_quarantine")
    gerbang = body.get("receipt_gate")
    assert isinstance(gerbang, dict), gerbang
    assert gerbang["batches"], "batch acuan di lokasi tujuan harus tercantum"
    baris = gerbang["batches"][0]
    for kunci in (
        "batch_id",
        "status",
        "can_receive",
        "can_quarantine",
        "receive_reasons",
        "quarantine_reasons",
    ):
        assert kunci in baris, (kunci, baris)
    assert baris["batch_id"] == panggung["batch_id"]
    # Lokasi acuan = TUJUAN keputusan (bukan lokasi sumber Jakarta).
    assert gerbang["location_id"] == panggung["location_id"]


# ------------------------------------------- 2. batch `pass` + catatan menunggu


def test_batch_pass_dengan_catatan_menunggu_boleh_diterima(client, panggung):
    body = _ringkasan(client, panggung, _login(client, panggung["kepala"]))
    assert body["can_receive"] is True, body["receipt_gate"]
    assert body["can_quarantine"] is True, body["receipt_gate"]
    assert body["receipt_gate"]["receive_reasons"] == []
    assert body["receipt_gate"]["quarantine_reasons"] == []
    assert body["receipt_gate"]["batches"][0]["status"] == "usable"


# ------------------------------------------------------------ 3. batch on_hold


def test_on_hold_tidak_menawarkan_terima(client, panggung):
    """`on_hold` (safety pending) bukan alasan menyetujui masuk stok."""
    _set_batch(panggung, safety_status="pending")
    body = _ringkasan(client, panggung, _login(client, panggung["kepala"]))
    assert body["can_receive"] is False, body["receipt_gate"]
    assert "safety_pending" in body["receipt_gate"]["receive_reasons"]
    assert body["receipt_gate"]["batches"][0]["status"] == "on_hold"
    # Menahan batch pending justru tindakan yang sah (`boleh_ditahan`).
    assert body["can_quarantine"] is True
    # Langkah berikutnya dibawa server, bukan dikarang klien.
    assert body["receipt_gate"]["next_step"]


def test_on_hold_alasan_bukan_gagal_uji(client, panggung):
    """`pending` tidak boleh dilaporkan sebagai `safety_fail` (pembeda Fase 4)."""
    _set_batch(panggung, safety_status="needs_verification")
    body = _ringkasan(client, panggung, _login(client, panggung["kepala"]))
    alasan = body["receipt_gate"]["receive_reasons"]
    assert "safety_needs_verification" in alasan, alasan
    assert "safety_fail" not in alasan, alasan


# ------------------------------------------------------------ 4. karantina


def test_batch_karantina_tidak_boleh_diterima_dan_tidak_ditahan_ulang(client, panggung):
    _set_batch(panggung, quarantine_status="quarantined")
    body = _ringkasan(client, panggung, _login(client, panggung["kepala"]))
    assert body["can_receive"] is False, body["receipt_gate"]
    assert "quarantined" in body["receipt_gate"]["receive_reasons"]
    # `status_setelah('quarantined', 'tahan')` tidak sah → tombol Tahan hilang.
    assert body["can_quarantine"] is False, body["receipt_gate"]
    assert "quarantine_transition_invalid" in body["receipt_gate"]["quarantine_reasons"]


def test_batch_fail_tidak_boleh_ditahan(client, panggung):
    """`boleh_ditahan('fail')` = False: karantina tidak diperlukan lagi."""
    _set_batch(panggung, safety_status="fail")
    body = _ringkasan(client, panggung, _login(client, panggung["kepala"]))
    assert body["can_quarantine"] is False, body["receipt_gate"]
    assert "safety_fail_not_quarantinable" in body["receipt_gate"]["quarantine_reasons"]


# ------------------------------------------------- 5. syarat catatan penerimaan


def test_tanpa_catatan_penerimaan_tidak_menawarkan_terima(client, panggung):
    """`POST /receipts/{id}/approve` butuh catatan; tanpa catatan tak ada tombol."""
    _db_exec("DELETE FROM batch_receipts WHERE batch_id = :b", {"b": panggung["batch_id"]})
    body = _ringkasan(client, panggung, _login(client, panggung["kepala"]))
    assert body["can_receive"] is False, body["receipt_gate"]
    assert "receipt_missing" in body["receipt_gate"]["receive_reasons"]
    # Karantina tidak menuntut catatan penerimaan lebih dulu.
    assert body["can_quarantine"] is True


def test_catatan_sudah_disetujui_tidak_menawarkan_terima_lagi(client, panggung):
    _db_exec(
        "UPDATE batch_receipts SET status = 'disetujui' WHERE id = :r",
        {"r": panggung["receipt_id"]},
    )
    body = _ringkasan(client, panggung, _login(client, panggung["kepala"]))
    assert body["can_receive"] is False, body["receipt_gate"]
    assert "receipt_already_decided" in body["receipt_gate"]["receive_reasons"]


# ---------------------------------------------------------------- 6. peran


def test_ahli_gizi_boleh_karantina_tidak_boleh_terima(client, panggung):
    body = _ringkasan(client, panggung, _login(client, panggung["gizi"]))
    assert body["can_receive"] is False, body["receipt_gate"]
    assert "role_not_head" in body["receipt_gate"]["receive_reasons"]
    # Kewenangan karantina milik SPPG (kepala DAN ahli gizi).
    assert body["can_quarantine"] is True


def test_bgn_monitor_tidak_mendapat_kedua_tombol(client, panggung):
    body = _ringkasan(client, panggung, _login(client, panggung["monitor"]))
    assert body["can_receive"] is False
    assert body["can_quarantine"] is False
    assert "role_not_head" in body["receipt_gate"]["receive_reasons"]
    assert "role_not_sppg" in body["receipt_gate"]["quarantine_reasons"]


# ------------------------------------------------- 7. batch di luar cakupan


def test_batch_lokasi_lain_tidak_ikut_dihitung(client, panggung):
    """Batch komoditas sama di lokasi lain bukan barang yang diterima dapur ini."""
    lain = str(
        _db_one(
            "INSERT INTO locations (name, region, latitude, longitude) "
            "VALUES (:n, 'Uji F9', -6.3, 106.9) RETURNING id",
            {"n": f"F9-lain-{panggung['akhiran']}"},
        )
    )
    try:
        _db_one(
            "INSERT INTO batches (commodity_id, location_id, supplier_id, quantity_kg, "
            "harvested_at, temperature_log, freshness_score, safety_status, usable_until) "
            "SELECT c.id, :l, :s, 90.00, now() - interval '5 hours', '[]'::jsonb, "
            "0.20, 'pass', now() + interval '2 hours' FROM commodities c "
            "WHERE c.name='telur' RETURNING id",
            {"l": lain, "s": panggung["supplier_id"]},
        )
        body = _ringkasan(client, panggung, _login(client, panggung["kepala"]))
        ids = [b["batch_id"] for b in body["receipt_gate"]["batches"]]
        assert ids == [panggung["batch_id"]], ids
        assert body["can_receive"] is True
    finally:
        _db_exec("DELETE FROM batches WHERE location_id = :l", {"l": lain})
        _db_exec("DELETE FROM locations WHERE id = :l", {"l": lain})


def test_langkah_berikutnya_milik_batch_masing_masing(client, panggung):
    """Satu keputusan bisa memuat batch kedaluwarsa DAN batch yang menunggu
    catatan. Menyuruh "selesaikan verifikasi" untuk barang yang sudah lewat masa
    layak adalah arahan yang salah — terukur di verifikasi browser 27 Okt 2026.
    """
    kedaluwarsa = str(
        _db_one(
            "INSERT INTO batches (commodity_id, location_id, supplier_id, quantity_kg, "
            "harvested_at, temperature_log, freshness_score, safety_status, usable_until) "
            "SELECT c.id, :l, :s, 70.00, now() - interval '30 hours', '[]'::jsonb, "
            "0.90, 'pass', now() - interval '1 hour' FROM commodities c "
            "WHERE c.name='telur' RETURNING id",
            {"l": panggung["location_id"], "s": panggung["supplier_id"]},
        )
    )
    try:
        _db_exec("DELETE FROM batch_receipts WHERE batch_id = :b", {"b": panggung["batch_id"]})
        body = _ringkasan(client, panggung, _login(client, panggung["kepala"]))
        per_batch = {b["batch_id"]: b for b in body["receipt_gate"]["batches"]}
        # Lokasi tujuan bisa memuat batch lain dari tes/fixture lain: yang penting
        # dua batch yang dikendalikan tes ini hadir, bukan kesamaan himpunan.
        assert {panggung["batch_id"], kedaluwarsa} <= set(per_batch), per_batch.keys()

        langkah_layak = per_batch[panggung["batch_id"]]["next_step"]
        assert langkah_layak == "catat hasil terima petugas lalu setujui penerimaan", langkah_layak

        baris_kedaluwarsa = per_batch[kedaluwarsa]
        assert baris_kedaluwarsa["status"] == "rejected", baris_kedaluwarsa
        assert "batch_expired" in baris_kedaluwarsa["receive_reasons"], baris_kedaluwarsa
        assert baris_kedaluwarsa["next_step"] != langkah_layak, baris_kedaluwarsa
        assert "masa layak" in baris_kedaluwarsa["next_step"], baris_kedaluwarsa

        # Agregat = langkah batch PERTAMA yang masih tertahan (urutan payload),
        # bukan selalu batch pertama secara buta.
        tertahan = [
            b
            for b in body["receipt_gate"]["batches"]
            if b["receive_reasons"] or b["quarantine_reasons"]
        ]
        assert tertahan, body["receipt_gate"]
        assert body["receipt_gate"]["next_step"] == tertahan[0]["next_step"], tertahan[0]
    finally:
        _db_exec("DELETE FROM batches WHERE id = :b", {"b": kedaluwarsa})
