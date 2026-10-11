"""Test `report.py` — pemformat angka & perender markdown (fungsi murni, tanpa jaringan).

Bentuk data yang dipakai di sini = backend klon (a) v0.2.0: `/batches`, `/balance/map`,
`/kpi` (metrics), dan `/decisions` + approval-summary.
"""

from __future__ import annotations

import report


# --- pemformat angka: gaya Indonesia, dan TIDAK mengarang nilai ---------------------------


def test_num_memakai_pemisah_ribuan_titik_dan_desimal_koma():
    assert report.num(1234.5) == "1.234,5"
    assert report.num(1234567) == "1.234.567"
    assert report.num(0) == "0"


def test_nilai_kosong_jadi_strip_bukan_nol():
    assert report.num(None) == report.MISSING
    assert report.kg(None) == report.MISSING
    assert report.rupiah(None) == report.MISSING
    assert report.percent(None) == report.MISSING
    assert report.num("bukan angka") == report.MISSING


def test_rupiah_tanpa_desimal():
    assert report.rupiah(16200000) == "Rp16.200.000"


def test_format_metric_mengikuti_satuan_backend():
    assert report.format_metric("74.95", "percent") == "74,95%"
    assert report.format_metric("2.89", "percent") == "2,89%"
    assert report.format_metric(1500000, "IDR") == "Rp1.500.000"
    assert report.format_metric(12.5, "minutes") == "12,5 menit"
    # Satuan tak dikenal: angka apa adanya, TIDAK dipaksa jadi satuan yang kita kenal.
    assert report.format_metric(3.5, "karung") == "3,5"
    assert report.format_metric(None, "percent") == report.MISSING


# --- situasi pasokan: keseimbangan + inventaris batch -------------------------------------


def _batch(location, commodity, kg, safety="pass", score=None, until=None):
    return {
        "id": f"{location}-{commodity}",
        "location": location,
        "commodity": commodity,
        "quantity_kg": kg,
        "safety_status": safety,
        "freshness_score": score,
        "usable_until": until,
    }


def _balance(commodity, rows):
    return {commodity: {"commodity": commodity, "locations": rows}}


def test_supply_report_mengutamakan_lokasi_kurang_dan_memakai_nama():
    balance = _balance(
        "telur",
        [
            {"location": "SPPG Bogor", "supply_kg": 500.0, "demand_kg": 100.0,
             "surplus_kg": 400.0, "shortage_kg": 0.0, "status": "surplus"},
            {"location": "SPPG Jakarta", "supply_kg": 20.0, "demand_kg": 450.0,
             "surplus_kg": 0.0, "shortage_kg": 430.0, "status": "shortage"},
        ],
    )

    teks = report.supply_report([], balance)

    assert "SPPG Jakarta" in teks and "SPPG Bogor" in teks
    assert teks.index("SPPG Jakarta") < teks.index("SPPG Bogor")  # yang kurang lebih dulu
    assert "kurang 430 kg" in teks
    assert "KURANG" in teks
    assert "Rp" not in teks  # laporan pasokan tidak memuat harga
    assert "bukan oleh model bahasa" in teks
    assert "**" not in teks  # tabel markdown biasa, bukan penekanan liar


def test_supply_report_menampilkan_inventaris_batch_dengan_keamanan_dan_skor():
    batches = [
        _batch("SPPG Palembang", "telur", 250.0, safety="fail", score=0.2,
               until="2026-09-10T00:00:00+00:00"),
        _batch("SPPG Bandung", "ayam", 400.0, safety="pass", score=0.69,
               until="2026-10-19T00:00:00+00:00"),
    ]

    teks = report.supply_report(batches, None)

    assert "Inventaris batch (2 batch)" in teks
    assert "GAGAL" in teks and "lolos" in teks
    assert "0,69" in teks  # skor apa adanya dari backend
    # Batch gagal keamanan tampil lebih dulu: itu yang butuh perhatian.
    assert teks.index("SPPG Palembang") < teks.index("SPPG Bandung")
    # Ambang pita kesegaran TIDAK dikarang di perender.
    assert "mendekati kedaluwarsa" not in teks


def test_supply_report_kesegaran_kosong_jadi_strip_bukan_angka_karangan():
    teks = report.supply_report([_batch("SPPG Medan", "ayam", 100.0, score=None)], None)

    assert report.MISSING in teks


