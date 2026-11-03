"""SEC-02 & SEC-03 (audit 24 Okt 2026): umur token dan pembatas login.

Dua lubang yang ditutup:

SEC-02 — `JWT_EXPIRE_MINUTES` di `.env` bernilai 5.256.000 menit (±10 tahun),
sehingga token yang bocor berlaku praktis selamanya. Sekarang nilai itu dijepit
ke 5..1440 menit, dan tes ini mengunci perilaku tersebut (termasuk untuk `.env`
lama yang masih berisi angka raksasa).

SEC-03 — `/auth/login` tidak punya pembatas percobaan. Sekarang percobaan GAGAL
dibatasi per (IP, email); login berhasil menghapus riwayat kunci itu.
"""

import os
import time

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.core import rate_limit
from app.main import app

EMAIL = "tidak.ada@demo.local"  # pasti tidak ada di DB → jalur 401
SALAH = "BukanPassword#1"


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _bersihkan():
    rate_limit.reset_semua()
    yield
    rate_limit.reset_semua()


def _claims(token: str) -> dict:
    return pyjwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])


def _login_benar(client: TestClient) -> dict:
    resp = client.post(
        "/auth/login",
        json={"email": "bgn.monitor@demo.local", "password": "Demo#BGN2026"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_umur_token_mengikuti_env(client, monkeypatch):
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "720")
    body = _login_benar(client)
    claims = _claims(body["access_token"])
    assert claims["exp"] - claims["iat"] == 720 * 60
    assert body["expires_in"] == 720 * 60


def test_umur_token_dijepit_bila_env_raksasa(client, monkeypatch):
    # Nilai lama di .env (5.256.000 menit) tidak boleh berlaku apa adanya.
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "5256000")
    body = _login_benar(client)
    claims = _claims(body["access_token"])
    assert claims["exp"] - claims["iat"] == 1440 * 60


def test_umur_token_dijepit_bila_env_terlalu_kecil(client, monkeypatch):
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "0")
    body = _login_benar(client)
    claims = _claims(body["access_token"])
    assert claims["exp"] - claims["iat"] == 5 * 60


def test_umur_token_env_sampah_diabaikan(client, monkeypatch):
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "bukan-angka")
    body = _login_benar(client)
    claims = _claims(body["access_token"])
    assert claims["exp"] - claims["iat"] == 30 * 60


def test_login_dibatasi_setelah_beberapa_kegagalan(client, monkeypatch):
    monkeypatch.setenv("LOGIN_RATE_LIMIT", "3")
    monkeypatch.setenv("LOGIN_RATE_WINDOW", "60")

    for _ in range(3):
        resp = client.post("/auth/login", json={"email": EMAIL, "password": SALAH})
        assert resp.status_code == 401, resp.text

    keempat = client.post("/auth/login", json={"email": EMAIL, "password": SALAH})
    assert keempat.status_code == 429, keempat.text
    assert "Retry-After" in keempat.headers
    assert int(keempat.headers["Retry-After"]) >= 1
    # Pesan tidak boleh membocorkan apakah email terdaftar.
    assert "email atau password salah" not in keempat.text


def test_email_lain_tidak_ikut_terblokir(client, monkeypatch):
    monkeypatch.setenv("LOGIN_RATE_LIMIT", "1")
    monkeypatch.setenv("LOGIN_RATE_WINDOW", "60")

    assert (
        client.post("/auth/login", json={"email": EMAIL, "password": SALAH}).status_code
        == 401
    )
    assert (
        client.post("/auth/login", json={"email": EMAIL, "password": SALAH}).status_code
        == 429
    )
    lain = client.post(
        "/auth/login", json={"email": "lain@demo.local", "password": SALAH}
    )
    assert lain.status_code == 401, lain.text


def test_login_berhasil_menghapus_riwayat_gagal(client, monkeypatch):
    monkeypatch.setenv("LOGIN_RATE_LIMIT", "2")
    monkeypatch.setenv("LOGIN_RATE_WINDOW", "60")

    for _ in range(2):
        client.post(
            "/auth/login",
            json={"email": "bgn.monitor@demo.local", "password": SALAH},
        )
    # Dua kegagalan sudah mencapai batas → percobaan berikutnya ditahan.
    assert (
        client.post(
            "/auth/login",
            json={"email": "bgn.monitor@demo.local", "password": SALAH},
        ).status_code
        == 429
    )

    # Setelah riwayat dihapus (mis. login berhasil dari sesi lain), kunci bebas lagi.
    rate_limit.lupakan("login:testclient:bgn.monitor@demo.local")
    assert _login_benar(client)["access_token"]


def test_jendela_geser_membebaskan_kunci(client, monkeypatch):
    monkeypatch.setenv("LOGIN_RATE_LIMIT", "1")
    monkeypatch.setenv("LOGIN_RATE_WINDOW", "1")

    client.post("/auth/login", json={"email": EMAIL, "password": SALAH})
    assert (
        client.post("/auth/login", json={"email": EMAIL, "password": SALAH}).status_code
        == 429
    )
    time.sleep(1.1)
    assert (
        client.post("/auth/login", json={"email": EMAIL, "password": SALAH}).status_code
        == 401
    )
