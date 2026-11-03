"""Pindahkan URL/token API yang dipakai runtime AgentCore — satu perintah.

Kenapa perlu: agent di AgentCore membaca API MealChain lewat `MEALCHAIN_API_URL`
di environment runtime. Kalau URL backend berubah (tunnel cloudflared baru, VPS
baru, domain baru), runtime tetap memakai URL lama dan setiap invoke akan gagal
atau menggantung. Skrip ini menulis env baru ke runtime, menunggu status READY,
dan (opsional) memperbarui `.env` supaya konsisten.

Contoh:
    python agent/set_runtime_env.py --api-url https://contoh.trycloudflare.com
    python agent/set_runtime_env.py --api-url https://api.domainku.id --token "$TOKEN"
    python agent/set_runtime_env.py --tampilkan      # lihat env runtime sekarang

Token tidak pernah dicetak. Tanpa `--token`, nilai diambil dari `.env`
(`MEALCHAIN_API_TOKEN`).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import boto3
from botocore.config import Config

ROOT = Path(__file__).resolve().parents[1]
KUNCI_TOKEN = "MEALCHAIN_API_TOKEN"
KUNCI_URL = "MEALCHAIN_API_URL"
DESKRIPSI = "Pindahkan URL/token API yang dipakai runtime AgentCore — satu perintah."


def muat_env(path: Path) -> dict[str, str]:
    hasil: dict[str, str] = {}
    if not path.exists():
        return hasil
    for baris in path.read_text(encoding="utf-8").splitlines():
        baris = baris.strip()
        if baris and not baris.startswith("#") and "=" in baris:
            kunci, nilai = baris.split("=", 1)
            if nilai.strip():
                hasil[kunci.strip()] = nilai.strip()
    return hasil


def tulis_env(path: Path, kunci: str, nilai: str) -> None:
    baris = [
        b
        for b in path.read_text(encoding="utf-8").splitlines()
        if not b.startswith(f"{kunci}=")
    ]
    baris.append(f"{kunci}={nilai}")
    path.write_text("\n".join(baris) + "\n", encoding="utf-8")


def klien(region: str):
    env = muat_env(ROOT / "secrets" / "aws-app.env")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", env.get("AWS_ACCESS_KEY_ID", ""))
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", env.get("AWS_SECRET_ACCESS_KEY", ""))
    konfig = Config(retries={"max_attempts": 3}, read_timeout=60)
    kontrol = boto3.client("bedrock-agentcore-control", region_name=region, config=konfig)
    return kontrol


def main() -> int:
    parser = argparse.ArgumentParser(description=DESKRIPSI)
    parser.add_argument("--runtime-id", default="", help="default: AGENTCORE_RUNTIME_ID/.env atau --runtime-id")
    parser.add_argument("--runtime-arn", default="", help="alternatif: ARN runtime (id diambil dari ARN)")
    parser.add_argument("--api-url", default="", help="URL API yang bisa dijangkau runtime")
    parser.add_argument("--token", default="", help="token Bearer baru (default dari .env)")
    parser.add_argument("--region", default="")
    parser.add_argument("--tampilkan", action="store_true", help="cetak env runtime lalu keluar")
    parser.add_argument("--tunggu-detik", type=int, default=180)
    args = parser.parse_args()

    env = muat_env(ROOT / ".env")
    region = args.region or env.get("AWS_REGION") or muat_env(ROOT / "secrets" / "aws-app.env").get("AWS_REGION") or "us-west-2"
    runtime_id = args.runtime_id or env.get("AGENTCORE_RUNTIME_ID", "")
    arn = args.runtime_arn or env.get("AGENTCORE_RUNTIME_ARN", "")
    if not runtime_id and arn:
        runtime_id = arn.rsplit("/", 1)[-1]
    if not runtime_id:
        raise SystemExit("runtime id tidak diketahui: isi AGENTCORE_RUNTIME_ARN di .env atau pakai --runtime-id")

    kontrol = klien(region)
    sekarang = kontrol.get_agent_runtime(agentRuntimeId=runtime_id)
    env_lama = dict(sekarang.get("environmentVariables") or {})

    if args.tampilkan:
        for kunci in sorted(env_lama):
            nilai = env_lama[kunci]
            tampil = f"(panjang {len(nilai)})" if kunci == KUNCI_TOKEN else nilai
            print(f"  {kunci} = {tampil}")
        print(f"status {sekarang['status']} · versi {sekarang.get('agentRuntimeVersion')}")
        return 0

    if not args.api_url and not args.token:
        raise SystemExit("tidak ada yang diubah: isi --api-url dan/atau --token")

    env_baru = dict(env_lama)
    if args.api_url:
        env_baru[KUNCI_URL] = args.api_url.rstrip("/")
    token = args.token or env.get(KUNCI_TOKEN, "")
    if token:
        env_baru[KUNCI_TOKEN] = token

    artifact = sekarang["agentRuntimeArtifact"]
    hasil = kontrol.update_agent_runtime(
        agentRuntimeId=runtime_id,
        agentRuntimeArtifact=artifact,
        roleArn=sekarang["roleArn"],
        networkConfiguration=sekarang["networkConfiguration"],
        protocolConfiguration=sekarang.get("protocolConfiguration", {"serverProtocol": "HTTP"}),
        environmentVariables=env_baru,
    )
    print(f"update dikirim · versi {hasil.get('agentRuntimeVersion')} · status {hasil.get('status')}")

    batas = time.time() + max(30, args.tunggu_detik)
    while time.time() < batas:
        info = kontrol.get_agent_runtime(agentRuntimeId=runtime_id)
        status = info["status"]
        if status == "READY":
            print(f"runtime READY · versi {info.get('agentRuntimeVersion')}")
            break
        if status in {"CREATE_FAILED", "UPDATE_FAILED", "DELETING"}:
            print(f"runtime {status} — periksa CloudWatch", file=sys.stderr)
            return 1
        time.sleep(5)
    else:
        print("runtime belum READY sampai batas tunggu; cek lagi nanti", file=sys.stderr)
        return 1

    if args.api_url:
        tulis_env(ROOT / ".env", KUNCI_URL, args.api_url.rstrip("/"))
        print(f".env: {KUNCI_URL} diperbarui")
    if args.token:
        tulis_env(ROOT / ".env", KUNCI_TOKEN, args.token)
        print(f".env: {KUNCI_TOKEN} diperbarui")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
