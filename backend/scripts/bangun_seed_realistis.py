"""Bangun dataset demo realistis untuk MealChain Guardian (seed 2 berkas JSON).

Kenapa skrip, bukan sunting JSON tangan:
- 60 pemasok x 10 hub + 80 lot batch + 40 pasang harga harus konsisten
  (nama pemasok di batches/prices/PO harus ADA di daftar pemasok, komoditas
  pemasok lokal harus cocok dengan komoditas batch, kode lot harus unik).
- Nilai yang tidak boleh bergeser (jangkar tes: Cianjur telur 1.400 kg,
  Jakarta telur 300 kg, Bogor telur 800 kg, 40 acuan harga, kutipan Cianjur)
  disalin dari berkas LAMA, bukan diketik ulang, supaya tidak melenceng.

Keluaran:
  data/seed/sprint1_seed.json   -> lokasi, komoditas, pemasok kanonik, supply,
                                   demand, harga, batch, stok/PO mock SAP
  data/seed/suppliers_demo.json -> profil pemasok (koordinat, alamat, kapasitas,
                                   kontak) — nama SAMA dengan daftar kanonik

Provenance: nama usaha, nama orang, dan alamat di berkas keluaran adalah
KARANGAN yang ditata mengikuti pasar induk / sentra produksi NYATA per kota
(Pasar Induk Kramat Jati, Pasar Induk Caringin, Pasar Terong, Pasar Induk
Jakabaring, Bandungan, Lembang, Berastagi, Malino, Maros, dst). Bukan
perusahaan atau orang nyata, jangan dipakai sebagai rujukan faktual.

Jalankan (dari akar repo, python apa pun >= 3.10, tanpa dependensi):
  python backend/scripts/bangun_seed_realistis.py
"""

from __future__ import annotations

import json
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "data" / "seed" / "sprint1_seed.json"
SUPPLIERS_PATH = ROOT / "data" / "seed" / "suppliers_demo.json"

# Tanggal acuan penamaan lot (mengikuti REF kanonik dataset 2026-10-08).
REF_DATE = date(2026, 10, 8)

CITY_CODE = {
    "Jakarta": "JKT",
    "Bogor": "BGR",
    "Cianjur": "CJR",
    "Bandung": "BDG",
    "Semarang": "SMG",
    "Yogyakarta": "YOG",
    "Surabaya": "SBY",
    "Makassar": "MKS",
    "Palembang": "PLM",
    "Medan": "MDN",
}

PLANT_CODE = {
    "Jakarta": "JKRTA",
    "Bogor": "BOGOR",
    "Cianjur": "CIANJ",
    "Bandung": "BDNG",
    "Semarang": "SMGG",
    "Yogyakarta": "YGYK",
    "Surabaya": "SRBY",
    "Makassar": "MKSR",
    "Palembang": "PLBG",
    "Medan": "MDAN",
}

COMMODITY_CODE = {"telur": "TLR", "ayam": "AYM", "wortel": "WRT", "beras": "BRS"}
MATERIAL_NUMBER = {"telur": "1000", "ayam": "1001", "wortel": "1002", "beras": "1003"}

# Suhu penyimpanan wajar per komoditas: barang kering TIDAK boleh dinilai
# dengan rentang dingin (akan tampak seperti penyimpangan padahal benar).
SAFE_TEMP = {
    "telur": (3.2, 5.5),
    "ayam": (1.5, 4.5),
    "wortel": (2.0, 6.0),
    "beras": (26.0, 28.0),
}

