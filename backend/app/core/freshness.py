"""Freshness engine — memakai hasil observasi bukti suhu yang SAMA dengan safety.

Perubahan Fase 3 (baca `MG/phase-03-commodity-evidence.md`):

- Pemanggil baru memberi `policy` (profil komoditas berversi), bukan tiga
  argumen longgar (`shelf_life_days`, `safe_min_c`, `safe_max_c`). Bentuk lama
  TETAP didukung supaya pemanggil yang belum dimigrasi tidak patah; keduanya
  menuju fungsi inti yang sama.
- Skor tidak lagi menafsirkan sendiri arti log. Ia memakai
  `parse_temperature_log` — parser yang sama dengan safety — sehingga satu log
  tidak mungkin dibaca dua cara berbeda oleh dua mesin.
- Bukti yang tidak `sufficient` (`missing`/`malformed`/`stale`) tidak bisa
  menghasilkan `pass` untuk komoditas yang mewajibkan bukti suhu, walau skor
  angkanya kebetulan di atas ambang. `fail` tetap `fail`: bukti tidak cukup
  tidak pernah menaikkan status.
- Profil ambient (`cold_chain_required=False`) tidak dihukum karena tanpa log:
  bukti suhu memang tidak diminta, dan excursion tidak diukur.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.commodity_policy import CommodityPolicy
from app.core.temperature import (
    EVIDENCE_SUFFICIENT,
    OBSERVED,
    TemperatureObservation,
    parse_temperature_log,
)

PASS_THRESHOLD = 0.85
VERIFY_THRESHOLD = 0.60
TEMP_PENALTY_WEIGHT = 0.30


@dataclass(frozen=True)
class FreshnessResult:
    """Satu evaluasi kesegaran lengkap — skor, status, dan bukti yang dipakainya."""

    score: float
    status: str
    usable_until: datetime
    observation: TemperatureObservation
    policy: CommodityPolicy

    @property
    def evidence_state(self) -> str:
        return self.observation.evidence_state

    @property
    def temperature_observation(self) -> str:
        return self.observation.observation


def evaluate_freshness(
    *,
    harvested_at: datetime,
    as_of: datetime,
    policy: CommodityPolicy,
    temperature_log: list[dict] | None,
) -> FreshnessResult:
    """Hitung skor + status kesegaran memakai satu pembacaan bukti suhu."""
    if harvested_at > as_of:
        raise ValueError("harvested_at tidak boleh di masa depan")
    if policy.shelf_life_days <= 0:
        raise ValueError("shelf_life_days harus positif")

    observation = parse_temperature_log(
        temperature_log, policy=policy, evaluation_time=as_of
    )
    score = _score(
        harvested_at=harvested_at,
        as_of=as_of,
        shelf_life_days=policy.shelf_life_days,
        observation=observation,
        policy=policy,
    )
    return FreshnessResult(
        score=score,
        status=classify_freshness(
            score,
            evidence_state=observation.evidence_state,
            observation=observation.observation,
            policy=policy,
        ),
        usable_until=compute_usable_until(
            harvested_at=harvested_at,
            shelf_life_days=policy.shelf_life_days,
            score=score,
        ),
        observation=observation,
        policy=policy,
    )


def compute_freshness_score(
    harvested_at: datetime,
    as_of: datetime,
    shelf_life_days: float | None = None,
    temperature_log: list[dict] | None = None,
    safe_min_c: float | None = None,
    safe_max_c: float | None = None,
    *,
    policy: CommodityPolicy | None = None,
) -> float:
    """Skor kesegaran 0..1.

    Dua bentuk pemanggilan:

    - baru: `compute_freshness_score(harvested, as_of, policy=..., temperature_log=...)`
    - lama: `compute_freshness_score(harvested, as_of, shelf_life_days, log, min, max)`

    Bentuk lama dibangun menjadi profil sementara supaya jalurnya tetap satu:
    log dibaca parser yang sama, dan bukti yang tidak cukup tetap tidak boleh
    mendapat skor rantai-dingin-bersih.
    """
    if policy is not None:
        profil = policy
    else:
        if shelf_life_days is None:
            raise TypeError("shelf_life_days wajib bila policy tidak diberikan")
        rantai_dingin = safe_min_c is not None and safe_max_c is not None
        profil = CommodityPolicy(
            commodity="(tanpa-nama)",
            cold_chain_required=rantai_dingin,
            safe_temp_min_c=safe_min_c,
            safe_temp_max_c=safe_max_c,
            shelf_life_days=float(shelf_life_days),
            # Bentuk lama tidak menyatakan usia maksimum sampel; tanpanya
            # "stale" tidak bisa dinilai, dan itu dinyatakan apa adanya
            # (`max_observation_age_minutes=None`), bukan ditebak.
            min_temperature_samples=2 if rantai_dingin else 0,
            max_observation_age_minutes=None,
            policy_version="inline",
            policy_basis="pemanggil lama tanpa profil komoditas",
        )

    if harvested_at > as_of:
        raise ValueError("harvested_at tidak boleh di masa depan")
    if profil.shelf_life_days <= 0:
        raise ValueError("shelf_life_days harus positif")

    observation = parse_temperature_log(
        temperature_log, policy=profil, evaluation_time=as_of
    )
    return _score(
        harvested_at=harvested_at,
        as_of=as_of,
        shelf_life_days=profil.shelf_life_days,
        observation=observation,
        policy=profil,
    )


def _score(
    *,
    harvested_at: datetime,
    as_of: datetime,
    shelf_life_days: float,
    observation: TemperatureObservation,
    policy: CommodityPolicy,
) -> float:
    """Skor dasar umur simpan dikurangi penalti bukti suhu."""
    age_fraction = (as_of - harvested_at).total_seconds() / (shelf_life_days * 86400.0)
    base = max(0.0, 1.0 - age_fraction)

    if not policy.requires_temperature_evidence:
        # Komoditas ambient: bukti suhu memang tidak diminta, jadi tidak ada
        # penalti suhu. Ini BUKAN "skor default pada bukti yang hilang" —
        # tidak ada bukti yang hilang karena tidak ada yang diminta.
        return max(0.0, min(1.0, base))

    if not observation.has_usable_evidence:
        # Bukti hilang/rusak/usang: tidak ada dasar menyatakan rantai dingin
        # aman. Penalti penuh; `classify_freshness` juga memaksa bukan `pass`.
        outside_fraction = 1.0
    elif observation.observed_minutes > 0:
        outside_fraction = observation.outside_minutes / observation.observed_minutes
    else:
        # Sampel cukup tetapi tidak membentuk interval (timestamp sama).
        outside_fraction = 1.0

    return max(0.0, min(1.0, base - TEMP_PENALTY_WEIGHT * outside_fraction))


def classify_freshness(
    score: float,
    pass_threshold: float = PASS_THRESHOLD,
    verify_threshold: float = VERIFY_THRESHOLD,
    *,
    evidence_state: str | None = None,
    observation: str | None = None,
    policy: CommodityPolicy | None = None,
) -> str:
    """Status kesegaran dari skor — dengan gerbang bukti suhu.

    `evidence_state`/`policy` opsional supaya fungsi ini tetap bisa dipakai
    murni sebagai klasifikasi angka (tes lama). Begitu bukti suhu diketahui,
    aturan Fase 3 berlaku: komoditas yang MEWAJIBKAN bukti suhu tidak boleh
    mendapat `pass` dari bukti yang tidak `sufficient`. `fail` tetap `fail` —
    bukti tidak cukup tidak boleh menaikkan status.
    """
    if score != score or score < 0.0 or score > 1.0:
        raise ValueError("score harus di [0.0, 1.0] dan bukan NaN")
    if verify_threshold >= pass_threshold:
        raise ValueError("verify_threshold harus di bawah pass_threshold")

    status = _status_from_score(score, pass_threshold, verify_threshold)

    if evidence_state is None or policy is None:
        return status
    if not policy.requires_temperature_evidence:
        return status
    if status == "fail":
        return "fail"
    if evidence_state != EVIDENCE_SUFFICIENT:
        return "needs_verification"
    if observation is not None and observation != OBSERVED:
        return "needs_verification"
    return status


def _status_from_score(score: float, pass_threshold: float, verify_threshold: float) -> str:
    if score >= pass_threshold:
        return "pass"
    if score >= verify_threshold:
        return "needs_verification"
    return "fail"


def compute_usable_until(
    harvested_at: datetime,
    shelf_life_days: float,
    score: float,
) -> datetime:
    if shelf_life_days <= 0:
        raise ValueError("shelf_life_days harus positif")
    if score != score or score < 0.0 or score > 1.0:
        raise ValueError("score harus di [0.0, 1.0] dan bukan NaN")
    return harvested_at + timedelta(days=shelf_life_days * score)
