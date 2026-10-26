"""Akun demo untuk layar login (26 Okt 2026).

Latar: sebelumnya tombol peran di layar login hanya mengisi email, dan kata sandi
diketik operator dari berkas lingkungan. Untuk demo, satu klik harus langsung siap
masuk — tanpa menaruh sandi di bundle frontend (yang bisa dibaca siapa pun).

Kontrak yang dikunci berkas ini:

1. `DEMO_MODE` aktif  → `GET /auth/demo-accounts` mengirim email + sandi yang benar,
   diambil dari satu sumber (`DEMO_PASSWORDS_JURI` lewat `resolve_demo_password`).
2. `DEMO_MODE` mati   → endpoint TIDAK mengirim satu pun sandi (dan tidak mengirim
   daftar akun), supaya instalasi non-demo tidak membocorkan kredensial.
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


def test_demo_mode_aktif_mengirim_email_dan_sandi_yang_benar(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    r = client.get("/auth/demo-accounts")

    assert r.status_code == 200
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


def test_demo_mode_mati_tidak_membocorkan_sandi(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")

    r = client.get("/auth/demo-accounts")

    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is False
    assert data["accounts"] == []
    assert "Demo#" not in r.text


def test_tanpa_demo_mode_env_tetap_tidak_membocorkan_sandi(client, monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)

    r = client.get("/auth/demo-accounts")

    assert r.json()["accounts"] == []
    assert "Demo#" not in r.text