# ---------------------------------------------------------------------------
# Pemasok: 60 usaha, tersebar 5-13 per hub, SEMUA berada di sekitar hub-nya.
# Nama usaha sengaja bervariasi bentuknya (PT/CV/UD/PD/Koperasi) dan memuat
# nama pasar induk / sentra produksi nyata di kota itu.
# ---------------------------------------------------------------------------
SUPPLIERS = [
    # --- Hub Jakarta (DKI Jakarta + penyangga, semua < 150 km) -------------
    dict(name="CV Cipinang Boga Utama", location="Jakarta", commodity="beras",
         reliability_score=0.87, capacity_kg_per_week=6000, certification_status="haccp",
         contact_name="Budi Santoso",
         address="Pasar Induk Beras Cipinang, Jl. Raya Bekasi Timur Km 18, "
                 "Jakarta Timur",
         latitude=-6.2246, longitude=106.8872),
    dict(name="Toko Sayur Bu Endang", location="Jakarta", commodity="wortel",
         reliability_score=0.82, capacity_kg_per_week=3000, certification_status="hygiene",
         contact_name="Bambang Prasetyo",
         address="Pasar Induk Kramat Jati Blok C-07, Jakarta Timur",
         latitude=-6.2712, longitude=106.8752),
    dict(name="PT Nusantara Prima Ayam", location="Jakarta", commodity="ayam",
         reliability_score=0.44, capacity_kg_per_week=1500, certification_status="none",
         contact_name="Hendra Wijaya", address="Jl. Daan Mogot Km 18, Cengkareng, Jakarta Barat",
         latitude=-6.1500, longitude=106.7350),
    dict(name="UD Sumber Rejeki Telur", location="Jakarta", commodity="telur",
         reliability_score=0.89, capacity_kg_per_week=3200, certification_status="haccp",
         contact_name="Siti Aminah", address="Jl. Raya Bekasi Km 25, Jakarta Timur",
         latitude=-6.2383, longitude=106.9896),
    dict(name="CV Berkah Telur Bekasi", location="Jakarta", commodity="telur",
         reliability_score=0.85, capacity_kg_per_week=2100, certification_status="hygiene",
         contact_name="Yusuf Hidayat", address="Jl. Raya Bekasi Km 27, Bekasi Timur",
         latitude=-6.2500, longitude=107.0000),
    dict(name="UD Tani Sayur Depok", location="Jakarta", commodity="wortel",
         reliability_score=0.80, capacity_kg_per_week=1700, certification_status="hygiene",
         contact_name="Rina Astuti", address="Jl. Margonda Raya No. 312, Depok",
         latitude=-6.4025, longitude=106.7942),
    dict(name="PT Tangerang Ayam Sentosa", location="Jakarta", commodity="ayam",
         reliability_score=0.79, capacity_kg_per_week=1900, certification_status="hygiene",
         contact_name="Rudi Hartono", address="Jl. Raya Cikupa No. 21, Kabupaten Tangerang",
         latitude=-6.1783, longitude=106.6319),
    dict(name="CV Karawang Ayam Jaya", location="Jakarta", commodity="ayam",
         reliability_score=0.86, capacity_kg_per_week=2200, certification_status="haccp",
         contact_name="Asep Sunandar", address="Kawasan Industri KIIC, Karawang Barat",
         latitude=-6.3015, longitude=107.3060),
    dict(name="UD H. Ujang Serang", location="Jakarta", commodity="ayam",
         reliability_score=0.87, capacity_kg_per_week=2000, certification_status="hygiene",
         contact_name="Dedi Kurniawan", address="Jl. Raya Serang-Jakarta Km 8, Serang",
         latitude=-6.1100, longitude=106.1500),
    dict(name="CV Hortikultura Subang Lestari", location="Jakarta", commodity="wortel",
         reliability_score=0.90, capacity_kg_per_week=2800, certification_status="haccp",
         contact_name="Iwan Setiawan", address="Kp. Cibogo, Kecamatan Cibogo, Subang",
         latitude=-6.5716, longitude=107.7583),
    dict(name="UD Puncak Sayur Asri", location="Jakarta", commodity="wortel",
         reliability_score=0.83, capacity_kg_per_week=2100, certification_status="hygiene",
         contact_name="Agus Salim", address="Jl. Raya Puncak Km 82, Cisarua, Bogor",
         latitude=-6.7000, longitude=106.9400),
    dict(name="CV Cengkareng Protein Mandiri", location="Jakarta", commodity="telur",
         reliability_score=0.76, capacity_kg_per_week=1600, certification_status="none",
         contact_name="Herman Susanto", address="Jl. Daan Mogot Km 17, Cengkareng, Jakarta Barat",
         latitude=-6.1550, longitude=106.7400),
    dict(name="UD Rorotan Jaya Beras", location="Jakarta", commodity="beras",
         reliability_score=0.86, capacity_kg_per_week=4200, certification_status="haccp",
         contact_name="Suryadi Pratama", address="Pasar Induk Rorotan Blok F-11, Jakarta Utara",
         latitude=-6.1500, longitude=106.9300),
    # --- Hub Bogor ---------------------------------------------------------
    dict(name="CV Beras Sari Bogor", location="Bogor", commodity="beras",
         reliability_score=0.89, capacity_kg_per_week=3800, certification_status="hygiene",
         contact_name="Nunung Hasanah", address="Jl. Raya Pajajaran No. 88, Bogor Utara",
         latitude=-6.5700, longitude=106.8000),
    dict(name="PT Bogor Prima Ayam", location="Bogor", commodity="ayam",
         reliability_score=0.91, capacity_kg_per_week=1350, certification_status="haccp",
         contact_name="Dedi Mulyadi", address="Jl. Raya Cibinong No. 45, Kabupaten Bogor",
         latitude=-6.4900, longitude=106.8400),
    dict(name="UD Cibinong Telur Berkah", location="Bogor", commodity="telur",
         reliability_score=0.87, capacity_kg_per_week=2400, certification_status="hygiene",
         contact_name="Euis Komariah", address="Jl. Raya Cibinong No. 45, Cibinong",
         latitude=-6.4800, longitude=106.8500),
    dict(name="CV Puncak Sayur Sejahtera", location="Bogor", commodity="wortel",
         reliability_score=0.86, capacity_kg_per_week=2600, certification_status="hygiene",
         contact_name="Wawan Hermawan", address="Jl. Raya Puncak Km 78, Cisarua",
         latitude=-6.7050, longitude=106.9350),
    dict(name="PD Cibinong Beras Mandiri", location="Bogor", commodity="beras",
         reliability_score=0.52, capacity_kg_per_week=1800, certification_status="none",
         contact_name="Sugeng Riyadi", address="Jl. Raya Jakarta-Bogor Km 42, Cibinong",
         latitude=-6.4700, longitude=106.8300),
    # --- Hub Cianjur (sentra telur & beras Pandan Wangi) -------------------
    dict(name="CV Pandan Wangi Cianjur", location="Cianjur", commodity="beras",
         reliability_score=0.94, capacity_kg_per_week=5200, certification_status="haccp",
         contact_name="Asep Saepudin", address="Jl. Raya Bandung Km 5, Cianjur",
         latitude=-6.8300, longitude=107.1300),
    dict(name="Koperasi Telur Cipanas Bersama", location="Cianjur", commodity="telur",
         reliability_score=0.92, capacity_kg_per_week=3600, certification_status="haccp",
         contact_name="Dadang Hermawan", address="Jl. Raya Cipanas No. 176, Cianjur",
         latitude=-6.7400, longitude=107.0400),
    dict(name="UD H. Asep Cianjur", location="Cianjur", commodity="telur",
         reliability_score=0.88, capacity_kg_per_week=2400, certification_status="hygiene",
         contact_name="Neneng Suhartini", address="Jl. Raya Bandung Km 7, Cianjur",
         latitude=-6.8350, longitude=107.1350),
    dict(name="CV Barokah Telur Cianjur", location="Cianjur", commodity="telur",
         reliability_score=0.85, capacity_kg_per_week=2000, certification_status="hygiene",
         contact_name="Ujang Suryana", address="Jl. Raya Cugenang No. 21, Cianjur",
         latitude=-6.8100, longitude=107.1000),
    dict(name="UD Cipanas Telur Sejahtera", location="Cianjur", commodity="telur",
         reliability_score=0.43, capacity_kg_per_week=2200, certification_status="none",
         contact_name="Ujang Solihin", address="Jl. Raya Cipanas Km 9, Cianjur",
         latitude=-6.7450, longitude=107.0450),
    dict(name="CV Ayam Kampung Cugenang", location="Cianjur", commodity="ayam",
         reliability_score=0.81, capacity_kg_per_week=1800, certification_status="none",
         contact_name="Iwan Gunawan", address="Kp. Cibeureum, Cugenang, Cianjur",
         latitude=-6.8000, longitude=107.0800),
    dict(name="CV Lestari Sayur Cugenang", location="Cianjur", commodity="wortel",
         reliability_score=0.85, capacity_kg_per_week=3000, certification_status="hygiene",
         contact_name="Wawan Setiana", address="Kp. Cibeureum, Cugenang, Cianjur",
         latitude=-6.8050, longitude=107.0750),
    # --- Hub Bandung -------------------------------------------------------
    dict(name="CV Lembang Sayur Makmur", location="Bandung", commodity="wortel",
         reliability_score=0.88, capacity_kg_per_week=2600, certification_status="hygiene",
         contact_name="Yayat Ruhiyat", address="Kp. Cikahuripan, Lembang, Bandung Barat",
         latitude=-6.8300, longitude=107.6200),
    dict(name="UD Caringin Sayur Induk", location="Bandung", commodity="wortel",
         reliability_score=0.84, capacity_kg_per_week=3200, certification_status="hygiene",
         contact_name="Asep Hidayat", address="Pasar Induk Caringin Blok B, Bandung",
         latitude=-6.9200, longitude=107.5800),
    dict(name="UD Rancaekek Beras Sejahtera", location="Bandung", commodity="beras",
         reliability_score=0.86, capacity_kg_per_week=2800, certification_status="hygiene",
         contact_name="Entis Sutisna", address="Jl. Raya Rancaekek No. 21, Kabupaten Bandung",
         latitude=-6.9700, longitude=107.7600),
    dict(name="CV Lembang Telur Segar", location="Bandung", commodity="telur",
         reliability_score=0.85, capacity_kg_per_week=2200, certification_status="hygiene",
         contact_name="Lilis Suryani", address="Jl. Raya Lembang No. 88, Bandung Barat",
         latitude=-6.8100, longitude=107.6100),
    dict(name="PT Cileunyi Ayam Segar", location="Bandung", commodity="ayam",
         reliability_score=0.89, capacity_kg_per_week=2000, certification_status="haccp",
         contact_name="Dadang Kurnia", address="Jl. Raya Cileunyi No. 12, Kabupaten Bandung",
         latitude=-6.9300, longitude=107.7000),
    # --- Hub Semarang ------------------------------------------------------
    dict(name="CV Bandungan Sayur Lestari", location="Semarang", commodity="wortel",
         reliability_score=0.92, capacity_kg_per_week=2300, certification_status="haccp",
         contact_name="Sutrisno", address="Desa Bandungan, Kabupaten Semarang",
         latitude=-7.2100, longitude=110.3700),
    dict(name="UD Demak Beras Makmur", location="Semarang", commodity="beras",
         reliability_score=0.84, capacity_kg_per_week=3000, certification_status="hygiene",
         contact_name="Sri Wahyuni", address="Jl. Raya Demak No. 45, Kabupaten Demak",
         latitude=-6.8900, longitude=110.6400),
    dict(name="CV Ambarawa Telur Utama", location="Semarang", commodity="telur",
         reliability_score=0.86, capacity_kg_per_week=2200, certification_status="hygiene",
         contact_name="Joko Purnomo", address="Jl. Raya Ambarawa No. 9, Kabupaten Semarang",
         latitude=-7.2600, longitude=110.4000),
    dict(name="CV Kendal Ayam Utama", location="Semarang", commodity="ayam",
         reliability_score=0.83, capacity_kg_per_week=1800, certification_status="hygiene",
         contact_name="Bambang Sutopo", address="Jl. Raya Kendal Km 8, Kabupaten Kendal",
         latitude=-6.9500, longitude=110.2300),
    dict(name="UD Johar Beras Semarang", location="Semarang", commodity="beras",
         reliability_score=0.79, capacity_kg_per_week=1600, certification_status="hygiene",
         contact_name="Tono Susilo", address="Pasar Johar, Semarang Tengah",
         latitude=-6.9700, longitude=110.4300),
    # --- Hub Yogyakarta ----------------------------------------------------
    dict(name="CV Kaliurang Sayur Lestari", location="Yogyakarta", commodity="wortel",
         reliability_score=0.94, capacity_kg_per_week=1900, certification_status="haccp",
         contact_name="Wagiman", address="Jl. Kaliurang Km 21, Sleman",
         latitude=-7.6000, longitude=110.4200),
    dict(name="UD Bantul Beras Utama", location="Yogyakarta", commodity="beras",
         reliability_score=0.86, capacity_kg_per_week=2600, certification_status="hygiene",
         contact_name="Suparmi", address="Jl. Raya Bantul Km 5, Bantul",
         latitude=-7.8900, longitude=110.3300),
    dict(name="CV Sleman Telur Lestari", location="Yogyakarta", commodity="telur",
         reliability_score=0.85, capacity_kg_per_week=2000, certification_status="hygiene",
         contact_name="Triyono", address="Jl. Raya Sleman No. 18, Sleman",
         latitude=-7.7200, longitude=110.3500),
    dict(name="PT Kulon Progo Ayam Jaya", location="Yogyakarta", commodity="ayam",
         reliability_score=0.90, capacity_kg_per_week=1600, certification_status="haccp",
         contact_name="Sarjono", address="Jl. Raya Wates Km 12, Kulon Progo",
         latitude=-7.8600, longitude=110.1500),
    dict(name="UD Giwangan Sayur Pasar", location="Yogyakarta", commodity="wortel",
         reliability_score=0.87, capacity_kg_per_week=2400, certification_status="hygiene",
         contact_name="Yuni Astuti", address="Pasar Induk Giwangan, Yogyakarta",
         latitude=-7.8300, longitude=110.3900),
    # --- Hub Surabaya ------------------------------------------------------
    dict(name="UD Surabaya Telur Jaya", location="Surabaya", commodity="telur",
         reliability_score=0.62, capacity_kg_per_week=2600, certification_status="none",
         contact_name="Hartono", address="Jl. Kedung Cowek No. 145, Surabaya",
         latitude=-7.2200, longitude=112.7600),
    dict(name="CV Keputran Sayur Utama", location="Surabaya", commodity="wortel",
         reliability_score=0.89, capacity_kg_per_week=2800, certification_status="hygiene",
         contact_name="Suharto", address="Pasar Keputran Blok A, Surabaya",
         latitude=-7.2600, longitude=112.7400),
    dict(name="PT Osowilangun Beras Utama", location="Surabaya", commodity="beras",
         reliability_score=0.87, capacity_kg_per_week=4200, certification_status="haccp",
         contact_name="Heny Kusuma", address="Pasar Induk Osowilangun, Surabaya",
         latitude=-7.2200, longitude=112.6800),
    dict(name="UD Blitar Telur Makmur", location="Surabaya", commodity="telur",
         reliability_score=0.80, capacity_kg_per_week=3000, certification_status="hygiene",
         contact_name="Slamet Riyadi", address="Jl. Raya Blitar No. 76, Kota Blitar",
         latitude=-8.1000, longitude=112.1600),
    dict(name="CV Sidoarjo Ayam Utama", location="Surabaya", commodity="ayam",
         reliability_score=0.88, capacity_kg_per_week=2400, certification_status="haccp",
         contact_name="Eko Prasetyo", address="Jl. Raya Sidoarjo No. 33, Sidoarjo",
         latitude=-7.4500, longitude=112.7000),
    # --- Hub Medan ---------------------------------------------------------
    dict(name="CV Berastagi Sayur Makmur", location="Medan", commodity="wortel",
         reliability_score=0.86, capacity_kg_per_week=2400, certification_status="hygiene",
         contact_name="Rudi Sinaga", address="Jl. Raya Berastagi, Kabupaten Karo",
         latitude=3.1900, longitude=98.5100),
    dict(name="CV Deli Serdang Beras", location="Medan", commodity="beras",
         reliability_score=0.85, capacity_kg_per_week=3200, certification_status="hygiene",
         contact_name="Jonni Siregar", address="Jl. Raya Lubuk Pakam No. 21, Deli Serdang",
         latitude=3.5600, longitude=98.8800),
    dict(name="UD Medan Telur Sumber", location="Medan", commodity="telur",
         reliability_score=0.78, capacity_kg_per_week=2000, certification_status="hygiene",
         contact_name="Mariani", address="Jl. Willem Iskandar No. 15, Medan",
         latitude=3.6100, longitude=98.7000),
    dict(name="PT Sunggal Ayam Utama", location="Medan", commodity="ayam",
         reliability_score=0.88, capacity_kg_per_week=1800, certification_status="haccp",
         contact_name="Ahmad Fauzi", address="Jl. Raya Sunggal Km 9, Deli Serdang",
         latitude=3.6100, longitude=98.6300),
    dict(name="UD Pusat Pasar Beras", location="Medan", commodity="beras",
         reliability_score=0.47, capacity_kg_per_week=1400, certification_status="none",
         contact_name="Lina Marlina", address="Pusat Pasar, Medan Kota",
         latitude=3.5900, longitude=98.6800),
    # --- Hub Palembang -----------------------------------------------------
    dict(name="CV Kenten Sayur Asri", location="Palembang", commodity="wortel",
         reliability_score=0.66, capacity_kg_per_week=1400, certification_status="hygiene",
         contact_name="Andi Saputra", address="Jl. Raya Kenten No. 12, Palembang",
         latitude=-2.9600, longitude=104.7600),
    dict(name="UD Ogan Ilir Beras", location="Palembang", commodity="beras",
         reliability_score=0.83, capacity_kg_per_week=2600, certification_status="hygiene",
         contact_name="Hasan Basri", address="Jl. Raya Indralaya Km 18, Ogan Ilir",
         latitude=-3.2200, longitude=104.6500),
    dict(name="CV Palembang Telur Makmur", location="Palembang", commodity="telur",
         reliability_score=0.74, capacity_kg_per_week=1600, certification_status="none",
         contact_name="Yuliana", address="Pasar 16 Ilir, Palembang",
         latitude=-2.9900, longitude=104.7600),
    dict(name="PT Banyuasin Ayam Jaya", location="Palembang", commodity="ayam",
         reliability_score=0.81, capacity_kg_per_week=1600, certification_status="hygiene",
         contact_name="Ahmadi", address="Jl. Raya Banyuasin Km 22, Banyuasin",
         latitude=-3.0500, longitude=104.8500),
    dict(name="CV Jakabaring Sayur", location="Palembang", commodity="wortel",
         reliability_score=0.84, capacity_kg_per_week=2200, certification_status="hygiene",
         contact_name="Dewi Sartika", address="Pasar Induk Jakabaring, Palembang",
         latitude=-3.0100, longitude=104.7900),
    # --- Hub Makassar ------------------------------------------------------
    dict(name="CV Malino Sayur Segar", location="Makassar", commodity="wortel",
         reliability_score=0.95, capacity_kg_per_week=2500, certification_status="haccp",
         contact_name="Syamsul Bahri", address="Malino, Kabupaten Gowa, Sulawesi Selatan",
         latitude=-5.2533, longitude=119.8539),
    dict(name="UD Maros Beras Lestari", location="Makassar", commodity="beras",
         reliability_score=0.85, capacity_kg_per_week=2800, certification_status="hygiene",
         contact_name="Nurhayati", address="Jl. Raya Maros Km 15, Kabupaten Maros",
         latitude=-5.0100, longitude=119.5800),
    dict(name="CV Gowa Telur Segar", location="Makassar", commodity="telur",
         reliability_score=0.81, capacity_kg_per_week=2000, certification_status="hygiene",
         contact_name="Hasanuddin", address="Jl. Raya Gowa No. 24, Kabupaten Gowa",
         latitude=-5.2000, longitude=119.4500),
    dict(name="PT Malino Ayam Segar", location="Makassar", commodity="ayam",
         reliability_score=0.87, capacity_kg_per_week=1800, certification_status="haccp",
         contact_name="Andi Baso", address="Jl. Raya Malino Km 30, Kabupaten Gowa",
         latitude=-5.2600, longitude=119.5700),
    dict(name="UD Pasar Terong Sayur", location="Makassar", commodity="wortel",
         reliability_score=0.88, capacity_kg_per_week=2400, certification_status="hygiene",
         contact_name="Fatimah", address="Pasar Terong, Makassar",
         latitude=-5.1300, longitude=119.4200),
]

