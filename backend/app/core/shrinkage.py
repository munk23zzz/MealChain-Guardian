"""Laju susut gudang per komoditas (revisi 2026-10-29b).

Angka pemilik: beras < 1%, telur 2–5%, sayur 10–20%. Yang dijaga di sini:

1. Rentang pemilik dihormati — bukan angka karangan yang lebih besar dari
   rentangnya, dan bukan satu laju 20% untuk semua komoditas (beras dihukum
   terlalu berat: 20% dari nilai beras untuk susut 180 hari).
2. Komoditas tak terdaftar TIDAK meminjam angka komoditas lain. Ia memakai
   cadangan kontrak lama (20%) dan sumbernya dilaporkan, supaya panel bukti
   bisa mengatakan "laju cadangan", bukan menyamarkannya sebagai angka tabel.
3. Laju adalah fraksi per UMUR SIMPAN penuh, bukan per hari. Pembagian ke hari
   dilakukan mesin SDC (`laju ÷ umur_simpan`), satu tempat.
"""

from decimal import Decimal

__all__ = [
    "DEFAULT_LAJU",
    "LAJU_SUSUT",
    "SUMBER_DEFAULT",
    "SUMBER_TABEL",
    "laju_susut",
]

#: Cadangan = kontrak lama (`_EXPECTED_LOSS_RATE` = 0,2). Hanya dipakai bila
#: komoditas tidak ada di tabel bawah, dan selalu dilaporkan sebagai cadangan.
DEFAULT_LAJU = Decimal("0.2")

SUMBER_TABEL = "tabel_laju_susut_komoditas"
SUMBER_DEFAULT = "laju_default_0.2"

#: Fraksi susut per umur simpan penuh. Rentang pemilik:
#: beras < 1% · telur 2–5% · sayur 10–20%. Ayam (protein segar, umur simpan
#: 5 hari) memakai 12% — di bawah sayur, di atas telur; dicatat sebagai asumsi
#: pemilik "protein segar" karena rentangnya tidak disebut eksplisit.
LAJU_SUSUT: dict[str, Decimal] = {
    "beras": Decimal("0.008"),
    "telur": Decimal("0.040"),
    "wortel": Decimal("0.150"),
    "ayam": Decimal("0.120"),
}


def laju_susut(commodity: str | None) -> tuple[Decimal, str]:
    """`(laju, sumber)` untuk satu komoditas; nama tidak peka huruf/spasi."""
    kunci = (commodity or "").strip().lower()
    nilai = LAJU_SUSUT.get(kunci)
    if nilai is None:
        return DEFAULT_LAJU, SUMBER_DEFAULT
    return nilai, SUMBER_TABEL
