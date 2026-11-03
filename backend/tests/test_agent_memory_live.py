"""Kontrak tulis-baca NYATA pada AgentCore Memory (Fase 11 MG, butir 5).

Tes ini sengaja opt-in: ia memanggil AWS (CreateEvent/ListEvents/DeleteEvent)
pada Memory yang ditunjuk `AGENTCORE_MEMORY_ID`. Jalankan hanya dengan izin:

    docker run --rm --network mealchain-guardian_mealchain-network \\
      --env-file secrets/aws-app.env --env-file .env \\
      -e RUN_LIVE_AGENTCORE=1 \\
      -v ".../backend:/app" -w /app mealchain-guardian-backend \\
      python -m pytest -q tests/test_agent_memory_live.py -s

Yang dibuktikan (dan tidak diklaim lebih dari itu):
1. `write` benar-benar menyimpan ke AgentCore Memory (bukan dict lokal).
2. `read` mengembalikan nilai yang sama, dibaca ulang dari AWS.
3. Namespace: sesi lain TIDAK bisa membaca nilai itu.
4. Payload yang tersimpan sudah disanitasi (tidak ada kata sandi/token).

Tes selalu membersihkan event yang ia buat (purge), termasuk saat gagal.
"""

from __future__ import annotations

import os
import uuid

import pytest

from app.services.agent_memory import create_memory

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_AGENTCORE") != "1",
    reason="tes live AWS: set RUN_LIVE_AGENTCORE=1 (memanggil AgentCore Memory nyata)",
)


def _memory_id() -> str:
    # conftest menghapus AGENTCORE_MEMORY_ID supaya unit test deterministik;
    # untuk tes live, variabel *_LIVE dipakai sebagai sumber eksplisit.
    memory_id = (
        os.environ.get("AGENTCORE_MEMORY_ID_LIVE") or os.environ.get("AGENTCORE_MEMORY_ID") or ""
    ).strip()
    if not memory_id:
        pytest.skip("AGENTCORE_MEMORY_ID kosong")
    return memory_id


@pytest.mark.live
def test_tulis_baca_agentcore_memory_nyata():
    mem = create_memory(provider="agentcore", memory_id=_memory_id())
    sesi = f"uji-fase11-{uuid.uuid4().hex[:10]}"
    muatan = {
        "decision_id": "uji-fase11",
        "commodity": "telur",
        "safety_status": "ok",
        "jumlah_kg": 120,
        "password": "harus-dibuang",
    }
    dibersihkan = 0
    try:
        mem.write(sesi, "learn", muatan)

        terbaca = mem.read(sesi, "learn")
        assert terbaca is not None, "write dilaporkan sukses tetapi read kosong"
        assert terbaca["commodity"] == "telur"
        assert terbaca["jumlah_kg"] == 120
        assert "password" not in terbaca
        assert mem.list_keys(sesi) == ["learn"]

        # Namespace: sesi lain tidak melihat apa pun.
        assert mem.read(f"{sesi}-lain", "learn") is None
    finally:
        dibersihkan = mem.purge(sesi)
        print(f"\n[memory] sesi={sesi} event_dibersihkan={dibersihkan}")
    assert dibersihkan >= 1, "event uji tidak terhapus — periksa izin DeleteEvent"


def test_kegagalan_memory_tidak_melempar_ke_pemanggil():
    """`catat_learn` melaporkan status, tidak pernah melempar (butir 6)."""
    from app.services.agent_memory import catat_learn

    status = catat_learn("uji-fase11-gagal", "learn", {"commodity": "telur"})
    assert status["status"] in {"saved", "unavailable", "error"}
    assert "commodity" not in status
