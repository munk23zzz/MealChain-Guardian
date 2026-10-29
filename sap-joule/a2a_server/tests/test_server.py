"""Test `server.py`: kartu agen, `/health`, routing skill deterministik, dan siklus hidup A2A.

Semua test di sini memakai `FakeClient` — tidak ada backend MealChain yang perlu hidup.
"""

from __future__ import annotations

import asyncio

from a2a.server.events import EventQueue
from a2a.types import (
    Message,
    MessageSendParams,
    Role,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)
from fastapi.testclient import TestClient

import server
from mealchain_client import MealchainRejected, MealchainUnavailable


class FakeClient:
    """Klien palsu: menjawab seperti backend, dan bisa disuruh gagal."""

    def __init__(self, *, gagal: bool = False) -> None:
        self.gagal = gagal
        self.dipanggil: list[str] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def close(self) -> None:
        return None

    def _cek(self) -> None:
        if self.gagal:
            raise MealchainUnavailable("backend MealChain tidak bisa dihubungi (uji)")

    def health(self) -> dict:
        self.dipanggil.append("health")
        if self.gagal:
            raise MealchainUnavailable("backend MealChain tidak bisa dihubungi (uji)")
        return {"status": "ok", "sap": {"data_source": "MOCK", "is_mixed": False}}

    def batches(self) -> list[dict]:
        self.dipanggil.append("batches")
        self._cek()
        return [
            {
                "id": "b-1",
                "location": "SPPG Jakarta",
                "location_id": "loc-1",
                "commodity": "telur",
                "quantity_kg": 120.0,
                "safety_status": "pass",
                "freshness_score": 0.7,
                "usable_until": "2026-10-20T00:00:00+00:00",
            }
        ]

    def suppliers(self) -> list[dict]:
        self.dipanggil.append("suppliers")
        self._cek()
        return [
            {
                "id": "sup-1",
                "name": "CV Cipinang Boga Utama",
                "location": "Jakarta",
                "commodity": "beras",
                "reliability": 0.92,
                "capacityKgPerWeek": 4200.0,
                "certification": "haccp",
                "address": "Jl. Cipinang Besar No. 12",
                "contactName": "Budi Santoso",
                "excludedAtHub": False,
                "shippingCount": 2,
                "shippingKg": 840.0,
                "shippingUntil": "2026-10-22T00:00:00+00:00",
            },
            {
                "id": "sup-2",
                "name": "UD Cipanas Telur Sejahtera",
                "location": "Cianjur",
                "commodity": "telur",
                "reliability": 0.86,
                "capacityKgPerWeek": 2100.0,
                "certification": "hygiene",
                "address": "Jl. Raya Cipanas No. 4",
                "contactName": "Asep",
                "excludedAtHub": True,
                "shippingCount": None,
                "shippingKg": None,
                "shippingUntil": None,
            },
        ]

    def balance_map(self, commodity: str) -> dict:
        self.dipanggil.append(f"balance_map:{commodity}")
        self._cek()
        return {
            "commodity": commodity,
            "locations": [
                {
                    "location": "SPPG Jakarta",
                    "supply_kg": 120.0,
                    "demand_kg": 300.0,
                    "surplus_kg": 0.0,
                    "shortage_kg": 180.0,
                    "status": "shortage",
                }
            ],
        }

    def kpi(
        self,
        days: int = 7,
        *,
        scope: str = "operational",
        demo_session_id: str | None = None,
    ) -> dict:
        # Fase 8: `render_skill` meneruskan cakupan/sesi; fake ini harus menerima
        # kontrak yang sama, bukan hanya `days`.
        self.dipanggil.append("kpi")
        self._cek()
        return {
            "metrics": [
                {
                    "name": "Meal Continuity Rate",
                    "unit": "percent",
                    "state": "available",
                    "value": "96.4",
                    "reason": None,
                }
            ]
        }

    def pending_decisions(self) -> list[dict]:
        self.dipanggil.append("pending_decisions")
        self._cek()
        return [
            {
                "id": "dec-001",
                "status": "pending_approval",
                "decisionType": "regional_balance",
                "quantityKg": 600.0,
                "sourceLocation": "Cianjur",
                "targetLocation": "Jakarta",
                "commodity": "telur",
            }
        ]

    def purchase_orders(self) -> list[dict]:
        self.dipanggil.append("purchase_orders")
        self._cek()
        return [
            {
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
        ]

    # --- read model baru (dipakai skill harga/kebutuhan/limbah/risiko/bukti/sistem) ---------

    def locations(self) -> list[dict]:
        self.dipanggil.append("locations")
        self._cek()
        return [
            {"id": "loc-1", "name": "Jakarta", "region": "DKI Jakarta"},
            {"id": "loc-2", "name": "Cianjur", "region": "Jawa Barat"},
        ]

    def supply_point(self, location_id: str, commodity: str) -> dict:
        self.dipanggil.append(f"supply_point:{location_id}/{commodity}")
        self._cek()
        return {
            "quantity_kg": 1207.32,
            "recorded_at": "2026-11-04T12:00:00+00:00",
            "source": "mock_sap",
        }

    def price(self, location_id: str, commodity: str) -> dict:
        self.dipanggil.append(f"price:{location_id}/{commodity}")
        self._cek()
        return {
            "location": "Jakarta",
            "commodity": commodity,
            "price_per_kg": 12225.53,
            "recorded_at": "2026-11-04T12:00:00+00:00",
            "source": "pihps_reference",
        }

    def price_quotes(self, location_id: str, commodity: str) -> dict:
        self.dipanggil.append(f"price_quotes:{location_id}/{commodity}")
        self._cek()
        return {
            "location": "Jakarta",
            "commodity": commodity,
            "quotes": [
                {
                    "supplier_name": "UD Rancaekek Beras Sejahtera",
                    "price_per_kg": 12039.42,
                    "recorded_at": "2026-11-03T00:00:00+00:00",
                }
            ],
        }

    def demand(self, location_id: str, commodity: str) -> dict:
        self.dipanggil.append(f"demand:{location_id}/{commodity}")
        self._cek()
        return {"quantity_kg": 957.04, "needed_by": "2026-11-07T00:00:00+00:00"}

    def demand_forecast(self, location_id: str, commodity: str) -> dict:
        self.dipanggil.append(f"demand_forecast:{location_id}/{commodity}")
        self._cek()
        return {"forecast_qty_kg": 6697.558, "method": "statistical_fallback", "confidence": 1.0}

    def waste_summary(self) -> dict:
        self.dipanggil.append("waste_summary")
        self._cek()
        return {
            "period": {
                "start": "2026-09-20T00:00:00+00:00",
                "end": "2026-10-20T00:00:00+00:00",
                "days": 30,
            },
            "scope": {"role": "bgn_monitor", "locations": ["Jakarta", "Cianjur"]},
            "computed_at": "2026-10-20T00:43:56+00:00",
            "recorded": {"available": True, "kg": 631.46, "events": 86},
            "diverted": {"available": True, "kg": 332.5, "events": 41},
            "unassigned": {"available": True, "kg": 298.96, "events": 45},
            "partners": [{"name": "PT Biogas Nusantara", "kg": 122.8, "events": 14}],
        }

    def supplier_exclusions(self) -> list[dict]:
        self.dipanggil.append("supplier_exclusions")
        self._cek()
        return [
            {
                "id": "exc-1",
                "supplier_id": "sup-1",
                "scope_location_id": "loc-1",
                "status": "active",
                "reason": "batch ayam gagal uji antibiotik",
                "activated_at": "2026-10-16T22:36:54+00:00",
                "revoked_at": None,
            }
        ]

    def supplier_routes(self) -> dict:
        self.dipanggil.append("supplier_routes")
        self._cek()
        return {
            "routes": [
                {
                    "supplierName": "CV Cipinang Boga Utama",
                    "destinationName": "Jakarta",
                    "commodity": "beras",
                    "quantityKg": 800.0,
                    "roadKm": 9.8,
                    "roadMinutes": 12.2,
                    "journeyState": "dalam perjalanan",
                    "etaAt": "2026-10-20T09:00:00+00:00",
                }
            ],
            "summary": {
                "routes": 1,
                "with_road": 1,
                "without_road": 0,
                "scope": "nasional",
                "journey_states": {"dalam_perjalanan": 1},
            },
        }

    def decisions(self) -> list[dict]:
        self.dipanggil.append("decisions")
        self._cek()
        return [
            {
                "decision_id": "cec7e30d-3eb5-4c29-82ee-c5fee581add1",
                "status": "proposed",
                "decision_type": "regional_balance",
                "quantity_kg": 600.0,
            }
        ]

    def decision_compliance(self, decision_id: str) -> dict:
        self.dipanggil.append(f"decision_compliance:{decision_id}")
        self._cek()
        return {
            "decision": {
                "id": decision_id,
                "decision_type": "regional_balance",
                "status": "proposed",
                "proposed_by": "supervisor_agent",
            },
            "evidence": [],
            "approvals": [],
            "traces": [{"step_name": "LEARN", "tool_called": "rejection_loop.repropose"}],
            "content_address": "mc1-13i7rjc532qre22o835j3ffb5sxqn2rzsi7pd2hda82zdg442w",
            "signature": {
                "state": "signed",
                "algorithm": "ECDSA-secp256k1-sha256 (deterministic RFC6979)",
                "signature": "95b57211c6ef5b6139a32703e21327d662c9eee2bd26d418f2bb73631bd7166e" * 2,
            },
            "verify": True,
        }

    def decision_packet(self, decision_id: str) -> dict:
        """Fase 6 butir 4: satu read model keputusan (bentuk yang sama dengan layar)."""
        self.dipanggil.append(f"decision_packet:{decision_id}")
        self._cek()
        return {
            "decision_id": decision_id,
            "batch_evaluations": [
                {"batch_id": "b-1", "status": "usable", "blocking_reasons": []},
                {
                    "batch_id": "b-2",
                    "status": "on_hold",
                    "blocking_reasons": ["temperature_evidence_incomplete"],
                },
            ],
            "costs": None,
            "delivery": {"due_at": None, "needed_by": None, "feasible": None},
            "evidence": {"source_types": [], "source_refs": [], "completeness": {}},
            "review": {"verifier": None, "approvals": [], "blocking_reasons": []},
        }

    def decision_chain(self, decision_id: str) -> dict:
        self.dipanggil.append(f"decision_chain:{decision_id}")
        self._cek()
        return {
            "anchor_id": decision_id,
            "chain": [
                {
                    "decision_id": decision_id,
                    "iteration": 2,
                    "status": "proposed",
                    "rejection_reason": None,
                    "quantity_kg": 600.0,
                    "created_at": "2026-10-19T20:33:04+00:00",
                }
            ],
        }

    def decision_traces(self, decision_id: str) -> dict:
        self.dipanggil.append(f"decision_traces:{decision_id}")
        self._cek()
        return {
            "decision_id": decision_id,
            "steps": [
                {
                    "step_name": "LEARN",
                    "tool_called": "rejection_loop.repropose",
                    "output_summary": {"learning_note": "harga terlalu tinggi — cari sumber lebih dekat"},
                    "step_at": "2026-10-19T20:33:04+00:00",
                }
            ],
        }

    def integrations_status(self) -> dict:
        self.dipanggil.append("integrations_status")
        self._cek()
        return {
            "checked_at": "2026-10-20T00:43:56+00:00",
            "components": [
                {
                    "id": "mock_sap",
                    "name": "Mock SAP (sap_integration)",
                    "category": "contract_tested",
                    "category_label": "kontrak diuji",
                    "evidence": "layanan mock-sap + tes kontrak PO",
                },
                {
                    "id": "agentcore_gateway",
                    "name": "AgentCore Gateway",
                    "category": "not_started",
                    "category_label": "belum dimulai",
                    "evidence": "env AGENTCORE_GATEWAY_URL kosong",
                },
            ],
        }

    def ledger_verify(self) -> dict:
        self.dipanggil.append("ledger_verify")
        self._cek()
        return {
            "valid": True,
            "blocks": 115,
            "head": "bdeeefb7f7b13441cd7432d8af5010b4946c3a8f5a23ea503343a1e652789a48",
            "linked_blocks": 115,
            "orphan_blocks": 0,
            "linked_ratio": 1.0,
            "coverage_warning": None,
        }

    def po_summary(self) -> dict:
        self.dipanggil.append("po_summary")
        self._cek()
        return {
            "by_status": {"draft": 0, "submitted": 9, "confirmed": 14},
            "count": 23,
            "total_value": 227295034.0,
            "scope": "nasional",
            "source": "mock_sap_table",
        }

    def receipts(self, batch_id: str) -> list[dict]:
        self.dipanggil.append(f"receipts:{batch_id}")
        self._cek()
        return [
            {
                "recorded_at": "2026-10-20T03:00:00+00:00",
                "recorded_by_name": "Petugas Gudang Jakarta",
                "checked": {"suhu": True, "catatan": True, "kemasan": False, "berat_kg": True},
                "other_note": "selisih 20 kg dilaporkan",
            }
        ]


def _app(fake: FakeClient):
    return server.build_app(client_factory=lambda: fake, app_url="http://bridge.test")


# --- routing skill (deterministik, tanpa model bahasa) -----------------------------------


def test_routing_json_eksplisit_menang():
    assert server.resolve_skill('{"skill": "kpi_snapshot"}')[0] == "kpi_snapshot"
    assert server.resolve_skill('{"skill": "approval_queue"}')[0] == "approval_queue"
    assert server.resolve_skill('{"skill": "supply_situation"}')[0] == "supply_situation"

def test_rujukan_pendek_dari_tabel_diteruskan_sebagai_payload():
    """Yang tampil di tabel (8 karakter) harus bisa dipakai di pertanyaan lanjutan."""
    skill, payload = server.resolve_skill("bukti keputusan cec7e30d")
    assert skill == server.SKILL_EVIDENCE
    assert payload["decision_id"] == "cec7e30d"

    skill, payload = server.resolve_skill("penerimaan barang batch 45204477")
    assert skill == server.SKILL_SUPPLY
    assert payload["batch_id"] == "45204477"

    # id utuh tetap diambil utuh, bukan terpotong oleh pola rujukan pendek
    skill, payload = server.resolve_skill("bukti keputusan cec7e30d-3eb5-4c29-82ee-c5fee581add1")
    assert payload["decision_id"] == "cec7e30d-3eb5-4c29-82ee-c5fee581add1"

def test_po_bernomor_sap_dibuka_rinciannya():
    """Nomor PO hasil impor SAP hanya angka; rincian harus tetap bisa dibuka."""
    skill, payload = server.resolve_skill("tampilkan PO 4500000001")
    assert skill == server.SKILL_PO
    assert payload["po_number"] == "4500000001"

    # nominal rupiah tidak boleh diperlakukan sebagai nomor dokumen
    skill, payload = server.resolve_skill("PO mana yang totalnya Rp14.100.000?")
    assert skill == server.SKILL_PO
    assert "po_number" not in payload




def test_routing_json_tidak_dikenal_kembali_ke_kata_kunci():
    assert server.resolve_skill('{"skill": "hapus-semua"}')[0] == "supply_situation"
    assert server.resolve_skill('{"skill": "hapus-semua", "teks": "kpi" }')[0] == "supply_situation"


def test_routing_kata_kunci_dan_default():
    assert server.resolve_skill("Tampilkan KPI minggu ini")[0] == "kpi_snapshot"
    assert server.resolve_skill("Apa saja usulan yang menunggu persetujuan?")[0] == "approval_queue"
    assert server.resolve_skill("Bagaimana kondisi pasokan SPPG Jakarta?")[0] == "supply_situation"
    assert server.resolve_skill("")[0] == "supply_situation"


def test_routing_kpi_dimenangkan_atas_antrean():
    # "usulan KPI" harus dibaca sebagai permintaan KPI, bukan antrean usulan.
    assert server.resolve_skill("lihat usulan kpi")[0] == "kpi_snapshot"


def test_routing_nomor_po_membawa_nomornya():
    skill, payload = server.resolve_skill("Tampilkan PO MC-661695B2C685")

    assert skill == "purchase_order"
    assert payload["po_number"] == "MC-661695B2C685"


def test_routing_po_dimenangkan_atas_kata_kunci_antrean():
    """Pertanyaan PO sering memuat kata `setuju`/`keputusan` milik skill antrean."""
    assert server.resolve_skill("PO mana yang sudah disetujui?")[0] == "purchase_order"
    assert server.resolve_skill("purchase order dari keputusan tadi")[0] == "purchase_order"
    assert server.resolve_skill("status pesanan pembelian terbaru")[0] == "purchase_order"


def test_routing_po_tidak_menarik_kata_yang_mengandung_po():
    # Batas kata: "produk"/"pasokan" bukan permintaan PO.
    assert server.resolve_skill("stok produk unggulan?")[0] == "supply_situation"
    assert server.resolve_skill("bagaimana pasokan hari ini?")[0] == "supply_situation"
    # "keputusan" tanpa PO tetap milik antrean.
    assert server.resolve_skill("keputusan yang menunggu persetujuan")[0] == "approval_queue"


def test_routing_direktori_pemasok_tetapi_antrean_tetap_menang():
    assert server.resolve_skill("Tampilkan direktori pemasok")[0] == "supplier_directory"
    assert server.resolve_skill("daftar supplier SPPG Jakarta")[0] == "supplier_directory"
    # "usulan eksklusi pemasok" adalah keputusan, bukan permintaan direktori.
    assert server.resolve_skill("usulan eksklusi pemasok")[0] == "approval_queue"


# --- kartu agen & /health -----------------------------------------------------------------


def test_agent_card_di_well_known_berisi_empat_belas_skill():
    with TestClient(_app(FakeClient())) as client:
        card = client.get("/.well-known/agent-card.json").json()

    ids = [skill["id"] for skill in card["skills"]]
    assert ids == [
        "supply_situation",
        "kpi_snapshot",
        "approval_queue",
        "receipts_queue",
        "quarantine_status",
        "batch_detail",
        "purchase_order",
        "supplier_directory",
        "price_intelligence",
        "demand_forecast",
        "food_loss",
        "supplier_risk",
        "decision_evidence",
        "system_status",
    ]
    assert card["url"] == "http://bridge.test"
    assert card["capabilities"]["streaming"] is False


def test_health_selalu_200_dan_melaporkan_keterjangkauan_backend():
    with TestClient(_app(FakeClient())) as client:
        hidup = client.get("/health")
    assert hidup.status_code == 200
    assert hidup.json()["backend"]["reachable"] is True
    assert hidup.json()["backend"]["sap"]["data_source"] == "MOCK"

    with TestClient(_app(FakeClient(gagal=True))) as client:
        mati = client.get("/health")
    assert mati.status_code == 200  # CF tidak boleh me-restart aplikasi karena backend mati
    assert mati.json()["backend"]["reachable"] is False
    assert "tidak bisa dihubungi" in mati.json()["backend"]["detail"]


# --- siklus hidup A2A -------------------------------------------------------------------


def _context(teks: str):
    pesan = Message(message_id="m-1", role=Role.user, parts=[TextPart(text=teks)])
    return server.RequestContext(request=MessageSendParams(message=pesan))


def _jalan(executor: server.MealchainExecutor, teks: str):
    """Jalankan satu tugas A2A dan kembalikan daftar event yang diterbitkan."""

    async def main():
        queue = EventQueue()
        context = _context(teks)
        await executor.execute(context, queue)

        events = []
        while True:
            try:
                events.append(await queue.dequeue_event(no_wait=True))
            except asyncio.QueueEmpty:
                break
        return events

    return asyncio.run(main())


def _teks_artefak(event: TaskArtifactUpdateEvent) -> str:
    part = event.artifact.parts[0]
    return getattr(part, "text", None) or part.root.text


def test_execute_menerbitkan_working_artefak_lalu_completed():
    fake = FakeClient()
    events = _jalan(server.MealchainExecutor(lambda: fake), "Bagaimana kondisi pasokan?")

    assert isinstance(events[0], TaskStatusUpdateEvent)
    assert events[0].status.state is TaskState.working and events[0].final is False
    assert isinstance(events[1], TaskArtifactUpdateEvent)
    assert events[1].artifact.artifact_id == "mealchain_report"
    assert isinstance(events[2], TaskStatusUpdateEvent)
    assert events[2].status.state is TaskState.completed and events[2].final is True

    teks = _teks_artefak(events[1])
    assert "SPPG Jakarta" in teks and "telur" in teks
    assert "kurang 180 kg" in teks
    assert "MOCK" in teks  # penanda sumber data ikut (Rules.md §1.4)
    assert fake.dipanggil[:1] == ["health"]
    assert "batches" in fake.dipanggil and "balance_map:telur" in fake.dipanggil


def test_execute_untuk_kpi_tidak_memanggil_endpoint_pasokan():
    fake = FakeClient()
    events = _jalan(server.MealchainExecutor(lambda: fake), '{"skill": "kpi_snapshot"}')

    teks = _teks_artefak(events[1])
    assert "96,4%" in teks
    # Skill KPI tidak boleh menyentuh read model pasokan.
    assert "batches" not in fake.dipanggil and "balance_map" not in "".join(fake.dipanggil)


def test_backend_mati_tetap_menghasilkan_artefak_jujur_dan_tugas_selesai():
    fake = FakeClient(gagal=True)
    events = _jalan(server.MealchainExecutor(lambda: fake), "kondisi pasokan?")

    assert isinstance(events[1], TaskArtifactUpdateEvent)
    teks = _teks_artefak(events[1])
    assert "belum bisa diambil" in teks
    assert "bukan berarti kondisinya aman" in teks
    assert events[2].status.state is TaskState.completed


def test_galat_tak_terduga_tidak_menggantung_pemanggil():
    class Meledak(FakeClient):
        def batches(self):  # type: ignore[override]
            raise RuntimeError("kode rusak")

    events = _jalan(server.MealchainExecutor(lambda: Meledak()), "kondisi pasokan?")

    assert "galat tak terduga" in _teks_artefak(events[1])
    assert events[2].status.state is TaskState.completed


def test_cancel_menutup_tugas():
    async def main():
        queue = EventQueue()
        context = _context("apa saja")
        await server.MealchainExecutor(lambda: FakeClient()).cancel(context, queue)
        return await queue.dequeue_event(no_wait=True)

    event = asyncio.run(main())

    assert isinstance(event, TaskStatusUpdateEvent)
    assert event.status.state is TaskState.canceled and event.final is True


# --- kesesuaian klien nyata dengan protokol jembatan --------------------------------------


def test_klien_nyata_memenuhi_protokol_jembatan():
    """Regresi: `server.py` memanggil metode ini, jadi klien nyata WAJIB memilikinya.

    Tanpa tes ini, perubahan klien (mis. pindah dari `/ui/*` v0.1.0 ke API v0.2.0) bisa
    meninggalkan `server.py` memanggil metode yang tidak ada — dan tes lain tidak menangkapnya
    karena memakai klien palsu sendiri. Kasus itu nyata terjadi 2026-10-11.
    """
    from mealchain_client import MealchainClient

    for nama in (
        "health",
        "batches",
        "balance_map",
        "kpi",
        "pending_decisions",
        "purchase_orders",
        "close",
        "__enter__",
        "__exit__",
    ):
        assert callable(getattr(MealchainClient, nama, None)), f"MealchainClient kehilangan {nama}"


def test_skill_antrean_menampilkan_asal_tujuan_dan_komoditas():
    events = _jalan(
        server.MealchainExecutor(lambda: FakeClient()), '{"skill": "approval_queue"}'
    )
    teks = _teks_artefak(events[1])

    assert "Cianjur → Jakarta" in teks
    assert "telur" in teks
    assert "600 kg" in teks
    assert "Persetujuan tidak bisa dilakukan dari Joule" in teks


def test_skill_direktori_pemasok_menampilkan_hub_dan_kiriman():
    fake = FakeClient()
    events = _jalan(server.MealchainExecutor(lambda: fake), "Tampilkan direktori pemasok")
    teks = _teks_artefak(events[1])

    assert "suppliers" in fake.dipanggil
    assert "batches" not in fake.dipanggil  # direktori tidak memanggil endpoint pasokan
    assert "CV Cipinang Boga Utama" in teks
    assert "Jakarta" in teks and "beras" in teks
    assert "2 batch" in teks and "840 kg" in teks
    assert "dikecualikan di hub" in teks
    assert "belum mengirim" in teks


def test_komoditas_tanpa_keseimbangan_tidak_mematikan_seluruh_laporan():
    """Satu komoditas yang 404 di `/balance/map` tidak boleh mengubah laporan jadi "tidak tersedia".

    Terukur pada DB demo: komoditas berasal dari `/batches`, sedangkan `/balance/map` menolak
    komoditas yang tidak dikenal (HTTP 404 "commodity tidak ditemukan"). Sebelum perbaikan ini,
    satu komoditas baru di inventaris membuat SELURUH jawaban pasokan gagal — Joule hanya
    menampilkan pesan error padahal tabel batch-nya masih bisa dibaca.
    """

    class KlienSebagian(FakeClient):
        def batches(self) -> list[dict]:
            self.dipanggil.append("batches")
            return [
                {
                    "id": "b-1",
                    "location": "SPPG Jakarta",
                    "commodity": "telur",
                    "quantity_kg": 120.0,
                    "safety_status": "pass",
                    "freshness_score": 0.7,
                    "usable_until": "2026-10-20T00:00:00+00:00",
                },
                {
                    "id": "b-2",
                    "location": "SPPG Bandung",
                    "commodity": "wortel",
                    "quantity_kg": 80.0,
                    "safety_status": "pass",
                    "freshness_score": 0.9,
                    "usable_until": "2026-10-21T00:00:00+00:00",
                },
            ]

        def balance_map(self, commodity: str) -> dict:
            if commodity == "wortel":
                raise MealchainRejected(
                    "/balance/map ditolak backend (HTTP 404): commodity tidak ditemukan"
                )
            return super().balance_map(commodity)

    teks = server.render_skill(KlienSebagian(), server.SKILL_SUPPLY)

    assert "telur" in teks, "komoditas yang datanya lengkap harus tetap tampil"
    assert "wortel" in teks, "batch wortel tetap harus terlihat di tabel inventaris"
    assert "Keseimbangan tidak terbaca untuk: wortel" in teks
    assert "bukan berarti nol" in teks
    assert "tidak dapat" not in teks.lower(), "laporan tidak boleh jatuh ke pesan 'tidak tersedia'"


def test_skill_po_mengirim_rincian_po_dan_tidak_menyentuh_pasokan():
    fake = FakeClient()
    events = _jalan(
        server.MealchainExecutor(lambda: fake),
        '{"skill": "purchase_order", "po_number": "MC-661695B2C685"}',
    )
    teks = _teks_artefak(events[1])

    assert "Purchase order MC-661695B2C685" in teks
    assert "Telur Berkah" in teks
    assert "600 kg" in teks
    assert "Rp10.800.000" in teks
    assert "purchase_orders" in fake.dipanggil
    assert "batches" not in fake.dipanggil, "skill PO tidak boleh membaca read model pasokan"


# --- skill baru: harga, kebutuhan, limbah, risiko, bukti, sistem --------------------------


def test_routing_skill_baru_dikenali_dari_kata_kunci():
    assert server.resolve_skill("berapa harga beras di Jakarta?")[0] == "price_intelligence"
    assert server.resolve_skill("tampilkan kuotasi pemasok beras")[0] == "price_intelligence"
    assert server.resolve_skill("berapa kebutuhan telur minggu ini?")[0] == "demand_forecast"
    assert server.resolve_skill("prakiraan kebutuhan beras")[0] == "demand_forecast"
    assert server.resolve_skill("berapa limbah pangan bulan ini?")[0] == "food_loss"
    assert server.resolve_skill("kehilangan pangan sebulan terakhir")[0] == "food_loss"
    assert server.resolve_skill("pemasok mana yang dikecualikan?")[0] == "supplier_risk"
    assert server.resolve_skill("rute kiriman ke Jakarta")[0] == "supplier_risk"
    assert server.resolve_skill("tunjukkan bukti keputusan terakhir")[0] == "decision_evidence"
    assert server.resolve_skill("status integrasi SAP")[0] == "system_status"
    assert server.resolve_skill("apakah ledger masih sah?")[0] == "system_status"


def test_routing_skill_baru_tidak_merebut_skill_lama():
    """Kata kunci baru bertumpang-tindih dengan yang lama; urutan prioritas harus menang."""
    # "usulan" milik antrean, walau kalimatnya menyebut eksklusi pemasok.
    assert server.resolve_skill("usulan eksklusi pemasok")[0] == "approval_queue"
    assert server.resolve_skill("keputusan yang menunggu persetujuan")[0] == "approval_queue"
    # "pemasok" tanpa kata eksklusi/rute/harga tetap direktori.
    assert server.resolve_skill("direktori pemasok")[0] == "supplier_directory"
    # KPI menang atas "kehilangan" (nama metrik KPI juga memuat kata itu).
    assert server.resolve_skill("KPI kehilangan pangan")[0] == "kpi_snapshot"
    assert server.resolve_skill("Tampilkan KPI minggu ini")[0] == "kpi_snapshot"
    assert server.resolve_skill("PO mana yang sudah disetujui?")[0] == "purchase_order"
    # Nama komoditas yang mengandung kata lain tidak boleh memicu filter salah.
    assert server.resolve_skill("bagaimana pasokan bayam?")[0] == "supply_situation"


def test_routing_bukti_membawa_id_keputusan():
    skill, payload = server.resolve_skill(
        "jelaskan bukti keputusan cec7e30d-3eb5-4c29-82ee-c5fee581add1"
    )

    assert skill == "decision_evidence"
    assert payload["decision_id"] == "cec7e30d-3eb5-4c29-82ee-c5fee581add1"


def test_routing_penerimaan_barang_membawa_id_batch():
    skill, payload = server.resolve_skill(
        "penerimaan barang batch 11111111-2222-3333-4444-555555555555"
    )

    assert skill == "supply_situation"
    assert payload["batch_id"] == "11111111-2222-3333-4444-555555555555"


def test_skill_harga_menampilkan_acuan_dan_kuotasi():
    fake = FakeClient()
    events = _jalan(server.MealchainExecutor(lambda: fake), "berapa harga beras di Jakarta?")
    teks = _teks_artefak(events[1])

    assert "Rp12.226" in teks, "harga acuan per kg dari backend harus tampil"
    assert "acuan PIHPS" in teks
    assert "UD Rancaekek Beras Sejahtera" in teks and "Rp12.039" in teks
    assert "price:loc-1/telur" in fake.dipanggil
    assert not any(p.startswith("balance_map") for p in fake.dipanggil), (
        "skill harga tidak boleh menyentuh read model pasokan"
    )


def test_skill_kebutuhan_menampilkan_prakiraan_dan_metodenya():
    events = _jalan(
        server.MealchainExecutor(lambda: FakeClient()), '{"skill": "demand_forecast"}'
    )
    teks = _teks_artefak(events[1])

    assert "957 kg" in teks
    assert "6.697,6 kg" in teks
    assert "cadangan statistik" in teks, "metode prakiraan harus terbaca, bukan disembunyikan"
    assert "Keyakinan (0–1)" in teks


def test_skill_kehilangan_pangan_memisahkan_tiga_angka():
    events = _jalan(server.MealchainExecutor(lambda: FakeClient()), "berapa limbah pangan?")
    teks = _teks_artefak(events[1])

    assert "631,5 kg · 86 kejadian" in teks
    assert "332,5 kg · 41 kejadian" in teks, "yang dialihkan ke mitra harus terpisah"
    assert "299 kg · 45 kejadian" in teks, "yang belum punya mitra harus terpisah"
    assert "PT Biogas Nusantara" in teks


def test_skill_risiko_pemasok_menerjemahkan_id_menjadi_nama():
    events = _jalan(
        server.MealchainExecutor(lambda: FakeClient()), "pemasok mana yang dikecualikan?"
    )
    teks = _teks_artefak(events[1])

    assert "CV Cipinang Boga Utama" in teks, "supplier_id harus diterjemahkan ke nama"
    assert "Jakarta" in teks
    assert "aktif" in teks and "batch ayam gagal uji antibiotik" in teks
    assert "9,8 km" in teks and "dalam perjalanan" in teks


def test_skill_bukti_menampilkan_tanda_tangan_rantai_dan_jejak():
    events = _jalan(
        server.MealchainExecutor(lambda: FakeClient()),
        '{"skill": "decision_evidence", "decision_id": "cec7e30d-3eb5-4c29-82ee-c5fee581add1"}',
    )
    teks = _teks_artefak(events[1])

    assert "bertanda tangan" in teks
    assert "verifikasi materi: cocok" in teks
    assert "mc1-13i7rjc" in teks
    assert "LEARN" in teks and "rejection_loop.repropose" in teks
    assert "harga terlalu tinggi" in teks


def test_skill_sistem_menampilkan_integrasi_ledger_dan_po():
    events = _jalan(
        server.MealchainExecutor(lambda: FakeClient()), "status integrasi dan ledger"
    )
    teks = _teks_artefak(events[1])

    assert "Mock SAP (sap_integration)" in teks
    assert "belum dimulai" in teks, "komponen yang belum jalan tidak boleh tampil hijau"
    assert "SAH" in teks
    assert "Rp227.295.034" in teks
    assert "Jaringan SPPG (2 lokasi)" in teks


def test_pasokan_menyebut_satu_pasangan_membaca_baris_pasokan_terakhir():
    fake = FakeClient()
    events = _jalan(server.MealchainExecutor(lambda: fake), "pasokan telur di SPPG Jakarta")
    teks = _teks_artefak(events[1])

    assert "supply_point:loc-1/telur" in fake.dipanggil
    assert "Catatan pasokan terakhir yang dilaporkan SAP" in teks
    assert "1.207,3 kg" in teks and "integrasi SAP simulasi" in teks  # sumber diterjemahkan, token mentah tidak tampil

def test_rujukan_pendek_membuka_keputusan_yang_tepat():
    """8 karakter pertama dari tabel chat harus bisa dipakai membuka bukti keputusan."""
    fake = FakeClient()
    events = _jalan(server.MealchainExecutor(lambda: fake), "bukti keputusan cec7e30d")
    teks = _teks_artefak(events[1])

    assert "decision_compliance:cec7e30d-3eb5-4c29-82ee-c5fee581add1" in fake.dipanggil
    assert "Keputusan cec7e30d" in teks  # tampil pendek, walau yang dibuka id utuh


def test_rujukan_pendek_ambigu_tidak_ditebak():
    utuh, galat = server._resolve_id(
        "cec7", ["cec7e30d-3eb5-4c29-82ee-c5fee581add1", "cec7ffff-1111-2222-3333-444444444444"],
        sebutan="keputusan",
    )

    assert utuh == "cec7" and galat is not None
    assert "2 keputusan yang cocok" in galat
    assert "tidak memilih salah satu" in galat


def test_rujukan_pendek_tidak_ditemukan_dan_id_utuh_diteruskan():
    _, galat = server._resolve_id("zzzz", ["cec7e30d-3eb5-4c29-82ee-c5fee581add1"], sebutan="batch")
    assert galat is not None and "Tidak ada batch" in galat

    # id utuh di luar daftar tetap diteruskan: backend yang memutuskan, bukan jembatan.
    asing = "1f2e3d4c-5b6a-4798-8a9b-0c1d2e3f4a5b"
    utuh, galat = server._resolve_id(asing, [], sebutan="keputusan")
    assert utuh == asing and galat is None



def test_penerimaan_barang_dibaca_per_batch_yang_disebut():
    fake = FakeClient()
    events = _jalan(
        server.MealchainExecutor(lambda: fake),
        "penerimaan barang batch 11111111-2222-3333-4444-555555555555",
    )
    teks = _teks_artefak(events[1])

    assert "receipts:11111111-2222-3333-4444-555555555555" in fake.dipanggil
    assert "Penerimaan barang untuk batch" in teks
    # Batch spesifik = jawaban spesifik: tabel pasokan tidak ikut disodorkan.
    assert "Keseimbangan pasokan per SPPG" not in teks
    assert "kemasan: belum" in teks and "selisih 20 kg dilaporkan" in teks


def test_bukti_keputusan_membawa_paket_dari_endpoint_paket():
    """Fase 6 butir 4: jembatan meneruskan paket keputusan, bukan merakit sendiri.

    Laporan bukti harus memuat state bukti batch yang DIKIRIM backend; jembatan
    tidak menghitung ulang skor apa pun.
    """
    fake = FakeClient()
    events = _jalan(server.MealchainExecutor(lambda: fake), "bukti keputusan cec7e30d")
    teks = _teks_artefak(events[1])

    assert "decision_packet:cec7e30d-3eb5-4c29-82ee-c5fee581add1" in fake.dipanggil
    assert "State bukti batch" in teks
    assert "2 dievaluasi" in teks and "1 ditahan" in teks
