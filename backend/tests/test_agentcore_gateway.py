"""Kontrak klien AgentCore Gateway (Fase 11 butir 4).

Dua lapis:
1. Kontrak tanpa AWS — `AGENTCORE_GATEWAY_URL` kosong harus NOT_CONFIGURED,
   bukan crash dan bukan klaim VERIFIED.
2. Uji LIVE (opt-in `RUN_LIVE_AGENTCORE_GATEWAY=1`) — satu tool benar-benar
   dipanggil lewat Gateway dan hasilnya dibaca aplikasi. Inilah bukti
   `tool_invoked` + `app_uses_gateway`; tanpa opt-in, tes ini di-skip supaya CI
   tidak bergantung pada resource AWS.
"""

from __future__ import annotations

import os

import pytest

from app.services.agentcore_gateway import panggil_tool


@pytest.mark.asyncio
async def test_tanpa_url_not_configured(monkeypatch):
    monkeypatch.delenv("AGENTCORE_GATEWAY_URL", raising=False)
    hasil = await panggil_tool("supply_get", {"location": "Jakarta", "commodity": "beras"})
    assert hasil["status"] == "NOT_CONFIGURED"
    assert "AGENTCORE_GATEWAY_URL" in hasil["alasan"]


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_AGENTCORE_GATEWAY") != "1",
    reason="live: butuh AGENTCORE_GATEWAY_URL + izin InvokeGateway "
    "(set RUN_LIVE_AGENTCORE_GATEWAY=1)",
)
async def test_live_tool_gateway_mengembalikan_data(monkeypatch):
    # conftest menghapus AGENTCORE_GATEWAY_URL supaya unit test deterministik;
    # untuk uji live, URL diambil dari variabel terpisah lalu dipasang di sini.
    url = os.environ.get("AGENTCORE_GATEWAY_URL_LIVE") or os.environ.get("AGENTCORE_GATEWAY_URL")
    if not url:
        pytest.skip("AGENTCORE_GATEWAY_URL_LIVE tidak diisi")
    monkeypatch.setenv("AGENTCORE_GATEWAY_URL", url)
    hasil = await panggil_tool("supply_get", {"location": "Jakarta", "commodity": "beras"})
    assert hasil["status"] == "VERIFIED", hasil
    assert hasil["tool"].endswith("supply_get")
    data = hasil["data"]
    assert isinstance(data.get("quantity_kg"), (int, float)), data
    assert data["quantity_kg"] > 0