# Kutipan pemasok yang HARUS persis (dikunci tes): Cianjur telur + beras.
QUOTE_ANCHOR = {
    ("Cianjur", "telur", "Koperasi Telur Cipanas Bersama"): 26200,
    ("Cianjur", "telur", "UD H. Asep Cianjur"): 27000,
    ("Cianjur", "telur", "UD Cipanas Telur Sejahtera"): 32000,
    ("Cianjur", "telur", "CV Barokah Telur Cianjur"): 25400,
    ("Cianjur", "beras", "CV Pandan Wangi Cianjur"): 12200,
}

# Faktor kutipan pemasok terhadap acuan pasar (realistis: pemasok lokal
# biasanya 2-12% di atas acuan, kadang di bawah untuk panen raya).
QUOTE_FACTOR = {
    "telur": [1.00, 1.02, 1.05, 1.09],
    "ayam": [0.97, 1.00, 1.03],
    "wortel": [0.96, 1.00, 1.06, 1.12],
    "beras": [0.98, 1.02, 1.06],
}

# Profil kesegaran/keamanan per pasangan (narasi demo yang sudah dikunci tes
# dan dokumentasi: Jakarta ayam gagal aman, Semarang ayam gagal segar,
# Palembang telur gagal segar, Surabaya telur penyimpangan suhu).
PAIR_PROFILE = {
    ("Jakarta", "ayam"): "safety_fail",
    ("Surabaya", "telur"): "safety_fail",
    ("Semarang", "ayam"): "freshness_fail",
    ("Palembang", "telur"): "freshness_fail",
    ("Bandung", "telur"): "needs_verification",
    ("Medan", "ayam"): "pending",
    ("Makassar", "wortel"): "needs_verification",
}

