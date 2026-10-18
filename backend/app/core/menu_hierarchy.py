"""Lapis 2 (gizi/menu) dan lapis 3 (kontinuitas makan) dari hierarki keputusan.

Proposal: keamanan → kecukupan gizi/menu → kontinuitas makan → biaya →
pengurangan limbah. Sebelum modul ini, hanya keamanan & kesegaran yang benar-benar
menyaring kandidat; gizi/menu dan kontinuitas hanya tertulis di dokumen.

Dua aturan yang ditegakkan di sini, keduanya deterministik dan bisa diuji:

- **Gizi/menu** — kebutuhan menu (porsi × gram per porsi) adalah LANTAI
  kekurangan destinasi: alokasi tidak boleh berhenti di bawah kebutuhan menunya
  hanya karena angka permintaan historis lebih rendah.
- **Kontinuitas** — sumber hanya mengekspor surplus di atas cadangan
  kontinuitasnya sendiri (porsi × gram × hari cadangan), supaya pengiriman
  antarwilayah tidak memutus makan di daerah asal.

Modul ini murni: gram per porsi dan jumlah hari cadangan datang dari pemanggil
(settings), bukan disimpulkan di sini.
"""

from __future__ import annotations

from decimal import Decimal

__all__ = [
    "cadangan_kontinuitas_kg",
    "kebutuhan_menu_kg",
    "shortage_setelah_gizi",
    "surplus_setelah_kontinuitas",
]


def _nilai(value, label: str) -> Decimal:
    try:
        hasil = Decimal(str(value))
    except Exception as exc:  # noqa: BLE001 - pesan yang jelas lebih berguna
        raise ValueError(f"{label} harus angka, dapat {value!r}") from exc
    if not hasil.is_finite():
        raise ValueError(f"{label} harus berhingga, dapat {value!r}")
    return hasil


def _non_negatif(value, label: str) -> Decimal:
    hasil = _nilai(value, label)
    if hasil < 0:
        raise ValueError(f"{label} tidak boleh negatif, dapat {value!r}")
    return hasil


def kebutuhan_menu_kg(planned_portions, gram_per_porsi) -> Decimal:
    """Kilogram yang dibutuhkan menu satu lokasi untuk satu komoditas.

    `gram_per_porsi = 0` berarti komoditas itu tidak masuk komposisi menu
    (mis. cabai sebagai bumbu) → kebutuhan 0, bukan galat.
    """
    porsi = _non_negatif(planned_portions, "planned_portions")
    gram = _non_negatif(gram_per_porsi, "gram_per_porsi")
    return (porsi * gram / Decimal("1000")).quantize(Decimal("0.01"))


def cadangan_kontinuitas_kg(planned_portions, gram_per_porsi, hari) -> Decimal:
    """Cadangan yang harus tetap tinggal di lokasi asal selama `hari` ke depan."""
    satu_hari = kebutuhan_menu_kg(planned_portions, gram_per_porsi)
    faktor = _non_negatif(hari, "hari")
    return (satu_hari * faktor).quantize(Decimal("0.01"))


def shortage_setelah_gizi(demand_kg, supply_lokal_kg, kebutuhan_menu) -> Decimal:
    """Kekurangan destinasi setelah kebutuhan menu dijadikan lantai.

    Diambil yang TERBESAR antara kekurangan berbasis permintaan dan kekurangan
    berbasis menu. Menu tidak pernah menurunkan kekurangan — ia hanya menaikkan
    ketika permintaan historis tercatat lebih rendah daripada kebutuhan menu.
    """
    permintaan = _non_negatif(demand_kg, "demand_kg")
    stok = _non_negatif(supply_lokal_kg, "supply_lokal_kg")
    menu = _non_negatif(kebutuhan_menu, "kebutuhan_menu")
    return max(permintaan - stok, menu - stok, Decimal("0"))


def surplus_setelah_kontinuitas(supply_kg, demand_lokal_kg, cadangan_kg) -> Decimal:
    """Surplus yang boleh diekspor setelah cadangan kontinuitas dijaga.

    Yang dijaga adalah yang TERBESAR antara permintaan lokal dan cadangan —
    kalau cadangan lebih besar, cadangan itulah lantainya.
    """
    stok = _non_negatif(supply_kg, "supply_kg")
    permintaan = _non_negatif(demand_lokal_kg, "demand_lokal_kg")
    cadangan = _non_negatif(cadangan_kg, "cadangan_kg")
    return max(stok - max(permintaan, cadangan), Decimal("0"))
