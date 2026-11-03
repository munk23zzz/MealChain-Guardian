"""Lensa Kesegaran harus punya data yang berbeda dari lensa Kuantitas.

Latar (25 Okt 2026): grafik "Kecukupan pasokan" punya dua lensa, Kuantitas dan
Kesegaran. Kesegaran hanya menghitung batch dengan sisa masa layak > 48 jam,
sedangkan Kuantitas menghitung layak + ≤48 jam. Karena template demo hanya
menyemai batch yang masih >48 jam, kedua lensa menampilkan angka yang PERSIS
sama di 39 dari 40 kombinasi lokasi×komoditas — juri melihat tombol yang tidak
mengubah apa pun.

Kontrak di sini: template wajib menyisakan beberapa batch yang masih layak
tetapi sudah masuk jendela ≤48 jam, dan konsisten antara `harvested_at`,
`usable_until`, serta `freshness_score` (rekomendasi layanan menghitung umur
dari `harvested_at` + umur simpan, jadi keduanya tidak boleh bertentangan).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.seed.demo_template import (
    STOK_MENDEKATI_BATAS,
    rencana_stok_mendekati_batas,
)

NOW = datetime(2026, 10, 25, 7, 0, tzinfo=timezone.utc)

UMUR_JAM = {
    "ayam": settings.shelf_life_days_ayam * 24,
    "telur": settings.shelf_life_days_telur * 24,
    "wortel": settings.shelf_life_days_wortel * 24,
    "beras": settings.shelf_life_days_beras * 24,
}


def test_rencana_masuk_jendela_48_jam_dan_konsisten():
    rencana = rencana_stok_mendekati_batas(NOW)

    assert len(rencana) == len(STOK_MENDEKATI_BATAS) >= 4, (
        "butuh beberapa batch agar semua kota demo melihat bedanya"
    )

    for item in rencana:
        sisa = (item["usable_until"] - NOW).total_seconds() / 3600
        assert 0 < sisa <= 48, f"{item['lokasi']} {item['komoditas']}: sisa {sisa} jam"
        assert item["harvested_at"] < item["usable_until"]
        # harvested_at + umur simpan harus TEPAT sama dengan usable_until.
        umur = UMUR_JAM[item["komoditas"]]
        selisih = (item["usable_until"] - item["harvested_at"]).total_seconds() / 3600
        assert abs(selisih - umur) < 1e-6, (
            f"{item['komoditas']}: umur simpan {selisih} jam, seharusnya {umur}"
        )
        # freshness_score = porsi umur simpan yang tersisa.
        assert abs(float(item["freshness_score"]) - sisa / umur) < 0.01


def test_rencana_deterministik():
    sekali = rencana_stok_mendekati_batas(NOW)
    dua_kali = rencana_stok_mendekati_batas(NOW)
    assert sekali == dua_kali, "template harus bisa dibangun ulang dengan angka sama"


def test_setiap_kota_template_punya_stok_mendekati_batas():
    kota = {item["lokasi"] for item in rencana_stok_mendekati_batas(NOW)}
    assert {"Jakarta", "Bandung", "Surabaya"} <= kota


def test_template_menyemai_stok_mendekati_batas_setelah_pemangkasan_jakarta():
    sumber = Path("app/seed/demo_template.py").read_text(encoding="utf-8")
    panggilan = "_semai_stok_mendekati_batas(db, now)"
    assert panggilan in sumber, "langkah ini harus dipanggil dari build_into"
    # Pemangkasan Jakarta menghapus batch terkecil; kalau langkah ini jalan
    # lebih dulu, batch target bisa hilang sebelum sempat diubah.
    assert sumber.index("_rapikan_kiriman_jakarta(db, now)") < sumber.index(panggilan)
