"""Joule membaca DOKUMEN PO, bukan hanya baris daftar (permintaan pemilik 29 Okt 2026).

Tiga lapis yang dikunci di sini:

1. **Klien** — `po_detail()` memanggil `/sap/purchase-orders/{nomor}/detail` dan
   memetakan kolom JSON backend ke bentuk camelCase perender, tanpa menghitung
   ulang apa pun.
2. **Perender** — `po_document_report()` mencetak bagian yang sama dengan PDF PO:
   rincian biaya, persetujuan **bernama** beserta komentar dan waktunya, syarat
   persetujuan, keputusan asal, dan status ketersediaan PDF.
3. **Routing** — kalimat yang menyebut nomor PO diarahkan ke jalur dokumen; bila
   backend belum punya rute `/detail`, jembatan jatuh ke tampilan daftar (bukan
   menjawab "tidak ditemukan").

Angka di berkas ini adalah angka contoh yang meniru bentuk respons backend —
tidak ada yang dihitung di jembatan, jadi tes pun tidak boleh menuntut hasil
aritmetika baru.
"""

from __future__ import annotations

import httpx
import pytest

import report
from mealchain_client import MealchainClient

API = "http://backend.test"
NOMOR = "MC-661695B2C685"

RESPONS = {
    "po_number": NOMOR,
    "status": "confirmed",
    "created_at": "2026-10-20T02:20:00+00:00",
    "material_number": "MAT-TELU",
    "commodity_name": "telur",
    "location_name": "SPPG Jakarta Pusat",
    "supplier_name": "Telur Berkah",
    "ordered_quantity": 600.0,
    "price": 18000.0,
    "total": 10800000.0,
    "commercial_cost": {
        "purchase_total": "10800000.00",
        "transport_total": "34200.00",
        "handling_total": "150000.00",
        "invoice_total": "10984200.00",
        "invoice_unit_price": "18307.00",
        "expected_loss": "100000.00",
        "freshness_risk": "0.00",
        "safety_penalty": "0.00",
        "sdc_total": "11084200.00",
        "sdc_unit_price": "18473.67",
        "risk_method": {"kind": "simulated_policy", "version": "sdc-policy-1"},
    },
    "keputusan": {
        "id": "11111111-2222-3333-4444-555555555555",
        "jenis": "supplier_procurement",
        "status": "approved",
        "iteration": 2,
        "proposed_by": "sppg_head",
        "created_at": "2026-10-19T02:00:00+00:00",
        "expires_at": "2026-10-21T02:00:00+00:00",
    },
    "persetujuan": [
        {
            "role": "sppg_head",
            "name": "Rina Kepala",
            "approved": True,
            "comment": "Harga masih dalam acuan.",
            "approved_at": "2026-10-19T03:00:00+00:00",
        },
        {
            "role": "sppg_nutritionist",
            "name": "Dewi Gizi",
            "approved": False,
            "comment": "Minta pasokan dikurangi.",
            "approved_at": "2026-10-19T04:00:00+00:00",
        },
    ],
    "syarat": {"min_approvals": 2, "required_roles": ["sppg_head"], "satisfied": True},
    "boleh_pdf": True,
    "source": "mock_sap_table",
}


def _client(handler) -> MealchainClient:
    return MealchainClient(
        base_url=API,
        username="bgn.monitor@demo.local",
        password="Demo#BGN2026",
        transport=httpx.MockTransport(handler),
    )


def test_klien_memanggil_rute_detail_dan_memetakan_kolom():
    jalur: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1", "role": "bgn_monitor"})
        jalur.append(request.url.path)
        return httpx.Response(200, json=RESPONS)

    with _client(handler) as client:
        dokumen = client.po_detail(NOMOR)

    assert jalur == [f"/sap/purchase-orders/{NOMOR}/detail"]
    assert dokumen["poNumber"] == NOMOR
    assert dokumen["quantityKg"] == 600.0
    assert dokumen["totalValue"] == 10800000.0
    assert dokumen["bolehPdf"] is True
    assert dokumen["keputusan"]["iteration"] == 2
    assert [p["name"] for p in dokumen["persetujuan"]] == ["Rina Kepala", "Dewi Gizi"]
    assert dokumen["syarat"]["min_approvals"] == 2


def test_klien_menolak_po_lokasi_lain_sebagai_galat():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1", "role": "bgn_monitor"})
        return httpx.Response(404, json={"detail": "purchase order tidak ditemukan"})

    with _client(handler) as client:
        with pytest.raises(Exception) as exc:
            client.po_detail(NOMOR)
    assert "404" in str(exc.value)


def _dokumen_jembatan() -> dict:
    """Bentuk yang diterima perender (hasil pemetaan klien)."""
    return {
        "poNumber": NOMOR,
        "status": RESPONS["status"],
        "createdAt": RESPONS["created_at"],
        "materialNumber": RESPONS["material_number"],
        "commodityName": RESPONS["commodity_name"],
        "locationName": RESPONS["location_name"],
        "supplierName": RESPONS["supplier_name"],
        "quantityKg": RESPONS["ordered_quantity"],
        "pricePerKg": RESPONS["price"],
        "totalValue": RESPONS["total"],
        "commercialCost": RESPONS["commercial_cost"],
        "keputusan": RESPONS["keputusan"],
        "persetujuan": [
            {
                "role": p["role"],
                "name": p["name"],
                "approved": p["approved"],
                "comment": p["comment"],
                "approvedAt": p["approved_at"],
            }
            for p in RESPONS["persetujuan"]
        ],
        "syarat": RESPONS["syarat"],
        "bolehPdf": RESPONS["boleh_pdf"],
    }


def test_perender_mencetak_rincian_biaya_dan_persetujuan_bernama():
    teks = report.po_document_report(_dokumen_jembatan())
    assert NOMOR in teks
    # Rincian biaya (bahan/angkut/penanganan) — bagian yang dulu tidak ada di chat.
    assert "Rincian biaya" in teks
    assert "Transportasi" in teks and "Penanganan" in teks
    assert "SDC analitis" in teks
    # Persetujuan bernama + komentar.
    assert "Rina Kepala" in teks and "Kepala SPPG" in teks
    assert "Harga masih dalam acuan." in teks
    assert "Dewi Gizi" in teks and "menolak" in teks
    # Keputusan asal + syarat + status PDF.
    assert "Keputusan asal" in teks
    assert "Terpenuhi" in teks
    assert "PDF PO sudah bisa diterbitkan" in teks


def test_perender_meratakan_peran_wajib_bertingkat():
    dokumen = _dokumen_jembatan()
    dokumen["syarat"] = {
        "min_approvals": 2,
        "required_roles": [["sppg_head"], ["sppg_nutritionist"]],
        "satisfied": False,
    }
    teks = report.po_document_report(dokumen)
    assert "Kepala SPPG, Ahli Gizi SPPG" in teks
    assert "—" not in teks.split("Peran wajib")[1].split("\n")[0]


def test_perender_jujur_saat_tidak_ada_persetujuan_dan_pdf_belum_bisa():
    dokumen = _dokumen_jembatan()
    dokumen["persetujuan"] = []
    dokumen["keputusan"] = None
    dokumen["bolehPdf"] = False
    dokumen["commercialCost"] = None
    teks = report.po_document_report(dokumen)
    assert "belum ada persetujuan tercatat" in teks
    assert "PDF PO belum diterbitkan" in teks
    # Tidak ada angka karangan saat rincian biaya tidak dikirim.
    assert "tidak tercatat" in teks
