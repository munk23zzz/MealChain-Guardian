"""S4: batch terkarantina tidak boleh masuk stok lewat penerimaan."""

from datetime import UTC, datetime, timedelta

from app.core.safety_gate import (
    BLOKIR_EKSEKUSI_KARANTINA,
    receipt_blokir_alasan,
)

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
LOG_LENGKAP = [
    {"timestamp": "2026-10-25T09:00:00+00:00", "temperature_c": 4.0},
    {"timestamp": "2026-10-25T10:00:00+00:00", "temperature_c": 4.2},
]


def test_receipt_pass_tetap_ditolak_bila_batch_dikarantina():
    alasan = receipt_blokir_alasan(
        safety_status="pass",
        quarantine_status="quarantined",
        usable_until=NOW + timedelta(hours=6),
        temperature_log=LOG_LENGKAP,
        sekarang=NOW,
    )
    assert alasan == BLOKIR_EKSEKUSI_KARANTINA


def test_receipt_released_boleh_lanjut_ke_gate_lain():
    alasan = receipt_blokir_alasan(
        safety_status="pass",
        quarantine_status="released",
        usable_until=NOW + timedelta(hours=6),
        temperature_log=LOG_LENGKAP,
        sekarang=NOW,
    )
    assert alasan is None
