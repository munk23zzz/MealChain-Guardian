"""Test skill `batch_detail`: rincian keamanan satu batch lewat `GET /batches/{id}`.

Yang dijaga di sini:

1. Pertanyaan "batch X aman?" dijawab dari rincian batch, bukan dari tabel pasokan.
2. Status keamanan TERSIMPAN dan HASIL EVALUASI ditampilkan terpisah — Joule tidak
   menyamakan keduanya dan tidak menyimpulkan sendiri.
3. Kebijakan demo ditandai sebagai kebijakan simulasi, tidak tampil seperti regulasi resmi.
4. Pertanyaan pembuangan batch tetap milik kehilangan pangan, dan "penerimaan barang
   batch X" tetap milik antrean penerimaan (dua kontrak lama yang mudah dicuri kata `batch`).
5. Id pendek 8 karakter dari tabel chat dipetakan ke id lengkap; tanpa id, Joule meminta
   id dan menampilkan kandidat — bukan mengarang rincian.
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
from mealchain_client import MealchainRejected

BATCH_A = "068edb8a-695b-48b0-b450-719d92f7a48c"
BATCH_B = "1b7f0c22-1111-4444-8888-9999aaaabbbb"


def _detail(**ubah) -> dict:
    """Bentuk respons `GET /batches/{id}` apa adanya (satu batch telur Bandung)."""
    dasar = {
        "batch": {
            "id": BATCH_A,
            "location": "Bandung",
            "commodity": "telur",
            "quantity_kg": 300.0,
            "safety_status": "pass",
            "freshness_score": 0.95,
            "usable_until": "2026-11-28T06:40:22.894657+00:00",
            "receipt_status": None,
            "quarantine_status": "none",
        },
        "eligibility": {"status": "usable", "blocking_reasons": [], "next_step": None},
        "evidence": {
            "commodity_profile": {
                "commodity": "telur",
                "cold_chain_required": True,
                "safe_temp_min_c": 0.0,
                "safe_temp_max_c": 8.0,
                "shelf_life_days": 28.0,
                "min_temperature_samples": 2,
                "max_observation_age_minutes": 360,
                "max_excursion_minutes": 30.0,
                "policy_version": "sim-2026-10-27.v1",
                "policy_basis": "Asumsi demo (belum divalidasi domain owner)",
                "policy_kind": "simulated_policy",
            },
            "profile_source": "commodity_policies",
            "temperature_observation": "observed",
            "evidence_state": "sufficient",
            "sample_count": 7,
            "observed_at": "2026-10-29T06:40:22.894657+00:00",
            "evaluation_time": "2026-10-29T07:22:47.637011+00:00",
            "source": "seed",
            "source_label": "log simulasi",
            "evidence_sufficient": True,
            "evidence_reasons": [],
            "stored_safety_status": "pass",
            "evaluated_safety_status": "pass",
        },
    }
    for jalur, nilai in ubah.items():
        bagian, kunci = jalur.split("__")
        dasar[bagian][kunci] = nilai
    return dasar


class FakeClient:
    """Klien palsu: daftar batch + rincian satu batch."""

    def __init__(self, *, detail_gagal: bool = False) -> None:
        self.detail_gagal = detail_gagal
        self.dipanggil: list[str] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def close(self) -> None:
        return None

    def batches(self) -> list[dict]:
        self.dipanggil.append("batches")
        return [
            {
                "id": BATCH_A,
                "commodity": "telur",
                "quantity_kg": 300.0,
                "location": "Bandung",
                "safety_status": "pass",
            },
            {
                "id": BATCH_B,
                "commodity": "ayam",
                "quantity_kg": 40.0,
                "location": "Jakarta",
                "safety_status": "needs_verification",
            },
        ]

    def batch_detail(self, batch_id: str) -> dict:
        self.dipanggil.append(f"batch_detail:{batch_id}")
        if self.detail_gagal or batch_id not in (BATCH_A, BATCH_B):
            raise MealchainRejected(404, "batch tidak ditemukan")
        return _detail()

    def demo_session(self) -> dict:
        return {"mode": "demo", "session_id": "s-1"}

    def health(self) -> dict:
        return {"status": "ok", "sap": {"data_source": "MOCK", "is_mixed": False}}


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


# --- routing -----------------------------------------------------------------------------


def test_pertanyaan_batch_aman_masuk_skill_rincian_batch():
    skill, payload = server.resolve_skill(f"batch {BATCH_A} aman atau tidak?")

    assert skill == server.SKILL_BATCH
    assert payload == {"batch_id": BATCH_A}


def test_kata_suhu_masuk_skill_rincian_batch():
    assert server.resolve_skill("suhu batch mana yang menyimpang?")[0] == server.SKILL_BATCH


def test_pertanyaan_pembuangan_batch_tetap_milik_kehilangan_pangan():
    # Laporan pembuangan (`batch_disposal_report`) lewat jalur pasokan tetap menang:
    # kata `batch` pada "batch mana yang harus dibuang" TIDAK boleh mencurinya.
    skill, _ = server.resolve_skill("batch mana yang harus dibuang?")
    teks, fake = _jalan("batch mana yang harus dibuang?")

    assert skill == server.SKILL_SUPPLY
    assert "batch_detail:" not in repr(fake.dipanggil)
    assert "Status keamanan (tersimpan)" not in teks


def test_penerimaan_barang_batch_tetap_milik_antrean_penerimaan():
    skill, payload = server.resolve_skill(f"penerimaan barang batch {BATCH_A}")

    assert skill == server.SKILL_SUPPLY
    assert payload == {"batch_id": BATCH_A}


def test_karantina_batch_tetap_milik_status_karantina():
    assert server.resolve_skill("karantina batch")[0] == server.SKILL_QUARANTINE


# --- isi jawaban ---------------------------------------------------------------------------


def test_jawaban_memuat_status_tersimpan_dan_hasil_evaluasi_terpisah():
    teks, fake = _jalan(f"batch {BATCH_A} aman atau tidak?")

    assert f"batch_detail:{BATCH_A}" in fake.dipanggil
    assert "Status keamanan (tersimpan)" in teks
    assert "Status keamanan (hasil evaluasi)" in teks
    assert "Kelayakan pakai: **layak dipakai**" in teks
    assert "300 kg" in teks


def test_kebijakan_demo_ditandai_simulasi_bukan_regulasi():
    teks, _ = _jalan(f"batch {BATCH_A} suhunya berapa?")

    assert "kebijakan simulasi" in teks
    # Rentang suhu datang dari kebijakan komoditas, bukan angka karangan perender.
    assert "0–8 °C" in teks
    assert "sim-2026-10-27.v1" in teks


def test_bukti_suhu_diteruskan_apa_adanya():
    teks, _ = _jalan(f"bukti suhu batch {BATCH_A} cukup?")

    assert "suhu tercatat" in teks
    assert "7 sampel" in teks
    assert "bukti cukup" in teks


def test_status_tersimpan_berbeda_tidak_disamakan():
    fake = FakeClient()
    teks, _ = _jalan(f"batch {BATCH_B} aman?", fake)

    # FakeClient mengembalikan detail yang sama; yang dijaga di sini adalah perender
    # menampilkan dua baris terpisah, bukan satu status gabungan.
    assert teks.count("Status keamanan") == 2


def test_id_pendek_dipetakan_ke_id_lengkap():
    teks, fake = _jalan("batch 068edb8a aman?")

    assert f"batch_detail:{BATCH_A}" in fake.dipanggil
    assert "300 kg" in teks


def test_tanpa_id_joule_meminta_id_dan_menampilkan_kandidat():
    teks, fake = _jalan("suhu batch mana yang menyimpang?")

    assert "Sebutkan ID batch" in teks
    assert "068edb8a" in teks
    assert "1b7f0c22" in teks
    assert "batch_detail:" not in repr(fake.dipanggil)


def test_batch_tidak_ditemukan_tidak_mengarang_rincian():
    teks, _ = _jalan("batch 00000000 aman?", FakeClient(detail_gagal=True))

    assert "tidak ditemukan" in teks
    assert "Status keamanan (tersimpan)" not in teks


# --- perender murni ------------------------------------------------------------------------


def test_perender_tanpa_payload_tidak_menulis_status_karangan():
    teks = report.batch_detail_report(None)

    assert "Sebutkan ID batch" in teks
    assert "Status keamanan (tersimpan)" not in teks
