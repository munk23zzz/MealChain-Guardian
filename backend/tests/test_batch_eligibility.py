"""Tes kontrak evaluator kelayakan batch (Fase 4 MG poin 2).

Semua tes MURNI: tanpa DB, tanpa HTTP. Yang diuji adalah aturan, bukan wiring;
wiring diuji terpisah di `test_dispatch_safety_gate.py` dan
`test_receipt_quarantine.py`.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta

import pytest

from app.core import batch_eligibility as be

SEKARANG = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)


def batch(**ubah) -> dict:
    """Batch sehat bawaan; tiap tes mengubah SATU hal saja."""
    data = {
        "batch_id": "b1",
        "safety_status": "pass",
        "quarantine_status": "none",
        "usable_until": SEKARANG + timedelta(days=3),
        "freshness_status": "pass",
        "temperature_log": [
            {
                "timestamp": (SEKARANG - timedelta(hours=2)).isoformat(),
                "temperature_c": 4.0,
            },
            {
                "timestamp": (SEKARANG - timedelta(hours=1)).isoformat(),
                "temperature_c": 5.0,
            },
        ],
    }
    data.update(ubah)
    return data


def test_batch_sehat_dinyatakan_usable() -> None:
    hasil = be.evaluate_batch(batch(), be.POLICY_BAWAAN, SEKARANG)
    assert hasil.status == be.USABLE
    assert hasil.blocking_reasons == ()
    assert hasil.dispatchable is True
    assert hasil.policy_version == be.POLICY_BAWAAN.policy_version


def test_safety_pending_on_hold_bukan_lolos() -> None:
    hasil = be.evaluate_batch(batch(safety_status="pending"), be.POLICY_BAWAAN, SEKARANG)
    assert hasil.status == be.ON_HOLD
    assert hasil.code == be.SAFETY_PENDING
    assert hasil.dispatchable is False


def test_safety_needs_verification_on_hold() -> None:
    hasil = be.evaluate_batch(
        batch(safety_status="needs_verification"), be.POLICY_BAWAAN, SEKARANG
    )
    assert hasil.status == be.ON_HOLD
    assert be.SAFETY_NEEDS_VERIFICATION in hasil.blocking_reasons


def test_safety_fail_ditolak() -> None:
    hasil = be.evaluate_batch(batch(safety_status="fail"), be.POLICY_BAWAAN, SEKARANG)
    assert hasil.status == be.REJECTED
    assert hasil.code == be.SAFETY_FAIL


def test_status_safety_tak_dikenal_on_hold() -> None:
    hasil = be.evaluate_batch(batch(safety_status=""), be.POLICY_BAWAAN, SEKARANG)
    assert hasil.status == be.ON_HOLD
    assert hasil.code == be.SAFETY_STATUS_UNKNOWN


def test_batch_dikarantina_tidak_bisa_lolos() -> None:
    hasil = be.evaluate_batch(
        batch(quarantine_status="quarantined"), be.POLICY_BAWAAN, SEKARANG
    )
    assert hasil.status == be.QUARANTINED
    assert hasil.code == be.QUARANTINE_BLOCK


def test_batch_kedaluwarsa_ditolak() -> None:
    hasil = be.evaluate_batch(
        batch(usable_until=SEKARANG - timedelta(minutes=1)), be.POLICY_BAWAAN, SEKARANG
    )
    assert hasil.status == be.REJECTED
    assert hasil.code == be.BATCH_EXPIRED


def test_usable_until_kosong_bukan_berarti_aman() -> None:
    hasil = be.evaluate_batch(batch(usable_until=None), be.POLICY_BAWAAN, SEKARANG)
    assert hasil.status == be.REJECTED
    assert hasil.code == be.EXPIRY_UNKNOWN


def test_bukti_suhu_kurang_on_hold_bukan_pass() -> None:
    satu_sampel = [batch()["temperature_log"][0]]
    hasil = be.evaluate_batch(
        batch(temperature_log=satu_sampel), be.POLICY_BAWAAN, SEKARANG
    )
    assert hasil.status == be.ON_HOLD
    assert hasil.code == be.TEMPERATURE_INCOMPLETE


def test_tanpa_log_suhu_sama_dengan_bukti_hilang() -> None:
    hasil = be.evaluate_batch(batch(temperature_log=None), be.POLICY_BAWAAN, SEKARANG)
    assert hasil.status == be.REJECTED
    assert hasil.code == be.EVIDENCE_MISSING


def test_bukti_suhu_precomputed_dipakai_service() -> None:
    hasil = be.evaluate_batch(
        batch(temperature_log=None, temperature_evidence_complete=True),
        be.POLICY_BAWAAN,
        SEKARANG,
    )
    assert hasil.status == be.USABLE


def test_freshness_fail_ditolak() -> None:
    hasil = be.evaluate_batch(batch(freshness_status="fail"), be.POLICY_BAWAAN, SEKARANG)
    assert hasil.status == be.REJECTED
    assert hasil.code == be.FRESHNESS_FAIL


def test_kedaluwarsa_sebelum_tiba_ditolak() -> None:
    tiba = SEKARANG + timedelta(days=4)
    hasil = be.evaluate_batch(
        batch(usable_until=SEKARANG + timedelta(days=3)),
        be.POLICY_BAWAAN,
        SEKARANG,
        arrival_due_at=tiba,
    )
    assert hasil.status == be.REJECTED
    assert hasil.code == be.EXPIRED_BEFORE_ARRIVAL


def test_delivery_window_terlampaui_ditolak() -> None:
    hasil = be.evaluate_batch(
        batch(delivery_window_exceeded=True), be.POLICY_BAWAAN, SEKARANG
    )
    assert hasil.status == be.REJECTED
    assert hasil.code == be.DELIVERY_WINDOW_EXCEEDED


def test_bukti_yang_disyaratkan_policy_harus_ada() -> None:
    policy = be.BatchPolicy(required_evidence=("harvest_record",))
    hasil = be.evaluate_batch(batch(), policy, SEKARANG)
    assert hasil.status == be.REJECTED
    assert hasil.code == be.EVIDENCE_MISSING

    lengkap = be.evaluate_batch(batch(evidence=("harvest_record",)), policy, SEKARANG)
    assert lengkap.status == be.USABLE


def test_assert_dispatchable_melempar_kode_yang_sama() -> None:
    hasil = be.evaluate_batch(batch(safety_status="pending"), be.POLICY_BAWAAN, SEKARANG)
    with pytest.raises(be.BatchNotEligible) as err:
        be.assert_dispatchable(hasil)
    assert err.value.code == be.SAFETY_PENDING
    assert err.value.reasons == hasil.blocking_reasons


def test_partition_memisahkan_usable_on_hold_dan_ditolak() -> None:
    daftar = [
        batch(batch_id="aman"),
        batch(batch_id="tunggu", safety_status="pending"),
        batch(batch_id="gagal", safety_status="fail"),
        batch(batch_id="karantina", quarantine_status="quarantined"),
    ]
    usable, on_hold, ditolak = be.partition_batches(
        daftar, evaluation_time=SEKARANG
    )
    assert [e.batch_id for e in usable] == ["aman"]
    assert [e.batch_id for e in on_hold] == ["tunggu"]
    assert [e.batch_id for e in ditolak] == ["gagal", "karantina"]


def test_evaluation_time_wajib_dari_pemanggil() -> None:
    with pytest.raises(ValueError):
        be.evaluate_batch(batch(), be.POLICY_BAWAAN, None)


def test_core_tidak_mengimpor_fastapi_atau_sqlalchemy() -> None:
    # Yang dilarang adalah IMPOR, bukan kata di docstring: modul ini menjelaskan
    # kenapa ia murni, dan menyebut nama framework di prosa tidak membuatnya
    # bergantung pada framework.
    impor = [
        baris.strip()
        for baris in inspect.getsource(be).splitlines()
        if baris.strip().startswith(("import ", "from "))
    ]
    for baris in impor:
        for terlarang in ("fastapi", "sqlalchemy"):
            assert terlarang not in baris.lower(), baris
