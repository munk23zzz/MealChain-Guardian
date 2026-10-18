"""Deploy Supervisor Agent MealChain Guardian ke AWS Bedrock AgentCore Runtime.

Dijalankan dari HOST (butuh docker CLI + kredensial AWS). Urutannya:
    cek identitas & IZIN  →  ECR repo  →  build+push image  →  CreateAgentRuntime  →  tunggu READY

Kalau izin kurang, skrip BERHENTI di langkah 1 dan mencetak persis izin yang hilang +
langkah perbaikannya (tanpa mengubah apa pun di AWS).

Contoh:
    python agent/deploy_agentcore.py --role-arn arn:aws:iam::624606539664:role/<nama> --write-env
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"

RUNTIME_NAME_DEFAULT = "mealchain_supervisor_agent"
ECR_REPO_DEFAULT = "mealchain/supervisor-agent"

# Izin minimum untuk SELURUH proses. Dipakai sebagai preflight (simulate) supaya
# kegagalan izin ketahuan SEBELUM build image, bukan setelah.
PERLU_STAR = [
    "ecr:CreateRepository",
    "ecr:GetAuthorizationToken",
    "ecr:BatchCheckLayerAvailability",
    "ecr:InitiateLayerUpload",
    "ecr:UploadLayerPart",
    "ecr:CompleteLayerUpload",
    "ecr:PutImage",
    "bedrock-agentcore:CreateAgentRuntime",
    "bedrock-agentcore:UpdateAgentRuntime",
    "bedrock-agentcore:GetAgentRuntime",
    "bedrock-agentcore:ListAgentRuntimes",
    "bedrock-agentcore:CreateWorkloadIdentity",
    "bedrock-agentcore:GetWorkloadIdentity",
    "bedrock-agentcore:ListWorkloadIdentities",
]
# Aksi control-plane yang dibatasi resource runtime/* di policy produksi.
PERLU_RUNTIME = [
    "bedrock-agentcore:CreateAgentRuntimeEndpoint",
    "bedrock-agentcore:UpdateAgentRuntimeEndpoint",
    "bedrock-agentcore:GetAgentRuntimeEndpoint",
    "bedrock-agentcore:DeleteAgentRuntimeEndpoint",
    "bedrock-agentcore:InvokeAgentRuntime",
]
# Aksi list tidak mendukung resource-level permission → disimulasikan pada "*".
PERLU_LIST = ["bedrock-agentcore:ListAgentRuntimeEndpoints"]
# Aksi beresource khusus: iam:PassRole → ARN peran; CreateServiceLinkedRole → ARN SLR.
PERLU_KHUSUS = ["iam:PassRole", "iam:CreateServiceLinkedRole"]
PERLU = PERLU_STAR + PERLU_RUNTIME + PERLU_LIST + PERLU_KHUSUS


def muat_env(path: Path) -> None:
    """Muat berkas env gaya `KEY=VALUE` ke os.environ (tanpa menimpa yang sudah ada)."""
    if not path.exists():
        return
    for baris in path.read_text(encoding="utf-8", errors="replace").splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        k, _, v = baris.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v:
            os.environ.setdefault(k, v)


def jalan(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("  $", " ".join(cmd[:6]), "…" if len(cmd) > 6 else "")
    return subprocess.run(cmd, check=True, text=True, **kw)


def preflight(region: str, role_arn: str = "") -> tuple[bool, list[str]]:
    """Kembalikan (boleh, daftar_izin_hilang). Tidak menulis apa pun.

    Resource simulasi harus cocok dengan bentuk di policy: `iam:PassRole` diuji pada ARN
    peran, `iam:CreateServiceLinkedRole` pada ARN SLR yang persis (wildcard pada resource
    simulasi dibaca literal, bukan pola), dan aksi list pada "*".
    """
    import boto3

    sts = boto3.client("sts")
    ident = sts.get_caller_identity()
    print(f"Identitas: {ident['Arn']} (akun {ident['Account']}, region {region})")

    iam = boto3.client("iam")
    keputusan: dict[str, tuple[str, str]] = {}
    try:
        akun = ident["Account"]
        runtime_arn = f"arn:aws:bedrock-agentcore:{region}:{akun}:runtime/*"
        slr_resources = [
            (
                f"arn:aws:iam::{akun}:role/aws-service-role/runtime-identity"
                ".bedrock-agentcore.amazonaws.com/"
                "AWSServiceRoleForBedrockAgentCoreRuntimeIdentity"
            ),
            (
                f"arn:aws:iam::{akun}:role/aws-service-role/network"
                ".bedrock-agentcore.amazonaws.com/AWSServiceRoleForBedrockAgentCoreNetwork"
            ),
        ]

        def sim(actions: list[str], resource: str) -> None:
            hasil = iam.simulate_principal_policy(
                PolicySourceArn=ident["Arn"], ActionNames=actions, ResourceArns=[resource]
            )
            for r in hasil["EvaluationResults"]:
                keputusan[r["EvalActionName"]] = (r["EvalDecision"], resource)

        sim(PERLU_STAR, "*")
        sim(PERLU_RUNTIME, runtime_arn)
        sim(PERLU_LIST, "*")
        if role_arn:
            sim(["iam:PassRole"], role_arn)
        slr_ok = True
        for arn_slr in slr_resources:
            hasil_slr = iam.simulate_principal_policy(
                PolicySourceArn=ident["Arn"],
                ActionNames=["iam:CreateServiceLinkedRole"],
                ResourceArns=[arn_slr],
            )
            if any(r["EvalDecision"] != "allowed" for r in hasil_slr["EvaluationResults"]):
                slr_ok = False
        keputusan["iam:CreateServiceLinkedRole"] = (
            "allowed" if slr_ok else "implicitDeny",
            "SLR runtime-identity + network",
        )
    except Exception as e:  # noqa: BLE001
        print(f"Preflight izin tidak bisa dijalankan: {type(e).__name__}: {e}")
        return True, []  # jangan menghalangi; kegagalan asli akan muncul saat aksi

    hilang = [a for a in PERLU if keputusan.get(a, ("?", ""))[0] != "allowed"]
    if not role_arn:
        hilang = [a for a in hilang if a != "iam:PassRole"]
    for aksi in PERLU:
        if aksi == "iam:PassRole" and not role_arn:
            print("  LEWAT iam:PassRole  (ARN peran belum diisi; uji dengan --role-arn)")
            continue
        hasil, resource = keputusan.get(aksi, ("?", ""))
        tanda = "ok   " if hasil == "allowed" else "TOLAK"
        print(f"  {tanda} {aksi}  ({resource})")
    return not hilang, hilang


def laporan_izin(hilang: list[str], region: str, akun: str) -> None:
    print("\n" + "=" * 78)
    print("BERHENTI — kredensial ini belum boleh mendeploy AgentCore Runtime.")
    print("Izin yang hilang:", ", ".join(hilang))
    print("""
