"""Dua sumbu waktu: kapan data DIEVALUASI vs kapan orang BERTINDAK.

Keputusan desain yang dijaga modul ini (rencana MG Fase 2, overview §"Dua sumbu
waktu"):

- **Jangkar evaluasi** (`evaluation_anchor`) milik SESI. Dipakai untuk umur
  dataset, freshness, dan timestamp kejadian simulasi. Replay memakai jangkar
  kanon historis `2026-10-08T12:00:00+00:00` supaya dapat direproduksi;
  realtime memakai waktu saat sesi dibuka.
- **Jam dinding** dipakai untuk aksi operator: approval, PO, penerimaan,
  eksekusi. Kalau aksi hari ini diberi waktu historis, Decision Time berubah
  menjadi "selisih hari" dan kartu KPI berbohong tanpa ada data yang salah.

Kenapa resolver ini ada (bukan `datetime.now()` di tiap pemanggil): ada 35
pemanggilan `datetime.now(timezone.utc)` di `app/`; tanpa satu pintu, sebagian
jalur memakai anchor dan sebagian jam dinding, lalu dua angka untuk satu
kejadian. `decision_now()` adalah pintu itu untuk sisi EVALUASI.

Aturan `decision_now()`:

1. Sesi eksplisit (`sesi=` atau relasi `decision.demo_session` yang SUDAH
   dimuat) → `sesi.evaluation_anchor`.
2. Tanpa sesi, tetapi baris demo LAMA (`demo_case` terisi) DAN `DEMO_MODE`
   menyala → jangkar kanon. Ini menjaga keputusan hasil semai lama (yang lahir
   sebelum kolom sesi ada) tetap dapat dievaluasi pada waktu yang sama.
3. Selain itu → jam dinding.

`demo_case` TIDAK boleh menyamarkan operasional: dengan `DEMO_MODE=False`,
baris ber-`demo_case` pun dijawab jam dinding, sehingga data lama terlihat
sebagai data lama, bukan sebagai data realtime.

Relasi `decision.demo_session` sengaja `lazy="raise"`, jadi resolver ini TIDAK
pernah memicu lazy-load: ia hanya membaca `__dict__` (relasi yang sudah dimuat
oleh `selectinload`). Read path yang butuh anchor harus memilih loading
strategy-nya sendiri — dan itu terlihat di kode pemanggil, bukan tersembunyi di
dalam loop seratus baris.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings

__all__ = [
    "MODE_SAH",
    "REPLAY_ANCHOR",
    "REPLAY_DATASET_VERSION",
    "anchor_untuk",
    "dataset_version_untuk",
    "decision_now",
    "mode_sah",
]

#: Jangkar kanon replay — sama dengan `app.seed.timeseries.CANONICAL_REF`.
REPLAY_ANCHOR = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)

#: Identitas versi dataset replay. Realtime memakai versi turunan anchor.
REPLAY_DATASET_VERSION = "kanon-2026-10-08T12:00:00Z"

MODE_SAH = ("replay", "realtime")


def mode_sah(mode: str | None) -> str:
    """Normalkan mode; nilai asing DITOLAK, bukan ditebak jadi `replay`."""
    nilai = (mode or "").strip().lower()
    if nilai not in MODE_SAH:
        raise ValueError(
            f"mode sesi tidak dikenal: {mode!r}; pilihan: {', '.join(MODE_SAH)}"
        )
    return nilai


def anchor_untuk(mode: str, *, saat: datetime | None = None) -> datetime:
    """Jangkar evaluasi untuk sebuah mode.

    `replay` selalu jangkar kanon (itulah yang membuatnya reproducible);
    `realtime` memakai `saat` (waktu sesi dibuka) — bukan tanggal global, dan
    bukan waktu tiap pembacaan.
    """
    nilai = mode_sah(mode)
    if nilai == "replay":
        return REPLAY_ANCHOR
    return saat or datetime.now(timezone.utc)


def dataset_version_untuk(mode: str, anchor: datetime) -> str:
    """Identitas versi dataset: replay tetap kanon, realtime turunan anchor.

    Anchor masuk ke versi supaya dua sesi realtime tidak pernah berbagi
    identitas dataset walau modenya sama.
    """
    nilai = mode_sah(mode)
    if nilai == "replay":
        return REPLAY_DATASET_VERSION
    return f"realtime-{anchor.astimezone(timezone.utc):%Y%m%dT%H%M%S}Z"


def evaluation_clock(as_of: datetime | None = None) -> datetime:
    """Jam evaluasi dataset untuk pipeline (rekomendasi, kelayakan, bukti).

    Urutannya: `as_of` eksplisit → jangkar kanon saat `DEMO_MODE` menyala →
    jam dinding. Alasan: dataset demo/seed adalah dataset replay yang
    berjangkar `2026-10-08 12:00`. Menilainya dengan jam dinding membuat bukti
    suhu yang sah terbaca basi (dan seluruh kandidat tertahan), sementara
    menilainya dengan jam dinding di produksi tetap benar karena tidak ada
    dataset replay. Preseden aturan ini sudah ada di `decision_now`.
    """
    if as_of is not None:
        return as_of
    if bool(settings.demo_mode):
        return REPLAY_ANCHOR
    return datetime.now(timezone.utc)


def _anchor_relasi(decision) -> datetime | None:
    """Anchor dari relasi sesi yang SUDAH dimuat (tanpa memicu lazy-load).

    `__dict__` hanya memuat atribut yang benar-benar dimuat; relasi
    `lazy="raise"` tidak pernah masuk ke sana sendiri. Karena itu fungsi ini
    aman dipanggil di loop list besar.
    """
    sesi = decision.__dict__.get("demo_session")
    if sesi is None:
        return None
    return getattr(sesi, "evaluation_anchor", None)


def decision_now(decision, *, sesi=None) -> datetime:
    """Waktu EVALUASI untuk satu keputusan (lihat aturan modul di atas)."""
    if sesi is not None:
        anchor = getattr(sesi, "evaluation_anchor", None)
        if anchor is not None:
            return anchor
    anchor = _anchor_relasi(decision)
    if anchor is not None:
        return anchor
    # Baris demo LAMA (tanpa sesi): hanya boleh memakai jangkar kanon bila mode
    # demo menyala. `demo_case` saja bukan alasan — operasional harus jujur.
    if (
        getattr(decision, "demo_session_id", None) is None
        and getattr(decision, "demo_case", None)
        and bool(settings.demo_mode)
    ):
        return REPLAY_ANCHOR
    return datetime.now(timezone.utc)