def test_supply_report_tanpa_data_menjelaskan_bukan_menampilkan_tabel_kosong():
    teks = report.supply_report([], {})

    assert "Belum ada data pasokan" in teks
    assert "| SPPG |" not in teks


def test_supply_report_membatasi_baris_dan_menyebut_sisanya():
    batches = [_batch(f"SPPG-{i}", "telur", 10.0) for i in range(15)]

    teks = report.supply_report(batches, None, limit=5)

    assert "10 baris lain tidak ditampilkan." in teks


def test_supply_report_selisih_tidak_dikirim_backend_jadi_strip():
    balance = _balance(
        "telur",
        [{"location": "SPPG Cianjur", "supply_kg": 100.0, "demand_kg": 100.0,
          "status": "balanced"}],
    )

    teks = report.supply_report([], balance)

    assert report.MISSING in teks
    assert "SEIMBANG" in teks


# --- KPI ----------------------------------------------------------------------------------


def test_kpi_report_menampilkan_metrik_tersedia_dengan_satuannya():
    teks = report.kpi_report(
        {
            "metrics": [
                {"name": "Meal Continuity Rate", "unit": "percent", "state": "available",
                 "value": "74.95", "reason": None},
                {"name": "Safe Delivered Cost", "unit": "IDR", "state": "no_data",
                 "value": None, "reason": "tidak ada record pada periode ini"},
            ]
        }
    )

    assert "74,95%" in teks
    assert "Meal Continuity Rate" in teks
    assert f"{report.MISSING} (tidak ada record pada periode ini)" in teks
    assert "1 indikator belum bisa dihitung" in teks
    assert "bukan diisi nol" in teks


def test_kpi_report_tanpa_metrik_jujur():
    teks = report.kpi_report({})

    assert "Belum ada metrik KPI" in teks
    assert "| Indikator |" not in teks


# --- antrean usulan ----------------------------------------------------------------------


def test_approval_queue_menegaskan_persetujuan_tidak_lewat_joule():
    decisions = [
        {"id": "dec-002", "status": "executed", "decisionType": "regional_balance",
         "sourceLocation": "Cianjur", "targetLocation": "Jakarta", "commodity": "telur",
         "quantityKg": 700.0},
        {"id": "dec-001", "status": "pending_approval", "decisionType": "price_anomaly",
         "sourceLocation": "SPPG Jakarta Utara", "targetLocation": "SPPG Bandung",
         "commodity": "ayam", "quantityKg": 80.0},
    ]

    teks = report.approval_queue_report(decisions)

    assert "penyeimbangan wilayah" in teks and "anomali harga" in teks
    assert teks.index("dec-001") < teks.index("dec-002")  # belum tuntas lebih dulu
    assert "Cianjur → Jakarta" in teks
    assert "telur" in teks and "700 kg" in teks
    assert "Persetujuan TIDAK bisa dilakukan dari Joule" in teks
    assert "Rules.md" in teks


def test_approval_queue_baris_tanpa_nama_lokasi_jadi_strip_bukan_karangan():
    decisions = [
        {"id": "dec-009", "status": "proposed", "decisionType": "safety_disruption",
         "sourceLocation": None, "targetLocation": None, "commodity": None,
         "quantityKg": None},
    ]

    teks = report.approval_queue_report(decisions)

    assert f"{report.MISSING} → {report.MISSING}" in teks
    assert "gangguan keamanan pangan" in teks


def test_approval_queue_membatasi_baris_dan_menyebut_sisanya():
    decisions = [
        {"id": f"dec-{i:03d}", "status": "proposed", "decisionType": "regional_balance",
         "sourceLocation": "A", "targetLocation": "B", "commodity": "telur",
         "quantityKg": 10.0}
        for i in range(15)
    ]

    teks = report.approval_queue_report(decisions, limit=12)

    assert "3 baris lain tidak ditampilkan." in teks


def test_unavailable_report_jujur_bahwa_tidak_ada_angka():
    teks = report.unavailable_report("supply_situation", "backend tidak bisa dihubungi")

    assert "belum bisa diambil" in teks
    assert "backend tidak bisa dihubungi" in teks
    assert "bukan berarti kondisinya aman" in teks
