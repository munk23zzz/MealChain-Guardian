"""Utility time-series suhu — SATU pintu makna bukti (freshness, safety, API, Joule).

Sejarah singkat (baca `MG/phase-03-commodity-evidence.md` sebelum mengubah):

- Versi pertama hanya menjawab "menit di luar rentang" (`summarize_temperature_log`).
- 25 Okt 2026 `core/freshness.py` menambal satu lubang: bukti kosong tidak boleh
  berarti "tidak ada simpangan" (fail-closed `outside_fraction = 1.0`). Tetapi
  hasilnya tetap skor numerik, dan parser masih tidak tahu apa-apa soal **log
  lama**: dua sampel bersih berumur lima hari tetap dinilai rantai dingin yang
  baik (terukur 27 Okt 2026: skor 0,98 → `pass`).
- Fase 3 MG menambahkan lapisan klasifikasi di atas ringkasan itu:
  `observed` | `missing` | `malformed` | `stale` plus `evidence_state`
  (`sufficient` | `insufficient` | `ambiguous`). Freshness, safety, API, dan
  Joule membaca hasil yang SAMA, sehingga tidak ada lagi dua definisi "log ini
  artinya apa". Yang boleh berbeda hanyalah ambang keputusan tiap mesin.
"""

from dataclasses import dataclass
from datetime import datetime

from app.core.commodity_policy import CommodityPolicy

# ── status bukti ────────────────────────────────────────────────────────────
#: Bukti suhu cukup untuk dipakai sebagai dasar keputusan.
EVIDENCE_SUFFICIENT = "sufficient"
#: Bukti tidak ada / tidak bisa dipakai — TIDAK boleh berarti "tidak ada simpangan".
EVIDENCE_INSUFFICIENT = "insufficient"
#: Bukti ada tetapi saling bertentangan (mis. timestamp duplikat).
EVIDENCE_AMBIGUOUS = "ambiguous"

EVIDENCE_STATES = (EVIDENCE_SUFFICIENT, EVIDENCE_INSUFFICIENT, EVIDENCE_AMBIGUOUS)

#: Ada sampel sah, cukup banyak, dan masih segar.
OBSERVED = "observed"
#: Tidak ada sampel sama sekali.
OBSERVATION_MISSING = "missing"
#: Ada entri yang tidak bisa dibaca, atau sampel sah kurang dari minimum profil.
OBSERVATION_MALFORMED = "malformed"
#: Sampel sah, tetapi seluruhnya lebih tua dari `max_observation_age_minutes`.
OBSERVATION_STALE = "stale"

OBSERVATION_STATES = (
    OBSERVED,
    OBSERVATION_MISSING,
    OBSERVATION_MALFORMED,
    OBSERVATION_STALE,
)


@dataclass(frozen=True)
class TemperatureSample:
    """Satu sampel suhu ternormalisasi (bentuk JSONB `Batch.temperature_log`)."""

    timestamp: datetime
    temperature_c: float


@dataclass(frozen=True)
class TemperatureSummary:
    observed_minutes: float
    outside_minutes: float
    complete: bool
    issues: tuple[str, ...]


@dataclass(frozen=True)
class TemperatureObservation:
    """Hasil satu kali pembacaan log — dipakai freshness, safety, API, Joule."""

    #: `observed` | `missing` | `malformed` | `stale`
    observation: str
    #: `sufficient` | `insufficient` | `ambiguous`
    evidence_state: str
    #: Jumlah entri yang bisa dibaca (timestamp + temperature valid).
    sample_count: int
    #: Jumlah entri yang tidak bisa dibaca.
    malformed_count: int
    #: Waktu sampel TERAKHIR yang sah; `None` bila tak ada satu pun.
    last_sample_at: datetime | None
    #: Menit di luar rentang (0 bila profil tidak punya rentang).
    outside_minutes: float
    #: Menit yang benar-benar tercakup interval sampel.
    observed_minutes: float
    #: Alasan yang bisa dibaca manusia; dipakai `reasons` API.
    issues: tuple[str, ...]

    @property
    def has_usable_evidence(self) -> bool:
        """True hanya bila bukti boleh dipakai sebagai dasar keputusan."""
        return self.evidence_state == EVIDENCE_SUFFICIENT

    def to_dict(self) -> dict:
        """Bentuk yang dikirim API (dan diteruskan Joule apa adanya)."""
        return {
            "observation": self.observation,
            "evidence_state": self.evidence_state,
            "sample_count": self.sample_count,
            "malformed_count": self.malformed_count,
            "last_sample_at": (
                self.last_sample_at.isoformat() if self.last_sample_at else None
            ),
            "outside_minutes": self.outside_minutes,
            "observed_minutes": self.observed_minutes,
            "issues": list(self.issues),
        }


