"""Klien AgentCore Gateway (MCP) — jalur aplikasi, bukan konfigurasi.

Tujuan: bukti `app_uses_gateway` harus datang dari aplikasi yang benar-benar
memanggil tool lewat Gateway dan membaca hasilnya. Modul ini yang melakukannya:

  hasil = await panggil_tool("supply_get", {"location": "Jakarta", "commodity": "beras"})

Alurnya MCP standar: initialize → tools/list (untuk memetakan nama tool yang
sebenarnya, karena Gateway memberi prefiks target) → tools/call.

Kalau `AGENTCORE_GATEWAY_URL` kosong, fungsi mengembalikan status
`NOT_CONFIGURED` tanpa melempar galat — aplikasi tetap jalan tanpa Gateway.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _url() -> str:
    return (os.environ.get("AGENTCORE_GATEWAY_URL") or "").strip()


async def _rpc(url: str, payload: dict, sesi: str | None) -> tuple[dict, str | None]:
    header = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if sesi:
        header["mcp-session-id"] = sesi
    async with httpx.AsyncClient(timeout=TIMEOUT) as klien:
        resp = await klien.post(url, json=payload, headers=header)
        resp.raise_for_status()
        sesi_baru = resp.headers.get("mcp-session-id") or sesi
        mentah = resp.text
        jenis = resp.headers.get("content-type", "")
    if "event-stream" in jenis or mentah.lstrip().startswith("event:") or "\ndata:" in mentah:
        for baris in mentah.splitlines():
            if baris.startswith("data:"):
                mentah = baris[5:].strip()
    return json.loads(mentah), sesi_baru


async def panggil_tool(nama: str, argumen: dict[str, Any]) -> dict[str, Any]:
    """Panggil satu tool Gateway dan kembalikan isi jawabannya.

    Mengembalikan dict berisi `status` (VERIFIED/NOT_CONFIGURED/UNVERIFIED),
    `tool` yang benar-benar dipanggil, dan `data` hasil parsing JSON dari teks
    jawaban tool (kalau ada).
    """
    url = _url()
    if not url:
        return {"status": "NOT_CONFIGURED", "alasan": "AGENTCORE_GATEWAY_URL kosong"}

    init, sesi = await _rpc(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mealchain-backend", "version": "1.0"},
            },
        },
        None,
    )
    if not init.get("result"):
        return {"status": "UNVERIFIED", "alasan": f"initialize gagal: {init.get('error')}"}

    daftar, sesi = await _rpc(
        url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, sesi
    )
    tools = [t.get("name", "") for t in daftar.get("result", {}).get("tools", [])]
    cocok = next((t for t in tools if t.endswith(nama) or t == nama), None)
    if cocok is None:
        return {
            "status": "UNVERIFIED",
            "alasan": f"tool {nama} tidak ada di gateway",
            "tools": tools,
        }

    jawab, _ = await _rpc(
        url,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": cocok, "arguments": argumen},
        },
        sesi,
    )
    hasil = jawab.get("result") or {}
    if not hasil or hasil.get("isError"):
        rinci = json.dumps(jawab.get("error") or hasil)[:300]
        return {"status": "UNVERIFIED", "tool": cocok, "alasan": rinci}

    teks = ""
    for potongan in hasil.get("content", []):
        if potongan.get("type") == "text":
            teks = potongan.get("text", "")
            break
    try:
        data = json.loads(teks)
    except json.JSONDecodeError:
        data = {"mentah": teks}
    return {"status": "VERIFIED", "tool": cocok, "data": data}
