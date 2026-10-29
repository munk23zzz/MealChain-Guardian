"""Anggaran panggilan model peramalan: cache, batas per menit, circuit breaker.

Alasan: setiap panggilan ke SAP AI Core adalah inferensi berbayar. Satu halaman
dashboard tidak boleh memicu puluhan panggilan, dan AI Core yang sedang mati
tidak boleh terus dihubungi.
"""

from __future__ import annotations

import json
import uuid
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import forecast_service as fs

LOKASI = uuid.UUID("33333333-3333-3333-3333-333333333333")
KOMODITAS = uuid.UUID("44444444-4444-4444-4444-444444444444")
HISTORY = [50.0 + i for i in range(10)]
JAWABAN = json.dumps({"forecast_qty_kg": 500.0, "confidence": 0.8})


class _Scalars:
    def __init__(self, nilai):
        self._nilai = nilai

    def scalars(self):
        return self

    def all(self):
        return self._nilai


class _Db:
    def __init__(self, nilai=None):
        self.nilai = HISTORY if nilai is None else nilai

    async def execute(self, *_a, **_k):
        return _Scalars(self.nilai)


class _Pemanggil:
    def __init__(self, jawaban: str | Exception = JAWABAN):
        self.jawaban = jawaban
        self.n = 0

    def __call__(self, _prompt: str) -> str:
        self.n += 1
        if isinstance(self.jawaban, Exception):
            raise self.jawaban
        return self.jawaban


@pytest.fixture(autouse=True)
def _bersih():
    fs.reset_state()
    yield
    fs.reset_state()


async def _jalan(caller, *, horizon=7, db=None, pakai_cache=True):
    return await fs.forecast_kebutuhan(
        db=cast(AsyncSession, db or _Db()),
        location_id=LOKASI,
        commodity_id=KOMODITAS,
        horizon_days=horizon,
        caller=caller,
        pakai_cache=pakai_cache,
    )


@pytest.mark.asyncio
async def test_permintaan_berulang_dilayani_dari_cache(monkeypatch):
    monkeypatch.setenv("FORECAST_CACHE_TTL_SECONDS", "900")
    monkeypatch.setenv("FORECAST_MAX_CALLS_PER_MINUTE", "0")
    pemanggil = _Pemanggil()

    pertama = await _jalan(pemanggil)
    kedua = await _jalan(pemanggil)

    assert pemanggil.n == 1, "permintaan kedua tidak boleh memanggil model"
    assert pertama.cache_hit is False
    assert kedua.cache_hit is True
    assert kedua.qty_kg == pertama.qty_kg


@pytest.mark.asyncio
async def test_horizon_berbeda_tidak_saling_menimpa_cache(monkeypatch):
    monkeypatch.setenv("FORECAST_CACHE_TTL_SECONDS", "900")
    monkeypatch.setenv("FORECAST_MAX_CALLS_PER_MINUTE", "0")
    pemanggil = _Pemanggil()

    await _jalan(pemanggil, horizon=7)
    await _jalan(pemanggil, horizon=14)

    assert pemanggil.n == 2, "horizon adalah bagian kunci cache"


@pytest.mark.asyncio
async def test_ttl_nol_mematikan_cache(monkeypatch):
    monkeypatch.setenv("FORECAST_CACHE_TTL_SECONDS", "0")
    monkeypatch.setenv("FORECAST_MAX_CALLS_PER_MINUTE", "0")
    pemanggil = _Pemanggil()

    await _jalan(pemanggil)
    await _jalan(pemanggil)

    assert pemanggil.n == 2


@pytest.mark.asyncio
async def test_batas_per_menit_tidak_menyentuh_jaringan(monkeypatch):
    monkeypatch.setenv("FORECAST_CACHE_TTL_SECONDS", "0")
    monkeypatch.setenv("FORECAST_MAX_CALLS_PER_MINUTE", "1")
    pemanggil = _Pemanggil()

    pertama = await _jalan(pemanggil)
    kedua = await _jalan(pemanggil)

    assert pemanggil.n == 1
    assert pertama.source == fs.SUMBER_MODEL
    assert kedua.source == fs.SUMBER_CADANGAN
    assert kedua.reason and "per menit" in kedua.reason


@pytest.mark.asyncio
async def test_breaker_membuka_setelah_kegagalan_berulang(monkeypatch):
    monkeypatch.setenv("FORECAST_CACHE_TTL_SECONDS", "0")
    monkeypatch.setenv("FORECAST_MAX_CALLS_PER_MINUTE", "0")
    monkeypatch.setenv("FORECAST_BREAKER_FAILS", "5")
    monkeypatch.setenv("FORECAST_BREAKER_SECONDS", "300")
    pemanggil = _Pemanggil(RuntimeError("AI Core mati"))

    for _ in range(5):
        await _jalan(pemanggil)
    assert pemanggil.n == 5

    keenam = await _jalan(pemanggil)

    assert pemanggil.n == 5, "breaker terbuka: tidak boleh ada panggilan baru"
    assert keenam.source == fs.SUMBER_CADANGAN
    assert keenam.reason and "circuit breaker" in keenam.reason


@pytest.mark.asyncio
async def test_breaker_menutup_setelah_jendela_lewat(monkeypatch):
    monkeypatch.setenv("FORECAST_CACHE_TTL_SECONDS", "0")
    monkeypatch.setenv("FORECAST_MAX_CALLS_PER_MINUTE", "0")
    monkeypatch.setenv("FORECAST_BREAKER_FAILS", "1")
    monkeypatch.setenv("FORECAST_BREAKER_SECONDS", "0")  # langsung kedaluwarsa
    pemanggil = _Pemanggil(RuntimeError("sekali gagal"))

    await _jalan(pemanggil)
    await _jalan(pemanggil)

    assert pemanggil.n == 2, "jendela 0 detik = breaker tidak menahan panggilan"


@pytest.mark.asyncio
async def test_penghitung_proses_terisi():
    await _jalan(_Pemanggil())

    angka = fs.statistik()
    assert angka["forecast_calls_total"] == 1
    assert angka["forecast_fallback_total"] == 0


@pytest.mark.asyncio
async def test_kegagalan_dihitung_sebagai_cadangan():
    await _jalan(_Pemanggil(RuntimeError("gagal")))

    angka = fs.statistik()
    assert angka["forecast_calls_total"] == 1
    assert angka["forecast_fallback_total"] == 1
