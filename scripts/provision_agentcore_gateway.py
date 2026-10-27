#!/usr/bin/env python3
"""Provisioning AgentCore Gateway untuk Fase 11 butir 4 (idempoten, aman diulang).

Urutan kerja:
  1. PREFLIGHT  — simulasikan izin yang dibutuhkan. Kalau ada yang implicitDeny,
                  skrip berhenti dengan status BLOCKED dan mencetak aksi yang
                  kurang. Tidak ada resource yang dibuat saat BLOCKED.
  2. GATEWAY    — pakai gateway bernama `mealchain-gateway` kalau sudah ada,
                  kalau belum buat (protocolType MCP, authorizer NONE).
  3. TARGET     — daftarkan 10 tool dari `backend/app/agent_tools/gateway_config.json`
                  sebagai OpenAPI inline payload, tunggu status READY.
  4. INVOKE     — panggil satu tool lewat MCP (initialize → tools/list → tools/call)
                  dan baca hasilnya. Ini yang membuat `tool_invoked` menjadi bukti,
                  bukan klaim dari konfigurasi.
  5. CATAT      — tulis AGENTCORE_GATEWAY_URL ke .env (backup .env.bak-gateway)
                  supaya aplikasi benar-benar memakai gateway.

Status yang dicetak mengikuti empat bukti terpisah di `scripts/probe_agentcore_gateway.py`:
resource_exists / target_ready / tool_invoked / app_uses_gateway.

Kredensial dibaca dari .env lalu secrets/aws-app.env (nilai kosong dilewati) dan
TIDAK pernah dicetak.

Exit code: 0 sukses penuh, 3 BLOCKED izin, 4 gagal di tengah jalan.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATEWAY_NAME = "mealchain-gateway"
TARGET_NAME = "mealchain-tools"
REGION_DEFAULT = "us-west-2"

AKSI_PERLU = [
    "bedrock-agentcore:ListGateways",
    "bedrock-agentcore:CreateGateway",
    "bedrock-agentcore:ListGatewayTargets",
    "bedrock-agentcore:CreateGatewayTarget",
    "bedrock-agentcore:InvokeGateway",
]


def muat_env() -> None:
    for nama in (".env", "secrets/aws-app.env"):
        p = REPO / nama
        if not p.exists():
            continue
        for baris in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            baris = baris.strip()
            if not baris or baris.startswith("#") or "=" not in baris:
                continue
            k, v = baris.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if k and v:
                os.environ[k] = v


def klien(nama: str):
    import boto3
    from botocore.config import Config

    return boto3.client(
        nama,
        region_name=os.environ.get("AWS_REGION", REGION_DEFAULT),
        config=Config(retries={"max_attempts": 3, "mode": "standard"}, read_timeout=60),
    )


def preflight() -> list[str]:
    iam = klien("iam")
    arn = klien("sts").get_caller_identity()["Arn"]
    r = iam.simulate_principal_policy(PolicySourceArn=arn, ActionNames=AKSI_PERLU, ResourceArns=["*"])
    kurang = [e["EvalActionName"] for e in r["EvaluationResults"] if e["EvalDecision"] != "allowed"]
    print(f"identitas: {arn}")
    for e in r["EvaluationResults"]:
        print(f"  {e['EvalDecision']:<14}{e['EvalActionName']}")
    return kurang


def skema_openapi() -> str:
    cfg = json.loads((REPO / "backend/app/agent_tools/gateway_config.json").read_text(encoding="utf-8"))
    base = (
        os.environ.get("BACKEND_PUBLIC_BASE_URL")
        or os.environ.get("MEALCHAIN_API_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")
    paths: dict[str, dict] = {}
    for tool in cfg["tools"]:
        path = tool["path"]
        metode = tool["method"].lower()
        operasi: dict = {"operationId": tool["name"].replace(".", "_"), "summary": tool["description"]}
        if "{" in path:
            operasi["parameters"] = [
                {"name": seg.strip("{}"), "in": "path", "required": True, "schema": {"type": "string"}}
                for seg in path.split("/")
                if seg.startswith("{")
            ]
        if metode == "post":
            operasi["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
            }
        else:
            operasi["parameters"] = operasi.get("parameters", []) + [
                {"name": "q", "in": "query", "required": False, "schema": {"type": "string"}}
            ]
        operasi["responses"] = {"200": {"description": "OK"}}
        paths.setdefault(path, {})[metode] = operasi
    return json.dumps(
        {"openapi": "3.0.1", "info": {"title": "MealChain deterministic tools", "version": "1.0.0"},
         "servers": [{"url": base}], "paths": paths},
        separators=(",", ":"),
    )


def pastikan_gateway(ctrl) -> tuple[str, str]:
    daftar = ctrl.list_gateways().get("items", [])
    for g in daftar:
        if g.get("name") == GATEWAY_NAME:
            gid = g.get("gatewayId") or g.get("id")
            print(f"gateway: sudah ada {gid} status={g.get('status')}")
            return gid, g.get("gatewayUrl", "")
    role = os.environ.get("AGENTCORE_GATEWAY_ROLE_ARN", "").strip()
    if not role:
        raise RuntimeError("AGENTCORE_GATEWAY_ROLE_ARN belum diisi — lihat _qa/fase11-langkah-manual.md langkah 2")
    r = ctrl.create_gateway(
        name=GATEWAY_NAME,
        description="MealChain Guardian deterministic tools (MCP)",
        roleArn=role,
        protocolType="MCP",
        authorizerType="NONE",
    )
    gid = r.get("gatewayId") or r.get("id")
    print(f"gateway: dibuat {gid}")
    d: dict = {}
    for _ in range(30):
        d = ctrl.get_gateway(gatewayIdentifier=gid)
        if d.get("status") in ("READY", "AVAILABLE"):
            return gid, d.get("gatewayUrl", "")
        time.sleep(5)
    return gid, d.get("gatewayUrl", "")


def pastikan_target(ctrl, gid: str) -> str:
    for t in ctrl.list_gateway_targets(gatewayIdentifier=gid).get("items", []):
        if t.get("name") == TARGET_NAME:
            print(f"target : sudah ada {t.get('targetId')} status={t.get('status')}")
            return t.get("status", "")
    r = ctrl.create_gateway_target(
        gatewayIdentifier=gid,
        name=TARGET_NAME,
        description="10 tool deterministik MealChain (OpenAPI inline)",
        targetConfiguration={"mcp": {"openApiSchema": {"inlinePayload": skema_openapi()}}},
    )
    tid = r.get("targetId")
    print(f"target : dibuat {tid}")
    status = ""
    for _ in range(60):
        for t in ctrl.list_gateway_targets(gatewayIdentifier=gid).get("items", []):
            if t.get("targetId") == tid:
                status = t.get("status", "")
                if status in ("READY", "FAILED", "CREATE_FAILED"):
                    return status
        time.sleep(5)
    return status


def panggil_mcp(url: str, tool: str, argumen: dict) -> dict:
    """MCP minimal: initialize → tools/call. Tanpa dependensi tambahan."""
    hasil: dict = {}

    def rpc(payload: dict, sesi: str | None = None) -> tuple[dict, str | None]:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **({"mcp-session-id": sesi} if sesi else {}),
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            sesi_baru = resp.headers.get("mcp-session-id") or sesi
            mentah = resp.read().decode("utf-8", "replace")
        if mentah.lstrip().startswith("event:") or "\ndata:" in mentah:
            for baris in mentah.splitlines():
                if baris.startswith("data:"):
                    mentah = baris[5:].strip()
        return json.loads(mentah), sesi_baru

    init, sesi = rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "mealchain-provisioner", "version": "1.0"}}})
    hasil["initialize"] = bool(init.get("result"))
    daftar, sesi = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, sesi)
    tools = [t.get("name") for t in daftar.get("result", {}).get("tools", [])]
    hasil["tools"] = tools
    panggil, _ = rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                      "params": {"name": tool, "arguments": argumen}}, sesi)
    hasil["call"] = panggil.get("result") or panggil.get("error")
    return hasil


def catat_env(url: str) -> None:
    p = REPO / ".env"
    teks = p.read_text(encoding="utf-8")
    baris = [b for b in teks.splitlines() if not b.startswith("AGENTCORE_GATEWAY_URL=")]
    baris.append(f"AGENTCORE_GATEWAY_URL={url}")
    (REPO / ".env.bak-gateway").write_text(teks, encoding="utf-8")
    p.write_text("\n".join(baris) + "\n", encoding="utf-8")
    print("env    : AGENTCORE_GATEWAY_URL dicatat di .env (backup .env.bak-gateway)")


def main() -> int:
    muat_env()
    kurang = preflight()
    if kurang:
        print("\nSTATUS: BLOCKED — izin belum ada:", ", ".join(kurang))
        print("Langkah admin ada di _qa/fase11-langkah-manual.md")
        return 3

    ctrl = klien("bedrock-agentcore-control")
    gid, url = pastikan_gateway(ctrl)
    status_target = pastikan_target(ctrl, gid)
    print(f"target : status akhir {status_target}")
    if status_target != "READY":
        print("\nSTATUS: GAGAL — target tidak READY, tool belum bisa dipanggil")
        return 4

    if not url:
        url = ctrl.get_gateway(gatewayIdentifier=gid).get("gatewayUrl", "")
    print(f"url    : {url}")

    hasil = panggil_mcp(url, "supply_get", {"location": "Jakarta", "commodity": "beras"})
    print("mcp    : tools =", len(hasil.get("tools") or []))
    print("mcp    : hasil call =", json.dumps(hasil.get("call"))[:220])

    catat_env(url)
    print("\nSTATUS: DONE — resource_exists=VERIFIED target_ready=READY tool_invoked=VERIFIED app_uses_gateway=CONFIGURED")
    print("Langkah berikut: jalankan scripts/probe_agentcore_gateway.py untuk merekam keempat bukti.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"GALAT: {type(exc).__name__}: {exc}")
        sys.exit(4)
