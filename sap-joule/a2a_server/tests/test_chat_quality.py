"""Test mutu jawaban chat Joule: pertanyaan spesifik, sapaan, batch bermasalah, PO disetujui.

Berkas ini menjaga tiga hal yang pernah salah di chat nyata (23 Okt 2026):

1. "berapa stok telur di Bandung?" dulu dijawab 40 baris + 125 batch — pertanyaannya
   spesifik, jawabannya tidak.
2. "halo, kamu bisa bantu apa?" dan "batch mana yang harus dibuang?" dulu dijawab tabel
   pasokan yang sama, sehingga terasa seperti jawaban asal-asalan.
3. "pemasok mana yang berisiko?" dulu jatuh ke direktori pemasok, bukan risk view.
"""

from __future__ import annotations

import asyncio

from a2a.server.events import EventQueue
from a2a.types import (
    Message,
    MessageSendParams,
    Role,
    TaskArtifactUpdateEvent,
    TextPart,
)

import report
import server
from mealchain_client import MealchainUnavailable


class FakeClient:
    """Backend palsu dua pasangan: SPPG Jakarta/telur dan SPPG Bogor/beras."""

    def __init__(self, *, gagal: bool = False) -> None:
        self.gagal = gagal
        self.dipanggil: list[str] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def close(self) -> None:
        return None

    def health(self) -> dict:
        self.dipanggil.append("health")
        return {"status": "ok", "sap": {"data_source": "MOCK", "is_mixed": False}}

    def batches(self) -> list[dict]:
        self.dipanggil.append("batches")
        if self.gagal:
            raise MealchainUnavailable("backend tidak bisa dihubungi (uji)")
        return [
            {
                "id": "b-1",
                "location": "SPPG Jakarta",
                "location_id": "loc-1",
                "commodity": "telur",
                "quantity_kg": 120.0,
                "safety_status": "fail",
                "freshness_score": 0.42,
                "quarantine_status": "quarantined",
                "usable_until": "2026-10-20T00:00:00+00:00",
            },
            {
                "id": "b-2",
                "location": "SPPG Bogor",
                "location_id": "loc-2",
                "commodity": "beras",
                "quantity_kg": 400.0,
                "safety_status": "pass",
                "freshness_score": 0.91,
                "quarantine_status": "none",
                "usable_until": "2026-11-02T00:00:00+00:00",
            },
        ]

    def balance_map(self, commodity: str) -> dict:
        self.dipanggil.append(f"balance_map:{commodity}")
        baris = {
            "telur": [
                {"location": "SPPG Jakarta", "supply_kg": 120.0, "demand_kg": 300.0,
                 "shortage_kg": 180.0, "surplus_kg": 0.0, "status": "shortage"},
            ],
            "beras": [
                {"location": "SPPG Bogor", "supply_kg": 400.0, "demand_kg": 250.0,
                 "shortage_kg": 0.0, "surplus_kg": 150.0, "status": "surplus"},
            ],
        }[commodity]
        return {"commodity": commodity, "locations": baris}

    def supply_point(self, location_id: str, commodity: str) -> dict:
        self.dipanggil.append(f"supply_point:{location_id}/{commodity}")
        return {
            "quantity_kg": 410.5,
            "recorded_at": "2026-10-22T02:00:00+00:00",
            "source": "mock_sap",
        }

    def suppliers(self) -> list[dict]:
        self.dipanggil.append("suppliers")
        return [
            {"id": "sup-1", "name": "CV Cipinang Boga Utama", "location": "Jakarta",
             "commodity": "beras", "reliability": 0.92, "capacityKgPerWeek": 4200.0,
             "shippingCount": 2, "shippingKg": 840.0, "excludedAtHub": False},
        ]

    def locations(self) -> list[dict]:
        self.dipanggil.append("locations")
        return [{"id": "loc-1", "name": "SPPG Jakarta"}, {"id": "loc-2", "name": "SPPG Bogor"}]

    def supplier_exclusions(self) -> list[dict]:
        self.dipanggil.append("supplier_exclusions")
        return [
            {"supplier_id": "sup-1", "scope_location_id": "loc-1", "reason": "harga di atas acuan",
             "status": "aktif", "distance_km": 12.5, "duration_minutes": 35}
        ]

    def supplier_routes(self) -> dict:
        self.dipanggil.append("supplier_routes")
        return {"routes": []}

    def purchase_orders(self) -> list[dict]:
        self.dipanggil.append("purchase_orders")
        dasar = {
            "status": "confirmed",
            "createdAt": "2026-10-20T02:20:00+00:00",
            "locationName": "SPPG Jakarta",
            "supplierName": "Telur Berkah",
            "materialNumber": "MAT-TELU",
            "commodityName": "telur",
            "quantityKg": 600.0,
            "pricePerKg": 18000.0,
            "totalValue": 10800000.0,
            "origin": "execution",
        }
        return [
            {**dasar, "poNumber": "MC-661695B2C685",
             "decisionId": "9f1c0a52-2b6e-4b31-91f5-3c0a1d5e7a11", "decisionStatus": "executed"},
            {**dasar, "poNumber": "MC-EXTREME01", "status": "draft",
             "decisionId": None, "decisionStatus": None, "origin": "demo"},
        ]


