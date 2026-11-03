"""Gerbang `DEMO_MODE` pada namespace `/demo` (Fase 12 MG butir 4).

Kontrak yang dikunci di sini — satu kalimat: **`DEMO_MODE=False` menutup
namespace `/demo` dengan 404, bukan menyembunyikan tombol.**

Alasan bentuk tes ini:

1. Operasional tidak boleh punya jalan pintas ke seed demo. Kalau `POST
   /demo/seed` masih menjawab 200/409 di mode operasional, "tidak ada baris demo
   baru" hanyalah janji UI — dan UI bukan penjaga.
2. Jawabannya **404**, bukan 403/409: rute demo tidak diakui sebagai bagian
   aplikasi operasional (sama seperti `/demo/agent/run` yang di rencana disebut
   sebagai contoh). Kode 409 milik pagar sesi (`DEMO_SESSION_ENFORCE`), jadi
   memakai 404 membuat kedua pagar bisa dibedakan dari luar.
3. Gerbang ini **tidak** boleh bergantung pada sesi: 404 harus keluar sebelum
   middleware sesi membuka DB, supaya aplikasi operasional tanpa tabel demo tetap
   menjawab 404, bukan 500.

Berkas ini hanya membaca status code; ia tidak menulis baris apa pun, jadi aman
dijalankan pada DB mana pun yang sudah di-migrasi.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

#: Jalur demo yang disebut rencana + dua jalur baca yang dipakai panel.
JALUR_TULIS = (
    "/demo/seed",
    "/demo/agent/run",
    "/demo/session/start",
    "/demo/session/extend",
    "/demo/session/end",
    "/demo/template/rebuild",
)
JALUR_BACA = ("/demo/session", "/demo/data-status", "/demo/agent/last-run")


@pytest.fixture()
def klien():
    with TestClient(app) as c:
        yield c


def test_mode_operasional_menutup_seluruh_jalur_demo(monkeypatch, klien):
    """`DEMO_MODE=False` → setiap jalur `/demo` menjawab 404."""
    monkeypatch.setattr(settings, "demo_mode", False)

    for jalur in JALUR_TULIS:
        r = klien.post(jalur, json={})
        assert r.status_code == 404, (jalur, r.status_code, r.text)
        assert r.json() == {"detail": "Not Found"}, (jalur, r.text)

    for jalur in JALUR_BACA:
        r = klien.get(jalur)
        assert r.status_code == 404, (jalur, r.status_code, r.text)


def test_mode_demo_membuka_jalur_demo(monkeypatch, klien):
    """`DEMO_MODE=True` → jalur demo TIDAK 404 (pagar lain yang menjawab).

    Yang dibuktikan hanya arah gerbangnya: dengan mode demo menyala, jalur ini
    sampai ke routing/pagar sesi. Status yang sah bisa 401/409/422 — bukan 404.
    """
    monkeypatch.setattr(settings, "demo_mode", True)

    for jalur in JALUR_TULIS:
        r = klien.post(jalur, json={})
        assert r.status_code != 404, (jalur, r.status_code, r.text)


def test_gerbang_tidak_menutup_jalur_lain(monkeypatch, klien):
    """Mode operasional tidak boleh ikut menutup `/health` atau `/decisions`."""
    monkeypatch.setattr(settings, "demo_mode", False)

    assert klien.get("/health").status_code == 200
    # Tanpa token: 401/403. Yang penting bukan 404.
    assert klien.get("/decisions").status_code != 404