HARVEST_OFFSET_HOURS = {-1: -18, -2: -42}  # lot ke-1, lot ke-2

DEMAND_TAMBAHAN = {
    ("Cianjur", "telur"): [700, 720, 690, 710, 730, 705, 715],
    ("Cianjur", "ayam"): [260, 250, 265, 255, 270, 260, 268],
    ("Cianjur", "wortel"): [420, 430, 415, 425, 440, 430, 435],
    ("Cianjur", "beras"): [1100, 1120, 1090, 1110, 1130, 1105, 1115],
    ("Bandung", "telur"): [520, 540, 510, 530, 545, 525, 538],
    ("Bandung", "ayam"): [300, 295, 305, 300, 310, 302, 308],
    ("Bandung", "wortel"): [380, 390, 375, 385, 395, 388, 392],
    ("Bandung", "beras"): [950, 970, 940, 960, 975, 955, 965],
}


def slug(name: str) -> str:
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()


#: Titik pusat hub — dipakai HANYA untuk mengurutkan pemasok menurut jarak,
#: supaya lot yang harus "di jalan" datang dari pemasok terjauh (rutenya cukup
#: panjang untuk memperagakan progres, bukan 0% lalu langsung tiba).
HUB_COORDS = {
    "Jakarta": (-6.2088, 106.8456),
    "Bogor": (-6.5950, 106.8166),
    "Cianjur": (-6.8420, 107.1426),
    "Bandung": (-6.9175, 107.6191),
    "Semarang": (-6.9667, 110.4167),
    "Yogyakarta": (-7.7956, 110.3695),
    "Surabaya": (-7.2575, 112.7521),
    "Makassar": (-5.1477, 119.4327),
    "Palembang": (-2.9761, 104.7754),
    "Medan": (3.5952, 98.6722),
}

