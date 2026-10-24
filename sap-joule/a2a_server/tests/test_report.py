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
    assert "1 kurang · 1 lebih" in teks  # ringkasan jumlah, bukan hanya baris teratas
    assert "Skor kesegaran berskala 0–1" not in teks  # catatan kesegaran hanya untuk tabel batch
    assert "**" not in teks  # tabel markdown biasa, bukan penekanan liar


def test_supply_report_menampilkan_inventaris_batch_dengan_keamanan_dan_skor():
    batches = [
        _batch("SPPG Palembang", "telur", 250.0, safety="fail", score=0.2,
               until="2026-09-10T00:00:00+00:00"),
        _batch("SPPG Bandung", "ayam", 400.0, safety="pass", score=0.69,
               until="2026-10-19T00:00:00+00:00"),
    ]

    teks = report.supply_report(batches, None)

    assert "Inventaris batch (2 batch: 1 gagal · 1 lolos)" in teks
    assert "1 gagal" in teks and "lolos" in teks
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

    assert "Tabel batch: Menampilkan 5 dari 15 baris." in teks


def test_supply_report_selisih_tidak_dikirim_backend_jadi_strip():
    balance = _balance(
        "telur",
        [{"location": "SPPG Cianjur", "supply_kg": 100.0, "demand_kg": 100.0,
          "status": "balanced"}],
    )

    teks = report.supply_report([], balance)

    assert report.MISSING in teks
    assert "SEIMBANG" in teks


# --- direktori pemasok -------------------------------------------------------------------


def test_supplier_directory_menampilkan_hub_komoditas_dan_kiriman():
    teks = report.supplier_directory_report(
        [
            {
                "name": "CV Cipinang Boga Utama",
                "location": "Jakarta",
                "commodity": "beras",
                "reliability": 0.92,
                "capacityKgPerWeek": 4200.0,
                "shippingCount": 2,
                "shippingKg": 840.0,
                "excludedAtHub": False,
            },
            {
                "name": "UD Cipanas Telur Sejahtera",
                "location": "Cianjur",
                "commodity": "telur",
                "reliability": 0.86,
                "capacityKgPerWeek": 2100.0,
                "shippingCount": None,
                "shippingKg": None,
                "excludedAtHub": True,
            },
        ]
    )

    assert "CV Cipinang Boga Utama" in teks
    assert "Jakarta" in teks and "beras" in teks
    assert "0,92" in teks and "4.200 kg" in teks
    assert "2 batch" in teks and "840 kg" in teks
    assert "belum mengirim" in teks
    assert "dikecualikan di hub" in teks


def test_supplier_directory_kosong_jujur_dan_membatasi_baris():
    assert "Belum ada data pemasok" in report.supplier_directory_report([])

    banyak = [
        {"name": f"Pemasok-{i:02d}", "location": "Jakarta", "commodity": "beras"}
        for i in range(30)
    ]
    teks = report.supplier_directory_report(banyak, limit=25)
    assert "Menampilkan 25 dari 30 baris." in teks


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
    assert "Keberlanjutan menu" in teks  # nama indikator tampil dalam bahasa Indonesia
    assert f"{report.MISSING} (tidak ada record pada periode ini)" in teks
    assert "1 indikator belum bisa dihitung" in teks
    assert "tidak terbaca nol" in teks


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
    assert "Persetujuan tidak bisa dilakukan dari Joule" in teks
    assert "Rules.md" not in teks  # rujukan dokumen internal tidak untuk pembaca chat


def test_approval_queue_baris_tanpa_nama_lokasi_jadi_strip_bukan_karangan():
    decisions = [
        {"id": "dec-009", "status": "proposed", "decisionType": "safety_disruption",
         "sourceLocation": None, "targetLocation": None, "commodity": None,
         "quantityKg": None},
    ]

    teks = report.approval_queue_report(decisions)

    assert f"{report.MISSING} → {report.MISSING}" in teks
    assert "gangguan keamanan pangan" in teks


def test_approval_queue_menyebut_jumlah_terbuka_sebenarnya():
    decisions = [
        {"id": f"dec-{i:03d}", "status": "pending_approval", "decisionType": "regional_balance",
         "sourceLocation": "A", "targetLocation": "B", "commodity": "telur", "quantityKg": 10.0}
        for i in range(12)
    ]

    teks = report.approval_queue_report(decisions, limit=12, total_belum=22)

    # 10 usulan lain tidak boleh seolah tidak ada hanya karena ringkasannya tidak ditarik.
    assert "22 usulan terbuka, 12 teratas ditampilkan" in teks


