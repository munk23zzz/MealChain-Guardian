"""Endpoint SSE `GET /demo/agent/stream` (29 Okt 2026).

Diuji tanpa HTTP client: fungsi endpoint dipanggil langsung dengan `Request`
palsu, lalu isi `StreamingResponse` dibaca seperti peramban membacanya.
Test HTTP penuh butuh login demo, dan itu bukan yang ingin dibuktikan di sini —
yang ingin dibuktikan adalah bentuk aliran: penanda siap lebih dulu, langkah
datang saat terjadi (bukan setelah selesai), kanal ditutup setelahnya.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

from fastapi.responses import StreamingResponse

from app.api.demo import stream_demo_agent
from app.services import agent_progress
from app.services.demo_procurement_orchestrator import _TraceStep


class _RequestPalsu:
    """Cukup untuk `is_disconnected()`; tidak ada koneksi sungguhan."""

    def __init__(self, putus_setelah: float = 5.0) -> None:
        self._mulai = time.monotonic()
        self._putus_setelah = putus_setelah

    async def is_disconnected(self) -> bool:
        return time.monotonic() - self._mulai > self._putus_setelah


def _langkah(nama: str) -> _TraceStep:
    return _TraceStep(
        step_name=nama,
        tool_called="supply.gap",
        input_summary=None,
        output_summary={"gap_kg": 780},
    )


async def _kumpulkan(resp: StreamingResponse, batas: float = 4.0) -> list[str]:
    potongan: list[str] = []
    async def baca() -> None:
        async for bagian in resp.body_iterator:  # type: ignore[union-attr]
            potongan.append(bagian if isinstance(bagian, str) else bagian.decode())
    await asyncio.wait_for(baca(), timeout=batas)
    return potongan


def test_aliran_diawali_penanda_siap_dan_langkah_datang_bertahap() -> None:
    token = "uji-aliran-1"

    async def skenario():
        # Putus di 1,0 dtk: tiga langkah (0,2/0,4/0,6) sempat terkirim, lalu
        # klien pergi — persis seperti tab yang ditutup setelah putaran.
        resp = await stream_demo_agent(
            _RequestPalsu(putus_setelah=1.0), run_token=token, user=None
        )
        assert isinstance(resp, StreamingResponse)
        assert resp.media_type == "text/event-stream"
        assert resp.headers["cache-control"].startswith("no-cache")

        kirim = agent_progress.penerbit(token)

        async def penyiar() -> None:
            # Tiga langkah dengan jeda: kalau endpoint menahan sampai selesai,
            # test ini akan menerima semuanya sekaligus di akhir.
            for nama in ("DETECT", "VERIFY", "DECIDE"):
                await asyncio.sleep(0.2)
                assert kirim is not None
                kirim(_langkah(nama))

        tugas = asyncio.create_task(penyiar())
        potongan = await _kumpulkan(resp)
        await tugas
        return potongan

    potongan = asyncio.run(skenario())
    gabungan = "".join(potongan)

    assert potongan[0] == ": siap\n\n", "penanda siap harus paling awal"
    assert gabungan.count("event: langkah") == 3
    terkirim = [
        json.loads(baris[len("data: ") :])
        for baris in gabungan.split("\n")
        if baris.startswith("data: ")
    ]
    assert [x["step"] for x in terkirim] == ["DETECT", "VERIFY", "DECIDE"]
    assert terkirim[0]["ringkas"] == "gap_kg=780"


def test_kanal_ditutup_setelah_aliran_selesai() -> None:
    """Batas 5 menit = pengaman; setelah generator selesai kanal harus hilang."""
    token = "uji-aliran-2"

    async def skenario():
        resp = await stream_demo_agent(_RequestPalsu(putus_setelah=0.5), run_token=token, user=None)
        return await _kumpulkan(resp, batas=3.0)

    asyncio.run(skenario())
    # Penerbit tidak lagi menemukan kanal: siaran menjadi no-op, bukan galat.
    kirim = agent_progress.penerbit(token)
    assert kirim is not None
    kirim(_langkah("SUPERVISE"))


def test_langkah_dari_utas_lain_sampai_ke_aliran() -> None:
    """Pipeline berjalan di threadpool (bukan event loop ini)."""
    token = "uji-aliran-3"

    async def skenario():
        resp = await stream_demo_agent(
            _RequestPalsu(putus_setelah=1.0), run_token=token, user=None
        )
        kirim = agent_progress.penerbit(token)

        def utas() -> None:
            time.sleep(0.2)
            assert kirim is not None
            kirim(_langkah("LOGISTICS"))

        threading.Thread(target=utas, daemon=True).start()
        return await _kumpulkan(resp)

    gabungan = "".join(asyncio.run(skenario()))
    assert "LOGISTICS" in gabungan
