"""Registry tool deterministik (S3-02) — sumber tunggal mapping Gateway.

10 logical tool names (kontrak plan S3-02) → route FastAPI aktif.
Gateway memanggil backend deterministik; tidak ada logika domain di sini.
"""

from __future__ import annotations

import json
from pathlib import Path

# method + path HARUS ada di app FastAPI (diuji test_tool_contracts).
TOOL_ROUTES: dict[str, dict] = {
    "supply.get": {"method": "GET", "path": "/supply/{location}/{commodity}"},
    "demand.get": {"method": "GET", "path": "/demand/{location}/{commodity}"},
    "freshness.evaluate": {"method": "POST", "path": "/freshness/evaluate"},
    "safety.evaluate": {"method": "POST", "path": "/safety/evaluate"},
    "price.deviation": {"method": "POST", "path": "/price/deviation"},
    "logistics.estimate": {"method": "POST", "path": "/logistics/estimate"},
    "evidence.fuse": {"method": "POST", "path": "/evidence/fuse"},
    "cost.safe_delivered": {"method": "POST", "path": "/cost/safe-delivered"},
    "balance.recommend": {"method": "POST", "path": "/balance/recommend"},
    "actions.propose": {"method": "POST", "path": "/actions/propose"},
}

_TOOLS_ORDER = [
    "supply.get",
    "demand.get",
    "freshness.evaluate",
    "safety.evaluate",
    "price.deviation",
    "logistics.estimate",
    "evidence.fuse",
    "cost.safe_delivered",
    "balance.recommend",
    "actions.propose",
]

_TOOL_DESCRIPTIONS = {
    "supply.get": "Stok pasokan terkini per lokasi+komoditas (deterministik).",
    "demand.get": "Kebutuhan terkini per lokasi+komoditas (deterministik).",
    "freshness.evaluate": "Skor + status kesegaran batch (PASS/NEEDS_VERIFICATION/FAIL).",
    "safety.evaluate": "Status keamanan pangan batch (FAIL = hard exclusion).",
    "price.deviation": "Deviasi harga supplier vs referensi PIHPS (5%/15%).",
    "logistics.estimate": "Estimasi jarak/waktu/kelayakan rute (deterministik).",
    "evidence.fuse": "Perakitan evidence audit dari snapshot rekomendasi.",
    "cost.safe_delivered": (
        "Safe Delivered Cost (formula Opsi A terkunci). Wajib menyebut `commodity` "
        "(atau `shelf_life_days`): susut gudang dihitung dari umur simpan dan lama "
        "simpan, bukan dari kesegaran."
    ),
    "balance.recommend": "Rekomendasi balancing + ranking deterministik penuh.",
    "actions.propose": "Ajukan decision untuk approval manusia (tanpa eksekusi).",
}


def build_gateway_config(backend_base_url: str = "${BACKEND_BASE_URL}") -> dict:
    """Artifact AgentCore Gateway MCP: deterministik, tanpa secret."""
    tools = []
    for name in _TOOLS_ORDER:
        spec = TOOL_ROUTES[name]
        tools.append(
            {
                "name": name,
                "description": _TOOL_DESCRIPTIONS[name],
                "method": spec["method"],
                "path": spec["path"],
                "target": {
                    "type": "http",
                    "baseUrl": backend_base_url,
                },
            }
        )
    return {
        "gatewayConfigVersion": "1.0.0",
        "targetRuntime": "AWS Bedrock AgentCore Gateway (MCP)",
        "note": (
            "Placeholder ${BACKEND_BASE_URL} diganti saat provisioning; "
            "token via Gateway auth, bukan file ini."
        ),
        "tools": tools,
    }


def write_gateway_artifact(path: Path | None = None) -> Path:
    target = path or Path(__file__).resolve().parent / "gateway_config.json"
    target.write_text(
        json.dumps(build_gateway_config(), indent=2) + "\n", encoding="utf-8"
    )
    return target
