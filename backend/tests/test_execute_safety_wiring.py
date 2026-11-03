"""Wiring gate keselamatan pada eksekusi (temuan A-01 / F-06).

`_source_batches_still_safe` dulu meloloskan eksekusi bila ADA satu batch yang
bukan `fail`, mengabaikan karantina/kedaluwarsa, dan mengembalikan `True` ketika
tidak menemukan batch sama sekali.

Percobaan pertama perbaikan (25 Okt 2026) terlalu jauh: "SEMUA batch harus
`pass`" atas seluruh batch lokasi+komoditas membuat satu batch `pending` yang
tak terkait memblokir eksekusi selamanya (seed kanonik: Jakarta/ayam
`['fail','pass']`) dan memutus paritas dengan `can_execute`.

Kontrak akhir (MG/phase-04-safety-gates.md poin 1-4): himpunan batch dari
`batch_sumber_transfer`, dievaluasi oleh SATU evaluator
(`app.core.batch_eligibility`). Hanya batch `usable` yang meloloskan eksekusi;
`pending` dan `needs_verification` adalah `on_hold` — boleh dilaporkan untuk
verifikasi, tetapi tidak boleh dieksekusi atau menjadi stok `usable`.
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
@pytest.mark.parametrize("status", ["pending", "needs_verification"])
async def test_status_belum_pass_memblokir_eksekusi(status):
    """Fase 4: batch yang belum terbukti aman TIDAK boleh dieksekusi.

    Sebelum Fase 4 kedua status ini lolos (paritas dengan `can_execute` lama
    yang hanya melihat `fail`) — itulah celah yang ditutup di sini.
    """
    assert await _nilai([_batch(), _batch(id="batch-2", safety_status=status)]) is False


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
async def test_bukti_suhu_tidak_lengkap_memblokir_eksekusi():
    """Log kurang dari dua sampel = `on_hold`, bukan `pass` (poin 1 Fase 4)."""
    assert await _nilai([_batch(temperature_log=[])]) is False


@pytest.mark.asyncio
async def test_usable_until_kosong_memblokir_eksekusi():
    """Tidak ada provenance masa layak = tidak dapat dibuktikan layak."""
    assert await _nilai([_batch(usable_until=None)]) is False


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
