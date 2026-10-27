"""Wiring gate keselamatan pada eksekusi (temuan A-01 / F-06).

`_source_batches_still_safe` dulu meloloskan eksekusi bila ADA satu batch yang
bukan `fail`, mengabaikan karantina/kedaluwarsa, dan mengembalikan `True` ketika
tidak menemukan batch sama sekali.

Percobaan pertama perbaikan (25 Okt 2026) terlalu jauh: "SEMUA batch harus
`pass`" atas seluruh batch lokasi+komoditas membuat satu batch `pending` yang
tak terkait memblokir eksekusi selamanya (seed kanonik: Jakarta/ayam
`['fail','pass']`) dan memutus paritas dengan `can_execute`.

Kontrak akhir: himpunan batch dari `batch_sumber_transfer`; blokir hanya pada
fakta keras (tidak ada batch, `fail`, karantina, kedaluwarsa); `pending` dan
`needs_verification` TIDAK memblokir karena itu keadaan normal sebelum
pengujian.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.api.actions import _source_batches_still_safe

SEKARANG = datetime.now(UTC)
LOG = [
    {"timestamp": (SEKARANG - timedelta(hours=2)).isoformat(), "temperature_c": 4.0},
    {"timestamp": (SEKARANG - timedelta(hours=1)).isoformat(), "temperature_c": 4.2},
]


@pytest.fixture(autouse=True)
def _transfer_palsu(monkeypatch):
    """Ganti `batch_sumber_transfer` (query DB) dengan himpunan yang diuji.

    `actions` mengimpor fungsi itu di dalam fungsi, jadi monkeypatch pada modul
    sumbernya benar-benar berlaku pada jalur yang dipanggil `execute_action`.
    Dengan begini test menguji KONTRAK gate, bukan perilaku fake session yang
    bisa menyimpang dari SQL sesungguhnya (kesalahan yang terjadi sebelumnya).
    """

    async def _transfer(_db, _decision):
        return list(_BATCH_AKTIF)

    monkeypatch.setattr(
        "app.services.supplier_eligibility.batch_sumber_transfer", _transfer
    )


_BATCH_AKTIF: list = []


class _SesiApaSaja:
    """Session tidak dipakai lagi sejak `batch_sumber_transfer` dipalsukan."""


def _batch(**ubah):
    dasar = {
        "id": "batch-1",
        "safety_status": "pass",
        "quarantine_status": "none",
        "usable_until": SEKARANG + timedelta(hours=6),
        "temperature_log": LOG,
    }
    dasar.update(ubah)
    return SimpleNamespace(**dasar)


_DECISION = SimpleNamespace(
    id="decision-1", source_location_id="loc-1", commodity_id="com-1"
)


async def _nilai(batch):
    _BATCH_AKTIF[:] = list(batch)
    return await _source_batches_still_safe(_SesiApaSaja(), _DECISION)


@pytest.mark.asyncio
async def test_semua_batch_aman_meloloskan_eksekusi():
    assert await _nilai([_batch(), _batch()]) is True


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "needs_verification", "pass"])
async def test_status_belum_pass_tidak_memblokir_eksekusi(status):
    """Paritas dengan `can_execute`: hanya `fail` yang memblokir eksekusi."""
    assert await _nilai([_batch(), _batch(id="batch-2", safety_status=status)]) is True


@pytest.mark.asyncio
async def test_batch_fail_memblokir_eksekusi():
    assert await _nilai([_batch(), _batch(id="batch-2", safety_status="fail")]) is False


@pytest.mark.asyncio
async def test_batch_dikarantina_memblokir_eksekusi():
    assert await _nilai([_batch(), _batch(quarantine_status="quarantined")]) is False


@pytest.mark.asyncio
async def test_batch_kedaluwarsa_memblokir_eksekusi():
    assert await _nilai([_batch(usable_until=SEKARANG - timedelta(hours=1))]) is False


@pytest.mark.asyncio
async def test_bukti_suhu_tidak_lengkap_tidak_memblokir_di_eksekusi():
    """Kelengkapan bukti ditegakkan saat dispatch (batch masuk `ditahan`),
    bukan dengan menolak seluruh keputusan — kalau tidak, paritas UI↔API
    pecah lagi (`can_execute` hanya melihat `fail`)."""
    assert await _nilai([_batch(temperature_log=[])]) is True


@pytest.mark.asyncio
async def test_tanpa_batch_sumber_memblokir_eksekusi():
    """Tidak ada batch = tidak ada bukti; dulu fungsi ini mengembalikan True."""
    assert await _nilai([]) is False


@pytest.mark.asyncio
async def test_decision_tanpa_identitas_sumber_memblokir_eksekusi():
    """AUD-9B-29: sumber tak teridentifikasi = fail-closed.

    Dulu fungsi ini mengembalikan `True` untuk keputusan tanpa lokasi/komoditas
    sumber ("tidak direvalidasi"). Itu jalur "tidak dapat dibuktikan = boleh";
    jenis keputusan yang memang tidak punya batch sumber (price_anomaly,
    review_only) sudah dipagari lebih dulu di `execute_action`, jadi sikap
    konservatif di sini tidak memblokir alur sah mana pun.
    """
    decision = SimpleNamespace(id="d-2", source_location_id=None, commodity_id=None)
    _BATCH_AKTIF[:] = []
    assert await _source_batches_still_safe(_SesiApaSaja(), decision) is False