def test_approval_queue_membatasi_baris_dan_menyebut_sisanya():
    decisions = [
        {"id": f"dec-{i:03d}", "status": "proposed", "decisionType": "regional_balance",
         "sourceLocation": "A", "targetLocation": "B", "commodity": "telur",
         "quantityKg": 10.0}
        for i in range(15)
    ]

    teks = report.approval_queue_report(decisions, limit=12)

    assert "Menampilkan 12 dari 15 baris." in teks


def test_unavailable_report_jujur_bahwa_tidak_ada_angka():
    teks = report.unavailable_report("supply_situation", "backend tidak bisa dihubungi")

    assert "belum bisa diambil" in teks
    assert "backend tidak bisa dihubungi" in teks
    assert "bukan berarti kondisinya aman" in teks


# --- purchase order: angka apa adanya, nomor dicocokkan persis ---------------------------


def _po(**ubah):
    baris = {
        "poNumber": "MC-661695B2C685",
        "status": "confirmed",
        "createdAt": "2026-10-20T02:20:00+00:00",
        "locationName": "SPPG Jakarta Pusat",
        "supplierName": "Telur Berkah",
        "materialNumber": "MAT-BERA",
        "commodityName": "telur",
        "quantityKg": 600.0,
        "pricePerKg": 18000.0,
        "totalValue": 10800000.0,
        "decisionId": "9f1c0a52-2b6e-4b31-91f5-3c0a1d5e7a11",
        "decisionStatus": "executed",
        "origin": "execution",
    }
    baris.update(ubah)
    return baris


def test_po_detail_menampilkan_kolom_dari_backend_dan_waktu_wib():
    teks = report.purchase_order_report([_po()], po_number="mc-661695b2c685")

    assert "Purchase order MC-661695B2C685" in teks
    assert "dikonfirmasi" in teks            # status PO diterjemahkan, id API tetap dikenal
    assert "20 Okt 2026 09.20 WIB" in teks   # 02.20 UTC -> 09.20 WIB
    assert "SPPG Jakarta Pusat" in teks
    assert "Telur Berkah" in teks
    assert "MAT-BERA" not in teks  # kode material SAP internal tidak ditampilkan
    assert "600 kg" in teks
    assert "Rp18.000" in teks
    assert "Rp10.800.000" in teks
    assert "dieksekusi" in teks
    assert "dibuat dari eksekusi keputusan" in teks
    # PDF bukan lampiran chat — keterbatasan itu disebut, bukan disembunyikan.
    assert "tidak melampirkan berkas" in teks


def test_po_total_dari_backend_tidak_dihitung_ulang():
    """Harga x jumlah sengaja dibuat tidak konsisten: perender WAJIB memakai `totalValue`."""
    teks = report.purchase_order_report(
        [_po(quantityKg=2.0, pricePerKg=1000.0, totalValue=999.0)], po_number="MC-661695B2C685"
    )

    assert "Rp999" in teks
    assert "Rp2.000" not in teks, "jembatan tidak boleh mengalikan harga x jumlah"


def test_po_daftar_menandai_baris_impor_sap_tanpa_keputusan():
    teks = report.purchase_order_report(
        [_po(), _po(poNumber="4500000001", decisionId=None, decisionStatus=None, origin="demo")]
    )

    assert "2 PO terbaca" in teks
    assert "| impor SAP |" in teks or "impor SAP |" in teks
    assert "dieksekusi" in teks


def test_po_nomor_tidak_dikenal_disebut_jujur_bukan_tabel_kosong():
    teks = report.purchase_order_report([_po()], po_number="MC-000000000000")

    assert "MC-000000000000 tidak ditemukan" in teks
    assert "1 PO" in teks
    assert "bukan berarti PO-nya fiktif" in teks


def test_po_kosong_disebut_kosong():
    teks = report.purchase_order_report([])

    assert "Belum ada purchase order" in teks


def test_po_daftar_membatasi_baris_dan_menyebut_sisanya():
    rows = [_po(poNumber=f"MC-00000000{i:04X}") for i in range(12)]

    teks = report.purchase_order_report(rows, limit=10)

    assert "12 PO terbaca" in teks
    assert "Tabel PO: Menampilkan 10 dari 12 baris." in teks