def _jalan(teks: str, fake: FakeClient | None = None):
    fake = fake or FakeClient()

    async def main():
        queue = EventQueue()
        pesan = Message(message_id="m-1", role=Role.user, parts=[TextPart(text=teks)])
        context = server.RequestContext(request=MessageSendParams(message=pesan))
        await server.MealchainExecutor(lambda: fake).execute(context, queue)
        events = []
        while True:
            try:
                events.append(await queue.dequeue_event(no_wait=True))
            except asyncio.QueueEmpty:
                break
        return events

    events = asyncio.run(main())
    artefak = [e for e in events if isinstance(e, TaskArtifactUpdateEvent)]
    part = artefak[0].artifact.parts[0]
    return getattr(part, "text", None) or part.root.text, fake


# --- pertanyaan spesifik: disempitkan ke satu pasangan ------------------------------------


def test_pertanyaan_stok_satu_pasangan_tidak_menyodorkan_seluruh_tabel():
    teks, fake = _jalan("berapa stok telur di SPPG Jakarta?")

    assert "Pasokan dan kebutuhan telur di SPPG Jakarta" in teks
    assert "Keseimbangan pasokan per SPPG" not in teks  # bukan lagi tabel 40 baris
    assert "kurang 180 kg" in teks  # angka dari backend, bukan hitungan jembatan
    assert "Inventaris batch (1 batch" in teks  # batch disaring ke pasangan itu
    assert "balance_map:beras" not in fake.dipanggil  # komoditas lain tidak ditarik


def test_pertanyaan_spesifik_menjelaskan_angka_sap_bukan_stok():
    teks, _ = _jalan("berapa stok telur di SPPG Jakarta?")

    assert "Catatan pasokan terakhir yang dilaporkan SAP" in teks
    assert "bukan stok batch yang bisa dipakai" in teks


def test_catatan_sap_bertanggal_masa_depan_diberi_keterangan():
    """Jawaban nyata 26 Okt 2026 menulis "dicatat 4 Nov 2026" tanpa penjelasan tanggal masa depan."""
    class FakeDepan(FakeClient):
        def supply_point(self, location_id: str, commodity: str) -> dict:
            return {
                "quantity_kg": 902.85,
                "recorded_at": "2026-11-04T12:00:00+00:00",
                "source": "sap_sim",
            }

    teks, _ = _jalan("Berapa stok telur di SPPG Jakarta?", FakeDepan())

    assert "melewati hari ini" in teks


def test_pertanyaan_umum_tetap_menampilkan_ringkasan_semua_pasangan():
    teks, _ = _jalan("bagaimana kondisi pasokan?")

    assert "Keseimbangan pasokan per SPPG" in teks
    assert "1 kurang · 1 lebih" in teks  # surplus tidak tersembunyi di balik 12 baris


# --- sapaan & batch bermasalah: tidak dijawab tabel pasokan -------------------------------


def test_sapaan_dijawab_daftar_kemampuan_tanpa_tabel():
    teks, fake = _jalan("halo, kamu bisa bantu apa?")

    assert "Contoh yang bisa Anda tanyakan" in teks
    assert "| SPPG |" not in teks
    assert "batches" not in fake.dipanggil  # tidak menyentuh backend untuk sapaan


def test_sapaan_di_depan_pertanyaan_data_tetap_menjawab_data():
    """Ditemukan 26 Okt 2026: "Halo, ... kondisi pasokan beras ..." dijawab menu bantuan.

    Kata `halo` saja tidak boleh membatalkan pertanyaan data yang jelas; pengguna asli
    membuka percakapan dengan sapaan lalu langsung bertanya.
    """
    pesan = (
        "Halo, saya Kepala SPPG Jakarta. Tolong jelaskan kondisi pasokan beras "
        "di lokasi saya hari ini."
    )

    skill, _ = server.resolve_skill(pesan)

    assert skill == server.SKILL_SUPPLY
    teks, _ = _jalan(pesan)
    assert "Contoh yang bisa Anda tanyakan" not in teks


