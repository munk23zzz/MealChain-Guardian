"""Pasang outbound auth (API key / Bearer) pada target AgentCore Gateway.

Kenapa: target `mealchain-tools` memanggil backend MealChain yang mewajibkan
`Authorization: Bearer <JWT>`. Tanpa credential provider, tool di Gateway
menjawab "An internal error occurred" (backend membalas 401).

Skrip ini:
1. membaca token dari .env (MEALCHAIN_API_TOKEN) — tidak pernah mencetak nilainya;
2. membuat/memperbarui credential provider API key bernama `mealchain-api-token`;
3. memperbarui target dengan credentialProviderConfigurations (HEADER Authorization,
   prefix 'Bearer ');
4. memanggil satu tool lewat MCP dan mencetak hasilnya (bukti tool_invoked).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATEWAY_ID = "mealchain-gateway-eofbeyei8p"
TARGET_ID = "OKYYXKMWVW"
PROVIDER_NAME = "mealchain-api-token"
REGION = "us-west-2"


def env(kunci: str) -> str:
    for line in (REPO / ".env").read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith(kunci + "="):
            return line.split("=", 1)[1].strip()
    return ""


def main() -> int:
    import boto3

    # kredensial: .env lalu secrets/aws-app.env (tidak pernah dicetak)
    for berkas in (REPO / ".env", REPO / "secrets" / "aws-app.env"):
        if not berkas.exists():
            continue
        for line in berkas.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and v and k not in os.environ:
                    os.environ[k] = v

    token = env("MEALCHAIN_API_TOKEN")
    if not token:
        print("token kosong di .env")
        return 2
    c = boto3.client("bedrock-agentcore-control", region_name=REGION)

    # 1. credential provider
    ada = {p["name"]: p for p in c.list_api_key_credential_providers().get("items", [])}
    if PROVIDER_NAME in ada:
        arn = ada[PROVIDER_NAME]["credentialProviderArn"]
        c.update_api_key_credential_provider(
            name=PROVIDER_NAME, apiKey=token
        )
        print(f"provider: diperbarui ({arn})")
    else:
        r = c.create_api_key_credential_provider(name=PROVIDER_NAME, apiKey=token)
        arn = r["credentialProviderArn"]
        print(f"provider: dibuat ({arn})")

    # 2. target config apa adanya (skema OpenAPI), hanya menambah auth
    t = c.get_gateway_target(gatewayIdentifier=GATEWAY_ID, targetId=TARGET_ID)
    conf = t["targetConfiguration"]
    auth = [
        {
            "credentialProviderType": "API_KEY",
            "credentialProvider": {
                "apiKeyCredentialProvider": {
                    "providerArn": arn,
                    "credentialParameterName": "Authorization",
                    "credentialPrefix": "Bearer ",
                    "credentialLocation": "HEADER",
                }
            },
        }
    ]
    c.update_gateway_target(
        gatewayIdentifier=GATEWAY_ID,
        targetId=TARGET_ID,
        name=t["name"],
        description=t.get("description", ""),
        targetConfiguration=conf,
        credentialProviderConfigurations=auth,
    )
    print("target: credentialProviderConfigurations terpasang")

    # 3. panggil tool lewat MCP
    url = env("AGENTCORE_GATEWAY_URL")


    def rpc(payload: dict, sesi: str | None) -> tuple[dict, str | None]:
        header = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if sesi:
            header["mcp-session-id"] = sesi
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), headers=header, method="POST"
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            sesi_baru = resp.headers.get("mcp-session-id") or sesi
            mentah = resp.read().decode()
            jenis = resp.headers.get("content-type", "")
        if "event-stream" in jenis or mentah.lstrip().startswith("event:"):
            for baris in mentah.splitlines():
                if baris.startswith("data:"):
                    mentah = baris[5:].strip()
        return json.loads(mentah), sesi_baru

    init, sesi = rpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mealchain-provision", "version": "1.0"},
            },
        },
        None,
    )
    if not init.get("result"):
        print("initialize gagal:", init.get("error"))
        return 4
    daftar, sesi = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, sesi)
    tools = [x.get("name", "") for x in daftar.get("result", {}).get("tools", [])]
    nama = next((x for x in tools if x.endswith("supply_get")), None)
    print("tools:", len(tools), "| dipakai:", nama)
    if not nama:
        return 4
    hasil, _ = rpc(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": nama,
                "arguments": {"location": "Jakarta", "commodity": "beras", "q": "demo"},
            },
        },
        sesi,
    )
    isi = hasil.get("result", {})
    teks = (isi.get("content") or [{}])[0].get("text", "")
    print("isError:", isi.get("isError"))
    print("cuplikan:", teks[:220])
    return 0 if not isi.get("isError") else 5


if __name__ == "__main__":
    sys.exit(main())