def test_wib_tidak_mengarang_zona_bila_offset_hilang():
    assert report.wib("2026-10-20T02:20:00+00:00") == "20 Okt 2026 09.20 WIB"
    assert report.wib("2026-10-20T02:20:00Z") == "20 Okt 2026 09.20 WIB"
    # Tanpa offset: dikembalikan apa adanya, TIDAK diasumsikan UTC.
    assert report.wib("2026-10-20T02:20:00") == "2026-10-20T02:20:00"
    assert report.wib(None) == report.MISSING


# --- perender skill baru -------------------------------------------------------------------


def test_harga_menampilkan_acuan_dan_kuotasi_tanpa_menghitung_termurah():
    teks = report.price_report(
        [
            {
                "location": "Bandung",
                "commodity": "beras",
                "price_per_kg": 12225.53,
                "recorded_at": "2026-11-04T12:00:00+00:00",
                "source": "pihps_reference",
            }
        ],
        [
            {
                "location": "Bandung",
                "commodity": "beras",
                "quotes": [
                    {
                        "supplier_name": "UD Rancaekek Beras Sejahtera",
                        "price_per_kg": 12039.42,
                        "recorded_at": "2026-11-03T00:00:00+00:00",
                    },
                    {
                        "supplier_name": "CV Cipinang Boga Utama",
                        "price_per_kg": 12500.0,
                        "recorded_at": "2026-11-02T00:00:00+00:00",
                    },
                ],
            }
        ],
    )

    assert "Rp12.226" in teks and "acuan PIHPS" in teks
    assert "UD Rancaekek Beras Sejahtera" in teks and "Rp12.039" in teks
    assert "CV Cipinang Boga Utama" in teks and "Rp12.500" in teks
    assert "termurah" in teks  # dinyatakan TIDAK dihitung, bukan disembunyikan


def test_harga_kosong_disebut_kosong_bukan_nol():
    teks = report.price_report([])

    assert "Belum ada data harga" in teks
    assert "Rp0" not in teks


def test_kebutuhan_menampilkan_metode_prakiraan_apa_adanya():
    teks = report.demand_report(
        [
            {
                "location": "Bandung",
                "commodity": "beras",
                "quantityKg": 957.04,
                "neededBy": "2026-11-07T00:00:00+00:00",
                "forecastKg": 6697.558,
                "forecastMethod": "statistical_fallback",
                "confidence": 1.0,
            }
        ]
    )

    assert "957 kg" in teks and "6.697,6 kg" in teks
    assert "cadangan statistik" in teks
    assert "Keyakinan (0–1)" in teks and "| 1,00 |" in teks


def test_kehilangan_pangan_memisahkan_tiga_angka():
    teks = report.food_loss_report(
        {
            "period": {
                "start": "2026-09-20T00:00:00+00:00",
                "end": "2026-10-20T00:00:00+00:00",
                "days": 30,
            },
            "scope": {"role": "bgn_monitor", "locations": ["Bandung", "Bogor"]},
            "computed_at": "2026-10-20T00:43:56+00:00",
            "recorded": {"available": True, "kg": 631.46, "events": 86},
            "diverted": {"available": True, "kg": 332.5, "events": 41},
            "unassigned": {"available": True, "kg": 298.96, "events": 45},
            "partners": [{"name": "PT Biogas Nusantara", "kg": 122.8, "events": 14}],
        }
    )

    assert "631,5 kg · 86 kejadian" in teks
    assert "332,5 kg · 41 kejadian" in teks
    assert "299 kg · 45 kejadian" in teks
    assert "PT Biogas Nusantara" in teks
    assert "2 SPPG · cakupan akun Anda" in teks  # slug peran tidak tampil di chat


def test_kehilangan_pangan_yang_tidak_tersedia_menyebut_alasannya():
    teks = report.food_loss_report(
        {"recorded": {"available": False, "reason": "tidak ada baris limbah"}}
    )

    assert "tidak ada baris limbah" in teks
    assert "0 kg" not in teks


def test_risiko_pemasok_menampilkan_eksklusi_dan_rute():
    teks = report.supplier_risk_report(
        [
            {
                "supplierName": "UD Ayam Sehat",
                "scopeLocationName": "Jakarta",
                "status": "active",
                "reason": "batch ayam gagal uji antibiotik",
                "activated_at": "2026-10-16T22:36:54+00:00",
                "revoked_at": None,
            }
        ],
        {
            "routes": [
                {
                    "supplierName": "CV Cipinang Boga Utama",
                    "destinationName": "Jakarta",
                    "commodity": "beras",
                    "quantityKg": 800.0,
                    "roadKm": 9.8,
                    "roadMinutes": 12.2,
                    "journeyState": "dalam perjalanan",
                }
            ],
            "summary": {
                "with_road": 1,
                "without_road": 0,
                "scope": "nasional",
                "journey_states": {"dalam_perjalanan": 1},
            },
        },
    )

    assert "aktif" in teks and "batch ayam gagal uji antibiotik" in teks
    assert "9,8 km" in teks and "12,2 menit" in teks
    assert "dalam perjalanan" in teks
    assert "1 kiriman punya rute jalan, 0 tanpa rute jalan" in teks