def test_permintaan_kemampuan_dengan_kalimat_lain_tetap_daftar_kemampuan():
    """Kebalikannya: "apa saja yang bisa Anda lakukan" dulu dijawab tabel pasokan."""
    teks, _ = _jalan(
        "Tolong jelaskan apa saja yang bisa Anda lakukan untuk membantu pekerjaan saya."
    )

    assert "Contoh yang bisa Anda tanyakan" in teks
    assert "Keseimbangan pasokan" not in teks


def test_sapaan_singkat_tanpa_kata_domain_tetap_daftar_kemampuan():
    for pesan in ("halo", "selamat pagi", "hai, apa kabar?"):
        teks, _ = _jalan(pesan)
        assert "Contoh yang bisa Anda tanyakan" in teks, pesan


# --- routing yang salah domain pada audit 26 Okt 2026 -------------------------------------


def test_keseimbangan_pasokan_dan_kebutuhan_masuk_pasokan_bukan_prakiraan():
    """"keseimbangan pasokan DAN kebutuhan" adalah tampilan saldo, bukan prakiraan."""
    skill, _ = server.resolve_skill(
        "Bagaimana keseimbangan pasokan dan kebutuhan telur di Bandung minggu ini?"
    )

    assert skill == server.SKILL_SUPPLY


def test_risiko_pemasok_dengan_kata_pengiriman_tetap_risiko_pemasok():
    """Kata `pengiriman` milik skill "belum tersedia" mencuri pertanyaan risiko pemasok."""
    skill, _ = server.resolve_skill(
        "Pemasok mana yang berisiko karena jarak pengiriman terlalu jauh?"
    )

    assert skill == server.SKILL_SUPPLIER_RISK


def test_pertanyaan_kesegaran_data_masuk_status_sistem():
    skill, _ = server.resolve_skill(
        "Kapan terakhir data diperbarui dan dari mana sumbernya?"
    )

    assert skill == server.SKILL_SYSTEM


def test_pesan_kosong_dijawab_daftar_kemampuan_bukan_tabel():
    """Pesan kosong/emoji saja tidak punya maksud apa pun — jangan tebak tabel 40 baris."""
    for pesan in ("", "   ", "\n", "🙏"):
        teks, _ = _jalan(pesan)
        assert "Contoh yang bisa Anda tanyakan" in teks, repr(pesan)


def test_batch_harus_dibuang_dijawab_kandidat_bukan_tabel_pasokan():
    teks, _ = _jalan("batch mana yang harus dibuang?")

    assert "Batch yang perlu ditinjau untuk pembuangan" in teks
    assert "Keseimbangan pasokan" not in teks
    assert "keputusan pembuangan" in teks  # keputusan tetap milik manusia
    assert "dikarantina" in teks  # label karantina, bukan nilai API mentah


# --- routing kata kunci yang dulu salah domain -------------------------------------------


def test_pemasok_berisiko_masuk_skill_risiko_bukan_direktori():
    skill, _ = server.resolve_skill("pemasok mana yang berisiko?")

    assert skill == server.SKILL_SUPPLIER_RISK


def test_po_sudah_disetujui_menyaring_rancangan():
    teks, _ = _jalan("PO mana yang sudah disetujui?")

    assert "Purchase order yang sudah disetujui atau dieksekusi (1 PO)" in teks
    assert "MC-EXTREME01" not in teks  # rancangan tidak menjawab "mana yang sudah disetujui"


# --- laporan batch bermasalah (unit, tanpa HTTP) ------------------------------------------


def test_batch_disposal_report_memuat_status_dan_peringatan_manusia():
    teks = report.batch_disposal_report(
        [
            {"location": "SPPG Jakarta", "commodity": "telur", "quantity_kg": 120.0,
             "safety_status": "fail", "freshness_score": 0.42,
             "quarantine_status": "quarantined", "usable_until": "2026-10-20T00:00:00+00:00"},
            {"location": "SPPG Bogor", "commodity": "beras", "quantity_kg": 400.0,
             "safety_status": "pass", "freshness_score": 0.91,
             "quarantine_status": "none", "usable_until": "2026-11-02T00:00:00+00:00"},
        ]
    )

    assert "1 dari 2 batch" in teks
    assert "SPPG Jakarta" in teks and "SPPG Bogor" not in teks
    assert "keputusan pembuangan" in teks


