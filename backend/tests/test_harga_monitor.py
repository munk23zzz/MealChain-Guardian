"""Monitor harga pasar — logika murni (tanpa DB, tanpa HTTP).

Yang dipaku di sini adalah kontrak yang mudah rusak diam-diam:
  1. Jendela `days` dihitung dari TANGGAL PUBLIKASI, bukan hari kalender —
     PIHPS tidak terbit Sabtu/Minggu, jadi 30 hari kalender hanya ~22 tanggal.
  2. Sel kosong tidak pernah menjadi 0 (harga 0 akan terbaca "gratis" di grafik).
  3. Filter komoditas menerima nama MealChain ('telur') DAN kode PIHPS ('com_10').
  4. Wortel tidak punya kode PIHPS; panel tidak boleh mengarang serinya.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from app.core.harga_monitor import (
    KOMODITAS_PROYEK,
    baca_snapshot,
    kode_diminta,
    pergerakan_teratas,
    susun_monitor,
)


def _snap() -> dict:
    """Snapshot mini: 6 tanggal publikasi (dengan jarak akhir pekan)."""
    tanggal = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-26"]
    rows = []
    for hari in tanggal:
        for kode, label, harga in (
            ("com_10", "Telur Ayam Ras Segar", 25700.0),
            ("com_3", "Beras Kualitas Medium I", 17050.0),
        ):
            rows.append(
                {
                    "commodity_code": kode,
                    "commodity_label": label,
                    "region_name": "Kota Jakarta Pusat",
                    "region_level": "kota",
                    "observed_on": hari,
                    "price_per_kg": harga,
                }
            )
    return {
        "sumber": "PIHPS Bank Indonesia",
        "source_url": "https://www.bi.go.id/hargapanan",
        "jenis_pasar": "Pasar Tradisional",
        "satuan": "Rp/kg",
        "fetched_at": "2026-10-26T09:00:00+00:00",
        "window": {"start": "2026-10-19", "end": "2026-10-26"},
        "tanggal_terisi": tanggal,
        "komoditas": [
            {"code": "com_10", "label": "Telur Ayam Ras Segar"},
            {"code": "com_3", "label": "Beras Kualitas Medium I"},
            {"code": "com_13", "label": "Cabai Merah Besar"},
        ],
        "wilayah": [{"level": "kota", "name": "Kota Jakarta Pusat"}],
        "rows": rows,
    }


def test_jendela_dihitung_dari_tanggal_publikasi():
    hasil = susun_monitor(_snap(), days=3, region="Kota Jakarta Pusat")
    tanggal = sorted({r["observed_on"] for r in hasil["rows"]})
    assert tanggal == ["2026-10-22", "2026-10-23", "2026-10-26"]
    assert hasil["coverage"]["tanggal_pertama"] == "2026-10-22"
    assert hasil["coverage"]["tanggal_terakhir"] == "2026-10-26"


def test_hari_tanpa_publikasi_tidak_menjadi_nol():
    hasil = susun_monitor(_snap(), days=30)
    tanggal = sorted({r["observed_on"] for r in hasil["rows"]})
    # 24/25 Okt adalah Sabtu-Minggu: tidak ada baris, dan tidak ada harga 0.
    assert "2026-10-24" not in tanggal
    assert "2026-10-25" not in tanggal
    assert all(r["price_per_kg"] > 0 for r in hasil["rows"])


def test_filter_menerima_nama_mealchain_dan_kode_pihps():
    assert kode_diminta("telur") == ["com_10"]
    assert kode_diminta("telur,com_3") == ["com_10", "com_3"]
    assert kode_diminta(None) is None
    # Nama tak dikenal TIDAK boleh berubah menjadi "tanpa filter".
    assert kode_diminta("wortel") is None
    assert kode_diminta("wortel,com_10") == ["com_10"]


def test_wortel_tidak_punya_kode_pihps():
    assert "wortel" not in KOMODITAS_PROYEK


def test_komoditas_membawa_project_key():
    hasil = susun_monitor(_snap(), days=30)
    peta = {item["code"]: item["project_key"] for item in hasil["commodities"]}
    assert peta["com_10"] == "telur"
    assert peta["com_3"] == "beras"
    assert peta["com_13"] is None  # seri PIHPS yang tidak dipakai modul


def test_filter_wilayah_dan_komoditas_berlaku_bersama():
    hasil = susun_monitor(_snap(), days=30, commodity="telur", region="Kota Jakarta Pusat")
    assert hasil["status"] == "ok"
    assert {r["commodity_code"] for r in hasil["rows"]} == {"com_10"}
    assert {r["region_name"] for r in hasil["rows"]} == {"Kota Jakarta Pusat"}


def test_wilayah_asing_menghasilkan_kosong_dengan_alasan():
    hasil = susun_monitor(_snap(), days=30, region="Kota Cianjur")
    assert hasil["status"] == "kosong"
    assert hasil["rows"] == []
    assert "Kota Cianjur" in (hasil["alasan"] or "")


def test_sumber_dan_waktu_tarik_ikut_terbawa():
    hasil = susun_monitor(_snap(), days=30)
    assert hasil["source"] == "PIHPS Bank Indonesia"
    assert hasil["fetched_at"] == "2026-10-26T09:00:00+00:00"
    assert hasil["unit"] == "Rp/kg"
    assert hasil["market"] == "Pasar Tradisional"


def test_baca_snapshot_hilang_mengembalikan_none(tmp_path):
    assert baca_snapshot(tmp_path / "tidak-ada.json") is None


def test_baca_snapshot_rusak_mengembalikan_none(tmp_path):
    rusak = tmp_path / "rusak.json"
    rusak.write_text("{bukan json", encoding="utf-8")
    assert baca_snapshot(rusak) is None


def test_baca_snapshot_memuat_ulang_saat_berkas_berubah(tmp_path):
    berkas = tmp_path / "snap.json"
    berkas.write_text(json.dumps({"sumber": "A"}), encoding="utf-8")
    assert (baca_snapshot(berkas) or {}).get("sumber") == "A"
    berkas.write_text(json.dumps({"sumber": "B"}), encoding="utf-8")
    # mtime bisa sama pada filesystem berbutir kasar; paksa berbeda.
    import os

    os.utime(berkas, (date.today().toordinal(), date.today().toordinal() + 10))
    assert (baca_snapshot(berkas) or {}).get("sumber") == "B"


def test_jendela_dibatasi_120_hari():
    snap = _snap()
    hasil = susun_monitor(snap, days=9999)
    assert hasil["days"] == 120


def test_snapshot_kosong_tidak_melempar():
    hasil = susun_monitor({"rows": [], "komoditas": [], "tanggal_terisi": []}, days=30)
    assert hasil["status"] == "kosong"
    assert hasil["coverage"]["tanggal_terisi"] == 0
    assert hasil["rows"] == []


def test_tanggal_di_luar_jendela_tidak_ikut():
    snap = _snap()
    jauh = (date(2026, 10, 26) + timedelta(days=1)).isoformat()
    snap["rows"].append(
        {
            "commodity_code": "com_10",
            "commodity_label": "Telur Ayam Ras Segar",
            "region_name": "Kota Jakarta Pusat",
            "region_level": "kota",
            "observed_on": jauh,
            "price_per_kg": 99999.0,
        }
    )
    hasil = susun_monitor(snap, days=30)
    assert all(r["observed_on"] != jauh for r in hasil["rows"])


def test_pergerakan_teratas_mengurutkan_menurut_besaran_perubahan():
    rows = [
        {"commodity_code": "com_10", "region_name": "Kota Jakarta Pusat",
         "observed_on": "2026-10-19", "price_per_kg": 25000.0},
        {"commodity_code": "com_10", "region_name": "Kota Jakarta Pusat",
         "observed_on": "2026-10-26", "price_per_kg": 25700.0},
        {"commodity_code": "com_10", "region_name": "Kota Medan",
         "observed_on": "2026-10-19", "price_per_kg": 30000.0},
        {"commodity_code": "com_10", "region_name": "Kota Medan",
         "observed_on": "2026-10-26", "price_per_kg": 27900.0},
        {"commodity_code": "com_10", "region_name": "Kota Bogor",
         "observed_on": "2026-10-26", "price_per_kg": 24000.0},
    ]
    hasil = pergerakan_teratas(rows, "com_10", 2)
    assert [h["region_name"] for h in hasil] == ["Kota Medan", "Kota Jakarta Pusat"]
    assert round(hasil[0]["delta_pct"], 1) == -7.0


def test_pergerakan_teratas_tidak_mengarang_untuk_satu_titik():
    rows = [{"commodity_code": "com_10", "region_name": "Kota Bogor",
             "observed_on": "2026-10-26", "price_per_kg": 24000.0}]
    assert pergerakan_teratas(rows, "com_10") == []


def test_susun_monitor_menyertakan_pergerakan_antar_wilayah():
    snap = _snap()
    # Kota Medan hanya muncul di satu snapshot mini; tambahkan dua titik supaya
    # pergerakan punya arah, lalu pastikan ikut terkirim meski filter wilayah
    # menunjuk kota lain.
    for hari, harga in (("2026-10-19", 30000.0), ("2026-10-26", 27900.0)):
        snap["rows"].append(
            {"commodity_code": "com_10", "commodity_label": "Telur Ayam Ras Segar",
             "region_name": "Kota Medan", "region_level": "kota",
             "observed_on": hari, "price_per_kg": harga}
        )
        snap["tanggal_terisi"] = sorted(set(snap["tanggal_terisi"]) | {hari})
    hasil = susun_monitor(snap, days=30, commodity="telur", region="Kota Jakarta Pusat")
    assert hasil["movers"], "movers harus terisi"
    assert hasil["movers"][0]["region_name"] == "Kota Medan"
    assert {r["region_name"] for r in hasil["rows"]} == {"Kota Jakarta Pusat"}
