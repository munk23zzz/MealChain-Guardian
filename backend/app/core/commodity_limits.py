"""Batas suhu aman PER KOMODITAS — fasad tipis di atas `core/commodity_policy.py`.

Sejarah (jangan dihapus tanpa membaca `MG/phase-03-commodity-evidence.md`):

- Awalnya modul ini memuat peta `SAFE_TEMP_BY_COMMODITY` (telur/ayam/wortel
  0-8 °C, beras 15-30 °C) plus `DEFAULT_SAFE_TEMP = (0, 8)` untuk komoditas
  lain. Peta itu memperbaiki bug 20 Okt 2026 (`api/safety.py` memakai settings
  global sehingga beras 27 °C dinilai `fail`), tetapi menyisakan tiga masalah
  yang ditutup Fase 3:

  1. **Bawaan 0-8 °C untuk komoditas tak dikenal** — komoditas baru otomatis
     dianggap rantai dingin tanpa dasar apa pun. Sekarang ditolak (`KeyError`).
  2. **Tidak ada `cold_chain_required`** — tidak ada cara menyatakan "komoditas
     ini TIDAK diukur terhadap rentang", hanya rentang lebar (beras 15-30 °C
     masih menuduh suhu ruang 32 °C sebagai excursion).
  3. **Tidak ada versi/dasar kebijakan** — angka demo tidak bisa dibedakan dari
     standar regulasi.

Modul ini tinggal meneruskan ke profil supaya pemanggil lama tidak perlu
berubah serentak; sumber kebenarannya satu (`PROFILES`).
"""

from __future__ import annotations

from app.core.commodity_policy import PROFILES, CommodityPolicy, policy_for

__all__ = [
    "PROFILES",
    "CommodityPolicy",
    "cold_chain_required",
    "policy_for",
    "safe_temp_for",
]


def safe_temp_for(commodity: str | None) -> tuple[float, float] | None:
    """Rentang suhu aman untuk satu komoditas, atau `None` bila ambient.

    `None` BUKAN "tidak tahu": artinya profil komoditas ini memang tidak
    mengukur excursion (mis. beras disimpan pada suhu ruang). Pemanggil yang
    memaksa tuple mendapat `TypeError` — dan itu benar, karena mengarang
    rentang untuk komoditas ambient justru bug yang sedang diperbaiki.
    """
    return policy_for(commodity).temp_band


def cold_chain_required(commodity: str | None) -> bool:
    """True bila komoditas ini wajib punya bukti suhu rantai dingin."""
    return policy_for(commodity).cold_chain_required