def test_bukti_keputusan_menampilkan_tanda_tangan_dan_jejak():
    teks = report.decision_evidence_report(
        [
            {
                "id": "cec7e30d-3eb5-4c29-82ee-c5fee581add1",
                "compliance": {
                    "decision": {
                        "decision_type": "regional_balance",
                        "status": "proposed",
                        "proposed_by": "supervisor_agent",
                    },
                    "evidence": [],
                    "approvals": [],
                    "content_address": "mc1-13i7rjc532qre22o835j3ffb5sxqn2rzsi7pd2hda82zdg442w",
                    "signature": {
                        "state": "signed",
                        "algorithm": "ECDSA-secp256k1-sha256 (deterministic RFC6979)",
                        "signature": "95b57211c6ef5b6139a32703e21327d6",
                    },
                    "verify": True,
                },
                "chain": {
                    "chain": [
                        {
                            "iteration": 2,
                            "status": "proposed",
                            "quantity_kg": 600.0,
                            "rejection_reason": None,
                            "created_at": "2026-10-19T20:33:04+00:00",
                        }
                    ]
                },
                "traces": {
                    "steps": [
                        {
                            "step_name": "LEARN",
                            "tool_called": "rejection_loop.repropose",
                            "output_summary": {"learning_note": "harga terlalu tinggi — cari sumber lebih dekat"},
                            "step_at": "2026-10-19T20:33:04+00:00",
                        }
                    ]
                },
            }
        ]
    )

    assert "bertanda tangan" in teks and "verifikasi materi: cocok" in teks
    assert "mc1-13i7rjc532qre22o835j3ffb5sxqn2rzsi7pd2hda82zdg442w" in teks
    assert "LEARN" in teks and "rejection_loop.repropose" in teks
    assert "harga terlalu tinggi" in teks
    assert "95b57211c6ef5b6139a32703…" in teks  # dipotong, bukan hilang


def test_status_sistem_tidak_menaikkan_status_komponen():
    teks = report.system_status_report(
        {
            "checked_at": "2026-10-20T00:43:56+00:00",
            "components": [
                {
                    "name": "AgentCore Gateway",
                    "category": "not_started",
                    "category_label": "belum dimulai",
                    "evidence": "env AGENTCORE_GATEWAY_URL kosong",
                }
            ],
        },
        {
            "valid": True,
            "blocks": 115,
            "linked_blocks": 115,
            "orphan_blocks": 0,
            "linked_ratio": 1.0,
            "head": "bdeeefb7",
            "coverage_warning": None,
        },
        {
            "by_status": {"submitted": 9, "confirmed": 14},
            "count": 23,
            "total_value": 227295034.0,
            "scope": "nasional",
            "source": "mock_sap_table",
        },
        [{"name": "Bandung", "region": "Jawa Barat"}],
    )

    assert "belum dimulai" in teks
    assert "SAH" in teks and "Rasio blok terhubung (0–1):** 1" in teks
    assert "Rp227.295.034" in teks
    assert "Jaringan SPPG (1 lokasi)" in teks and "Bandung (Jawa Barat)" in teks
    assert "/admin/users" not in teks  # path internal tidak untuk pembaca chat
    assert "tidak dibuka lewat chat" in teks  # alasannya tetap dinyatakan


def test_penerimaan_barang_satu_batch():
    teks = report.receipt_report(
        [
            {
                "recorded_at": "2026-10-20T03:00:00+00:00",
                "recorded_by_name": "SPPG Head Demo",
                "checked": {"suhu": True, "catatan": False, "kemasan": True, "berat_kg": True},
                "other_note": "selisih 20 kg dilaporkan",
            }
        ],
        batch_id="b-1",
    )

    assert "batch b-1 (1 catatan)" in teks
    assert "SPPG Head Demo" in teks and "suhu: ya" in teks and "catatan: belum" in teks
    assert "selisih 20 kg dilaporkan" in teks


def test_penerimaan_barang_kosong_disebut_kosong():
    teks = report.receipt_report([], batch_id="b-1")

    assert "Belum ada penerimaan barang" in teks
    assert "0 kg" not in teks
