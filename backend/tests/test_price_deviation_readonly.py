"""P2 — /price/deviation adalah komputasi murni: peran baca harus boleh memakainya.

Konteksnya nyata, bukan teoretis: worker Price milik agen berjalan dengan token
read-only (`bgn_monitor`). Endpoint ini hanya membaca satu baris harga referensi
lalu menghitung deviasi dengan fungsi murni `price_deviation()` — tidak menulis
apa pun. Menjaganya dengan `MUTATING_ROLES` membuat satu dari tujuh agen selalu
`degraded`, padahal tidak ada data yang dilindungi.

Tes ini menjaga dua hal sekaligus:
1. peran baca mendapat angka (200 + field lengkap),
2. memanggilnya TIDAK mengubah keadaan (ledger & keputusan tetap).
"""

import os
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DSN = DSN_SYNC
PW = "TestPass#2026"


def _mk_user(email: str, role: str, location: str | None) -> None:
    from bcrypt import gensalt, hashpw

    engine = create_engine(DSN)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
            loc_id = None
            if location:
                loc_id = conn.execute(
                    text("SELECT id FROM locations WHERE name = :n"), {"n": location}
                ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (gen_random_uuid(), 'Deviasi Baca', :e, :h, :r, :l)"
                ),
                {"e": email, "h": hashpw(PW.encode(), gensalt()).decode(), "r": role, "l": loc_id},
            )
    finally:
        engine.dispose()


def _hapus(email: str) -> None:
    engine = create_engine(DSN)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
    finally:
        engine.dispose()


def _hitung() -> tuple[int, int]:
    engine = create_engine(DSN)
    try:
        with engine.connect() as conn:
            blok = conn.execute(text("SELECT count(*) FROM ledger_blocks")).scalar_one()
            keputusan = conn.execute(text("SELECT count(*) FROM decisions")).scalar_one()
        return int(blok), int(keputusan)
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_monitor_boleh_menghitung_deviasi_tanpa_menulis(client):
    email = f"deviasi-{uuid.uuid4().hex[:8]}@test.local"
    _mk_user(email, "bgn_monitor", None)
    try:
        login = client.post("/auth/login", json={"email": email, "password": PW})
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        sebelum = _hitung()
        resp = client.post(
            "/price/deviation",
            json={"location": "Jakarta", "commodity": "telur", "supplier_price": 28000},
            headers=headers,
        )
        sesudah = _hitung()

        assert resp.status_code == 200, resp.text
        badan = resp.json()
        assert set(badan) == {"deviation_pct", "reference_price", "classification", "flagged"}
        assert float(badan["reference_price"]) > 0
        assert sebelum == sesudah, f"endpoint komputasi menulis data: {sebelum} → {sesudah}"
    finally:
        _hapus(email)


def test_monitor_tetap_ditolak_pada_mutasi_nyata(client):
    """Kontrol negatif: melonggarkan komputasi tidak boleh ikut melonggarkan tulis."""
    email = f"deviasi-{uuid.uuid4().hex[:8]}@test.local"
    _mk_user(email, "bgn_monitor", None)
    try:
        login = client.post("/auth/login", json={"email": email, "password": PW})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        resp = client.post(
            "/safety/evaluate",
            json={"batch_id": "00000000-0000-0000-0000-000000000000"},
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
    finally:
        _hapus(email)


def test_tanpa_token_tetap_401(client):
    resp = client.post(
        "/price/deviation",
        json={"location": "Jakarta", "commodity": "telur", "supplier_price": 28000},
    )
    assert resp.status_code == 401


def test_token_kedaluwarsa_ditolak(client):
    """Guard tetap memeriksa keaslian token, bukan hanya peran."""
    kedaluwarsa = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000000", "exp": 1_600_000_000},
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )
    resp = client.post(
        "/price/deviation",
        json={"location": "Jakarta", "commodity": "telur", "supplier_price": 28000},
        headers={"Authorization": f"Bearer {kedaluwarsa}"},
    )
    assert resp.status_code == 401
