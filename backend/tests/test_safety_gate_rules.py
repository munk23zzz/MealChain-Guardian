"""Aturan gate keselamatan (temuan F-01 & A-01) — murni, tanpa DB.

Kontrak yang dikunci:

1. Penerimaan barang (receipt) hanya boleh disetujui bila batch berstatus
   `pass`, bukti suhunya lengkap, dan belum kedaluwarsa. Status `pending`,
   `needs_verification`, `fail`, atau kosong = tolak.
2. Eksekusi/ dispatch hanya boleh memakai batch `pass`, tidak dikarantina,
   belum kedaluwarsa, dan berbukti suhu lengkap. Satu batch ragu di antara
   batch aman tidak boleh diloloskan (fail-closed), dan kumpulan batch kosong
   juga tidak boleh diloloskan.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.safety_gate import (
    BLOKIR_EKSEKUSI_KARANTINA,
    BLOKIR_EKSEKUSI_KEDALUWARSA,
    BLOKIR_EKSEKUSI_TANPA_BATCH,
    BLOKIR_SAFETY_BUKAN_PASS,
    BLOKIR_SUHU_TIDAK_LENGKAP,
    batch_blokir_eksekusi,
    kumpulan_batch_blokir_eksekusi,
    receipt_blokir_alasan,
)

NOW = datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)
LOG_LENGKAP = [
    {"timestamp": "2026-10-25T09:00:00+00:00", "temperature_c": 4.0},
    {"timestamp": "2026-10-25T10:00:00+00:00", "temperature_c": 4.2},
]
NANTI = NOW + timedelta(hours=6)
KEMARIN = NOW - timedelta(hours=6)


# ── Penerimaan barang ──────────────────────────────────────────────────────


def test_receipt_batch_pass_berbukti_lengkap_diizinkan():
    alasan = receipt_blokir_alasan(
        safety_status="pass",
        usable_until=NANTI,
        temperature_log=LOG_LENGKAP,
        sekarang=NOW,
    )
    assert alasan is None


@pytest.mark.parametrize("status", ["pending", "needs_verification", "fail", "FAIL", None, ""])
def test_receipt_status_selain_pass_ditolak(status):
    alasan = receipt_blokir_alasan(
        safety_status=status,
        usable_until=NANTI,
        temperature_log=LOG_LENGKAP,
        sekarang=NOW,
    )
    assert alasan == BLOKIR_SAFETY_BUKAN_PASS


@pytest.mark.parametrize(
    "log",
    [
        [],
        [{"timestamp": "2026-10-25T09:00:00+00:00", "temperature_c": 4.0}],
    ],
    ids=["log-kosong", "satu-sampel"],
)
def test_receipt_batch_pass_tanpa_bukti_suhu_cukup_ditolak(log):
    alasan = receipt_blokir_alasan(
        safety_status="pass",
        usable_until=NANTI,
        temperature_log=log,
        sekarang=NOW,
    )
    assert alasan == BLOKIR_SUHU_TIDAK_LENGKAP


def test_receipt_batch_kedaluwarsa_ditolak():
    alasan = receipt_blokir_alasan(
        safety_status="pass",
        usable_until=KEMARIN,
        temperature_log=LOG_LENGKAP,
        sekarang=NOW,
    )
    assert alasan == BLOKIR_EKSEKUSI_KEDALUWARSA


# ── Eksekusi & dispatch ────────────────────────────────────────────────────


def test_batch_pass_bersih_tidak_memblokir_eksekusi():
    assert (
        batch_blokir_eksekusi(
            safety_status="pass",
            quarantine_status="none",
            usable_until=NANTI,
            temperature_log=LOG_LENGKAP,
            sekarang=NOW,
        )
        is None
    )


@pytest.mark.parametrize("status", ["pending", "needs_verification", "fail", None])
def test_batch_selain_pass_memblokir_eksekusi(status):
    assert (
        batch_blokir_eksekusi(
            safety_status=status,
            quarantine_status="none",
            usable_until=NANTI,
            temperature_log=LOG_LENGKAP,
            sekarang=NOW,
        )
        == BLOKIR_SAFETY_BUKAN_PASS
    )


@pytest.mark.parametrize("q", ["quarantined", "failed"])
def test_batch_dikarantina_memblokir_eksekusi(q):
    assert (
        batch_blokir_eksekusi(
            safety_status="pass",
            quarantine_status=q,
            usable_until=NANTI,
            temperature_log=LOG_LENGKAP,
            sekarang=NOW,
        )
        == BLOKIR_EKSEKUSI_KARANTINA
    )


def test_batch_kedaluwarsa_memblokir_eksekusi():
    assert (
        batch_blokir_eksekusi(
            safety_status="pass",
            quarantine_status="none",
            usable_until=KEMARIN,
            temperature_log=LOG_LENGKAP,
            sekarang=NOW,
        )
        == BLOKIR_EKSEKUSI_KEDALUWARSA
    )


def test_kumpulan_kosong_memblokir_eksekusi():
    assert kumpulan_batch_blokir_eksekusi([], sekarang=NOW) == BLOKIR_EKSEKUSI_TANPA_BATCH


def test_satu_batch_ragu_di_antara_batch_aman_memblokir_eksekusi():
    batch = [
        {
            "safety_status": "pass",
            "quarantine_status": "none",
            "usable_until": NANTI,
            "temperature_log": LOG_LENGKAP,
        },
        {
            "safety_status": "pass",
            "quarantine_status": "none",
            "usable_until": NANTI,
            "temperature_log": LOG_LENGKAP,
        },
        {
            "safety_status": "needs_verification",
            "quarantine_status": "none",
            "usable_until": NANTI,
            "temperature_log": LOG_LENGKAP,
        },
    ]
    assert kumpulan_batch_blokir_eksekusi(batch, sekarang=NOW) == BLOKIR_SAFETY_BUKAN_PASS


def test_semua_batch_aman_tidak_memblokir():
    batch = [
        {
            "safety_status": "pass",
            "quarantine_status": "none",
            "usable_until": NANTI,
            "temperature_log": LOG_LENGKAP,
        }
    ]
    assert kumpulan_batch_blokir_eksekusi(batch, sekarang=NOW) is None
