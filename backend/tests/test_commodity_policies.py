"""Profil komoditas + bukti suhu (Fase 3 MG).

Berkas ini MENGUNCI kontrak yang belum ada sebelum Fase 3: `commodity_profile`
tidak muncul di kode mana pun (0 kemunculan), dan `temperature_log` kosong
sebelumnya tetap boleh menghasilkan skor kesegaran tinggi untuk komoditas yang
membutuhkan bukti suhu.

Kontrak yang diuji di sini:

1. Setiap komoditas punya PROFIL berversi (`CommodityPolicy`) — bukan rentang
   global 0-8 °C, bukan peta Python yang terpisah dari API/seed/Joule.
2. Parser BATAS menolak profil cacat: `min > max`, `shelf_life_days <= 0`,
   `min_temperature_samples < 0` tidak boleh melewati batas.
3. HASIL OBSERVASI tunggal: `observed` | `missing` | `malformed` | `stale`,
   plus `evidence_state` (`sufficient` | `insufficient` | `ambiguous`).
   Satu parser harian dipakai freshness DAN safety.
4. Cold chain + bukti tidak cukup → freshness TIDAK `pass`, safety
   `needs_verification`, `evidence_state=insufficient`.
5. Ambient (`cold_chain_required=False`) boleh tanpa log, tetapi tidak boleh
   dievaluasi terhadap rentang dingin.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.commodity_limits import policy_for, safe_temp_for
from app.core.freshness import classify_freshness, compute_freshness_score
from app.core.safety import evaluate_safety
from app.core.temperature import (
    EVIDENCE_AMBIGUOUS,
    EVIDENCE_INSUFFICIENT,
    EVIDENCE_SUFFICIENT,
    OBSERVATION_MALFORMED,
    OBSERVATION_MISSING,
    OBSERVATION_STALE,
    OBSERVED,
    parse_temperature_log,
)

AS_OF = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)

EGG = policy_for("telur")
RICE = policy_for("beras")


def stamp(hours_ago: float, temp: float, base: datetime = AS_OF) -> dict:
    return {
        "timestamp": (base - timedelta(hours=hours_ago)).isoformat(),
        "temperature_c": temp,
    }


# ── 1. Profil per komoditas ─────────────────────────────────────────────────


def test_profil_telur_wajib_rantai_dingin():
    assert EGG.cold_chain_required is True
    assert EGG.safe_temp_min_c is not None and EGG.safe_temp_max_c is not None
    assert EGG.safe_temp_min_c < EGG.safe_temp_max_c
    assert EGG.shelf_life_days > 0


def test_profil_beras_ambient_tanpa_rentang_dingin():
    """Beras tidak boleh dipaksa ke 0-8 °C: itu yang membuat 27 °C dinilai fail."""
    assert RICE.cold_chain_required is False
    assert RICE.safe_temp_min_c is None and RICE.safe_temp_max_c is None


def test_profil_berversi_dan_menyebut_dasar():
    """Profil harus punya versi + dasar; kalau asumsi demo, labelnya jujur."""
    for policy in (EGG, RICE):
        assert policy.policy_version.strip(), "policy_version tidak boleh kosong"
        assert policy.policy_basis.strip(), "policy_basis tidak boleh kosong"
    assert EGG.policy_kind == "simulated_policy", (
        "angka suhu belum divalidasi domain owner → harus jujur sebagai simulasi"
    )


def test_komoditas_tak_dikenal_ditolak_bukan_ditebak():
    with pytest.raises(KeyError):
        policy_for("jagung-manis-tak-ada")
    with pytest.raises(KeyError):
        safe_temp_for("jagung-manis-tak-ada")


def test_komoditas_ambient_tak_punya_rentang_dingin():
    """`safe_temp_for` untuk ambient harus None, bukan 0-8 °C bawaan."""
    assert safe_temp_for("beras") is None


# ── 2. Parser batas: profil cacat tidak boleh lolos ─────────────────────────


def _profil(**ganti):
    dasar = {
        "commodity": "telur",
        "cold_chain_required": True,
        "safe_temp_min_c": 0.0,
        "safe_temp_max_c": 8.0,
        "shelf_life_days": 28.0,
        "min_temperature_samples": 2,
        "max_observation_age_minutes": 360,
        "policy_version": "v1",
        "policy_basis": "uji",
        "policy_kind": "simulated_policy",
    }
    dasar.update(ganti)
    return dasar


@pytest.mark.parametrize(
    "rusak, alasan",
    [
        ({"safe_temp_min_c": 9.0}, "min > max"),
        ({"shelf_life_days": 0}, "shelf_life_days nol"),
        ({"shelf_life_days": -3}, "shelf_life_days negatif"),
        ({"min_temperature_samples": -1}, "sampel minimum negatif"),
        ({"max_observation_age_minutes": 0}, "usia observasi nol"),
        ({"policy_version": "  "}, "versi kosong"),
        ({"policy_basis": ""}, "dasar kosong"),
    ],
)
def test_profil_cacat_ditolak(rusak, alasan):  # noqa: ARG001 - alasan = dokumentasi kasus
    from app.core.commodity_policy import CommodityPolicy

    with pytest.raises(ValueError):
        CommodityPolicy(**{**_profil(), **rusak})


def test_profil_cold_chain_wajib_punya_rentang():
    from app.core.commodity_policy import CommodityPolicy

    with pytest.raises(ValueError):
        CommodityPolicy(**_profil(cold_chain_required=True, safe_temp_min_c=None))
    with pytest.raises(ValueError):
        CommodityPolicy(**_profil(cold_chain_required=True, safe_temp_max_c=None))


def test_profil_ambient_boleh_tanpa_rentang():
    from app.core.commodity_policy import CommodityPolicy

    policy = CommodityPolicy(
        **_profil(
            commodity="beras",
            cold_chain_required=False,
            safe_temp_min_c=None,
            safe_temp_max_c=None,
            shelf_life_days=180.0,
            min_temperature_samples=0,
            max_observation_age_minutes=None,
        )
    )
    assert policy.safe_temp_min_c is None


# ── 3. Hasil observasi tunggal ──────────────────────────────────────────────


def test_log_kosong_menghasilkan_missing():
    hasil = parse_temperature_log([], policy=EGG, evaluation_time=AS_OF)
    assert hasil.observation == OBSERVATION_MISSING
    assert hasil.evidence_state == EVIDENCE_INSUFFICIENT
    assert hasil.sample_count == 0
    assert hasil.last_sample_at is None


def test_satu_sampel_cold_chain_tidak_cukup():
    hasil = parse_temperature_log(
        [stamp(1, 4.0)], policy=EGG, evaluation_time=AS_OF
    )
    assert hasil.sample_count == 1
    assert hasil.evidence_state == EVIDENCE_INSUFFICIENT
    assert hasil.observation != OBSERVED


def test_log_malformed_ditandai_malformed():
    log = [stamp(2, 4.0), {"timestamp": "bukan-waktu", "temperature_c": 4.0}, stamp(1, 4.5)]
    hasil = parse_temperature_log(log, policy=EGG, evaluation_time=AS_OF)
    assert hasil.observation == OBSERVATION_MALFORMED
    assert hasil.evidence_state == EVIDENCE_INSUFFICIENT
    assert any("malformed" in alasan for alasan in hasil.issues)


def test_log_lama_ditandai_stale():
    """Sampel lebih tua dari `max_observation_age_minutes` bukan observasi real-time."""
    log = [stamp(24 * 5, 4.0), stamp(24 * 5 - 0.5, 4.5)]
    hasil = parse_temperature_log(log, policy=EGG, evaluation_time=AS_OF)
    assert hasil.observation == OBSERVATION_STALE
    assert hasil.evidence_state == EVIDENCE_INSUFFICIENT
    assert hasil.last_sample_at is not None


def test_log_sah_ditandai_observed():
    log = [stamp(2, 4.0), stamp(1, 4.5)]
    hasil = parse_temperature_log(log, policy=EGG, evaluation_time=AS_OF)
    assert hasil.observation == OBSERVED
    assert hasil.evidence_state == EVIDENCE_SUFFICIENT
    assert hasil.sample_count == 2
    assert hasil.last_sample_at == AS_OF - timedelta(hours=1)


def test_timestamp_duplikat_ambiguous_bukan_sufficient():
    log = [stamp(1, 4.0), stamp(1, 4.5)]
    hasil = parse_temperature_log(log, policy=EGG, evaluation_time=AS_OF)
    assert hasil.evidence_state == EVIDENCE_AMBIGUOUS
    assert hasil.evidence_state != EVIDENCE_SUFFICIENT


# ── 4. Freshness & safety memakai hasil observasi yang SAMA ─────────────────


def test_telur_log_kosong_tidak_memperoleh_freshness_pass():
    score = compute_freshness_score(
        harvested_at=AS_OF - timedelta(hours=3),
        as_of=AS_OF,
        policy=EGG,
        temperature_log=[],
    )
    assert classify_freshness(score) != "pass"


def test_safety_telur_log_kosong_needs_verification_bukan_pass():
    hasil = evaluate_safety(temperature_log=[], policy=EGG, evaluation_time=AS_OF)
    assert hasil["safety_status"] == "needs_verification"
    assert hasil["evidence_state"] == EVIDENCE_INSUFFICIENT
    assert hasil["temperature_observation"] == OBSERVATION_MISSING


def test_freshness_dan_safety_melihat_observasi_yang_sama():
    """Satu parser: dua mesin tidak boleh berbeda pendapat soal arti log ini."""
    log = [stamp(24 * 5, 4.0), stamp(24 * 5 - 0.5, 4.5)]  # stale
    score = compute_freshness_score(
        harvested_at=AS_OF - timedelta(hours=3),
        as_of=AS_OF,
        policy=EGG,
        temperature_log=log,
    )
    safety = evaluate_safety(temperature_log=log, policy=EGG, evaluation_time=AS_OF)

    assert safety["temperature_observation"] == OBSERVATION_STALE
    assert classify_freshness(score) != "pass", (
        "log lama tidak boleh memberi freshness pass saat safety menyebutnya stale"
    )


def test_log_sah_bersih_tetap_lolos_cold_chain():
    """Regresi: perbaikan tidak boleh menghukum rantai dingin yang benar."""
    log = [stamp(2, 4.0), stamp(1, 4.5)]
    score = compute_freshness_score(
        harvested_at=AS_OF - timedelta(hours=3),
        as_of=AS_OF,
        policy=EGG,
        temperature_log=log,
    )
    safety = evaluate_safety(temperature_log=log, policy=EGG, evaluation_time=AS_OF)

    assert classify_freshness(score) == "pass"
    assert safety["safety_status"] == "pass"


def test_beras_ambient_tanpa_log_bukan_fail():
    score = compute_freshness_score(
        harvested_at=AS_OF - timedelta(days=10),
        as_of=AS_OF,
        policy=RICE,
        temperature_log=[],
    )
    safety = evaluate_safety(temperature_log=[], policy=RICE, evaluation_time=AS_OF)

    assert safety["safety_status"] != "fail"
    assert safety["temperature_observation"] == OBSERVATION_MISSING
    assert classify_freshness(score) != "fail"


def test_beras_ambient_tidak_mengukur_excursion_terhadap_rentang_dingin():
    """27 °C untuk beras bukan excursion: profil ambient tidak punya rentang."""
    log = [stamp(2, 27.0), stamp(1, 27.5)]
    safety = evaluate_safety(temperature_log=log, policy=RICE, evaluation_time=AS_OF)
    assert safety["safety_status"] == "pass"
    assert safety["excursion_minutes"] == 0.0


def test_bukti_hilang_tidak_mendapat_skor_default():
    """Tanpa bukti suhu, skor tidak boleh sama dengan rantai bersih."""
    bersih = compute_freshness_score(
        harvested_at=AS_OF - timedelta(hours=3),
        as_of=AS_OF,
        policy=EGG,
        temperature_log=[stamp(2, 4.0), stamp(1, 4.5)],
    )
    kosong = compute_freshness_score(
        harvested_at=AS_OF - timedelta(hours=3),
        as_of=AS_OF,
        policy=EGG,
        temperature_log=[],
    )
    assert kosong < bersih