Yang harus dilakukan PEMILIK AKUN (sekali saja, di konsol AWS / CloudShell):

1) Buat peran eksekusi untuk runtime (trust policy — AgentCore memanggilnya):
   BedrockAgentCoreRuntimeRole  (ganti <AKUN> = %s)

   Trust policy:
   {"Version":"2012-10-17","Statement":[{"Effect":"Allow",
     "Principal":{"Service":"bedrock-agentcore.amazonaws.com"},
     "Action":"sts:AssumeRole"}]}

   Permission policy (minimum agar agent bisa menjawab):
   {"Version":"2012-10-17","Statement":[
     {"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream",
       "logs:PutLogEvents"],"Resource":"*"},
     {"Effect":"Allow","Action":["bedrock:InvokeModel",
       "bedrock:InvokeModelWithResponseStream"],"Resource":"*"},
     {"Effect":"Allow","Action":["ecr:GetAuthorizationToken",
       "ecr:BatchCheckLayerAvailability","ecr:GetDownloadUrlForLayer",
       "ecr:BatchGetImage"],"Resource":"*"}]}

2) Izinkan user IAM `megu` mendeploy (agar agen yang mengerjakan tidak
   menunggu Anda setiap kali). Inline policy pada user `megu`:
   {"Version":"2012-10-17","Statement":[
     {"Effect":"Allow","Action":["ecr:CreateRepository","ecr:GetAuthorizationToken",
       "ecr:BatchCheckLayerAvailability","ecr:InitiateLayerUpload","ecr:UploadLayerPart",
       "ecr:CompleteLayerUpload","ecr:PutImage"],"Resource":"*"},
     {"Effect":"Allow","Action":["iam:PassRole"],
       "Resource":"arn:aws:iam::%s:role/BedrockAgentCoreRuntimeRole"},
     {"Effect":"Allow","Action":["bedrock-agentcore:CreateAgentRuntime",
       "bedrock-agentcore:UpdateAgentRuntime","bedrock-agentcore:GetAgentRuntime",
       "bedrock-agentcore:CreateAgentRuntimeEndpoint","bedrock-agentcore:DeleteAgentRuntime"],
       "Resource":"*"}]}

