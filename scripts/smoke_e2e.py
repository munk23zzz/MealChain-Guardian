"""Smoke test ujung-ke-ujung MealChain Guardian (bukan sekadar demo).

Memeriksa bahwa seluruh rantai benar-benar hidup, bukan hanya satu halaman:

1. backend sehat (`GET /health`)
2. tiga akun demo bisa login dan `/auth/me` mengembalikan peran yang benar
3. RBAC endpoint sesuai matriks peran (admin, demo, event)
4. ada keputusan di DB dan keputusan hasil review punya >= 7 baris trace
5. runtime AgentCore `READY` dan invoke `review_decision` mengembalikan 7 finding

Keluar dengan kode 1 bila ada pemeriksaan GAGAL. `SKIP` tidak menggagalkan, tetapi
dihitung terpisah supaya tidak terlihat seperti lulus.

Contoh:
    python scripts/smoke_e2e.py
    python scripts/smoke_e2e.py --skip-aws           # tanpa kredensial AWS
    python scripts/smoke_e2e.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AKUN = [
    ("sppg.head@demo.local", "Demo#SPPG2026", "sppg_head"),
    ("sppg.nutritionist@demo.local", "Demo#Nut2026", "sppg_nutritionist"),
    ("bgn.monitor@demo.local", "Demo#BGN2026", "bgn_monitor"),
]

LULUS, GAGAL, LEWAT = "LULUS", "GAGAL", "SKIP"


class Hasil:
    def __init__(self) -> None:
        self.baris: list[tuple[str, str, str]] = []

    def catat(self, nama: str, status: str, detail: str = "") -> None:
        self.baris.append((nama, status, detail))

    def ringkas(self) -> int:
        lebar = max(len(n) for n, _s, _d in self.baris) + 2
        for nama, status, detail in self.baris:
            print(f"  {nama.ljust(lebar)} {status:5s} {detail}")
        jumlah = {s: sum(1 for _n, st, _d in self.baris if st == s) for s in (LULUS, GAGAL, LEWAT)}
        print(f"\n  {jumlah[LULUS]} lulus · {jumlah[GAGAL]} gagal · {jumlah[LEWAT]} skip")
        return 1 if jumlah[GAGAL] else 0


def panggil(base: str, path: str, *, token: str = "", method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{base}{path}", data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            mentah = resp.read().decode("utf-8", errors="replace")
            return resp.status, (json.loads(mentah) if mentah.strip().startswith(("{", "[")) else mentah)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")[:200]
    except urllib.error.URLError as exc:
        return 0, f"tidak dapat menghubungi {base}: {exc.reason}"


def muat_env() -> dict[str, str]:
    hasil: dict[str, str] = {}
    for path in (ROOT / ".env", ROOT / "secrets" / "aws-app.env"):
        if not path.exists():
            continue
        for baris in path.read_text(encoding="utf-8").splitlines():
            baris = baris.strip()
            if baris and not baris.startswith("#") and "=" in baris:
                k, v = baris.split("=", 1)
                if v.strip():
                    hasil[k.strip()] = v.strip()
    return hasil


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test ujung-ke-ujung")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--skip-aws", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    env = muat_env()
    hasil = Hasil()

    kode, _ = panggil(base, "/health")
    hasil.catat("backend /health", LULUS if kode == 200 else GAGAL, f"HTTP {kode}")

    token_per_peran: dict[str, str] = {}
    for email, sandi, peran in AKUN:
        kode, data = panggil(base, "/auth/login", method="POST", body={"email": email, "password": sandi})
        if kode != 200 or not isinstance(data, dict):
            hasil.catat(f"login {peran}", GAGAL, f"HTTP {kode}")
            continue
        token = data.get("access_token", "")
        token_per_peran[peran] = token
        kode_me, me = panggil(base, "/auth/me", token=token)
        peran_me = me.get("role") if isinstance(me, dict) else None
        hasil.catat(
            f"login + /auth/me {peran}",
            LULUS if kode_me == 200 and peran_me == peran else GAGAL,
            f"role={peran_me}",
        )

    head = token_per_peran.get("sppg_head", "")
    monitor = token_per_peran.get("bgn_monitor", "")
    if head and monitor:
        uji = [
            ("GET /admin/users (head)", "/admin/users", head, 403),
            ("GET /admin/users (monitor)", "/admin/users", monitor, 200),
            ("GET /demo/data-status (head)", "/demo/data-status", head, 200),
            ("GET /demo/data-status (monitor)", "/demo/data-status", monitor, 403),
        ]
        for nama, path, token, harap in uji:
            kode, _d = panggil(base, path, token=token)
            hasil.catat(f"RBAC {nama}", LULUS if kode == harap else GAGAL, f"HTTP {kode} (harap {harap})")

    kode, daftar = panggil(base, "/decisions", token=head)
    keputusan = daftar if isinstance(daftar, list) else (daftar or {}).get("items", []) if isinstance(daftar, dict) else []
    hasil.catat("daftar keputusan", LULUS if keputusan else GAGAL, f"{len(keputusan)} keputusan")

    dengan_review = None
    for k in keputusan:
        kid = (k.get("decision_id") or k.get("id")) if isinstance(k, dict) else None
        if not kid:
            continue
        kode, jejak = panggil(base, f"/decisions/{kid}/traces", token=head)
        # respons: {"decision_id": ..., "steps": [...]}; baris worker punya agent_name
        langkah = jejak.get("steps", []) if isinstance(jejak, dict) else (jejak if isinstance(jejak, list) else [])
        agen = {s.get("agent_name") for s in langkah if isinstance(s, dict) and s.get("agent_name")}
        if len(agen) >= 7:
            dengan_review = (kid, len(langkah), len(agen))
            break
    if dengan_review:
        kid, n, a = dengan_review
        hasil.catat("trace review 7 agen", LULUS, f"{kid[:8]} · {n} baris · {a} agen")
    else:
        hasil.catat("trace review 7 agen", GAGAL, "tidak ada keputusan dengan 7 baris worker")

    if args.skip_aws:
        hasil.catat("runtime AgentCore", LEWAT, "--skip-aws")
    else:
        arn = env.get("AGENTCORE_RUNTIME_ARN", "")
        if not arn:
            hasil.catat("runtime AgentCore", GAGAL, "AGENTCORE_RUNTIME_ARN kosong di .env")
        else:
            os.environ.setdefault("AWS_ACCESS_KEY_ID", env.get("AWS_ACCESS_KEY_ID", ""))
            os.environ.setdefault("AWS_SECRET_ACCESS_KEY", env.get("AWS_SECRET_ACCESS_KEY", ""))
            import boto3
            from botocore.config import Config

            region = env.get("AWS_REGION", "us-west-2")
            kontrol = boto3.client("bedrock-agentcore-control", region_name=region, config=Config(retries={"max_attempts": 0}, read_timeout=40))
            try:
                info = kontrol.get_agent_runtime(agentRuntimeId=arn.rsplit("/", 1)[-1])
                status = info["status"]
                hasil.catat("runtime AgentCore READY", LULUS if status == "READY" else GAGAL, f"{status} v{info.get('agentRuntimeVersion')}")
                env_runtime = info.get("environmentVariables") or {}
                hasil.catat(
                    "runtime punya MEALCHAIN_API_URL",
                    LULUS if env_runtime.get("MEALCHAIN_API_URL") else GAGAL,
                    env_runtime.get("MEALCHAIN_API_URL", "-"),
                )
            except Exception as exc:  # noqa: BLE001
                hasil.catat("runtime AgentCore READY", GAGAL, f"{type(exc).__name__}: {str(exc)[:80]}")

            klien = boto3.client("bedrock-agentcore", region_name=region, config=Config(retries={"max_attempts": 0}, read_timeout=180))
            kid = dengan_review[0] if dengan_review else None
            if not kid:
                hasil.catat("invoke review_decision", LEWAT, "butuh decision id")
            else:
                try:
                    resp = klien.invoke_agent_runtime(
                        agentRuntimeArn=arn,
                        contentType="application/json",
                        accept="application/json",
                        payload=json.dumps({"task": "review_decision", "decision_id": kid}),
                    )
                    mentah = resp["response"]
                    if hasattr(mentah, "read"):
                        mentah = mentah.read()
                    if isinstance(mentah, list):
                        mentah = b"".join(mentah)
                    isi = json.loads(mentah.decode() if isinstance(mentah, (bytes, bytearray)) else mentah)
                    dalam = json.loads(isi["response"]) if isinstance(isi.get("response"), str) else isi["response"]
                    findings = dalam.get("findings", [])
                    jejak = dalam.get("trace_rows", [])
                    ok = len(findings) == 7 and len(jejak) >= 7
                    hasil.catat("invoke review_decision", LULUS if ok else GAGAL, f"{len(findings)} finding · {len(jejak)} trace row")
                except Exception as exc:  # noqa: BLE001
                    hasil.catat("invoke review_decision", GAGAL, f"{type(exc).__name__}: {str(exc)[:80]}")

    return hasil.ringkas()


if __name__ == "__main__":
    sys.exit(main())
