"""Seed kasus demo per kota (audit M4, 18 Okt 2026).

Masalah: `POST /demo/seed` mengabaikan pemanggilnya (`_user`) dan menanam empat
kasus dengan target **Jakarta** selalu. Kepala Bandung menekan "Muat kasus
demo", lalu menerima empat kartu yang tidak bisa ia sentuh (approve ditolak
403 scope) — demo mati di kota itu.

Kontrak baru:
1. Target kasus = lokasi pemanggil.
2. Sumber bahan != lokasi target (kalau sama, keputusan tidak masuk akal:
   memindahkan barang ke dirinya sendiri).
3. Idempoten PER KOTA: seed kedua tanpa `force` tidak menggandakan, dan
   `force=true` hanya menghapus baris demo kota pemanggil — kasus kota lain
   tidak ikut hilang.
"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.demo import DEMO_CASES
from app.main import app
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DB_URL = (
    DSN_ASYNC
).replace("+asyncpg", "+psycopg")

PW = "TestPass#2026"
CASES = (
    "rejection-loop-kuota",
    "shortage-darurat",
    "supplier-janggal",
    "gangguan-logistik",
)


def _db():
    return create_engine(DB_URL)


def _mk_user(role: str, location: str) -> dict:
    email = f"{role}-{uuid.uuid4().hex[:8]}@seed-kota.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    engine = _db()
    try:
        with engine.begin() as conn:
            loc = conn.execute(
                text("SELECT id FROM locations WHERE name = :n"), {"n": location}
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (gen_random_uuid(), :n, :e, :h, :r, :l)"
                ),
                {"n": f"T {role} {location}", "e": email, "h": digest, "r": role, "l": loc},
            )
        return {"email": email, "password": PW}
    finally:
        engine.dispose()


def _drop(email: str) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
    finally:
        engine.dispose()


def _login(client: TestClient, user: dict) -> dict:
    resp = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _rows(query: str, params: dict | None = None) -> list[dict]:
    engine = _db()
    try:
        with engine.connect() as conn:
            return [dict(r) for r in conn.execute(text(query), params or {}).mappings()]
    finally:
        engine.dispose()


def _demo_rows(kota: str) -> list[dict]:
    """Baris kasus `/demo/seed` untuk satu kota.

    Disaring ke namespace `DEMO_CASES` milik endpoint itu, bukan "semua baris
    yang punya `demo_case` di kota ini": builder pelengkap cakupan
    (`seed/demo_extra.py`) menulis `demo_case='extra:*'` untuk kota yang sama,
    jadi tanpa saringan ini tes menghitung 8 baris padahal endpoint menyemai 4,
    dan `already` (7) tidak sama dengan `jumlah` (8). Saringan ini menyatakan
    maksud tesnya (keluaran `/demo/seed`), bukan melonggarkan asersinya —
    himpunan yang dituntut tetap `set(CASES)` dan target tetap harus kota itu.
    """
    return _rows(
        "SELECT d.id, d.demo_case, d.status, dl.name AS target, sl.name AS sumber "
        "FROM decisions d "
        "JOIN locations dl ON dl.id = d.target_location_id "
        "LEFT JOIN locations sl ON sl.id = d.source_location_id "
        "WHERE d.demo_case = ANY(:kasus) AND dl.name = :k",
        {"k": kota, "kasus": list(DEMO_CASES)},
    )


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_seed_dari_bandung_menargetkan_bandung(client):
    kepala = _mk_user("sppg_head", "Bandung")
    try:
        resp = client.post(
            "/demo/seed", json={"force": True}, headers=_login(client, kepala)
        )
        assert resp.status_code == 200, resp.text
        rows = _demo_rows("Bandung")
        assert {r["demo_case"] for r in rows} == set(CASES), rows
        assert all(r["target"] == "Bandung" for r in rows), rows
        # Sumber tidak boleh = target.
        assert all(r["sumber"] not in (None, "Bandung") for r in rows), rows
    finally:
        _drop(kepala["email"])


def test_seed_idempoten_per_kota(client):
    kepala = _mk_user("sppg_head", "Bandung")
    try:
        headers = _login(client, kepala)
        client.post("/demo/seed", json={"force": True}, headers=headers)
        jumlah = len(_demo_rows("Bandung"))
        resp = client.post("/demo/seed", json={"force": False}, headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["seeded"] is False
        assert body["already"] == jumlah
        assert len(_demo_rows("Bandung")) == jumlah
    finally:
        _drop(kepala["email"])


def test_force_bandung_tidak_menghapus_kasus_jakarta(client):
    jakarta = _mk_user("sppg_head", "Jakarta")
    bandung = _mk_user("sppg_head", "Bandung")
    try:
        # Pastikan Jakarta punya kasus dulu — jangan bergantung pada sisa run lain.
        client.post("/demo/seed", json={"force": True}, headers=_login(client, jakarta))
        jakarta_awal = len(_demo_rows("Jakarta"))
        assert jakarta_awal >= len(CASES)

        client.post("/demo/seed", json={"force": True}, headers=_login(client, bandung))

        jakarta_akhir = _demo_rows("Jakarta")
        assert len(jakarta_akhir) == jakarta_awal, (jakarta_awal, len(jakarta_akhir))
        assert all(r["target"] == "Jakarta" for r in jakarta_akhir)
        assert {r["demo_case"] for r in _demo_rows("Bandung")} == set(CASES)
    finally:
        _drop(jakarta["email"])
        _drop(bandung["email"])


def test_ahli_gizi_kota_boleh_menyemai(client):
    # Panel Demo Control memang untuk dua peran SPPG.
    gizi = _mk_user("sppg_nutritionist", "Surabaya")
    try:
        resp = client.post(
            "/demo/seed", json={"force": True}, headers=_login(client, gizi)
        )
        assert resp.status_code == 200, resp.text
        rows = _demo_rows("Surabaya")
        assert {r["demo_case"] for r in rows} == set(CASES), rows
        assert all(r["target"] == "Surabaya" for r in rows), rows
    finally:
        _drop(gizi["email"])
