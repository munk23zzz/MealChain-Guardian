"""Safety engine — hard constraint tanpa jalur override, parser bukti bersama.

Perubahan Fase 3 (baca `MG/phase-03-commodity-evidence.md`):

- `evaluate_safety` menerima `policy` (profil komoditas) dan
  `evaluation_time`, lalu membaca log lewat `parse_temperature_log` — parser
  yang SAMA dengan freshness. Sebelumnya kedua mesin memanggil
  `summarize_temperature_log` tetapi menafsirkan hasilnya sendiri, sehingga satu
  log bisa berarti "tidak lengkap" bagi safety dan "skor 0,68 hampir segar" bagi
  freshness.
- Hasil safety membawa `temperature_observation` dan `evidence_state` supaya
  API/Joule bisa menyebut bukti apa yang dipakai, bukan hanya verdict.
- Komoditas ambient (`cold_chain_required=False`) tidak diukur terhadap rentang
  dingin: tidak ada excursion yang bisa dilanggar bila tidak ada rentang.
- Bukti tidak cukup tetap `needs_verification` (bukan `fail`): rencana Fase 3
  menegaskan ini bukan otomatis `fail` untuk semua komoditas.
"""

from datetime import UTC, datetime

from app.core.commodity_policy import CommodityPolicy
from app.core.temperature import parse_samples, parse_temperature_log

FAIL_EXCURSION_DEFAULT_MINUTES = 30.0


def evaluate_safety(
    temperature_log: list[dict] | None,
    safe_min_c: float | None = None,
    safe_max_c: float | None = None,
    max_excursion_minutes: float | None = None,
    *,
    policy: CommodityPolicy | None = None,
    evaluation_time: datetime | None = None,
) -> dict[str, object]:
    """Evaluasi keamanan satu batch.

    Bentuk lama (`safe_min_c`, `safe_max_c`, `max_excursion_minutes` posisional)
    tetap sah untuk pemanggil yang belum punya profil. Profil, bila diberikan,
    menjadi sumber kebenaran rentang dan ambangnya.
    """
    if policy is None:
        if safe_min_c is None or safe_max_c is None:
            raise TypeError("policy atau (safe_min_c dan safe_max_c) wajib diberikan")
        if safe_min_c > safe_max_c:
            raise ValueError("safe_min_c tidak boleh lebih besar dari safe_max_c")
        ambang = (
            FAIL_EXCURSION_DEFAULT_MINUTES
            if max_excursion_minutes is None
            else max_excursion_minutes
        )
        if ambang <= 0:
            raise ValueError("max_excursion_minutes harus positif")
        # Tanpa profil, satu-satunya cara membaca log adalah sebagai rantai
        # dingin dengan rentang yang diberikan — dan itu dinyatakan eksplisit
        # di profil sementara, bukan disimpulkan diam-diam.
        profil = _profil_inline(safe_min_c, safe_max_c, ambang)
    else:
        profil = policy
        ambang = (
            profil.max_excursion_minutes
            if max_excursion_minutes is None
            else max_excursion_minutes
        )
        if ambang <= 0:
            raise ValueError("max_excursion_minutes harus positif")

    evaluasi = _waktu_evaluasi(evaluation_time, temperature_log)

    observation = parse_temperature_log(
        temperature_log, policy=profil, evaluation_time=evaluasi
    )
    reasons = list(observation.issues)

    # ── ambient: tidak ada rentang, jadi tidak ada excursion ───────────────
    if not profil.requires_temperature_evidence:
        return {
            "safety_status": "pass",
            "reasons": [
                "komoditas ambient — bukti suhu tidak diwajibkan "
                f"(bukti: {observation.observation})",
            ],
            "excursion_minutes": 0.0,
            "temperature_observation": observation.observation,
            "evidence_state": observation.evidence_state,
            "sample_count": observation.sample_count,
            "last_sample_at": observation.last_sample_at,
        }

    # ── rantai dingin: bukti harus cukup dulu ──────────────────────────────
    if not observation.has_usable_evidence:
        return {
            "safety_status": "needs_verification",
            "reasons": reasons or ["bukti suhu tidak cukup"],
            "excursion_minutes": observation.outside_minutes,
            "temperature_observation": observation.observation,
            "evidence_state": observation.evidence_state,
            "sample_count": observation.sample_count,
            "last_sample_at": observation.last_sample_at,
        }

    if observation.outside_minutes >= ambang:
        reasons.append(
            f"excursion {observation.outside_minutes:.3f} menit "
            f">= ambang fail {ambang} menit"
        )
        status = "fail"
    elif observation.outside_minutes > 0:
        reasons.append(
            f"excursion {observation.outside_minutes:.3f} menit > 0 "
            f"dan < ambang fail {ambang} menit"
        )
        status = "needs_verification"
    else:
        status = "pass"

    return {
        "safety_status": status,
        "reasons": reasons,
        "excursion_minutes": observation.outside_minutes,
        "temperature_observation": observation.observation,
        "evidence_state": observation.evidence_state,
        "sample_count": observation.sample_count,
        "last_sample_at": observation.last_sample_at,
    }


def _profil_inline(safe_min_c: float, safe_max_c: float, ambang: float) -> CommodityPolicy:
    return CommodityPolicy(
        commodity="(tanpa-nama)",
        cold_chain_required=True,
        safe_temp_min_c=safe_min_c,
        safe_temp_max_c=safe_max_c,
        shelf_life_days=1.0,
        min_temperature_samples=2,
        max_observation_age_minutes=None,
        max_excursion_minutes=ambang,
        policy_version="inline",
        policy_basis="pemanggil lama tanpa profil komoditas",
    )


def _waktu_evaluasi(
    evaluation_time: datetime | None, temperature_log: list[dict] | None
) -> datetime:
    """Waktu acuan untuk menilai "stale".

    Kalau pemanggil tidak menyebutkan, dipakai sampel TERAKHIR di log — bukan
    jam dinding. Alasannya: event/replay mengevaluasi log historis, dan memakai
    `now()` akan menuduh setiap log historis sebagai "stale" hanya karena hari
    ini bukan hari kejadian. Tanpa sampel sama sekali hasilnya tetap `missing`,
    sehingga waktu tidak berpengaruh.
    """
    if evaluation_time is not None:
        return evaluation_time
    sah, _ = parse_samples(temperature_log)
    if sah:
        return max(sample.timestamp for sample in sah)
    return datetime.now(UTC)