def parse_samples(
    temperature_log: list[dict] | None,
) -> tuple[list[TemperatureSample], list[int]]:
    """Pisahkan entri yang terbaca dari yang rusak — SATU definisi "sampel sah".

    `timestamp` dibaca ISO-8601 dan `temperature_c` harus angka. `NaN`/`inf`
    bukan pengukuran, jadi diperlakukan rusak, bukan dihitung sebagai sampel
    dengan suhu aneh.
    """
    sah: list[TemperatureSample] = []
    rusak: list[int] = []
    for index, entry in enumerate(temperature_log or []):
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            temp = float(entry["temperature_c"])
        except (KeyError, TypeError, ValueError):
            rusak.append(index)
            continue
        if temp != temp or abs(temp) == float("inf"):
            rusak.append(index)
            continue
        sah.append(TemperatureSample(timestamp=ts, temperature_c=temp))
    return sah, rusak


def summarize_temperature_log(
    temperature_log: list[dict],
    safe_min_c: float,
    safe_max_c: float,
) -> TemperatureSummary:
    """Ringkasan interval: menit teramati vs menit di luar rentang.

    Maknanya tidak diubah Fase 3; lapisan makna bukti ada di
    `parse_temperature_log`.
    """
    if safe_min_c > safe_max_c:
        raise ValueError("safe_min_c tidak boleh lebih besar dari safe_max_c")

    issues: list[str] = []
    sah, rusak = parse_samples(temperature_log)
    for index in rusak:
        # Teks alasan tampil apa adanya di kartu "Bukti suhu", jadi ditulis
        # sebagai kalimat Indonesia — bukan campuran istilah parser
        # ("malformed entry … index") yang terbaca seperti log internal.
        issues.append(f"entri log rusak pada indeks {index}")

    timestamps = [s.timestamp for s in sah]
    if len(timestamps) != len(set(timestamps)):
        issues.append("timestamp duplikat")

    if len(sah) < 2:
        issues.append(f"sampel sah kurang dari 2 (ada {len(sah)})")
        return TemperatureSummary(
            observed_minutes=0.0,
            outside_minutes=0.0,
            complete=False,
            issues=tuple(issues),
        )

    ordered = sorted(sah, key=lambda s: s.timestamp)
    observed_minutes = 0.0
    outside_minutes = 0.0
    jumlah_interval = len(ordered) - 1
    for posisi, (prev, curr) in enumerate(zip(ordered, ordered[1:])):
        duration = (curr.timestamp - prev.timestamp).total_seconds() / 60.0
        observed_minutes += duration
        prev_luar = prev.temperature_c < safe_min_c or prev.temperature_c > safe_max_c
        curr_luar = curr.temperature_c < safe_min_c or curr.temperature_c > safe_max_c
        # Audit 2026-10-29 (AUD-007): interval dinilai dari `prev` — aturan lama,
        # dan angka kalibrasi freshness/safety bergantung padanya. Yang BOCOR
        # adalah sampel terakhir: ia tidak pernah menjadi `prev`, sehingga log
        # yang memanas di ujung perjalanan (…5 °C, 20 °C) menghasilkan
        # outside_minutes == 0 dan lolos gerbang. Karena itu interval TERAKHIR
        # juga dihitung bila ujungnya di luar rentang — tanpa mengubah interval
        # lain, supaya spike satu sampel tidak terhitung dua kali.
        if prev_luar or (posisi == jumlah_interval - 1 and curr_luar):
            outside_minutes += duration
    return TemperatureSummary(
        observed_minutes=observed_minutes,
        outside_minutes=outside_minutes,
        complete=len(issues) == 0,
        issues=tuple(issues),
    )


# ── klasifikasi bukti ───────────────────────────────────────────────────────


