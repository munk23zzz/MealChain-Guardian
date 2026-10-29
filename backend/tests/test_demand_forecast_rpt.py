"""Kontrak peramalan: SAP-RPT-1.6 → cadangan statistik (satu pintu).

Menguji `app.services.forecast_service.forecast_kebutuhan` tanpa database nyata:
sesi DB diganti stub yang hanya mengembalikan deret riwayat. Yang dikunci:

1. RPT menghasilkan angka → `source="SAP-RPT-1.6"`, dibulatkan 2 desimal.
2. Balasan sampah / tanpa angka / pemanggil melempar → cadangan statistik,
   label jujur, alasan ikut dikembalikan.
3. Riwayat di bawah ambang minimum → model TIDAK dipanggil.
4. Tanpa pemanggil terkonfigurasi → statistik, tanpa klaim SAP.
5. Riwayat kosong → `qty_kg=None` (bukan 0), dengan alasan.

Versi sebelumnya menguji `api.demand.susun_forecast`; fungsi itu sudah dihapus
karena seluruh pemanggilan model kini lewat `services/forecast_service`.
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.services import forecast_service as fs

LOKASI = uuid.UUID("11111111-1111-1111-1111-111111111111")
KOMODITAS = uuid.UUID("22222222-2222-2222-2222-222222222222")
HISTORY = [100.0 + i for i in range(14)]


class _Scalars:
    def __init__(self, nilai: list[float]) -> None:
        self._nilai = nilai

    def scalars(self) -> _Scalars:
        return self

    def all(self) -> list[float]:
        return self._nilai


class _Db:
    """Stub AsyncSession: `execute(select(...))` → deret riwayat.

    Query asli memakai `ORDER BY recorded_at DESC`, jadi stub ini membalik deret
    kronologis yang diberikan supaya layanan (yang membaliknya kembali) menerima
    urutan lama → baru seperti di produksi.
    """

    def __init__(self, nilai: list[float]) -> None:
        self.nilai = list(reversed(nilai))
        self.dipanggil = 0

    async def execute(self, *_args, **_kwargs) -> _Scalars:
        self.dipanggil += 1
        return _Scalars(self.nilai)


class _Pemanggil:
    def __init__(self, jawaban: str | Exception) -> None:
        self.jawaban = jawaban
        self.n = 0
        self.prompt: str | None = None

    def __call__(self, prompt: str) -> str:
        self.n += 1
        self.prompt = prompt
        if isinstance(self.jawaban, Exception):
            raise self.jawaban
        return self.jawaban


@pytest.fixture(autouse=True)
def _bersih(monkeypatch):
    fs.reset_state()
    monkeypatch.setenv("FORECAST_CACHE_TTL_SECONDS", "0")
    monkeypatch.setenv("FORECAST_MAX_CALLS_PER_MINUTE", "0")
    monkeypatch.setenv("FORECAST_BREAKER_FAILS", "0")
    yield
    fs.reset_state()


async def _jalan(db, *, caller, horizon=7):
    return await fs.forecast_kebutuhan(
        db,
        location_id=LOKASI,
        commodity_id=KOMODITAS,
        horizon_days=horizon,
        caller=caller,
    )


@pytest.mark.asyncio
async def test_rpt_menghasilkan_angka_dilabeli_dan_dibulatkan():
    pemanggil = _Pemanggil(json.dumps({"forecast_qty_kg": 812.5678, "confidence": 0.71}))

    hasil = await _jalan(_Db(HISTORY), caller=pemanggil)

    assert hasil.source == fs.SUMBER_MODEL
    assert hasil.method == "sap_rpt_1_6"
    assert hasil.fallback_used is False
    assert hasil.qty_kg == 812.57  # 2 desimal, HALF_UP
    assert hasil.confidence == 0.71
    assert hasil.sample_count == len(HISTORY)
    prompt = json.loads(pemanggil.prompt or "{}")
    assert prompt["history_daily_kg"] == HISTORY
    assert prompt["horizon_days"] == 7


@pytest.mark.asyncio
async def test_balasan_sampah_turun_ke_cadangan():
    hasil = await _jalan(_Db(HISTORY), caller=_Pemanggil("maaf tidak bisa"))

    assert hasil.source == fs.SUMBER_CADANGAN
    assert hasil.fallback_used is True
    assert hasil.qty_kg is not None and hasil.qty_kg > 0
    assert hasil.reason and "gagal" in hasil.reason


@pytest.mark.asyncio
async def test_balasan_tanpa_angka_tidak_ditaksir():
    hasil = await _jalan(_Db(HISTORY), caller=_Pemanggil(json.dumps({"catatan": "kosong"})))

    assert hasil.source == fs.SUMBER_CADANGAN
    assert hasil.qty_kg is not None  # dari statistik, bukan angka karangan model


@pytest.mark.asyncio
async def test_pemanggil_melempar_turun_ke_cadangan():
    hasil = await _jalan(_Db(HISTORY), caller=_Pemanggil(RuntimeError("AI Core 503")))

    assert hasil.source == fs.SUMBER_CADANGAN
    assert hasil.fallback_used is True


@pytest.mark.asyncio
async def test_riwayat_di_bawah_ambang_model_tidak_dipanggil():
    pemanggil = _Pemanggil(json.dumps({"forecast_qty_kg": 999}))

    hasil = await _jalan(_Db([10.0, 11.0, 12.0]), caller=pemanggil)

    assert pemanggil.n == 0, "model tidak boleh dipanggil untuk riwayat tipis"
    assert hasil.source == fs.SUMBER_CADANGAN
    assert hasil.reason and "kurang dari" in hasil.reason


@pytest.mark.asyncio
async def test_tanpa_pemanggil_tetap_statistik():
    hasil = await _jalan(_Db(HISTORY), caller=None)

    assert hasil.source == fs.SUMBER_CADANGAN
    assert hasil.fallback_used is True
    assert hasil.reason and "tidak dikonfigurasi" in hasil.reason


@pytest.mark.asyncio
async def test_riwayat_kosong_mengembalikan_none_bukan_nol():
    hasil = await _jalan(_Db([]), caller=None)

    assert hasil.qty_kg is None
    assert hasil.source == fs.SUMBER_CADANGAN
    assert hasil.reason


@pytest.mark.asyncio
async def test_rem_darurat_mematikan_model_meski_pemanggil_ada(monkeypatch):
    """`FORECAST_PROVIDER=statistical` harus menang atas pemanggil yang terbangun.

    Tanpa ini, rem biaya bisa dilewati jalur yang sudah memegang klien RPT —
    tepat pada situasi darurat ketika rem itu paling dibutuhkan.
    """
    monkeypatch.setenv("FORECAST_PROVIDER", "statistical")
    pemanggil = _Pemanggil(json.dumps({"forecast_qty_kg": 999}))

    hasil = await _jalan(_Db(HISTORY), caller=pemanggil)

    assert pemanggil.n == 0, "model tidak boleh dipanggil saat rem darurat aktif"
    assert hasil.source == fs.SUMBER_CADANGAN
    assert hasil.reason and "FORECAST_PROVIDER" in hasil.reason
