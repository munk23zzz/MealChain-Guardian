"""Integritas bukti freshness (temuan F-02).

Kontrak yang diuji: bukti suhu kosong, tidak lengkap, malformed, atau
duplikat TIDAK boleh menghasilkan verdict `pass`. Untuk bukti yang sama,
freshness tidak boleh mengklaim lebih aman daripada safety evaluator
(deterministik, fail-closed).
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.freshness import classify_freshness, compute_freshness_score
from app.core.safety import evaluate_safety

AS_OF = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
HARVEST = AS_OF - timedelta(days=2.8)  # base score 0.90 bila tanpa penalti
SAFE_MIN, SAFE_MAX = 0.0, 8.0


def _score(log):
    return compute_freshness_score(
        harvested_at=HARVEST,
        as_of=AS_OF,
        shelf_life_days=28.0,
        temperature_log=log,
        safe_min_c=SAFE_MIN,
        safe_max_c=SAFE_MAX,
    )


def _clean_log():
    return [
        {"timestamp": "2026-10-01T09:50:00+00:00", "temperature_c": 4.0},
        {"timestamp": "2026-10-01T10:00:00+00:00", "temperature_c": 4.5},
    ]


@pytest.mark.parametrize(
    "log",
    [
        [],
        [{"timestamp": "2026-10-01T09:50:00+00:00", "temperature_c": 4.0}],
    ],
    ids=["log-kosong", "satu-sampel"],
)
def test_bukti_suhu_tidak_cukup_tidak_boleh_pass(log):
    assert classify_freshness(_score(log)) != "pass"


def test_entri_malformed_tidak_boleh_pass():
    log = [
        {"timestamp": "2026-10-01T09:50:00+00:00", "temperature_c": 4.0},
        {"timestamp": "bukan-waktu", "temperature_c": 4.0},
        {"timestamp": "2026-10-01T10:00:00+00:00", "temperature_c": 4.5},
    ]
    assert classify_freshness(_score(log)) != "pass"


def test_timestamp_duplikat_tidak_boleh_pass():
    log = [
        {"timestamp": "2026-10-01T09:50:00+00:00", "temperature_c": 4.0},
        {"timestamp": "2026-10-01T09:50:00+00:00", "temperature_c": 4.5},
        {"timestamp": "2026-10-01T10:00:00+00:00", "temperature_c": 4.5},
    ]
    assert classify_freshness(_score(log)) != "pass"


def test_log_lengkap_bersih_tetap_pass_dengan_skor_sembilan_puluh():
    """Regresi: perbaikan tidak boleh menghukum rantai pendingin yang bersih."""
    score = _score(_clean_log())

    assert score == pytest.approx(0.90)
    assert classify_freshness(score) == "pass"


def test_freshness_tidak_lebih_longgar_daripada_safety_untuk_bukti_yang_sama():
    log = []
    safety_status = evaluate_safety(log, SAFE_MIN, SAFE_MAX)["safety_status"]
    freshness_status = classify_freshness(_score(log))

    assert safety_status != "pass", "prasyarat: safety fail-closed untuk log kosong"
    assert not (safety_status != "pass" and freshness_status == "pass")
