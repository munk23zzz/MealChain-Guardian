"""Validasi angka rekomendasi di `POST /decisions` (temuan F-09 / A-02).

Sebelum perbaikan 25 Oktober 2026: `quantity_kg` negatif tetap tersimpan
(`201`), dan nilai bukan angka (`"abc"`) meledak menjadi HTTP 500
`decimal.InvalidOperation`. Keduanya harus menjadi penolakan 422 yang jelas,
karena angka itu kelak dipakai untuk menerbitkan purchase order.
"""

from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.test_actions import RECOMMENDATION


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _kirim(client, headers, **ubah):
    rec = copy.deepcopy(RECOMMENDATION)
    kandidat = rec.setdefault("candidate", {})
    for kunci, nilai in ubah.items():
        if kunci in {"quantity_kg", "commodity", "source_location", "destination_location"}:
            kandidat[kunci] = nilai
        else:
            rec[kunci] = nilai
    return client.post("/decisions", json={"recommendation": rec}, headers=headers)


@pytest.mark.parametrize(
    "qty",
    [-5, 0, "abc", 10**9],
    ids=["negatif", "nol", "bukan-angka", "kelebihan"],
)
def test_kuantitas_tidak_sah_ditolak_422(client, auth_headers, qty):
    resp = _kirim(client, auth_headers, quantity_kg=qty)
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize("biaya", [-1, 0, "bukan-angka"], ids=["negatif", "nol", "bukan-angka"])
def test_biaya_tidak_sah_ditolak_422(client, auth_headers, biaya):
    resp = _kirim(client, auth_headers, safe_delivered_cost=biaya)
    assert resp.status_code == 422, resp.text


def test_harga_satuan_tidak_wajar_ditolak_422(client, auth_headers):
    # 100 kg dengan biaya Rp 1 miliar → Rp 10 juta/kg, tidak wajar untuk pangan.
    resp = _kirim(client, auth_headers, quantity_kg=100, safe_delivered_cost=1_000_000_000)
    assert resp.status_code == 422, resp.text


def test_rincian_biaya_tidak_cocok_ditolak_422(client, auth_headers):
    resp = _kirim(
        client,
        auth_headers,
        cost_breakdown={
            "commodity_cost": 1000,
            "logistics_cost": 500,
            "other_cost": 0,
            "total": 999_999,
        },
    )
    assert resp.status_code == 422, resp.text
