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
from mealchain_client import MealchainUnavailable


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
                "commodity": "telur",
                "quantity_kg": 120.0,
                "safety_status": "pass",
                "freshness_score": 0.7,
                "usable_until": "2026-10-20T00:00:00+00:00",
            }
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

    def kpi(self, days: int = 7) -> dict:
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


def _app(fake: FakeClient):
    return server.build_app(client_factory=lambda: fake, app_url="http://bridge.test")


# --- routing skill (deterministik, tanpa model bahasa) -----------------------------------


def test_routing_json_eksplisit_menang():
    assert server.resolve_skill('{"skill": "kpi_snapshot"}')[0] == "kpi_snapshot"
    assert server.resolve_skill('{"skill": "approval_queue"}')[0] == "approval_queue"
    assert server.resolve_skill('{"skill": "supply_situation"}')[0] == "supply_situation"


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


# --- kartu agen & /health -----------------------------------------------------------------


def test_agent_card_di_well_known_berisi_tiga_skill():
    with TestClient(_app(FakeClient())) as client:
        card = client.get("/.well-known/agent-card.json").json()

    ids = [skill["id"] for skill in card["skills"]]
    assert ids == ["supply_situation", "kpi_snapshot", "approval_queue"]
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
    assert "Persetujuan TIDAK bisa dilakukan dari Joule" in teks