#: Rencana perjalanan Jakarta, dalam MENIT relatif REF (negatif = sudah lewat).
#: Dikunci `tests/test_seed_jakarta_journey_states.py`: tiga keadaan harus ada
#: saat seed, tepat SATU "di jalan" dengan progres terbaca (0,15-0,50) dan sisa
#: >= 45 menit. Karena itu lot wortel (pemasok terjauh, Subang ~60 km -> ~84
#: menit) berangkat -28 menit; sisanya sudah tiba atau belum berangkat.
JAKARTA_DISPATCH_MIN: dict[tuple[str, int], int | None] = {
    ("ayam", 1): None,      # belum berangkat
    ("ayam", 2): -185,      # sudah tiba
    ("beras", 1): -185,     # sudah tiba
    ("beras", 2): -180,     # sudah tiba
    ("telur", 1): -200,     # sudah tiba
    ("telur", 2): -190,     # sudah tiba
    ("wortel", 1): -28,     # DI JALAN (satu-satunya)
    ("wortel", 2): -190,    # sudah tiba
}


def _jarak_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a))


def supplier_for(city: str, commodity: str) -> list[dict]:
    return [
        s for s in SUPPLIERS
        if s["location"] == city and s["commodity"] == commodity
    ]


def band(score: float) -> str:
    if score >= 0.85:
        return "pass"
    if score >= 0.60:
        return "needs_verification"
    return "fail"


