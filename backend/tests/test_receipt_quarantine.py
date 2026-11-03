"""Revalidasi kelayakan batch di PENERIMAAN + uji transaksi (Fase 4 poin 5 & 8).

Kontrak yang dikunci berkas ini (MG/phase-04-safety-gates.md):

1. `POST /receipts` — pencatatan penerimaan DITOLAK 409 bila evaluator tunggal
   (`app.core.batch_eligibility`) menyatakan batch `rejected` atau
   `quarantined` (safety_fail, batch_expired, expiry_unknown, quarantined,
   evidence_missing, freshness_fail). Batch `on_hold` (safety `pending`/
   `needs_verification`/bukti suhu kurang) TETAP DITERIMA: ceklis petugas
   itulah bahan verifikasi lanjutan. `batches.safety_status` TIDAK diubah.
2. `POST /receipts/{id}/approve` — hanya batch `usable` yang boleh disetujui.
   `on_hold` dan `rejected` sama-sama 409, tetapi kalimatnya BERBEDA:
   `safety_pending` bukan `safety_fail`.
3. `GET /batches/{id}` — field `eligibility` {status, blocking_reasons,
   next_step} dihitung SERVER dari evaluator, bukan dari UI.
4. `POST /batches/{id}/quarantine` — alasan wajib, aktor reviewer tercatat,
   dan `safety_status` tidak berubah (karantina bukan penerimaan sukses).
5. Uji transaksi — bila revalidasi safety gagal saat `POST /actions/execute`,
   TIDAK boleh ada PO draft, `delivery_events`, `supply_records`, maupun blok
   ledger baru, dan status keputusan tetap.

Diuji terhadap DB nyata (pola conftest repo): baris batch/receipt/keputusan
dibuat oleh berkas ini sendiri lalu dihapus lagi, sehingga tidak bergantung
pada keadaan data demo yang bisa diubah tes lain.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC

PW = "TestPass#2026"
LOG_LENGKAP = [
    {"timestamp": "2026-10-25T09:00:00+00:00", "temperature_c": 4.0},
    {"timestamp": "2026-10-25T10:00:00+00:00", "temperature_c": 4.2},
]


# ---------------------------------------------------------------------------
# Helper DB (psycopg sinkron, DSN mengikuti DATABASE_URL)
# ---------------------------------------------------------------------------


def _dsn() -> str:
    return DSN_SYNC


def _db():
    return create_engine(_dsn())


def _exec(sql: str, params: dict | None = None):
    engine = _db()
    try:
        with engine.begin() as conn:
            res = conn.execute(text(sql), params or {})
            try:
                return res.fetchall()
            except Exception:  # noqa: BLE001 - statement tanpa resultset
                return []
    finally:
        engine.dispose()


def _scalar(sql: str, params: dict | None = None):
    engine = _db()
    try:
        with engine.begin() as conn:
            return conn.execute(text(sql), params or {}).scalar_one_or_none()
    finally:
        engine.dispose()


def _hitung(tabel: str) -> int:
    return int(_scalar(f"SELECT count(*) FROM {tabel}"))


def _mk_user(role: str, kota: str = "Jakarta") -> dict:
    email = f"{role}-{uuid.uuid4().hex[:8]}@uji-f4-receipt.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    uid = str(uuid.uuid4())
    _exec(
        "INSERT INTO users (id, name, email, password_hash, role, location_id) "
        "SELECT :i, 'Uji F4 penerimaan', :e, :h, :r, l.id "
        "FROM locations l WHERE l.name = :k",
        {"i": uid, "e": email, "h": digest, "r": role, "k": kota},
    )
    return {"id": uid, "email": email, "password": PW}


def _login(client: TestClient, user: dict) -> dict:
    resp = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _drop_user(user: dict | None) -> None:
    if user:
        _exec(
            "DELETE FROM approvals WHERE approved_by = CAST(:i AS uuid)", {"i": user["id"]}
        )
        _exec("DELETE FROM users WHERE id = CAST(:i AS uuid)", {"i": user["id"]})


def _lokasi(kota: str) -> str:
    return str(_scalar("SELECT id FROM locations WHERE name = :k", {"k": kota}))


def _komoditas(nama: str) -> str:
    return str(_scalar("SELECT id FROM commodities WHERE name = :c", {"c": nama}))


def _supplier() -> str:
    return str(_scalar("SELECT id FROM suppliers ORDER BY id LIMIT 1"))


def _buat_batch(
    *,
    kota: str = "Jakarta",
    komoditas: str = "telur",
    supplier_id: str | None = None,
    quantity_kg: float = 150,
    safety_status: str = "pass",
    quarantine_status: str = "none",
    freshness_score: float = 0.95,
    usable_until: datetime | None | str = "default",
    temperature_log: list | None = None,
) -> dict:
    """Batch uji yang seluruh keadaannya ditentukan pemanggil.

    `usable_until="default"` berarti `now() + 5 hari`; `None` berarti NULL
    (masa layak tidak tercatat). Dibuat sendiri supaya tes tidak bergantung
    pada data demo yang bisa diubah tes lain di suite yang sama.
    """
    bid = str(uuid.uuid4())
    if usable_until == "default":
        usable_until = datetime.now(UTC) + timedelta(days=5)
    log = LOG_LENGKAP if temperature_log is None else temperature_log
    _exec(
        "INSERT INTO batches (id, commodity_id, location_id, supplier_id, "
        "quantity_kg, harvested_at, temperature_log, certification_status, "
        "freshness_score, safety_status, usable_until, quarantine_status, origin) "
        "VALUES (CAST(:i AS uuid), CAST(:c AS uuid), CAST(:l AS uuid), "
        "CAST(:s AS uuid), :kg, :h, CAST(:t AS jsonb), 'hygiene', :fs, :ss, "
        ":uu, :q, 'demo')",
        {
            "i": bid,
            "c": _komoditas(komoditas),
            "l": _lokasi(kota),
            "s": supplier_id or _supplier(),
            "kg": quantity_kg,
            "h": datetime.now(UTC) - timedelta(hours=6),
            "t": json.dumps(log),
            "fs": freshness_score,
            "ss": safety_status,
            "uu": usable_until,
            "q": quarantine_status,
        },
    )
    return {
        "batch_id": bid,
        "location_id": _lokasi(kota),
        "commodity_id": _komoditas(komoditas),
        "supplier_id": supplier_id or _supplier(),
        "quantity_kg": quantity_kg,
    }


def _hapus_batch(batch_id: str) -> None:
    # `batch_receipts` ikut terhapus (FK ON DELETE CASCADE); baris stok yang
    # lahir dari approve penerimaan tidak menunjuk batch, jadi dihapus di
    # pemanggil lewat `_hapus_supply`.
    _exec("DELETE FROM batches WHERE id = CAST(:b AS uuid)", {"b": batch_id})


def _hapus_supply(supply_ids: list[str]) -> None:
    for sid in supply_ids:
        _exec("DELETE FROM supply_records WHERE id = CAST(:i AS uuid)", {"i": sid})


def _supply_terakhir(location_id: str, commodity_id: str) -> float:
    nilai = _scalar(
        "SELECT quantity_kg FROM supply_records "
        "WHERE location_id = CAST(:l AS uuid) AND commodity_id = CAST(:c AS uuid) "
        "AND recorded_at <= now() ORDER BY recorded_at DESC, id DESC LIMIT 1",
        {"l": location_id, "c": commodity_id},
    )
    return float(nilai) if nilai is not None else 0.0


def _jumlah_receipt(batch_id: str) -> int:
    return int(
        _scalar(
            "SELECT count(*) FROM batch_receipts WHERE batch_id = CAST(:b AS uuid)",
            {"b": batch_id},
        )
    )


def _status_batch(batch_id: str) -> dict:
    baris = _exec(
        "SELECT safety_status, quarantine_status FROM batches "
        "WHERE id = CAST(:b AS uuid)",
        {"b": batch_id},
    )[0]
    return {"safety_status": baris[0], "quarantine_status": baris[1]}


def _catat(client, headers, batch_id: str, catatan: str = "uji f4"):
    return client.post(
        "/receipts",
        headers=headers,
        json={
            "batch_id": batch_id,
            "checked": {"kemasan": True, "suhu": True},
            "other_note": catatan,
        },
    )


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def kepala():
    user = _mk_user("sppg_head")
    yield user
    _drop_user(user)


@pytest.fixture()
def gizi():
    user = _mk_user("sppg_nutritionist")
    yield user
    _drop_user(user)


# ---------------------------------------------------------------------------
# 1. POST /receipts — tolak bila evaluator menyatakan rejected/quarantined
# ---------------------------------------------------------------------------


def test_catat_penerimaan_ditolak_untuk_batch_safety_fail(client, kepala):
    """`safety_fail` = rejected: ceklis tidak boleh menutupi kegagalan uji."""
    batch = _buat_batch(safety_status="fail")
    headers = _login(client, kepala)
    try:
        resp = _catat(client, headers, batch["batch_id"])
        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"].lower()
        assert "tidak aman" in detail, resp.text
        assert _jumlah_receipt(batch["batch_id"]) == 0
        # Pencatatan yang ditolak TIDAK boleh mengubah status keamanan batch.
        assert _status_batch(batch["batch_id"])["safety_status"] == "fail"
    finally:
        _hapus_batch(batch["batch_id"])


def test_catat_penerimaan_ditolak_untuk_batch_kedaluwarsa(client, kepala):
    batch = _buat_batch(usable_until=datetime.now(UTC) - timedelta(days=1))
    headers = _login(client, kepala)
    try:
        resp = _catat(client, headers, batch["batch_id"])
        assert resp.status_code == 409, resp.text
        assert "kedaluwarsa" in resp.json()["detail"].lower(), resp.text
        assert _jumlah_receipt(batch["batch_id"]) == 0
    finally:
        _hapus_batch(batch["batch_id"])


def test_catat_penerimaan_ditolak_bila_masa_layak_tidak_tercatat(client, kepala):
    """`usable_until` NULL = tidak dapat dibuktikan layak (expiry_unknown)."""
    batch = _buat_batch(usable_until=None)
    headers = _login(client, kepala)
    try:
        resp = _catat(client, headers, batch["batch_id"])
        assert resp.status_code == 409, resp.text
        assert "masa layak" in resp.json()["detail"].lower(), resp.text
        assert _jumlah_receipt(batch["batch_id"]) == 0
    finally:
        _hapus_batch(batch["batch_id"])


def test_catat_penerimaan_ditolak_untuk_batch_karantina(client, kepala):
    batch = _buat_batch(quarantine_status="quarantined")
    headers = _login(client, kepala)
    try:
        resp = _catat(client, headers, batch["batch_id"])
        assert resp.status_code == 409, resp.text
        assert "karantina" in resp.json()["detail"].lower(), resp.text
        assert _jumlah_receipt(batch["batch_id"]) == 0
        # Karantina bukan alasan mengubah status keamanan.
        assert _status_batch(batch["batch_id"])["safety_status"] == "pass"
    finally:
        _hapus_batch(batch["batch_id"])


def test_catat_penerimaan_ditolak_bila_freshness_fail(client, kepala):
    """`freshness_fail` juga rejected — skor segar di bawah ambang verifikasi."""
    batch = _buat_batch(freshness_score=0.40)
    headers = _login(client, kepala)
    try:
        resp = _catat(client, headers, batch["batch_id"])
        assert resp.status_code == 409, resp.text
        assert "segar" in resp.json()["detail"].lower(), resp.text
        assert _jumlah_receipt(batch["batch_id"]) == 0
    finally:
        _hapus_batch(batch["batch_id"])


@pytest.mark.parametrize(
    "safety_status", ["pending", "needs_verification"], ids=["pending", "needs-verification"]
)
def test_catat_penerimaan_on_hold_tetap_diterima(client, kepala, safety_status):
    """`on_hold` BUKAN alasan menolak pencatatan: ceklis = bahan verifikasi."""
    batch = _buat_batch(safety_status=safety_status)
    dibuat: list[str] = []
    headers = _login(client, kepala)
    try:
        resp = _catat(client, headers, batch["batch_id"])
        assert resp.status_code == 201, resp.text
        badan = resp.json()
        dibuat.append(badan["id"])
        assert badan["status"] == "menunggu"
        assert badan["stock_kg"] is None
        # Ceklis tercatat apa adanya — bukti untuk verifikasi lanjutan.
        assert badan["checked"] == {"kemasan": True, "suhu": True}
        assert _status_batch(batch["batch_id"])["safety_status"] == safety_status
    finally:
        _hapus_batch(batch["batch_id"])


# ---------------------------------------------------------------------------
# 2. POST /receipts/{id}/approve — hanya `usable` yang boleh disetujui
# ---------------------------------------------------------------------------


def test_setujui_penerimaan_batch_usable_menulis_stok(client, kepala):
    batch = _buat_batch()
    supply: list[str] = []
    headers = _login(client, kepala)
    try:
        # Stok on-hand dapur ini bisa saja sudah berisi (data demo/tes lain),
        # jadi yang diuji adalah SELISIH, bukan angka absolut.
        sebelum = _supply_terakhir(batch["location_id"], batch["commodity_id"])
        dibuat = _catat(client, headers, batch["batch_id"])
        assert dibuat.status_code == 201, dibuat.text
        setuju = client.post(
            f"/receipts/{dibuat.json()['id']}/approve", headers=headers
        )
        assert setuju.status_code == 200, setuju.text
        badan = setuju.json()
        assert badan["status"] == "disetujui"
        assert badan["stock_kg"] == batch["quantity_kg"]
        supply.append(badan["supply_record_id"])
        assert _supply_terakhir(
            batch["location_id"], batch["commodity_id"]
        ) == pytest.approx(sebelum + batch["quantity_kg"], abs=0.01)

        # Idempotensi yang sudah ada harus bertahan: klik kedua `sudah: true`.
        lagi = client.post(f"/receipts/{dibuat.json()['id']}/approve", headers=headers)
        assert lagi.status_code == 200, lagi.text
        assert lagi.json()["sudah"] is True
        assert lagi.json()["supply_record_id"] == badan["supply_record_id"]
    finally:
        _hapus_batch(batch["batch_id"])
        _hapus_supply(supply)


def test_setujui_ditolak_untuk_batch_safety_pending_dengan_kalimat_sendiri(
    client, kepala
):
    """`on_hold` = 409, tetapi kalimatnya menyebut BELUM DIUJI, bukan FAIL."""
    batch = _buat_batch(safety_status="pending")
    headers = _login(client, kepala)
    try:
        sebelum = _supply_terakhir(batch["location_id"], batch["commodity_id"])
        dibuat = _catat(client, headers, batch["batch_id"])
        assert dibuat.status_code == 201, dibuat.text
        resp = client.post(f"/receipts/{dibuat.json()['id']}/approve", headers=headers)
        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"].lower()
        assert "belum diuji" in detail or "pending" in detail, resp.text
        # `safety_pending` tidak boleh disamakan dengan kegagalan uji.
        assert "tidak aman" not in detail, resp.text
        assert _supply_terakhir(
            batch["location_id"], batch["commodity_id"]
        ) == pytest.approx(sebelum, abs=0.01), "on_hold tidak boleh menulis stok"
    finally:
        _hapus_batch(batch["batch_id"])


def test_setujui_ditolak_untuk_batch_safety_fail(client, kepala):
    batch = _buat_batch(safety_status="fail")
    headers = _login(client, kepala)
    try:
        # Catatan dibuat langsung di DB: POST /receipts memang menolak batch
        # rejected, tetapi persetujuan tetap harus dijaga sendiri (defense in
        # depth) — catatan lama bisa lahir sebelum batch dinyatakan fail.
        rid = str(uuid.uuid4())
        _exec(
            "INSERT INTO batch_receipts (id, batch_id, checked, other_note, "
            "recorded_by, status) VALUES (CAST(:i AS uuid), CAST(:b AS uuid), "
            "'{\"kemasan\": true}'::jsonb, 'catatan lama', CAST(:u AS uuid), 'menunggu')",
            {"i": rid, "b": batch["batch_id"], "u": kepala["id"]},
        )
        sebelum = _supply_terakhir(batch["location_id"], batch["commodity_id"])
        resp = client.post(f"/receipts/{rid}/approve", headers=headers)
        assert resp.status_code == 409, resp.text
        assert "tidak aman" in resp.json()["detail"].lower(), resp.text
        assert _supply_terakhir(
            batch["location_id"], batch["commodity_id"]
        ) == pytest.approx(sebelum, abs=0.01)
    finally:
        _hapus_batch(batch["batch_id"])


def test_setujui_ditolak_untuk_batch_dikarantina(client, kepala):
    batch = _buat_batch(quarantine_status="quarantined")
    headers = _login(client, kepala)
    try:
        rid = str(uuid.uuid4())
        _exec(
            "INSERT INTO batch_receipts (id, batch_id, checked, other_note, "
            "recorded_by, status) VALUES (CAST(:i AS uuid), CAST(:b AS uuid), "
            "'{}'::jsonb, 'catatan lama', CAST(:u AS uuid), 'menunggu')",
            {"i": rid, "b": batch["batch_id"], "u": kepala["id"]},
        )
        sebelum = _supply_terakhir(batch["location_id"], batch["commodity_id"])
        resp = client.post(f"/receipts/{rid}/approve", headers=headers)
        assert resp.status_code == 409, resp.text
        assert "karantina" in resp.json()["detail"].lower(), resp.text
        assert _supply_terakhir(
            batch["location_id"], batch["commodity_id"]
        ) == pytest.approx(sebelum, abs=0.01)
    finally:
        _hapus_batch(batch["batch_id"])


# ---------------------------------------------------------------------------
# 3. GET /batches/{id} — eligibility dihitung server
# ---------------------------------------------------------------------------


def test_detail_batch_on_hold_membawa_eligibility_dari_server(client, kepala):
    batch = _buat_batch(safety_status="pending")
    headers = _login(client, kepala)
    try:
        resp = client.get(f"/batches/{batch['batch_id']}", headers=headers)
        assert resp.status_code == 200, resp.text
        eligibility = resp.json()["eligibility"]
        assert eligibility["status"] == "on_hold", eligibility
        assert "safety_pending" in eligibility["blocking_reasons"], eligibility
        assert "uji keamanan pangan" in eligibility["next_step"].lower(), eligibility
    finally:
        _hapus_batch(batch["batch_id"])


def test_detail_batch_usable_tanpa_langkah_lanjutan(client, kepala):
    batch = _buat_batch()
    headers = _login(client, kepala)
    try:
        resp = client.get(f"/batches/{batch['batch_id']}", headers=headers)
        assert resp.status_code == 200, resp.text
        eligibility = resp.json()["eligibility"]
        assert eligibility["status"] == "usable", eligibility
        assert eligibility["blocking_reasons"] == []
        assert eligibility["next_step"] is None
    finally:
        _hapus_batch(batch["batch_id"])


def test_detail_batch_karantina_menyebut_langkah_pelepasan(client, kepala):
    batch = _buat_batch(quarantine_status="quarantined")
    headers = _login(client, kepala)
    try:
        resp = client.get(f"/batches/{batch['batch_id']}", headers=headers)
        assert resp.status_code == 200, resp.text
        eligibility = resp.json()["eligibility"]
        assert eligibility["status"] == "quarantined", eligibility
        assert "quarantined" in eligibility["blocking_reasons"], eligibility
        assert "lepas karantina" in eligibility["next_step"].lower(), eligibility
    finally:
        _hapus_batch(batch["batch_id"])


def test_detail_batch_eligibility_mengikuti_perubahan_keadaan(client, kepala):
    """Field ini dihitung saat dibaca — bukan snapshot lama yang disimpan UI."""
    batch = _buat_batch(safety_status="pending")
    headers = _login(client, kepala)
    try:
        sebelum = client.get(
            f"/batches/{batch['batch_id']}", headers=headers
        ).json()["eligibility"]
        assert sebelum["status"] == "on_hold", sebelum

        _exec(
            "UPDATE batches SET safety_status = 'fail' WHERE id = CAST(:b AS uuid)",
            {"b": batch["batch_id"]},
        )
        sesudah = client.get(
            f"/batches/{batch['batch_id']}", headers=headers
        ).json()["eligibility"]
        assert sesudah["status"] == "rejected", sesudah
        assert "safety_fail" in sesudah["blocking_reasons"], sesudah
    finally:
        _hapus_batch(batch["batch_id"])


# ---------------------------------------------------------------------------
# 4. POST /batches/{id}/quarantine — regresi: alasan wajib, aktor, safety tetap
# ---------------------------------------------------------------------------


def test_karantina_wajib_alasan_dan_tidak_mengubah_safety_status(client, kepala):
    batch = _buat_batch(safety_status="pass")
    headers = _login(client, kepala)
    try:
        kosong = client.post(
            f"/batches/{batch['batch_id']}/quarantine",
            json={"aksi": "tahan", "alasan": "   "},
            headers=headers,
        )
        assert kosong.status_code == 422, kosong.text
        assert _status_batch(batch["batch_id"])["quarantine_status"] == "none"

        resp = client.post(
            f"/batches/{batch['batch_id']}/quarantine",
            json={"aksi": "tahan", "alasan": "suhu ruang muat 12 C"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        badan = resp.json()
        assert badan["quarantine_status"] == "quarantined"
        assert badan["quarantine_reason"] == "suhu ruang muat 12 C"
        # Karantina menahan alokasi, bukan mengubah status keamanan pangan.
        assert badan["safety_status"] == "pass"
        status = _status_batch(batch["batch_id"])
        assert status == {"safety_status": "pass", "quarantine_status": "quarantined"}

        # Aktor reviewer tercatat di baris batch DAN di blok ledger.
        aktor = _scalar(
            "SELECT quarantine_actor_id FROM batches WHERE id = CAST(:b AS uuid)",
            {"b": batch["batch_id"]},
        )
        assert str(aktor) == kepala["id"]
        payload = _scalar(
            "SELECT payload FROM ledger_blocks WHERE entity_id = CAST(:b AS uuid) "
            "ORDER BY height DESC LIMIT 1",
            {"b": batch["batch_id"]},
        )
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["alasan"] == "suhu ruang muat 12 C"
        assert payload["oleh"] == kepala["email"]
        assert payload["safety_status"] == "pass"
    finally:
        _hapus_batch(batch["batch_id"])


def test_karantina_bukan_penerimaan_sukses(client, kepala):
    """Batch terkarantina tidak menambah stok walau ada catatan penerimaan."""
    batch = _buat_batch()
    headers = _login(client, kepala)
    try:
        sebelum = _supply_terakhir(batch["location_id"], batch["commodity_id"])
        resp = client.post(
            f"/batches/{batch['batch_id']}/quarantine",
            json={"aksi": "tahan", "alasan": "kemasan bocor"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

        catat = _catat(client, headers, batch["batch_id"])
        assert catat.status_code == 409, catat.text
        assert _jumlah_receipt(batch["batch_id"]) == 0
        assert _supply_terakhir(
            batch["location_id"], batch["commodity_id"]
        ) == pytest.approx(sebelum, abs=0.01)
    finally:
        _hapus_batch(batch["batch_id"])


# ---------------------------------------------------------------------------
# 5. Uji transaksi — revalidasi gagal tidak meninggalkan tulisan apa pun
# ---------------------------------------------------------------------------


TABLE_FAKTA = (
    "sap_mock_purchase_orders",
    "supply_records",
    "delivery_events",
    "ledger_blocks",
    "agent_traces",
    "price_signals",
)


def _siapkan_keputusan(
    *, batch: dict, kepala: dict, gizi: dict, source_location_id: str, target: str
) -> str:
    """Keputusan transfer terverifikasi + dua approval lokasi TUJUAN."""
    did = str(uuid.uuid4())
    _exec(
        "INSERT INTO decisions (id, decision_type, status, proposed_by, "
        "source_location_id, target_location_id, commodity_id, quantity_kg, "
        "safe_delivered_cost, expires_at, cost_breakdown, iteration, "
        "verified_by, verifier_note, supplier_id) "
        "VALUES (CAST(:i AS uuid), 'regional_balance', 'pending_approval', "
        "'supervisor_agent', CAST(:src AS uuid), CAST(:tgt AS uuid), "
        "CAST(:kom AS uuid), 150, 2250000, now() + interval '45 minutes', "
        "'{\"purchase\": \"2250000\"}'::jsonb, 1, 'verifier_agent', 'consistent', "
        "CAST(:sup AS uuid))",
        {
            "i": did,
            "src": source_location_id,
            "tgt": target,
            "kom": batch["commodity_id"],
            "sup": batch["supplier_id"],
        },
    )
    _exec(
        "INSERT INTO decision_evidence (decision_id, evidence_type, payload) "
        "VALUES (CAST(:d AS uuid), 'human_inspection', CAST(:p AS jsonb))",
        {
            "d": did,
            "p": json.dumps(
                {
                    "allocation_binding": True,
                    "supplier_id": batch["supplier_id"],
                    "batch_ids": [batch["batch_id"]],
                }
            ),
        },
    )
    for u in (kepala, gizi):
        _exec(
            "INSERT INTO approvals (decision_id, approved_by, approved, comment) "
            "VALUES (CAST(:d AS uuid), CAST(:u AS uuid), true, 'fixture f4')",
            {"d": did, "u": u["id"]},
        )
    return did


def _bersihkan_keputusan(did: str) -> None:
    _exec(
        "DELETE FROM sap_mock_purchase_orders WHERE decision_id = CAST(:d AS uuid)",
        {"d": did},
    )
    _exec(
        "DELETE FROM price_signals WHERE source_ref IN ("
        "SELECT 'po:' || po_number FROM sap_mock_purchase_orders "
        "WHERE decision_id = CAST(:d AS uuid))",
        {"d": did},
    )
    _exec("DELETE FROM approvals WHERE decision_id = CAST(:d AS uuid)", {"d": did})
    _exec("DELETE FROM decision_evidence WHERE decision_id = CAST(:d AS uuid)", {"d": did})
    _exec("DELETE FROM agent_traces WHERE decision_id = CAST(:d AS uuid)", {"d": did})
    _exec("DELETE FROM decisions WHERE id = CAST(:d AS uuid)", {"d": did})


@pytest.mark.parametrize(
    "keadaan",
    [
        {"safety_status": "fail"},
        {"safety_status": "pending"},
        {"usable_until": datetime.now(UTC) - timedelta(hours=2)},
    ],
    ids=["safety-fail", "safety-pending", "kedaluwarsa"],
)
def test_execute_gagal_revalidasi_tidak_menulis_apa_pun(client, kepala, gizi, keadaan):
    """Poin 8: revalidasi safety gagal → nol tulisan, status keputusan tetap."""
    batch = _buat_batch(kota="Cianjur", safety_status="pass")
    headers = _login(client, kepala)
    did = _siapkan_keputusan(
        batch=batch,
        kepala=kepala,
        gizi=gizi,
        source_location_id=batch["location_id"],
        target=_lokasi("Jakarta"),
    )
    try:
        # Keadaan batch berubah SESUDAH keputusan disetujui: inilah revalidasi.
        _exec(
            "UPDATE batches SET safety_status = :ss, usable_until = :uu "
            "WHERE id = CAST(:b AS uuid)",
            {
                "ss": keadaan.get("safety_status", "pass"),
                "uu": keadaan.get("usable_until", datetime.now(UTC) + timedelta(days=5)),
                "b": batch["batch_id"],
            },
        )
        sebelum = {t: _hitung(t) for t in TABLE_FAKTA}
        status_sebelum = _scalar(
            "SELECT status FROM decisions WHERE id = CAST(:d AS uuid)", {"d": did}
        )

        resp = client.post(
            "/actions/execute", json={"decision_id": did}, headers=headers
        )
        assert resp.status_code == 409, resp.text
        assert "safety revalidation gagal" in resp.text, resp.text

        sesudah = {t: _hitung(t) for t in TABLE_FAKTA}
        assert sesudah == sebelum, {
            t: (sebelum[t], sesudah[t]) for t in TABLE_FAKTA if sebelum[t] != sesudah[t]
        }
        assert (
            _scalar("SELECT status FROM decisions WHERE id = CAST(:d AS uuid)", {"d": did})
            == status_sebelum
        ), "status keputusan tidak boleh berubah saat eksekusi ditolak"
        # Batch juga tidak diberangkatkan / ditulisi tenggat baru.
        assert (
            _scalar(
                "SELECT dispatched_at FROM batches WHERE id = CAST(:b AS uuid)",
                {"b": batch["batch_id"]},
            )
            is None
        )
    finally:
        _bersihkan_keputusan(did)
        _hapus_batch(batch["batch_id"])


def test_setujui_penerimaan_gagal_tidak_menulis_stok_dan_kpi(client, kepala):
    """Poin 8 untuk jalur penerimaan: revalidasi gagal = nol tulisan.

    Catatan `menunggu` disisipkan langsung supaya yang diuji adalah gerbang
    PERSETUJUAN (bukan penolakan pencatatan). Batch dengan `usable_until` NULL
    lolos aturan lama (`receipt_blokir_alasan` tidak menilainya) sehingga stok
    dulu bertambah; evaluator Fase 4 menyebutnya `expiry_unknown` = rejected.
    """
    batch = _buat_batch(usable_until=None)
    headers = _login(client, kepala)
    rid = str(uuid.uuid4())
    try:
        _exec(
            "INSERT INTO batch_receipts (id, batch_id, checked, other_note, "
            "recorded_by, status) VALUES (CAST(:i AS uuid), CAST(:b AS uuid), "
            "'{\"kemasan\": true}'::jsonb, 'catatan lama', CAST(:u AS uuid), 'menunggu')",
            {"i": rid, "b": batch["batch_id"], "u": kepala["id"]},
        )
        sebelum = {t: _hitung(t) for t in TABLE_FAKTA}

        resp = client.post(f"/receipts/{rid}/approve", headers=headers)
        assert resp.status_code == 409, resp.text
        assert "masa layak" in resp.json()["detail"].lower(), resp.text

        sesudah = {t: _hitung(t) for t in TABLE_FAKTA}
        assert sesudah == sebelum, {
            t: (sebelum[t], sesudah[t]) for t in TABLE_FAKTA if sebelum[t] != sesudah[t]
        }
        status = _scalar(
            "SELECT status FROM batch_receipts WHERE id = CAST(:i AS uuid)", {"i": rid}
        )
        assert status == "menunggu", "keputusan penerimaan tidak boleh berubah"
    finally:
        _hapus_batch(batch["batch_id"])