3) Beri tahu agen "izin sudah ditambahkan" — sisa deploy dijalankan otomatis:
   python agent/deploy_agentcore.py --role-arn arn:aws:iam::%s:role/BedrockAgentCoreRuntimeRole --write-env
""" % (akun, akun, akun))
    print("=" * 78)


def pastikan_ecr(region: str, repo: str) -> str:
    import boto3
    from botocore.exceptions import ClientError

    ecr = boto3.client("ecr", region_name=region)
    try:
        uri = ecr.describe_repositories(repositoryNames=[repo])["repositories"][0]["repositoryUri"]
        print(f"  repo sudah ada: {uri}")
        return uri
    except ClientError as e:
        if e.response["Error"]["Code"] != "RepositoryNotFoundException":
            raise
    uri = ecr.create_repository(
        repositoryName=repo, imageScanningConfiguration={"scanOnPush": True}
    )["repository"]["repositoryUri"]
    print(f"  repo dibuat: {uri}")
    return uri


def build_push(region: str, akun: str, uri: str, platform: str, tag: str) -> str:
    import base64

    import boto3

    ecr = boto3.client("ecr", region_name=region)
    auth = ecr.get_authorization_token()["authorizationData"][0]
    token = base64.b64decode(auth["authorizationToken"]).decode()
    user, _, pw = token.partition(":")
    registry = auth["proxyEndpoint"].replace("https://", "")

    # Password hanya lewat stdin docker login — TIDAK muncul di argv.
    subprocess.run(
        ["docker", "login", "--username", user, "--password-stdin", registry],
        input=pw, text=True, check=True, stdout=subprocess.DEVNULL,
    )
    image = f"{uri}:{tag}"
    jalan(["docker", "build", "--platform", platform, "-t", image, "-f", str(AGENT_DIR / "Dockerfile"), str(AGENT_DIR)])
    jalan(["docker", "push", image])
    return image


def tunggu_ready(region: str, runtime_id: str, batas_detik: int = 900) -> dict:
    import boto3

    ctrl = boto3.client("bedrock-agentcore-control", region_name=region)
    t0 = time.time()
    terakhir = ""
    while time.time() - t0 < batas_detik:
        info = ctrl.get_agent_runtime(agentRuntimeId=runtime_id)
        status = info.get("status", "?")
        if status != terakhir:
            print(f"  status: {status} ({int(time.time()-t0)} dtk)")
            terakhir = status
        if status in ("READY", "CREATE_FAILED", "UPDATE_FAILED", "DELETING"):
            return info
        time.sleep(10)
    return {"status": "TIMEOUT"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role-arn", default=os.environ.get("AGENTCORE_RUNTIME_ROLE_ARN", ""))
    ap.add_argument("--region", default="")
    ap.add_argument("--name", default=RUNTIME_NAME_DEFAULT)
    ap.add_argument("--repo", default=ECR_REPO_DEFAULT)
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--platform", default="linux/arm64", help="AgentCore Runtime = linux/arm64")
    ap.add_argument("--write-env", action="store_true", help="tulis AGENTCORE_RUNTIME_ARN ke .env")
    ap.add_argument("--preflight-saja", action="store_true")
    args = ap.parse_args()

    for berkas in (ROOT / ".env", ROOT / "secrets" / "aws-app.env"):
        muat_env(berkas)
    region = args.region or os.environ.get("AWS_REGION") or "us-west-2"

    import boto3

    akun = boto3.client("sts").get_caller_identity()["Account"]

    print("\n== 1/5 preflight izin ==")
    boleh, hilang = preflight(region, args.role_arn)
    if args.preflight_saja:
        return 0 if boleh else 2
    if not boleh:
        laporan_izin(hilang, region, akun)
        return 2
    if not args.role_arn:
        print("--role-arn belum diisi (peran eksekusi runtime). Jalankan dengan --role-arn.")
        return 2

    print("\n== 2/5 periksa peran eksekusi ==")
    nama_peran = args.role_arn.rsplit("/", 1)[-1]
    try:
        peran = boto3.client("iam").get_role(RoleName=nama_peran)["Role"]
        print(f"  peran ada: {peran['Arn']}")
    except Exception as e:  # noqa: BLE001
        print(f"  peran tidak bisa dibaca: {type(e).__name__}: {e}")
        return 2

    print("\n== 3/5 ECR + build/push image ==")
    uri = pastikan_ecr(region, args.repo)
    image = build_push(region, akun, uri, args.platform, args.tag)
    print(f"  image: {image}")

    print("\n== 4/5 CreateAgentRuntime ==")
    ctrl = boto3.client("bedrock-agentcore-control", region_name=region)
    env_vars = {
        "SUPERVISOR_AGENT_MODEL": os.environ.get(
            "SUPERVISOR_AGENT_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        )
    }
    # Tool supervisor memanggil API MealChain. Tanpa dua variabel ini tool
    # menolak dengan missing_config (jujur), bukan mengarang angka.
    for nama in ("MEALCHAIN_API_URL", "MEALCHAIN_API_TOKEN"):
        nilai = (os.environ.get(nama) or "").strip()
        if nilai:
            env_vars[nama] = nilai
    try:
        dibuat = ctrl.create_agent_runtime(
            agentRuntimeName=args.name,
            agentRuntimeArtifact={"containerConfiguration": {"containerUri": image}},
            roleArn=args.role_arn,
            networkConfiguration={"networkMode": "PUBLIC"},
            protocolConfiguration={"serverProtocol": "HTTP"},
            description="Supervisor Agent MealChain Guardian (Strands SDK + Bedrock)",
            environmentVariables=env_vars,
        )
        runtime_id = dibuat["agentRuntimeId"]
        arn = dibuat["agentRuntimeArn"]
        print(f"  dibuat: {runtime_id}")
        print(f"  ARN   : {arn}")
    except Exception as e:  # noqa: BLE001
        pesan = str(e)
        if "Conflict" in pesan or "already exists" in pesan:
            daftar = ctrl.list_agent_runtimes(maxResults=100)["agentRuntimes"]
            kandidat = [r for r in daftar if r["agentRuntimeName"] == args.name]
            if not kandidat:
                print("  konflik tapi runtime tidak ditemukan — berhenti")
                return 1
            runtime_id = kandidat[0]["agentRuntimeId"]
            arn = kandidat[0]["agentRuntimeArn"]
            print(f"  runtime sudah ada → update: {runtime_id}")
            ctrl.update_agent_runtime(
                agentRuntimeId=runtime_id,
                agentRuntimeArtifact={"containerConfiguration": {"containerUri": image}},
                roleArn=args.role_arn,
                networkConfiguration={"networkMode": "PUBLIC"},
                protocolConfiguration={"serverProtocol": "HTTP"},
            )
        else:
            print(f"  GAGAL: {type(e).__name__}: {pesan[:400]}")
            return 1

    print("\n== 5/5 tunggu READY ==")
    info = tunggu_ready(region, runtime_id)
    print(f"  status akhir: {info.get('status')}")
    if info.get("status") != "READY":
        print(json.dumps({k: str(v) for k, v in info.items()}, indent=2)[:1500])
        return 1

    arn = info.get("agentRuntimeArn", arn)
    print(f"\nARN siap dipakai: {arn}")
    if args.write_env:
        env_path = ROOT / ".env"
        teks = env_path.read_text(encoding="utf-8")
        baru = []
        ketemu = False
        for baris in teks.splitlines():
            if baris.startswith("AGENTCORE_RUNTIME_ARN="):
                baru.append(f"AGENTCORE_RUNTIME_ARN={arn}")
                ketemu = True
            else:
                baru.append(baris)
        if not ketemu:
            baru.append(f"AGENTCORE_RUNTIME_ARN={arn}")
        env_path.write_text("\n".join(baru) + "\n", encoding="utf-8")
        print("  .env diperbarui: AGENTCORE_RUNTIME_ARN diisi.")
        print("  Jalankan: docker compose up -d backend   (env dibaca saat create/start)")
    else:
        print(f"  Tambahkan ke .env → AGENTCORE_RUNTIME_ARN={arn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
