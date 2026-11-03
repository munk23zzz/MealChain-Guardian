"""Hierarki keputusan lapis 2 & 3 — gizi/menu dan kontinuitas makan.

Lapis 1 (keamanan) dan kesegaran sudah menyaring kandidat. Dua lapis berikutnya
di proposal — "kecukupan gizi/menu" lalu "kontinuitas makan" — sebelumnya hanya
tertulis di dokumen, tidak menegakkan apa pun. Modul ini menutupnya:

- Lapis 2: kebutuhan menu (porsi × gram per porsi) adalah LANTAI kebutuhan
  destinasi. Kekurangan yang dialokasikan tidak boleh lebih kecil dari kebutuhan
  menunya, walau data permintaan historis lebih rendah.
- Lapis 3: sumber hanya mengekspor surplus di atas cadangan kontinuitasnya
  sendiri, supaya pengiriman antarwilayah tidak memutus makan di daerah asal.
"""

from decimal import Decimal

import pytest

from app.core.menu_hierarchy import (
    cadangan_kontinuitas_kg,
    kebutuhan_menu_kg,
    shortage_setelah_gizi,
    surplus_setelah_kontinuitas,
)


class TestKebutuhanMenu:
    def test_porsi_kali_gram_per_porsi(self):
        # 1000 porsi × 60 g = 60 kg
        assert kebutuhan_menu_kg(1000, 60.0) == Decimal("60")

    def test_tanpa_porsi_berarti_tanpa_kebutuhan(self):
        assert kebutuhan_menu_kg(0, 60.0) == Decimal("0")

    def test_komoditas_tanpa_gram_per_porsi_tidak_menambah_kebutuhan(self):
        assert kebutuhan_menu_kg(1000, 0.0) == Decimal("0")

    def test_porsi_negatif_ditolak(self):
        with pytest.raises(ValueError):
            kebutuhan_menu_kg(-1, 60.0)


class TestCadanganKontinuitas:
    def test_satu_hari_sama_dengan_kebutuhan_menu(self):
        assert cadangan_kontinuitas_kg(1000, 60.0, hari=1) == Decimal("60")

    def test_dua_hari_dua_kali_kebutuhan(self):
        assert cadangan_kontinuitas_kg(1000, 60.0, hari=2) == Decimal("120")

    def test_hari_pecahan_dihitung_proporsional(self):
        assert cadangan_kontinuitas_kg(1000, 60.0, hari=1.5) == Decimal("90")

    def test_hari_negatif_ditolak(self):
        with pytest.raises(ValueError):
            cadangan_kontinuitas_kg(1000, 60.0, hari=-1)


class TestShortageSetelahGizi:
    def test_kebutuhan_menu_menjadi_lantai_kekurangan(self):
        # permintaan historis 100, stok lokal 40 → kekurangan 60;
        # kebutuhan menu 90 juga menghasilkan 50, dan yang dipakai yang
        # TERBESAR: 60. Menu tidak boleh menurunkan kekurangan.
        assert shortage_setelah_gizi(100, 40, 90) == Decimal("60")

    def test_kebutuhan_menu_mendorong_kekurangan_ke_atas(self):
        # permintaan historis rendah (30) tapi menu butuh 90 kg, stok 40
        assert shortage_setelah_gizi(30, 40, 90) == Decimal("50")

    def test_menu_lebih_kecil_dari_permintaan_tidak_menurunkan(self):
        assert shortage_setelah_gizi(100, 40, 10) == Decimal("60")

    def test_stok_lokal_menutup_semua_kebutuhan(self):
        assert shortage_setelah_gizi(100, 200, 90) == Decimal("0")


class TestSurplusSetelahKontinuitas:
    def test_cadangan_mengurangi_surplus(self):
        # stok 1000, permintaan lokal 700, cadangan 200 (di bawah permintaan)
        assert surplus_setelah_kontinuitas(1000, 700, 200) == Decimal("300")

    def test_cadangan_lebih_besar_dari_permintaan_ikut_dijaga(self):
        # permintaan lokal 300, cadangan 500 → ekspor maksimum 500
        assert surplus_setelah_kontinuitas(1000, 300, 500) == Decimal("500")

    def test_cadangan_melebihi_stok_tidak_mengekspor(self):
        assert surplus_setelah_kontinuitas(100, 50, 400) == Decimal("0")

    def test_nilai_negatif_ditolak(self):
        with pytest.raises(ValueError):
            surplus_setelah_kontinuitas(-1, 0, 0)