def temperature_log(commodity: str, profile: str, harvest_hours: float) -> list[dict]:
    lo, hi = SAFE_TEMP[commodity]
    mid = round((lo + hi) / 2, 1)
    points = [
        (harvest_hours, mid),
        (harvest_hours + 6, round(mid + 0.3, 1)),
        (harvest_hours + 18, round(mid - 0.2, 1)),
    ]
    if profile == "safety_fail":
        # Satu titik penyimpangan: barang dingin naik ke 10-13 C, beras lembap 34 C.
        menyimpang = 11.8 if commodity != "beras" else 34.0
        points[1] = (harvest_hours + 7, menyimpang)
    return [
        {"timestamp_offset_hours": h, "temperature_c": t} for h, t in points
    ]


def build_batches(base: dict) -> list[dict]:
    batches: list[dict] = []
    supply_qty = {(s["location"], s["commodity"]): float(s["quantity_kg"]) for s in base["supply"]}
    commodity_shelf = {c["name"]: c["shelf_life_days"] for c in base["commodities"]}

    for (city, commodity), total_qty in sorted(
        supply_qty.items(), key=lambda kv: (kv[0][1], kv[0][0])
    ):
        kandidat = supplier_for(city, commodity)
        if not kandidat:
            raise SystemExit(f"Tidak ada pemasok lokal {commodity} di {city}")
        if city == "Jakarta":
            # Terjauh lebih dulu: lot 1 Jakarta yang dipakai memperagakan
            # "di jalan" harus punya rute panjang (lihat JAKARTA_DISPATCH_MIN).
            hub_lat, hub_lon = HUB_COORDS[city]
            kandidat = sorted(
                kandidat,
                key=lambda s: _jarak_km(
                    s["latitude"], s["longitude"], hub_lat, hub_lon
                ),
                reverse=True,
            )
        profile = PAIR_PROFILE.get((city, commodity), "pass")
        # Dua lot per pasangan: lot pertama mengikuti profil, lot kedua sehat —
        # stok nyata jarang seragam statusnya.
        profil_lot = [profile, "pass"]
        potongan = [round(total_qty * 0.6), total_qty - round(total_qty * 0.6)]
        if potongan[1] < 50:  # stok kecil -> satu lot saja
            potongan = [total_qty]
            profil_lot = [profile]

        for i, (qty, prof) in enumerate(zip(potongan, profil_lot), start=1):
            sup = kandidat[(i - 1) % len(kandidat)]
            score = {
                "pass": 0.90 + 0.02 * ((i + len(city)) % 4),
                "needs_verification": 0.66 + 0.03 * (i % 4),
                "freshness_fail": 0.38 + 0.04 * (i % 3),
                "safety_fail": 0.88,
                "pending": 0.91,
            }[prof]
            harvest = HARVEST_OFFSET_HOURS.get(-i, -42)
            dispatch = None if (i == 2 and (i + len(city)) % 3 == 0) else harvest + 2.5
            if city == "Jakarta":
                rencana = JAKARTA_DISPATCH_MIN.get((commodity, i), harvest + 2.5)
                dispatch = None if rencana is None else rencana / 60.0
            if prof == "safety_fail":
                safety = "fail"
            elif prof == "pending":
                safety = "pending"
            else:
                safety = "pass"
            code = (
                f"{CITY_CODE[city]}-{COMMODITY_CODE[commodity]}-"
                f"{REF_DATE:%Y%m%d}-{i:02d}"
            )
            batches.append(
                {
                    "code": code,
                    "location": city,
                    "commodity": commodity,
                    "supplier": sup["name"],
                    "quantity_kg": qty,
                    "harvested_at_offset_hours": harvest,
                    "dispatch_offset_hours": dispatch,
                    "shelf_life_days": commodity_shelf[commodity],
                    "freshness_score": round(score, 2),
                    "freshness_status": band(round(score, 2)),
                    "safety_status": safety,
                    "temperature_log": temperature_log(commodity, prof, harvest),
                    "certification_status": sup["certification_status"],
                }
            )
    return batches