def parse_temperature_log(
    temperature_log: list[dict] | None,
    *,
    policy: CommodityPolicy,
    evaluation_time: datetime,
) -> TemperatureObservation:
    """Baca satu log suhu terhadap satu profil komoditas.

    Aturan (rencana Fase 3 §"Aturan yang diusulkan"):

    - `missing`/`malformed` **tidak pernah** dihitung sebagai nol menit
      excursion lengkap: keduanya menurunkan `evidence_state`.
    - Kurang dari `min_temperature_samples` → bukti tidak cukup.
    - `stale` memakai usia sampel terakhir relatif pada `evaluation_time` dan
      `max_observation_age_minutes` profil; log lama bukan observasi real-time.
    - Profil ambient tanpa rentang **tidak** mengukur excursion.
    """
    log = list(temperature_log or [])

    if not log:
        return TemperatureObservation(
            observation=OBSERVATION_MISSING,
            evidence_state=EVIDENCE_INSUFFICIENT,
            sample_count=0,
            malformed_count=0,
            last_sample_at=None,
            outside_minutes=0.0,
            observed_minutes=0.0,
            issues=("log suhu kosong",),
        )

    band = policy.temp_band
    ringkasan = summarize_temperature_log(
        log,
        safe_min_c=band[0] if band else float("-inf"),
        safe_max_c=band[1] if band else float("inf"),
    )

    sah, rusak = parse_samples(log)
    malformed_count = len(rusak)
    issues: list[str] = list(ringkasan.issues)
    last_sample_at = max((s.timestamp for s in sah), default=None)

    if malformed_count:
        observation = OBSERVATION_MALFORMED
        evidence_state = EVIDENCE_INSUFFICIENT
        issues.append(f"{malformed_count} entri log tidak terbaca")
    elif len(sah) < policy.min_temperature_samples:
        observation = OBSERVATION_MISSING if not sah else OBSERVATION_MALFORMED
        evidence_state = EVIDENCE_INSUFFICIENT
        issues.append(
            f"sampel sah {len(sah)} dari minimum {policy.min_temperature_samples}"
        )
    elif _usang(last_sample_at, evaluation_time, policy):
        observation = OBSERVATION_STALE
        evidence_state = EVIDENCE_INSUFFICIENT
        usia = (
            (evaluation_time - last_sample_at).total_seconds() / 60.0
            if last_sample_at is not None
            else None
        )
        batas = policy.max_observation_age_minutes
        issues.append(
            f"sampel terakhir {usia:.0f} menit lalu, lewat batas {batas} menit"
            if usia is not None
            else "sampel terakhir tidak diketahui"
        )
    elif not ringkasan.complete:
        # Bukti ada dan segar, tetapi saling bertentangan (mis. timestamp duplikat).
        observation = OBSERVED
        evidence_state = EVIDENCE_AMBIGUOUS
    else:
        observation = OBSERVED
        evidence_state = EVIDENCE_SUFFICIENT

    return TemperatureObservation(
        observation=observation,
        evidence_state=evidence_state,
        sample_count=len(sah),
        malformed_count=malformed_count,
        last_sample_at=last_sample_at,
        outside_minutes=ringkasan.outside_minutes if band else 0.0,
        observed_minutes=ringkasan.observed_minutes,
        issues=tuple(dict.fromkeys(issues)),
    )


def classify_evidence_state(
    *,
    sample_count: int,
    malformed_count: int,
    last_sample_at: datetime | None,
    complete: bool,
    policy: CommodityPolicy,
    evaluation_time: datetime,
) -> str:
    """`evidence_state` saja — untuk pemanggil yang sudah memegang angka ringkasan."""
    if malformed_count:
        return EVIDENCE_INSUFFICIENT
    if sample_count < policy.min_temperature_samples:
        return EVIDENCE_INSUFFICIENT
    if _usang(last_sample_at, evaluation_time, policy):
        return EVIDENCE_INSUFFICIENT
    if not complete:
        return EVIDENCE_AMBIGUOUS
    return EVIDENCE_SUFFICIENT


def _usang(
    last_sample_at: datetime | None,
    evaluation_time: datetime,
    policy: CommodityPolicy,
) -> bool:
    """True bila sampel terakhir melewati batas usia profil.

    Profil tanpa batas (ambient) tidak pernah "usang": tidak ada kewajiban
    observasi real-time untuk komoditas yang tidak butuh bukti suhu.
    """
    if policy.max_observation_age_minutes is None:
        return False
    if last_sample_at is None:
        return True
    usia_menit = (evaluation_time - last_sample_at).total_seconds() / 60.0
    return usia_menit > policy.max_observation_age_minutes

