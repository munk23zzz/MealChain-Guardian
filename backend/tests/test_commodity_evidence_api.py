"""Bukti suhu pada API batch (Fase 3 butir 5) — daftar DAN detail, satu parser.

Kontrak yang dikunci berkas ini (MG/phase-03-commodity-evidence.md butir 5):

1. `GET /batches/{id}` mengembalikan blok `evidence` berisi profil yang dipakai,
   hasil observasi (`observed`/`missing`/`malformed`/`stale`), `evidence_state`,
   jumlah sampel, waktu observasi, dan **asal log** (`source`/`source_label`).
2. `GET /batches` mengembalikan blok yang SAMA untuk tiap baris: pembaca daftar
   tidak boleh menyimpulkan kelengkapan bukti sendiri, dan tidak boleh berbeda
   pendapat dengan detail untuk batch yang sama.
3. Asal log disebut apa adanya: log tulisan penyemai/jalur demo adalah
   **"log simulasi"** — repo ini tidak punya satu pun jalur penulisan log dari
   sensor sungguhan, jadi "sensor aktif" adalah klaim yang tidak boleh muncul.
4. Bukti yang tidak cukup TIDAK boleh tampil sebagai skor tinggi: batch rantai
   dingin tanpa log tetap `insufficient`, bukan `sufficient` dengan penalti nol.
5. Komoditas ambient (beras) boleh tanpa log dan tetap tidak `fail`; profilnya
   memang tidak punya rentang dingin untuk dilanggar.

Diuji terhadap DB nyata (pola `test_receipt_quarantine.py`): baris batch dibuat
berkas ini sendiri lalu dihapus lagi, sehingga tidak bergantung pada data demo
yang bisa diubah tes lain.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC

#: Kunci blok bukti yang dibaca UI dan Joule. Menambah kunci boleh; menghapus
#: salah satunya memutus pembaca yang sudah ada.
KUNCI_BUKTI = {
    "commodity_profile",
    "profile_source",
    "temperature_observation",
    "evidence_state",
    "sample_count",
    "observed_at",
    "source",
    "source_label",
    "evidence_sufficient",
    "evidence_reasons",
}


# ---------------------------------------------------------------------------
# Helper DB (psycopg sinkron, DSN mengikuti DATABASE_URL)
# ---------------------------------------------------------------------------


def _db():
    return create_engine(DSN_SYNC)


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


def _lokasi(kota: str = "Jakarta") -> str:
    return str(_scalar("SELECT id FROM locations WHERE name = :k", {"k": kota}))


def _komoditas(nama: str) -> str:
    return str(_scalar("SELECT id FROM commodities WHERE name = :c", {"c": nama}))


def _supplier() -> str:
    return str(_scalar("SELECT id FROM suppliers ORDER BY id LIMIT 1"))


def _buat_batch(
    *,
    komoditas: str = "telur",
    kota: str = "Jakarta",
    quantity_kg: float = 90,
    temperature_log: list | None = None,
    origin: str = "seed",
    safety_status: str = "pending",
    freshness_score: float | None = 0.9,
) -> str:
    """Batch uji dengan log suhu yang ditentukan pemanggil (bukan state demo)."""
    bid = str(uuid.uuid4())
    _exec(
        "INSERT INTO batches (id, commodity_id, location_id, supplier_id, "
        "quantity_kg, harvested_at, temperature_log, certification_status, "
        "freshness_score, safety_status, usable_until, quarantine_status, origin) "
        "VALUES (CAST(:i AS uuid), CAST(:c AS uuid), CAST(:l AS uuid), "
        "CAST(:s AS uuid), :kg, :h, CAST(:t AS jsonb), 'hygiene', "
        ":fs, :ss, :uu, 'none', :orig)",
        {
            "i": bid,
            "c": _komoditas(komoditas),
            "l": _lokasi(kota),
            "s": _supplier(),
            "kg": quantity_kg,
            "h": datetime.now(UTC) - timedelta(hours=6),
            "t": json.dumps(temperature_log or []),
            "fs": freshness_score,
            "ss": safety_status,
            "uu": datetime.now(UTC) + timedelta(days=5),
            "orig": origin,
        },
    )
    return bid


def _hapus_batch(*batch_ids: str) -> None:
    for bid in batch_ids:
        _exec("DELETE FROM batches WHERE id = CAST(:b AS uuid)", {"b": bid})


def _stamp(jam_lalu: float, suhu: float) -> dict:
    return {
        "timestamp": (datetime.now(UTC) - timedelta(hours=jam_lalu)).isoformat(),
        "temperature_c": suhu,
    }


LOG_SAH = [_stamp(2, 4.0), _stamp(1, 4.5)]
LOG_LAMA = [_stamp(24 * 5, 4.0), _stamp(24 * 5 - 0.5, 4.5)]


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. Blok bukti ada dan berbentuk satu kontrak
# ---------------------------------------------------------------------------


def test_detail_batch_membawa_blok_bukti_lengkap(client, auth_headers):
    bid = _buat_batch(temperature_log=LOG_SAH)
    try:
        resp = client.get(f"/batches/{bid}", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        bukti = resp.json().get("evidence")
        assert bukti is not None, "detail batch wajib membawa blok `evidence`"
        assert KUNCI_BUKTI <= set(bukti), f"kunci hilang: {KUNCI_BUKTI - set(bukti)}"

        profil = bukti["commodity_profile"]
        assert profil["commodity"] == "telur"
        assert profil["cold_chain_required"] is True
        assert profil["policy_kind"] == "simulated_policy", (
            "angka suhu belum divalidasi domain owner → profil harus jujur "
            "sebagai simulasi"
        )
        assert profil["policy_version"], "profil tanpa versi tidak bisa ditelusuri"
        assert bukti["profile_source"], "asal profil wajib disebut"
    finally:
        _hapus_batch(bid)


def test_profil_dan_bukti_tidak_mengubah_bentuk_baris_daftar(client, auth_headers):
    """`batch` pada detail tetap sama dengan elemen daftar (kontrak P6)."""
    bid = _buat_batch(temperature_log=LOG_SAH)
    try:
        detail = client.get(f"/batches/{bid}", headers=auth_headers).json()
        daftar = client.get(
            "/batches", params={"limit": 500}, headers=auth_headers
        ).json()
        baris = next(b for b in daftar["batches"] if b["id"] == bid)

        # Blok bukti hidup di tingkat ATAS detail dan di dalam tiap baris daftar;
        # `batch`/`_baris` sendiri tidak bertambah kunci (dikunci
        # `test_batch_detail.KOLOM`).
        assert set(detail["batch"]) == set(baris) - {"evidence"}
        assert detail["evidence"]["evidence_state"] == baris["evidence"]["evidence_state"]
        assert detail["evidence"]["temperature_observation"] == (
            baris["evidence"]["temperature_observation"]
        )
    finally:
        _hapus_batch(bid)


# ---------------------------------------------------------------------------
# 2. Bukti kurang tidak boleh tampil sebagai cukup
# ---------------------------------------------------------------------------


def test_cold_chain_tanpa_log_bukti_tidak_cukup(client, auth_headers):
    bid = _buat_batch(temperature_log=[])
    try:
        bukti = client.get(f"/batches/{bid}", headers=auth_headers).json()["evidence"]
        assert bukti["temperature_observation"] == "missing"
        assert bukti["evidence_state"] == "insufficient"
        assert bukti["evidence_sufficient"] is False
        assert bukti["sample_count"] == 0
        assert bukti["observed_at"] is None
        assert bukti["evidence_reasons"], "alasan ketidakcukupan wajib disebut"
    finally:
        _hapus_batch(bid)


def test_satu_sampel_cold_chain_belum_cukup(client, auth_headers):
    bid = _buat_batch(temperature_log=[_stamp(1, 4.0)])
    try:
        bukti = client.get(f"/batches/{bid}", headers=auth_headers).json()["evidence"]
        assert bukti["sample_count"] == 1
        assert bukti["evidence_state"] == "insufficient"
    finally:
        _hapus_batch(bid)


def test_log_lama_tidak_dianggap_observasi_realtime(client, auth_headers):
    """Sampel lima hari lalu bukan bukti rantai dingin hari ini."""
    bid = _buat_batch(temperature_log=LOG_LAMA)
    try:
        bukti = client.get(f"/batches/{bid}", headers=auth_headers).json()["evidence"]
        assert bukti["temperature_observation"] == "stale"
        assert bukti["evidence_state"] == "insufficient"
        assert bukti["observed_at"] is not None, "waktu sampel terakhir tetap dilaporkan"
    finally:
        _hapus_batch(bid)


def test_log_sah_cukup_dan_menyebut_waktu_observasi(client, auth_headers):
    bid = _buat_batch(temperature_log=LOG_SAH)
    try:
        bukti = client.get(f"/batches/{bid}", headers=auth_headers).json()["evidence"]
        assert bukti["temperature_observation"] == "observed"
        assert bukti["evidence_state"] == "sufficient"
        assert bukti["evidence_sufficient"] is True
        assert bukti["sample_count"] == 2
        assert bukti["observed_at"] is not None
    finally:
        _hapus_batch(bid)


def test_beras_ambient_tanpa_log_bukan_fail(client, auth_headers):
    bid = _buat_batch(komoditas="beras", temperature_log=[])
    try:
        bukti = client.get(f"/batches/{bid}", headers=auth_headers).json()["evidence"]
        assert bukti["commodity_profile"]["cold_chain_required"] is False
        assert bukti["temperature_observation"] == "missing"
        assert bukti["evaluated_safety_status"] != "fail"
    finally:
        _hapus_batch(bid)


# ---------------------------------------------------------------------------
# 3. Asal log disebut apa adanya — bukan "sensor aktif"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("origin", ["seed", "demo"])
def test_asal_log_disebut_log_simulasi(client, auth_headers, origin):
    """Tidak ada satu pun jalur penulisan log dari sensor sungguhan di repo ini."""
    bid = _buat_batch(temperature_log=LOG_SAH, origin=origin)
    try:
        bukti = client.get(f"/batches/{bid}", headers=auth_headers).json()["evidence"]
        assert bukti["source"] == origin
        assert bukti["source_label"] == "log simulasi"
        assert "sensor" not in bukti["source_label"].lower()
    finally:
        _hapus_batch(bid)


def test_daftar_batch_membawa_bukti_per_baris(client, auth_headers):
    bid = _buat_batch(temperature_log=LOG_SAH)
    try:
        daftar = client.get(
            "/batches", params={"limit": 500}, headers=auth_headers
        ).json()
        for baris in daftar["batches"]:
            assert "evidence" in baris, (
                "pembaca daftar tidak boleh menyimpulkan kelengkapan bukti sendiri"
            )
            assert KUNCI_BUKTI <= set(baris["evidence"])
    finally:
        _hapus_batch(bid)
