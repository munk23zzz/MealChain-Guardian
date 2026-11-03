"""Endpoint bukti `app_uses_gateway` — aplikasi memanggil tool lewat Gateway.

Kenapa ada: probe AWS hanya bisa membuktikan `resource_exists`, `target_ready`,
dan (lewat skrip) `tool_invoked`. `app_uses_gateway` baru sah bila APLIKASI
memanggil tool lewat Gateway dan membaca hasilnya. Sebelum ini
`services/agentcore_gateway.panggil_tool` hanya dipanggil tes dan skrip probe,
jadi klaim "aplikasi memakai Gateway" tidak punya bukti runtime.

Kontrak yang diuji:
1. Tanpa token → 401 (read-only bukan publik).
2. Env `AGENTCORE_GATEWAY_URL` kosong → `NOT_CONFIGURED`, `probes_run == 0`,
   dan **tidak ada** panggilan jaringan sama sekali (bukan galat 500).
3. Env terisi + tool menjawab → `VERIFIED`, `probes_run == 1`, nama tool dan data
   dikembalikan apa adanya dari Gateway.
4. Gateway menjawab galat → 200 dengan status `UNVERIFIED` + alasan; UI tidak
   pecah dan tidak ada status hijau palsu.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_tanpa_token_401(client):
    assert client.get("/integrations/gateway/tool-check").status_code == 401


def test_env_kosong_tidak_memanggil_jaringan(client, monitor_headers, monkeypatch):
    monkeypatch.delenv("AGENTCORE_GATEWAY_URL", raising=False)

    from app.services import agentcore_gateway

    def _tidak_boleh(*_a, **_k):  # pragma: no cover - dipanggil = gagal
        raise AssertionError("_rpc tidak boleh dipanggil saat env kosong")

    # Yang dijaga adalah lapisan JARINGAN, bukan panggil_tool: panggil_tool tetap
    # dipanggil aplikasi dan harus menjawab NOT_CONFIGURED tanpa membuka koneksi.
    monkeypatch.setattr(agentcore_gateway, "_rpc", _tidak_boleh)
    resp = client.get("/integrations/gateway/tool-check", headers=monitor_headers)
    assert resp.status_code == 200, resp.text
    isi = resp.json()
    assert isi["status"] == "NOT_CONFIGURED"
    assert isi["probes_run"] == 0


def test_tool_menjawab_status_verified(client, monitor_headers, monkeypatch):
    monkeypatch.setenv("AGENTCORE_GATEWAY_URL", "https://gateway.contoh/mcp")

    from app.services import agentcore_gateway

    async def _palsu(nama, argumen):
        assert nama == "supply_get"
        return {
            "status": "VERIFIED",
            "tool": "mealchain-tools___supply_get",
            "data": {"location": "Jakarta", "commodity": "beras", "quantity_kg": 100},
        }

    monkeypatch.setattr(agentcore_gateway, "panggil_tool", _palsu)
    resp = client.get("/integrations/gateway/tool-check", headers=monitor_headers)
    assert resp.status_code == 200, resp.text
    isi = resp.json()
    assert isi["status"] == "VERIFIED"
    assert isi["probes_run"] == 1
    assert isi["tool"].endswith("supply_get")
    assert isi["data"]["quantity_kg"] == 100


def test_gateway_galat_jadi_unverified_bukan_500(client, monitor_headers, monkeypatch):
    monkeypatch.setenv("AGENTCORE_GATEWAY_URL", "https://gateway.contoh/mcp")

    from app.services import agentcore_gateway

    async def _gagal(_nama, _argumen):
        return {"status": "UNVERIFIED", "alasan": "initialize gagal: timeout"}

    monkeypatch.setattr(agentcore_gateway, "panggil_tool", _gagal)
    resp = client.get("/integrations/gateway/tool-check", headers=monitor_headers)
    assert resp.status_code == 200, resp.text
    isi = resp.json()
    assert isi["status"] == "UNVERIFIED"
    assert "timeout" in (isi.get("detail") or "")
