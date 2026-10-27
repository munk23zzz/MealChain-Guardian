"""Kebijakan jendela kirim: kapan barang HARUS tiba (Fase 4 MG poin 6).

Modul murni — tanpa DB, tanpa HTTP, tanpa jam dinding. Semua waktu disuplai
pemanggil, supaya keputusan yang sama bisa direproduksi saat demo replay.

Latar masalah yang ditutup modul ini:

- `estimate_logistics()` sudah punya parameter `delivery_window_min`, tetapi
  tidak ada pemanggil produksi yang mengisinya (`app/services/recommendation_service.py`
  memanggilnya dengan tiga argumen). Karena `delivery_window_min=None` berarti
  `feasible=True`, setiap kandidat selalu "layak" — bukan karena jadwalnya
  terpenuhi, melainkan karena tidak ada batas yang diperiksa.
- `DemandRecord.needed_by` sudah lama tersimpan (kapan komoditas dibutuhkan),
  tetapi rantai rekomendasi hanya membawa `quantity_kg`. Tanpa `needed_by`,
  tidak ada dasar untuk menghitung batas kirim.

Rumus (sama dengan rencana Fase 4 butir 6):

    window_min = (needed_by - evaluation_time) - lead_time_min

dijepit ke `0.0`. `lead_time_min` adalah waktu yang habis SEBELUM kendaraan
berjalan (persiapan/muat). Kandidat gugur bila `estimated_time_min` hasil
logistik melebihi `window_min` — dan karena `needed_by` yang sudah lewat
menghasilkan jendela 0, kandidat itu otomatis gugur.

Tiga keadaan yang dibedakan, tidak pernah disamakan:

- ``terpenuhi``      — ada `needed_by` dan anggaran waktunya masih positif;
- ``terlampaui``     — `needed_by` sudah lewat saat evaluasi;
- ``tidak_tercatat`` — tidak ada baris permintaan; jadwal TIDAK diklaim
  terpenuhi (ini alasan modul ini ada: "tidak ada batas" bukan "aman").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

__all__ = [
    "TERPERNUHI",
    "TERLAMPAUI",
    "TIDAK_TERCATAT",
    "JendelaKirim",
    "arrival_due_at",
    "jendela_kirim",
    "muat_terlampaui",
]

TERPERNUHI = "terpenuhi"
TERLAMPAUI = "terlampaui"
TIDAK_TERCATAT = "tidak_tercatat"


@dataclass(frozen=True)
class JendelaKirim:
    """Hasil hitung jendela untuk satu pasangan (sumber, tujuan, komoditas)."""

    needed_by: datetime | None
    window_min: float | None
    state: str

    @property
    def has_bound(self) -> bool:
        """True bila ada batas waktu yang benar-benar diperiksa."""
        return self.state != TIDAK_TERCATAT


def _sadar_zona(nilai: datetime) -> bool:
    return nilai.tzinfo is not None and nilai.tzinfo.utcoffset(nilai) is not None


def jendela_kirim(
    *,
    needed_by: datetime | None,
    evaluation_time: datetime,
    lead_time_min: float = 0.0,
) -> JendelaKirim:
    """Hitung anggaran waktu angkut dari kebutuhan sampai `needed_by`.

    `evaluation_time` wajib dari pemanggil (server), bukan dari UI. Waktu naif
    dan waktu sadar-zona tidak boleh dicampur: perbandingannya akan menghasilkan
    selisih jam yang tampak sah padahal salah zona.
    """
    if lead_time_min < 0:
        raise ValueError("lead_time_min tidak boleh negatif")
    if not isinstance(evaluation_time, datetime):
        raise ValueError("evaluation_time wajib datetime")
    if needed_by is None:
        return JendelaKirim(needed_by=None, window_min=None, state=TIDAK_TERCATAT)
    if not isinstance(needed_by, datetime):
        raise ValueError("needed_by wajib datetime atau None")
    if _sadar_zona(needed_by) != _sadar_zona(evaluation_time):
        raise ValueError(
            "needed_by dan evaluation_time harus sama-sama sadar-zona atau "
            "sama-sama naif"
        )

    anggaran = (needed_by - evaluation_time).total_seconds() / 60.0 - lead_time_min
    if anggaran <= 0:
        return JendelaKirim(needed_by=needed_by, window_min=0.0, state=TERLAMPAUI)
    return JendelaKirim(needed_by=needed_by, window_min=anggaran, state=TERPERNUHI)


def arrival_due_at(evaluation_time: datetime, estimated_time_min: float) -> datetime:
    """Waktu tiba yang harus diuji terhadap `usable_until` batch.

    Sebelum Fase 4, satu-satunya uji umur barang adalah `due_at + 24 jam` milik
    tabel kiriman — angka yang tidak berhubungan dengan lamanya perjalanan.
    """
    if estimated_time_min < 0:
        raise ValueError("estimated_time_min tidak boleh negatif")
    return evaluation_time + timedelta(minutes=float(estimated_time_min))


def muat_terlampaui(jendela: JendelaKirim, *, estimated_time_min: float) -> bool:
    """True bila perjalanan tidak muat dalam jendela.

    Jendela `tidak_tercatat` TIDAK dianggap terlampaui: tidak ada dasar untuk
    menyatakan gugur, dan menganggapnya gugur akan menghapus kandidat hanya
    karena baris permintaan tidak ada. Pemanggil wajib melaporkan keadaan itu
    apa adanya (`state`), bukan menyamakannya dengan "jadwal terpenuhi".
    """
    if jendela.window_min is None:
        return False
    return float(estimated_time_min) > jendela.window_min
