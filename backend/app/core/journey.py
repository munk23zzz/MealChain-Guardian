"""Perjalanan kiriman: jam berangkat → estimasi tiba (deterministik, dari DB).

Kenapa modul terpisah dan murni (tanpa DB, tanpa HTTP): angka perjalanan adalah
angka yang paling mudah "dikarang". Semua di sini hanya aritmetika atas data
yang benar-benar ada:

- jam berangkat dari `batches.dispatched_at` (NULL = belum berangkat),
- waktu tempuh dari cache rute jalan `road_routes.duration_s` (OSRM),
- batas layak dari `batches.usable_until`.

Aturan yang dipegang:
1. Tidak ada jam berangkat → tidak ada estimasi tiba (`eta_at=None`). Keadaan
   jujurnya `belum_berangkat`; waktu tempuh tetap boleh dilaporkan karena itu
   sifat JALUR, bukan sifat barang.
2. Sudah berangkat tetapi waktu tempuh belum ada → keadaan `tidak_diketahui`,
   bukan "di jalan" (kita tidak tahu ia sudah tiba atau belum).
3. Jam berangkat tidak boleh mendahului panen; dijaga di sini dan oleh CHECK
   constraint `batches_dispatch_after_harvest` di DB.
4. Perbandingan dengan `usable_until` hanya PERBANDINGAN dua angka, bukan klaim
   keamanan pangan.
"""

from datetime import datetime, timedelta

#: Barang masih di pemasok (jam berangkat belum ada / masih di depan).
STATE_BELUM_BERANGKAT = "belum_berangkat"
#: Sudah berangkat dan estimasi tiba masih di depan.
STATE_DI_JALAN = "di_jalan"
#: Waktu sekarang sudah melewati estimasi tiba.
STATE_SUDAH_TIBA = "sudah_tiba"
#: Sudah berangkat, tetapi waktu tempuh jalurnya belum ada → tidak diklaim.
STATE_TIDAK_DIKETAHUI = "tidak_diketahui"

STATE_LABELS = {
    STATE_BELUM_BERANGKAT: "Belum berangkat",
    STATE_DI_JALAN: "Di jalan",
    STATE_SUDAH_TIBA: "Sudah tiba",
    STATE_TIDAK_DIKETAHUI: "Perjalanan belum bisa dipastikan",
}

#: Urutan tetap untuk ringkasan di API/UI (belum berangkat → di jalan → tiba →
#: tidak diketahui), supaya kedua sisi tidak menampilkan urutan yang berbeda.
URUTAN_KEADAAN = (
    STATE_BELUM_BERANGKAT,
    STATE_DI_JALAN,
    STATE_SUDAH_TIBA,
    STATE_TIDAK_DIKETAHUI,
)


def _require_aware(moment: datetime, nama: str) -> None:
    """Waktu tanpa zona tidak boleh dipakai: bisa bergeser 7 jam di WIB."""
    if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
        raise ValueError(f"{nama} wajib menyertakan zona waktu")


def dispatch_time(reference_time: datetime, offset_hours: float | None) -> datetime | None:
    """Jam berangkat dari offset relatif waktu referensi seeder.

    `None` berarti kiriman memang belum berangkat (NULL di DB) — bukan jam nol,
    bukan waktu referensi.
    """
    _require_aware(reference_time, "reference_time")
    if offset_hours is None:
        return None
    jam = float(offset_hours)
    if jam != jam or jam in (float("inf"), float("-inf")):
        raise ValueError("offset jam berangkat harus angka berhingga")
    return reference_time + timedelta(hours=jam)


def validate_dispatch(harvested_at: datetime, dispatched_at: datetime | None) -> None:
    """Tolak kiriman yang berangkat sebelum barangnya dipanen."""
    if dispatched_at is None:
        return
    _require_aware(harvested_at, "harvested_at")
    _require_aware(dispatched_at, "dispatched_at")
    if dispatched_at < harvested_at:
        raise ValueError(
            "jam berangkat tidak boleh mendahului jam panen "
            f"({dispatched_at.isoformat()} < {harvested_at.isoformat()})"
        )
    return None


def eta_at(dispatched_at: datetime | None, travel_s: float | None) -> datetime | None:
    """Estimasi tiba = jam berangkat + waktu tempuh jalan (OSRM)."""
    if dispatched_at is None or travel_s is None:
        return None
    detik = float(travel_s)
    if detik <= 0:
        return None
    return dispatched_at + timedelta(seconds=detik)


def journey_state(
    now: datetime, dispatched_at: datetime | None, eta: datetime | None
) -> str:
    """Keadaan perjalanan dibaca dari waktu, bukan dari tebakan."""
    if dispatched_at is None or dispatched_at > now:
        return STATE_BELUM_BERANGKAT
    if eta is None:
        return STATE_TIDAK_DIKETAHUI
    if now >= eta:
        return STATE_SUDAH_TIBA
    return STATE_DI_JALAN


def elapsed_min(now: datetime, dispatched_at: datetime | None) -> float | None:
    """Sudah berapa menit di jalan (0 bila belum berangkat)."""
    if dispatched_at is None:
        return None
    return max(0.0, (now - dispatched_at).total_seconds() / 60.0)


def remaining_min(now: datetime, eta: datetime | None) -> float | None:
    """Sisa menit menuju estimasi tiba (negatif = estimasi sudah lewat)."""
    if eta is None:
        return None
    return (eta - now).total_seconds() / 60.0


def progress_ratio(
    now: datetime, dispatched_at: datetime | None, eta: datetime | None
) -> float | None:
    """Bagian perjalanan yang sudah ditempuh (0..1), dijaga di rentang itu."""
    if dispatched_at is None or eta is None or eta <= dispatched_at:
        return None
    bagian = (now - dispatched_at).total_seconds() / (eta - dispatched_at).total_seconds()
    return min(1.0, max(0.0, bagian))


def journey_payload(
    *,
    now: datetime,
    dispatched_at: datetime | None,
    travel_s: float | None,
    travel_source: str | None,
    usable_until: datetime | None = None,
) -> dict:
    """Ringkasan perjalanan satu kiriman untuk API & UI (satu sumber kebenaran)."""
    eta = eta_at(dispatched_at, travel_s)
    state = journey_state(now, dispatched_at, eta)
    sisa = remaining_min(now, eta)
    berjalan = elapsed_min(now, dispatched_at)
    progres = progress_ratio(now, dispatched_at, eta)
    dalam_batas = None
    if eta is not None and usable_until is not None:
        dalam_batas = eta <= usable_until
    return {
        "dispatched_at": dispatched_at.isoformat() if dispatched_at else None,
        "eta_at": eta.isoformat() if eta else None,
        "state": state,
        "state_label": STATE_LABELS[state],
        "travel_s": float(travel_s) if travel_s else None,
        "travel_min": round(float(travel_s) / 60.0, 1) if travel_s else None,
        "travel_source": travel_source or None,
        "elapsed_min": round(berjalan, 1) if berjalan is not None else None,
        "remaining_min": round(sisa, 1) if sisa is not None else None,
        "progress": round(progres, 3) if progres is not None else None,
        "usable_until": usable_until.isoformat() if usable_until else None,
        "arrives_before_usable_until": dalam_batas,
    }