def build_prices(base: dict) -> list[dict]:
    refs = [p for p in base["prices"] if p["source"] == "pihps_reference"]
    ref_by_pair = {(p["location"], p["commodity"]): float(p["price_per_kg"]) for p in refs}

    quotes: list[dict] = []
    for (city, commodity), harga in sorted(ref_by_pair.items()):
        kandidat = supplier_for(city, commodity)
        if not kandidat:
            raise SystemExit(f"Tidak ada pemasok lokal {commodity} di {city} untuk kutipan")
        for i, sup in enumerate(kandidat):
            anchor = QUOTE_ANCHOR.get((city, commodity, sup["name"]))
            if anchor is not None:
                harga_kutipan = anchor
            else:
                faktor = QUOTE_FACTOR[commodity][i % len(QUOTE_FACTOR[commodity])]
                harga_kutipan = int(round(harga * faktor / 100.0) * 100)
            quotes.append(
                {
                    "location": city,
                    "commodity": commodity,
                    "source": "supplier_quote",
                    "supplier": sup["name"],
                    "price_per_kg": harga_kutipan,
                }
            )
    return refs + quotes


def build_demand(base: dict) -> list[dict]:
    existing = {(d["location"], d["commodity"]): d for d in base["demand"]}
    for key, obs in DEMAND_TAMBAHAN.items():
        existing.setdefault(
            key,
            {
                "location": key[0],
                "commodity": key[1],
                "observations_kg": obs,
                "interval_days": 7,
                "needed_by_offset_days": 3,
            },
        )
    return list(existing.values())


def build_mock_sap(base: dict, batches: list[dict]) -> dict:
    stock: list[dict] = []
    lot_pertama = {}
    for b in batches:
        lot_pertama.setdefault((b["location"], b["commodity"]), b["code"])

    for s in base["supply"]:
        key = (s["location"], s["commodity"])
        stock.append(
            {
                "material_number": MATERIAL_NUMBER[s["commodity"]],
                "plant": PLANT_CODE[s["location"]],
                "storage_location": "FG01",
                "batch": lot_pertama[key],
                "quantity": s["quantity_kg"],
                "unit": "KG",
            }
        )

    po: list[dict] = []
    nomor = 4500000001
    # PO kanonik pertama WAJIB tetap 4500000001 / Cianjur telur (dipakai tes SAP).
    po.append(
        {
            "po_number": str(nomor),
            "supplier": "Koperasi Telur Cipanas Bersama",
            "material_number": MATERIAL_NUMBER["telur"],
            "ordered_quantity": 500,
            "price": 26200,
            "status": "confirmed",
        }
    )
    pola = [
        ("Bogor", "beras", 700, "confirmed"),
        ("Jakarta", "wortel", 400, "confirmed"),
        ("Bandung", "ayam", 300, "confirmed"),
        ("Semarang", "beras", 600, "confirmed"),
        ("Yogyakarta", "wortel", 350, "confirmed"),
        ("Surabaya", "telur", 800, "confirmed"),
        ("Medan", "beras", 500, "submitted"),
        ("Palembang", "wortel", 300, "confirmed"),
        ("Makassar", "beras", 450, "confirmed"),
        ("Cianjur", "ayam", 250, "confirmed"),
        ("Jakarta", "telur", 300, "submitted"),
    ]
    for city, commodity, qty, status in pola:
        nomor += 1
        sup = supplier_for(city, commodity)[0]
        harga = next(
            q["price_per_kg"]
            for q in build_prices(base)
            if q["location"] == city
            and q["commodity"] == commodity
            and q["source"] == "supplier_quote"
        )
        po.append(
            {
                "po_number": str(nomor),
                "supplier": sup["name"],
                "material_number": MATERIAL_NUMBER[commodity],
                "ordered_quantity": qty,
                "price": harga,
                "status": status,
            }
        )
    return {"material_stock": stock, "purchase_orders": po}


