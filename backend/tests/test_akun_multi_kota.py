"""Akun SPPG per kota (keputusan produk 3A, 18 Okt 2026).

Sebelum ini hanya ada SATU Kepala SPPG dan SATU Ahli Gizi, keduanya Jakarta.
Karena `/actions/approve` dan `/actions/execute` mengunci lokasi target, setiap
keputusan yang menyasar Bandung/Surabaya mustahil di-approve siapa pun. Riwayat
demo "executed" untuk dua kota itu pun disemai dengan approval akun Jakarta —
sah sebagai baris, tidak sah sebagai alur.

Yang dipaku di berkas ini:

1. untuk setiap kota demo (Bandung, Surabaya) ada Kepala SPPG dan Ahli Gizi
   yang benar-benar ber-lokasi kota itu, dan password demo-nya bisa dipakai login;
2. setiap approval pada keputusan demo yang sudah `executed` berasal dari user
   yang lokasinya SAMA dengan lokasi target keputusan (tidak ada lagi approval
   lintas kota);
3. Kepala SPPG Bandung hanya melihat keputusan bertarget Bandung di feed-nya.

Domain email tidak dipakai di sini (akun demo `@demo.local` milik produk, bukan
fixture tes), jadi tidak terpengaruh sapuan `%@test.local` sesi lain.
"""

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.seed.seed_data import DEMO_USERS, ensure_demo_users
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DB_URL = (
    DSN_ASYNC
).replace("+asyncpg", "+psycopg")

KOTA = ("Bandung", "Surabaya")


def _db():
    return create_engine(DB_URL)


def _rows(sql: str, params: dict | None = None):
    engine = _db()
    try:
        with engine.connect() as conn:
            return conn.execute(text(sql), params or {}).mappings().all()
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def seed_akun():
    """Pastikan akun demo per kota ada (idempoten, sama seperti seed produksi)."""
    ensure_demo_users()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_akun_kepala_dan_gizi_ada_di_setiap_kota(seed_akun):
    rows = _rows(
        "SELECT u.email, u.role, l.name AS lokasi FROM users u "
        "LEFT JOIN locations l ON l.id = u.location_id "
        "WHERE u.email = ANY(:emails)",
        {"emails": [u["email"] for u in DEMO_USERS]},
    )
    peta = {(r["role"], r["lokasi"]): r["email"] for r in rows}
    for kota in KOTA:
        assert ("sppg_head", kota) in peta, f"Kepala SPPG {kota} belum ada"
        assert ("sppg_nutritionist", kota) in peta, f"Ahli Gizi {kota} belum ada"


def test_password_akun_kota_bisa_dipakai_login(seed_akun, client):
    for kota in KOTA:
        for akun in DEMO_USERS:
            if akun["location"] != kota or akun["role"] == "bgn_monitor":
                continue
            resp = client.post(
                "/auth/login",
                json={"email": akun["email"], "password": akun["password"]},
            )
            assert resp.status_code == 200, f"{akun['email']}: {resp.text}"
            assert resp.json()["access_token"]


def test_password_demo_cocok_dengan_hash_di_db(seed_akun):
    """Password di kode dan hash di DB tidak boleh menyimpang."""
    for akun in DEMO_USERS:
        if akun["location"] not in KOTA:
            continue
        rows = _rows(
            "SELECT password_hash FROM users WHERE email = :e", {"e": akun["email"]}
        )
        assert rows, f"{akun['email']} tidak ada di DB"
        hash_db = rows[0]["password_hash"]
        assert bcrypt.checkpw(akun["password"].encode(), hash_db.encode()), akun["email"]


def test_approval_riwayat_demo_sesuai_lokasi_target(seed_akun):
    """Tidak boleh ada lagi approval lintas kota pada riwayat `executed`."""
    rows = _rows(
        "SELECT d.status, dl.name AS target, ul.name AS approver_loc, u.role "
        "FROM approvals a "
        "JOIN decisions d ON d.id = a.decision_id "
        "JOIN users u ON u.id = a.approved_by "
        "LEFT JOIN locations ul ON ul.id = u.location_id "
        "LEFT JOIN locations dl ON dl.id = d.target_location_id "
        # Filter lama `d.origin = 'demo'` mengikat tes ke satu cara penyemaian.
        # Template demo membekukan origin menjadi 'seed' supaya barisnya selamat
        # dari penyapu sesi (lihat `_bekukan` di app/seed/demo_template.py), jadi
        # invarian ini diuji pada SELURUH keputusan executed — cakupan lebih luas,
        # bukan lebih longgar.
        "WHERE d.status = 'executed'"
    )
    assert rows, "riwayat demo executed tidak ada — seed belum dijalankan?"
    beda = [r for r in rows if r["approver_loc"] != r["target"]]
    assert not beda, beda


def test_semua_approval_sesuai_lokasi_target(seed_akun):
    """Pagarnya bukan hanya riwayat demo: SETIAP approval di DB harus berasal
    dari approver di lokasi target keputusannya. Ini penjaga A5 yang paling
    luas — kalau ada jalur lain yang menyemai approval lintas kota, tes ini
    merah tanpa perlu tahu jalur mana."""
    rows = _rows(
        "SELECT d.status, dl.name AS target, ul.name AS approver_loc, u.role, "
        "a.decision_id "
        "FROM approvals a "
        "JOIN decisions d ON d.id = a.decision_id "
        "JOIN users u ON u.id = a.approved_by "
        "LEFT JOIN locations ul ON ul.id = u.location_id "
        "LEFT JOIN locations dl ON dl.id = d.target_location_id"
    )
    assert rows, "tidak ada approval sama sekali — DB demo belum disemai?"
    beda = [r for r in rows if r["approver_loc"] != r["target"]]
    assert not beda, beda


def test_kepala_bandung_hanya_melihat_keputusan_bandung(seed_akun, client):
    akun = next(
        u
        for u in DEMO_USERS
        if u["location"] == "Bandung" and u["role"] == "sppg_head"
    )
    token = client.post(
        "/auth/login", json={"email": akun["email"], "password": akun["password"]}
    ).json()["access_token"]
    resp = client.get("/decisions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert items, "keputusan demo Bandung tidak terlihat oleh Kepala Bandung"
    ids = [i["decision_id"] for i in items]
    rows = _rows(
        "SELECT DISTINCT l.name AS target FROM decisions d "
        "LEFT JOIN locations l ON l.id = d.target_location_id "
        "WHERE d.id = ANY(CAST(:ids AS uuid[]))",
        {"ids": ids},
    )
    lokasi = {r["target"] for r in rows}
    assert lokasi == {"Bandung"}, lokasi
