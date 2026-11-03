"""Wiring sidik approval pada approve → eksekusi (Fase 4 MG butir 4).

Yang dikunci berkas ini:

1. Sidik dihitung dari bukti yang benar-benar mengikat keputusan: batch sumber,
   pemasok, kuantitas/biaya, profil komoditas (versinya), dan status evaluasi.
2. Saat eksekusi, sidik yang tersimpan dibandingkan dengan sidik yang dihitung
   ulang. Perbedaan menyebut ASPEK yang berubah, bukan pesan umum.
3. Keputusan yang disetujui sebelum sidik ada (data demo/seed) tidak dihukum:
   tidak ada sidik tersimpan → `None`, dan gate safety tetap berjalan.

Uji di sini berada di SEAM helper (bukan HTTP), sama seperti
`test_execute_safety_wiring.py`: nilainya adalah kontrak fungsi yang dipanggil
endpoint, tanpa perlu mem-POST data demo yang tidak bisa dibuat ulang.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api import actions
from app.core.commodity_policy import policy_for

SEKARANG = datetime.now(UTC)
LOG = [
    {"timestamp": (SEKARANG - timedelta(hours=2)).isoformat(), "temperature_c": 4.0},
    {"timestamp": (SEKARANG - timedelta(hours=1)).isoformat(), "temperature_c": 4.2},
]


class _Hasil:
    """Hasil query palsu yang melayani kedua bentuk pemakaian di `actions`."""

    def __init__(self, evidence, nama_komoditas):
        self._evidence = evidence
        self._nama = nama_komoditas

    def scalars(self):
        return self

    def first(self):
        return self._evidence

    def scalar_one_or_none(self):
        return self._nama


class _Db:
    """Session palsu: cukup untuk query komoditas dan evidence terakhir."""

    def __init__(self, evidence=None, nama_komoditas="telur"):
        self._evidence = evidence
        self._nama = nama_komoditas

    async def execute(self, _stmt):
        return _Hasil(self._evidence, self._nama)


def _batch(batch_id=None):
    return SimpleNamespace(
        id=batch_id or uuid.uuid4(),
        safety_status="pass",
        quarantine_status="none",
        usable_until=SEKARANG + timedelta(hours=6),
        temperature_log=LOG,
    )


def _decision():
    return SimpleNamespace(
        id=uuid.uuid4(),
        decision_type="logistics_transfer",
        source_location_id=uuid.uuid4(),
        target_location_id=uuid.uuid4(),
        supplier_id=uuid.uuid4(),
        commodity_id=uuid.uuid4(),
        quantity_kg=Decimal("500"),
        safe_delivered_cost=Decimal("15000000"),
    )


@pytest.fixture
def pasang(monkeypatch):
    """Pasang batch/profil/alasan blokir yang bisa diubah tiap tes."""
    state = {"batches": [_batch()], "alasan": None, "policy_version": None}

    async def _transfer(_db, _decision):
        return list(state["batches"])

    async def _blokir(_db, _decision):
        return state["alasan"]

    async def _profil(_db):
        pol = policy_for("telur")
        if state["policy_version"]:
            pol = pol.__class__(**{**pol.__dict__, "policy_version": state["policy_version"]})
        return {("telur",): (pol, "db"), "telur": (pol, "db")}

    monkeypatch.setattr(
        "app.services.supplier_eligibility.batch_sumber_transfer", _transfer
    )
    monkeypatch.setattr(actions, "_source_batches_block_reason", _blokir)
    monkeypatch.setattr("app.core.policy_store.baca_semua_profil", _profil)
    return state


async def _sidik(db=None, decision=None):
    return await actions._sidik_bukti(db or _Db(), decision or _decision())


def test_sidik_usable_memuat_batch_dan_status(pasang):
    import asyncio

    sidik = asyncio.run(_sidik())
    assert sidik["evaluation_status"] == "usable"
    assert sidik["blocking_reasons"] == []
    assert len(sidik["batch_ids"]) == 1
    assert sidik["fingerprint"].startswith("sha256:")


def test_sidik_on_hold_membawa_alasan(pasang):
    import asyncio

    pasang["alasan"] = "safety_pending"
    sidik = asyncio.run(_sidik())
    assert sidik["evaluation_status"] == "on_hold"
    assert sidik["blocking_reasons"] == ["safety_pending"]


def test_tanpa_approval_tersimpan_tidak_menghukum_data_lama(pasang):
    import asyncio

    assert asyncio.run(actions._sidik_berubah(_Db(evidence=None), _decision())) is None


def test_sidik_sama_tidak_memblokir_eksekusi(pasang):
    import asyncio

    decision = _decision()
    tersimpan = asyncio.run(_sidik(_Db(), decision))
    evidence = SimpleNamespace(payload=tersimpan)
    assert (
        asyncio.run(actions._sidik_berubah(_Db(evidence=evidence), decision)) is None
    )


def test_batch_berganti_setelah_approval_disebut_sebagai_sebab(pasang):
    import asyncio

    decision = _decision()
    tersimpan = asyncio.run(_sidik(_Db(), decision))
    evidence = SimpleNamespace(payload=tersimpan)
    pasang["batches"] = [_batch(), _batch()]

    sebab = asyncio.run(actions._sidik_berubah(_Db(evidence=evidence), decision))
    assert sebab == "batch sumber"


def test_status_bukti_berubah_setelah_approval_disebut(pasang):
    import asyncio

    decision = _decision()
    tersimpan = asyncio.run(_sidik(_Db(), decision))
    evidence = SimpleNamespace(payload=tersimpan)
    pasang["alasan"] = "safety_pending"

    sebab = asyncio.run(actions._sidik_berubah(_Db(evidence=evidence), decision))
    assert "status bukti" in sebab


def test_profil_komoditas_berversi_baru_disebut(pasang):
    import asyncio

    decision = _decision()
    tersimpan = asyncio.run(_sidik(_Db(), decision))
    evidence = SimpleNamespace(payload=tersimpan)
    pasang["policy_version"] = "telur-2099.1"

    sebab = asyncio.run(actions._sidik_berubah(_Db(evidence=evidence), decision))
    assert "profil komoditas" in sebab