def main() -> None:
    base = json.loads(SEED_PATH.read_text(encoding="utf-8"))

    batches = build_batches(base)
    prices = build_prices(base)
    demand = build_demand(base)
    mock_sap = build_mock_sap(base, batches)

    seed = {
        "locations": base["locations"],
        "commodities": base["commodities"],
        "suppliers": [
            {
                "name": s["name"],
                "location": s["location"],
                "reliability_score": s["reliability_score"],
            }
            for s in SUPPLIERS
        ],
        "supply": base["supply"],
        "demand": demand,
        "batches": batches,
        "prices": prices,
        "mock_sap": mock_sap,
    }
    SEED_PATH.write_text(
        json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    demo = {
        "_meta": {
            "purpose": (
                "Profil pemasok demo: nama usaha, alamat, kontak, kapasitas, dan "
                "koordinat untuk 60 pemasok lokal di 10 hub SPPG."
            ),
            "provenance": (
                "SINTETIS. Nama usaha, nama orang, dan alamat KARANGAN, ditata "
                "mengikuti pasar induk/sentra produksi NYATA per kota (Kramat Jati, "
                "Cipinang, Caringin, Keputran, Osowilangun, Terong, Jakabaring, "
                "Bandungan, Lembang, Berastagi, Malino, Maros). Bukan perusahaan "
                "atau orang nyata; jangan dipakai sebagai rujukan faktual."
            ),
            "coordinates": (
                "SEMUA baris memakai koordinat ABSOLUT di sekitar hub-nya (bukan "
                "offset), supaya jarak pemasok-SPPG bisa dihitung apa adanya dan "
                "pin di peta berada di wilayah yang benar."
            ),
            "canonical_overlap": (
                "Nama di berkas ini SAMA dengan daftar pemasok kanonik di "
                "sprint1_seed.json, sehingga pemuat demo hanya MENGISI profil "
                "(koordinat/alamat/kapasitas) baris kanonik, tidak menggandakannya."
            ),
            "low_reliability": (
                "Lima pemasok sengaja <= 0.52 sebagai bahan kasus 'pemasok janggal': "
                "PT Nusantara Prima Ayam (0.44), UD Cipanas Telur Sejahtera "
                "(0.43), UD Pusat Pasar Beras (0.47), PD Cibinong Beras Mandiri "
                "(0.52), UD Surabaya Telur Jaya (0.62)."
            ),
        },
        "suppliers": [
            {
                "name": s["name"],
                "location": s["location"],
                "commodity": s["commodity"],
                "reliability_score": s["reliability_score"],
                "capacity_kg_per_week": s["capacity_kg_per_week"],
                "certification_status": s["certification_status"],
                "contact_name": s["contact_name"],
                "address": s["address"],
                "latitude": s["latitude"],
                "longitude": s["longitude"],
            }
            for s in SUPPLIERS
        ],
    }
    SUPPLIERS_PATH.write_text(
        json.dumps(demo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    per_hub: dict[str, int] = {}
    for s in SUPPLIERS:
        per_hub[s["location"]] = per_hub.get(s["location"], 0) + 1
    pairs = {(b["location"], b["commodity"]) for b in batches}
    print(f"locations           : {len(seed['locations'])}")
    print(f"commodities         : {len(seed['commodities'])}")
    print(f"suppliers           : {len(SUPPLIERS)}  (per hub: {per_hub})")
    print(f"supply pairs        : {len(seed['supply'])}")
    print(f"demand series       : {len(demand)} pasangan")
    print(f"price signals       : {len(prices)} "
          f"(acuan {sum(1 for p in prices if p['source']=='pihps_reference')}, "
          f"kutipan {sum(1 for p in prices if p['source']=='supplier_quote')})")
    print(f"batches             : {len(batches)} lot untuk {len(pairs)} pasangan")
    print(f"SAP stock rows      : {len(mock_sap['material_stock'])}")
    print(f"SAP purchase orders : {len(mock_sap['purchase_orders'])}")
    status = {}
    for b in batches:
        status[(b["freshness_status"], b["safety_status"])] = (
            status.get((b["freshness_status"], b["safety_status"]), 0) + 1
        )
    print(f"profil batch        : {status}")


if __name__ == "__main__":
    main()
