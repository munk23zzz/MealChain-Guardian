"""Akun demo: daftar + penjagaan akses (26 Okt 2026).

Latar: endpoint `GET /auth/demo-accounts` mengembalikan KREDENSIAL (email +
sandi yang berlaku). Sejak 26 Okt ia menuntut Bearer token ber-peran admin;
skema tidak punya peran `admin` (Schema.md §1), jadi penjaganya mengikuti pola
`/admin/*`: `require_roles("bgn_monitor")` — lihat `app/core/admin_rules.py`.
Halaman login publik tidak lagi memanggilnya (daftar tanpa sandi ada di
`frontend/lib/demo-accounts.ts`).

Kontrak yang dikunci berkas ini:

1. tanpa token                                    → 401 (tidak ada kebocoran),
2. token non-admin (sppg_head)                    → 403,
3. token admin (bgn_monitor) + `DEMO_MODE` aktif  → 200, email + sandi benar,
4. token admin + `DEMO_MODE` mati                 → 200, `{enabled:false, accounts:[]}`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_credentials import resolve_demo_password


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_tanpa_token_401(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    r = client.get("/auth/demo-accounts")

    assert r.status_code == 401
    assert "Demo#" not in r.text


def test_token_non_admin_403(client, auth_headers, monkeypatch):
    """`sppg_head` bukan pengelola pengguna/kredensial — 403, bukan 200."""
    monkeypatch.setenv("DEMO_MODE", "true")

    r = client.get("/auth/demo-accounts", headers=auth_headers)

    assert r.status_code == 403, r.text
    assert "Demo#" not in r.text


def test_admin_demo_mode_aktif_mengirim_email_dan_sandi_yang_benar(
    client, monitor_headers, monkeypatch
):
    monkeypatch.setenv("DEMO_MODE", "true")

    r = client.get("/auth/demo-accounts", headers=monitor_headers)

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["enabled"] is True
    akun = data["accounts"]
    assert len(akun) >= 7  # 3 peran utama + 4 approver kota

    for baris in akun:
        assert baris["email"].endswith("@demo.local")
        assert baris["label"]
        assert baris["role"] in {"sppg_head", "sppg_nutritionist", "bgn_monitor"}
        # Sandi yang dikirim HARUS sama dengan yang dipakai seed/login.
        assert baris["password"] == resolve_demo_password(baris["role"])

    email = {a["email"] for a in akun}
    assert {
        "sppg.head@demo.local",
        "sppg.nutritionist@demo.local",
        "bgn.monitor@demo.local",
    } <= email
    assert {"sppg.head.bandung@demo.local", "sppg.nutritionist.surabaya@demo.local"} <= email


def test_admin_demo_mode_mati_tidak_membocorkan_sandi(client, monitor_headers, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")

    r = client.get("/auth/demo-accounts", headers=monitor_headers)

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["enabled"] is False
    assert data["accounts"] == []
    assert "Demo#" not in r.text


def test_admin_tanpa_demo_mode_env_tetap_tidak_membocorkan_sandi(
    client, monitor_headers, monkeypatch
):
    monkeypatch.delenv("DEMO_MODE", raising=False)

    r = client.get("/auth/demo-accounts", headers=monitor_headers)

    assert r.status_code == 200, r.text
    assert r.json()["accounts"] == []
    assert "Demo#" not in r.text


# --- Jalur layar login (27 Okt 2026) -------------------------------------------------
# Halaman login publik tidak punya token, jadi ia butuh pintu sendiri. Pintu itu
# `GET /auth/demo-login`, dan hanya terbuka bila DUA kunci aktif: `DEMO_MODE` dan
# `DEMO_LOGIN_AUTOFILL`. Satu kunci saja tidak cukup.


def test_login_tanpa_flag_autofill_tidak_mengirim_sandi(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.delenv("DEMO_LOGIN_AUTOFILL", raising=False)

    r = client.get("/auth/demo-login")

    assert r.status_code == 200, r.text
    assert r.json() == {"enabled": False, "accounts": []}
    assert "Demo#" not in r.text


def test_login_flag_aktif_dan_demo_mode_mengirim_sandi_tanpa_token(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_LOGIN_AUTOFILL", "true")

    r = client.get("/auth/demo-login")

    assert r.status_code == 200, r.text  # tanpa Bearer token
    data = r.json()
    assert data["enabled"] is True
    akun = data["accounts"]
    assert len(akun) >= 7
    for baris in akun:
        assert baris["password"] == resolve_demo_password(baris["role"])


def test_login_flag_aktif_tanpa_demo_mode_tetap_tertutup(client, monkeypatch):
    """Flag autofill tidak boleh membuka kunci sendiri saat DEMO_MODE mati."""
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("DEMO_LOGIN_AUTOFILL", "true")

    r = client.get("/auth/demo-login")

    assert r.status_code == 200, r.text
    assert r.json() == {"enabled": False, "accounts": []}
    assert "Demo#" not in r.text


# --- Kunci ketiga: pemanggil harus LOKAL (audit 2026-10-29, AUD-005) ----------------
# Dua flag hanya menyatakan "demo mengizinkan autofill", bukan "siapa yang boleh
# bertanya". Endpoint tanpa token + publish 0.0.0.0:8000 = sandi terbaca dari LAN.


class _Req:
    """Request palsu: hanya `.client.host` yang dibaca helper."""

    class _C:
        def __init__(self, host: str) -> None:
            self.host = host

    def __init__(self, host: str | None) -> None:
        self.client = self._C(host) if host is not None else None


def test_autofill_dari_host_remote_ditolak(monkeypatch):
    from app.api.auth import boleh_autofill_dari

    monkeypatch.delenv("DEMO_LOGIN_ALLOW_REMOTE", raising=False)

    assert boleh_autofill_dari(_Req("192.168.1.20")) is False
    assert boleh_autofill_dari(_Req("10.0.0.7")) is False
    assert boleh_autofill_dari(_Req(None)) is False


def test_autofill_dari_host_lokal_diizinkan(monkeypatch):
    from app.api.auth import boleh_autofill_dari

    monkeypatch.delenv("DEMO_LOGIN_ALLOW_REMOTE", raising=False)

    assert boleh_autofill_dari(_Req("127.0.0.1")) is True
    assert boleh_autofill_dari(_Req("::1")) is True
    assert boleh_autofill_dari(_Req("testclient")) is True


def test_autofill_remote_butuh_override_eksplisit(monkeypatch):
    from app.api.auth import boleh_autofill_dari

    monkeypatch.setenv("DEMO_LOGIN_ALLOW_REMOTE", "true")

    assert boleh_autofill_dari(_Req("192.168.1.20")) is True

    monkeypatch.setenv("DEMO_LOGIN_ALLOW_REMOTE", "false")
    assert boleh_autofill_dari(_Req("192.168.1.20")) is False


def test_autofill_gateway_container_diizinkan(monkeypatch):
    """Browser demo di host masuk lewat gateway bridge, bukan 127.0.0.1.

    Kalau ini salah, tombol akun demo di layar login mati saat demo dijalankan
    dari laptop (terukur: container melihat `172.20.0.1`).
    """
    from app.api.auth import _ip_gateway, boleh_autofill_dari

    monkeypatch.delenv("DEMO_LOGIN_ALLOW_REMOTE", raising=False)
    gateway = _ip_gateway()
    if gateway is None:  # host non-Linux: tidak ada /proc/net/route
        return

    assert boleh_autofill_dari(_Req(gateway)) is True
    # Tetangga di subnet yang sama TIDAK otomatis diizinkan.
    assert boleh_autofill_dari(_Req("192.168.1.20")) is False
