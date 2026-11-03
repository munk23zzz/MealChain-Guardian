"""Kontrak domain Joule: pertanyaan pengguna harus jatuh ke skill yang benar.

Audit 21 Okt 2026 menguji enam pertanyaan wajar terhadap jembatan yang hidup dan
menemukan empat di antaranya dijawab domain yang salah — tanpa satu pun galat:

  "penerimaan barang mana yang menunggu persetujuan?" → Antrean keputusan (12 baris),
      padahal `batch_receipts` punya 2 catatan menunggu dan `/receipts/menunggu` ada.
  "pengiriman hari ini?"            → pasokan (tidak ada konsep pengiriman di sana)
  "stok material SAP?"              → pasokan
  "batch mana yang dikarantina?"    → pasokan (padahal `quarantine_status` ada di /batches)
  "siapa yang menyetujui?"          → antrean tanpa nama penyetuju

Modul ini mengunci pemetaan kata kunci → skill dan bentuk laporan penerimaan/karantina,
supaya regresi domain tertangkap tanpa memanggil backend hidup.
"""

from __future__ import annotations

import pytest

import report
from server import (
    SKILL_QUARANTINE,
    SKILL_QUEUE,
    SKILL_RECEIPTS,
    SKILL_SUPPLY,
    resolve_skill,
)

#: Pertanyaan nyata dari audit → skill yang WAJIB dipilih.
PETA = [
    ("penerimaan barang mana yang menunggu persetujuan?", SKILL_RECEIPTS),
    ("ada penerimaan barang yang belum diperiksa?", SKILL_RECEIPTS),
    ("batch mana yang sedang dikarantina?", SKILL_QUARANTINE),
    ("karantina hari ini apa saja?", SKILL_QUARANTINE),
    ("usulan keputusan apa yang menunggu persetujuan?", SKILL_QUEUE),
    ("pengiriman hari ini apa saja?", "unsupported_domain"),
    ("berapa stok material di SAP?", "unsupported_domain"),
    ("siapa yang menyetujui keputusan itu?", "decision_evidence"),
    ("berapa stok beras di Bandung?", SKILL_SUPPLY),
]


@pytest.mark.parametrize("teks,skill", PETA)
def test_pertanyaan_jatuh_ke_skill_yang_benar(teks: str, skill: str):
    dipilih, _payload = resolve_skill(teks)
    assert dipilih == skill, f"{teks!r} jatuh ke {dipilih}, seharusnya {skill}"


def test_penerimaan_menang_atas_antrean_untuk_kata_persetujuan():
    """Kata `persetujuan` milik antrean keputusan, tetapi domainnya penerimaan.

    Urutan pemeriksaan kata kunci adalah kontrak: kalau antrean diperiksa lebih dulu,
    pertanyaan penerimaan tidak akan pernah sampai ke skill penerimaan.
    """
    for teks in (
        "penerimaan barang menunggu persetujuan",
        "receiving yang butuh persetujuan kepala",
        "barang datang belum disetujui",
    ):
        assert resolve_skill(teks)[0] == SKILL_RECEIPTS


def test_laporan_penerimaan_memuat_angka_backend():
    payload = {
        "items": [
            {
                "id": "r1",
                "batch_id": "b1",
                "commodity": "Beras",
                "quantity_kg": 25.0,
                "location": "Bandung",
                "safety_status": "pass",
                "checked_count": 3,
                "recorded_by_name": "Kepala Bandung",
                "recorded_at": "2026-10-21T03:10:00+00:00",
            }
        ],
        "total": 1,
    }
    teks = report.receipts_queue_report(payload, note=None)
    assert "1 penerimaan barang" in teks
    assert "Beras" in teks and "25 kg" in teks
    assert "3/3" in teks
    assert "sudah dibatasi ke lokasi pengguna" in teks


def test_laporan_penerimaan_kosong_tidak_berbohong():
    teks = report.receipts_queue_report({"items": [], "total": 0}, note=None)
    assert "Tidak ada penerimaan barang" in teks
    assert "0 penerimaan" not in teks


def test_laporan_karantina_menyaring_kolom_sendiri():
    batches = [
        {"code": "MC-1", "commodity": "Beras", "quantity_kg": 10.0, "location": "Bandung",
         "safety_status": "fail", "quarantine_status": "quarantined"},
        {"code": "MC-2", "commodity": "Telur", "quantity_kg": 5.0, "location": "Bandung",
         "safety_status": "pass", "quarantine_status": "none"},
    ]
    teks = report.quarantine_report(batches, note=None)
    assert "1 batch berstatus karantina" in teks
    assert "MC-1" in teks
    assert "MC-2" not in teks


def test_bukti_menyebut_nama_penyetuju_bukan_hanya_peran():
    kasus = [
        {
            "id": "d1",
            "compliance": {
                "decision": {"decision_type": "regional_balance", "status": "executed"},
                "approvals": [
                    {"role": "sppg_head", "approved_by_name": "Kepala Bandung", "approved": True},
                    {"role": "sppg_nutritionist", "approved_by_name": "Ahli Gizi Bandung", "approved": True},
                ],
                "evidence": [],
            },
            "chain": {},
            "traces": {},
        }
    ]
    teks = report.decision_evidence_report(kasus, note=None)
    assert "Kepala Bandung" in teks and "Ahli Gizi Bandung" in teks
    assert "sppg_head" in teks  # peran tetap tampil sebagai konteks


def test_domain_belum_tersedia_tidak_meminjam_angka_domain_lain():
    teks = report.unsupported_report(
        "pengiriman barang", "belum ada sumber data untuk pengiriman"
    )
    assert "belum bisa menjawab" in teks
    assert "Keseimbangan pasokan" not in teks
    assert "belum tersedia" in teks or "belum ada sumber data" in teks


def test_laporan_karantina_kosong_jujur():
    teks = report.quarantine_report([], note=None)
    assert "Tidak ada batch berstatus karantina" in teks
