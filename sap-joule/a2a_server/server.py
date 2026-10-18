"""A2A server MealChain Guardian — jembatan BACA-SAJA ke SAP Joule (Bring Your Own Agent).

Alur (pola dari tutorial `joule_a2a/` repo hackathon SAP-AWS, Apache-2.0 — lihat `NOTICE`):

    Joule chat → scenario → function `agent-request` → BTP Destination
      → app ini (Cloud Foundry) → endpoint baca backend MealChain v0.2.0 → markdown → artefak A2A → Joule

Kenapa hanya BACA dan kenapa angka tidak dihitung di sini:

* `Rules.md` §1.1 — angka safety-critical keluar dari modul deterministik backend, bukan dari
  model bahasa. Karena itu modul ini tidak menjumlahkan apa pun; `report.py` hanya memformat.
* `Rules.md` §1.2 — tidak ada auto-execute. Joule boleh MELIHAT antrean usulan, tetapi
  persetujuan tetap di UI MealChain memakai token approver sendiri.
* Joule menunggu sinkron maksimum 60 detik (troubleshooting tutorial latihan 03). Karena itu
  setiap skill memanggil endpoint baca yang cepat, tanpa rantai model.

Pemilihan skill DETERMINISTIK (bukan LLM):

1. pesan berbentuk JSON dengan field `skill` — kontrak eksplisit, dipakai test & A2A Editor; atau
2. kata kunci pada teks pesan (`kpi`/`indikator` → KPI; `approval`/`persetujuan`/`usulan` → antrean
   usulan), sisanya → situasi pasokan.

Batas yang jujur: routing kata kunci bisa salah tebak kalau kalimat pengguna ambigu. Perbaikan
yang lebih kuat (satu BTP Destination + satu agent card per skill) sengaja belum diambil supaya
tidak menambah permukaan konfigurasi sebelum dipakai di panggung.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Callable, Mapping, Protocol

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps.jsonrpc import A2AFastAPIApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Artifact,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import report
from mealchain_client import MealchainClient, MealchainRejected, MealchainUnavailable

ARTIFACT_ID = "mealchain_report"
ARTIFACT_NAME = "mealchain_report"
DEFAULT_PORT = "8080"

SKILL_SUPPLY = "supply_situation"
SKILL_KPI = "kpi_snapshot"
SKILL_QUEUE = "approval_queue"
SKILLS = (SKILL_SUPPLY, SKILL_KPI, SKILL_QUEUE)

# Urutan penting: KPI diperiksa sebelum antrean, supaya "usulan KPI" tidak salah masuk antrean.
_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (SKILL_KPI, ("kpi", "indikator", "kinerja", "metrik", "performance")),
    (
        SKILL_QUEUE,
        ("approval", "approve", "persetujuan", "setuju", "usulan", "keputusan", "antrean", "queue"),
    ),
)


class ReadOnlyBackend(Protocol):
    """Kontrak yang dipakai jembatan ini — SENGAJA hanya baca.

    `MealchainClient` memenuhinya; test memakai klien palsu yang memenuhi kontrak sama.
    Tidak ada metode tulis di sini: jembatan ini tidak boleh mengusulkan/menyetujui apa pun
    (`Rules.md` §1.2).
    """

    def __enter__(self) -> "ReadOnlyBackend": ...
    def __exit__(self, *_: object) -> None: ...
    def close(self) -> None: ...
    def health(self) -> dict[str, Any]: ...
    def batches(self) -> list[dict[str, Any]]: ...
    def balance_map(self, commodity: str) -> dict[str, Any]: ...
    def kpi(self, days: int = ...) -> dict[str, Any]: ...
    def pending_decisions(self) -> list[dict[str, Any]]: ...


def resolve_skill(user_input: str) -> tuple[str, Mapping[str, Any]]:
    """Tentukan skill dari pesan masuk — deterministik, tidak memanggil model bahasa."""
    pesan = (user_input or "").strip()
    if pesan.startswith("{"):
        try:
            data = json.loads(pesan)
        except ValueError:
            data = None
        if isinstance(data, dict):
            # Pesan JSON = kontrak eksplisit. Skill tak dikenal TIDAK dipindai kata kuncinya:
            # seluruh isi JSON akan terbaca sebagai kata kunci dan menebak salah.
            diminta = str(data.get("skill") or "").strip()
            return (diminta if diminta in SKILLS else SKILL_SUPPLY), data
    teks = pesan.lower()
    for skill, keywords in _KEYWORDS:
        if any(keyword in teks for keyword in keywords):
            return skill, {}
    return SKILL_SUPPLY, {}


def _data_source_note(client: ReadOnlyBackend) -> str | None:
    """Penanda sumber data dari `/health` — `Rules.md` §1.4: yang mock harus terlihat mock.

    Gagal membaca `/health` bukan alasan menggagalkan laporan: catatan ini hanya konteks,
    dan laporan tetap menyebut asal angkanya.
    """
    try:
        sap = (client.health() or {}).get("sap") or {}
    except MealchainUnavailable:
        return None
    sumber = sap.get("data_source")
    if not sumber:
        return None
    tambahan = " (campuran beberapa sumber)" if sap.get("is_mixed") else ""
    return f"Sumber data SAP pada backend: {sumber}{tambahan} — data mock ditandai mock, bukan klaim SAP nyata."


def render_skill(client: ReadOnlyBackend, skill: str) -> str:
    """Jalankan satu skill: ambil dari backend, render markdown. Tidak ada aritmetika di sini.

    Skill pasokan membaca dua read model: `/batches` (keamanan & kesegaran melekat pada batch)
    dan `/balance/map` (pasokan/kebutuhan per lokasi) — satu panggilan per komoditas yang
    benar-benar ada di inventaris. Komoditasnya DIBACA dari data, bukan didaftar tetap di kode.
    """
    note = _data_source_note(client)
    if skill == SKILL_KPI:
        return report.kpi_report(client.kpi(), note=note)
    if skill == SKILL_QUEUE:
        return report.approval_queue_report(client.pending_decisions(), note=note)

    batches = client.batches()
    komoditas = sorted(
        {str(row.get("commodity")) for row in batches if row.get("commodity")}
    )
    balance: dict[str, Mapping[str, Any]] = {}
    gagal: list[str] = []
    for nama in komoditas:
        try:
            balance[nama] = client.balance_map(nama)
        except MealchainRejected as exc:
            # Satu komoditas yang tidak punya data keseimbangan tidak boleh mematikan seluruh
            # laporan: tabel batch (keamanan/kesegaran) tetap berguna. Kekosongannya disebut
            # apa adanya — bukan diisi nol, karena nol terbaca "tidak ada masalah".
            gagal.append(f"{nama} ({exc})")
    if gagal:
        tambahan = (
            "Keseimbangan tidak terbaca untuk: "
            + "; ".join(gagal)
            + " — komoditas itu tidak muncul di tabel keseimbangan, bukan berarti nol."
        )
        note = f"{note}\n\n{tambahan}" if note else tambahan
    return report.supply_report(batches, balance, note=note)


def default_client_factory() -> MealchainClient:
    """Klien dari environment (`MEALCHAIN_API_URL`, `MEALCHAIN_READ_USERNAME/PASSWORD`)."""
    return MealchainClient()


class MealchainExecutor(AgentExecutor):
    """Menjembatani siklus hidup tugas A2A ke pembacaan backend MealChain.

    Pekerjaan backend bersifat sinkron (httpx), jadi dijalankan di thread pool dengan
    `run_in_executor` supaya event loop server tidak beku — sama seperti pola tutorial.
    """

    def __init__(
        self, client_factory: Callable[[], ReadOnlyBackend] = default_client_factory
    ) -> None:
        self._client_factory = client_factory

    def _render(self, skill: str) -> str:
        with self._client_factory() as client:
            return render_skill(client, skill)

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
            )
        )

        skill, _payload = resolve_skill(context.get_user_input())
        try:
            loop = asyncio.get_running_loop()
            body = await loop.run_in_executor(None, self._render, skill)
        except MealchainUnavailable as exc:
            # Diterbitkan sebagai ARTEFAK teks, bukan tugas `failed`: function Joule membaca
            # `artifacts[0].parts[0].text`, jadi hanya begini pengguna melihat penyebabnya.
            body = report.unavailable_report(skill, str(exc))
        except Exception as exc:  # jaring pengaman: pengguna harus tetap dapat penjelasan
            body = report.unavailable_report(skill, f"galat tak terduga: {exc!r}")

        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                artifact=Artifact(
                    artifactId=ARTIFACT_ID,
                    name=ARTIFACT_NAME,
                    parts=[TextPart(text=body)],
                ),
            )
        )
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.completed),
                final=True,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.canceled),
                final=True,
            )
        )


def public_url() -> str:
    """URL publik aplikasi: dari `VCAP_APPLICATION` saat di Cloud Foundry, else localhost."""
    vcap = json.loads(os.environ.get("VCAP_APPLICATION", "{}") or "{}")
    uris = vcap.get("application_uris") or []
    if uris:
        return f"https://{uris[0]}"
    return f"http://localhost:{os.environ.get('PORT', DEFAULT_PORT)}"


def agent_card(app_url: str) -> AgentCard:
    """Identitas agen — dibaca Joule (via BTP Destination) di `/.well-known/agent-card.json`."""
    modalitas = ["text/plain", "application/json"]
    return AgentCard(
        name="MealChain Guardian — jembatan Joule",
        description=(
            "Membaca situasi pasokan, indikator kinerja, dan antrean usulan keputusan "
            "MealChain Guardian (SPPG/BGN). Baca-saja: persetujuan tetap dilakukan manusia."
        ),
        url=app_url,
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id=SKILL_SUPPLY,
                name="Situasi pasokan SPPG",
                description=(
                    "Stok terpakai, kebutuhan, selisih surplus/kurang, kesegaran, dan status "
                    "keamanan pangan per SPPG dan komoditas."
                ),
                tags=["pangan", "pasokan", "sppg", "mbg", "surplus", "kekurangan"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_KPI,
                name="Indikator kinerja",
                description=(
                    "KPI MealChain Guardian: keberlanjutan porsi, kehilangan pangan yang bisa "
                    "dihindari, penyelesaian ketimpangan wilayah, biaya aman terkirim, "
                    "simpangan harga, waktu keputusan, kelengkapan bukti."
                ),
                tags=["kpi", "indikator", "kinerja", "metrik"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
            AgentSkill(
                id=SKILL_QUEUE,
                name="Antrean usulan keputusan",
                description=(
                    "Daftar usulan rebalancing/anomali harga/gangguan keamanan/eksklusi pemasok "
                    "beserta statusnya. Hanya untuk dilihat; persetujuan di UI MealChain."
                ),
                tags=["usulan", "approval", "persetujuan", "keputusan"],
                inputModes=modalitas,
                outputModes=["text/markdown"],
            ),
        ],
        defaultInputModes=modalitas,
        defaultOutputModes=["text/markdown"],
    )


def cors_origins() -> list[str]:
    """Origin CORS: `MEALCHAIN_BRIDGE_CORS_ORIGINS` (dipisah koma), default `*` untuk demo."""
    mentah = os.environ.get("MEALCHAIN_BRIDGE_CORS_ORIGINS", "*")
    return [origin.strip() for origin in mentah.split(",") if origin.strip()]


def build_app(
    client_factory: Callable[[], ReadOnlyBackend] = default_client_factory,
    app_url: str | None = None,
) -> FastAPI:
    """Bangun aplikasi A2A + `/health`. `client_factory` disuntik test (`FakeClient`)."""
    handler = DefaultRequestHandler(
        agent_executor=MealchainExecutor(client_factory),
        task_store=InMemoryTaskStore(),
    )
    fastapi_app = A2AFastAPIApplication(
        agent_card=agent_card(app_url or public_url()), http_handler=handler
    ).build()

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @fastapi_app.get("/health")
    def health() -> dict[str, Any]:
        """Selalu 200 selama aplikasi hidup (Cloud Foundry memakainya untuk health check).

        Keterjangkauan backend MealChain dilaporkan sebagai DATA, bukan sebagai status HTTP:
        kalau endpoint ini ikut gagal saat backend mati, Cloud Foundry akan me-restart aplikasi
        berulang kali padahal yang bermasalah bukan aplikasi ini.
        """
        hasil: dict[str, Any] = {"status": "ok", "service": "mealchain-joule-bridge"}
        try:
            with client_factory() as client:
                hasil["backend"] = {"reachable": True, **(client.health() or {})}
        except MealchainUnavailable as exc:
            hasil["backend"] = {"reachable": False, "detail": str(exc)}
        return hasil

    return fastapi_app


app = build_app()


if __name__ == "__main__":  # jalur lokal; di Cloud Foundry dipakai `command:` di manifest.yml
    uvicorn = __import__("uvicorn")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", DEFAULT_PORT)))