def test_batch_disposal_report_kosong_menyebut_jumlah_batch_diperiksa():
    teks = report.batch_disposal_report(
        [{"location": "SPPG Bogor", "commodity": "beras", "quantity_kg": 400.0,
          "safety_status": "pass", "quarantine_status": "none"}]
    )

    assert "Tidak ada batch" in teks and "1 batch diperiksa" in teks


# --- kebersihan kata di chat ---------------------------------------------------------------
# Juri membaca jawaban sebagai bahasa aplikasi. Kode enum, path endpoint, nama berkas dokumen,
# dan nama tabel tidak boleh muncul; alasan yang bisa ditindaklanjuti tetap ditulis.

TERLARANG = [
    "supplier_procurement",
    "bgn_monitor",
    "mock_sap",
    "MAT-",
    "Rules.md",
    "/admin/users",
    "/compliance",
    "HTTP 4",
    "ditolak backend",
    "GAGAL",
    "AKTIF",
    "tanpa geometri jalan",
]


def test_tidak_ada_kode_internal_di_jawaban_antrean_dan_po():
    teks = report.approval_queue_report(
        [
            {"id": "dec-1", "status": "pending_approval", "decisionType": "supplier_procurement",
             "sourceLocation": "Cianjur", "targetLocation": "Bandung", "commodity": "beras",
             "quantityKg": 200.0}
        ]
    )
    teks += report.purchase_order_report(
        [{"po_number": "MC-661695B2C685", "status": "confirmed", "destination_location": "Jakarta",
          "material_name": "beras", "material_number": "MAT-BERA", "quantity_kg": 600.0,
          "unit_price": 13300.0, "total_amount": 7980000.0, "origin": "decision_execution",
          "decision_status": "executed"}]
    )

    assert "pengadaan pemasok" in teks  # jenis keputusan diterjemahkan
    for kata in TERLARANG:
        assert kata not in teks, f"kata internal bocor ke chat: {kata}"


def test_nama_kpi_memakai_bahasa_indonesia_dan_nilai_tetap():
    teks = report.kpi_report(
        {
            "metrics": [
                {"name": "Meal Continuity Rate", "state": "available", "value": 74.95,
                 "unit": "percent"},
                {"name": "Decision Time", "state": "available", "value": 20.0, "unit": "minutes"},
                {"name": "Metrik Karangan", "state": "available", "value": 1.0, "unit": None},
            ]
        }
    )

    assert "Keberlanjutan menu" in teks and "Waktu keputusan" in teks
    assert "Meal Continuity Rate" not in teks
    assert "Metrik Karangan" in teks  # nama tak dikenal lolos apa adanya, tidak dikarang
    assert "74,95%" in teks


def test_eksklusi_pemasok_memakai_huruf_kecil_dan_tanpa_istilah_geometri():
    teks = report.supplier_risk_report(
        [
            {"supplierName": "CV Uji", "scopeLocationName": "Jakarta", "status": "active",
             "reason": "suhu kiriman di atas ambang", "effective_from": None,
             "revoked_at": None}
        ],
        {"routes": [], "summary": {"routes": 1, "with_road": 1, "without_road": 0,
                                   "journey_states": {"dalam perjalanan": 1}}},
    )

    assert "| aktif |" in teks
    assert "AKTIF" not in teks
    assert "geometri" not in teks


# --- rujukan pendek (8 karakter) -----------------------------------------------------------
# Tabel chat tidak menampung 36 karakter per baris, tetapi potongan itu tetap bisa dipakai
# untuk membuka satu record: `server._resolve_id` mencocokkan persis dulu, lalu awalan unik.

ID_UTUH = "0edf11eb-4b09-4af7-a388-c12ef153a48c"


def test_tabel_antrean_dan_karantina_memakai_id_pendek():
    teks = report.approval_queue_report(
        [
            {"id": ID_UTUH, "status": "pending_approval", "decisionType": "price_anomaly",
             "sourceLocation": "Cianjur", "targetLocation": "Bandung", "commodity": "telur",
             "quantityKg": 600.0}
        ]
    )
    teks += report.quarantine_report(
        [{"id": "467caaad-9d7b-559d-8f81-3e5efd48d53f", "commodity": "beras", "quantity_kg": 540.0,
          "location": "Jakarta", "safety_status": "needs_verification",
          "quarantine_status": "quarantined"}]
    )

    assert "0edf11eb" in teks and ID_UTUH not in teks
    assert "467caaad" in teks and "467caaad-9d7b" not in teks
    assert "8 karakter pertama" in teks  # cara memakai rujukan pendek ikut dijelaskan

