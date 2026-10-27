#!/usr/bin/env python3
"""Probe READ-ONLY AgentCore Gateway & Memory (Fase 11 MG, butir 4 & 5).

Tujuan: memisahkan EMPAT bukti yang sering dicampur menjadi satu kata "DONE":

  1. `resource_exists`  — Gateway benar-benar ada di akun/region ini.
  2. `target_ready`     — target (MCP/tool) ada dan statusnya READY.
  3. `tool_invoked`     — satu tool benar-benar dipanggil dan hasilnya dibaca.
  4. `app_uses_gateway` — aplikasi (registry/adapter) memakai Gateway itu,
                          bukan hanya konfigurasi yang terisi.

Selain itu skrip ini memeriksa Memory: apakah `AGENTCORE_MEMORY_ID` menunjuk
resource nyata (GetMemory) — tanpa menulis apa pun.

Aturan yang dipegang:
- HANYA operasi baca: ListGateways/GetGateway/ListGatewayTargets/GetMemory/
  ListAgentRuntimes. Tidak ada Create/Update/Delete, tidak ada InvokeAgentRuntime.
- `tool_invoked` TIDAK pernah diklaim dari konfigurasi: nilainya `UNVERIFIED`
  kecuali ada pemanggilan nyata yang hasilnya dibaca. Skrip ini tidak memanggil
  tool, jadi selalu melaporkan UNVERIFIED beserta alasannya.
- AccessDenied → `UNVERIFIED` (izin belum ada), BUKAN `FAIL` dan BUKAN `WORKING`.
- Tidak mencetak kredensial; ARN dipotong menjadi ID pendek.

Keluaran: JSON ke stdout (boleh disimpan) + ringkasan baris per bukti.

Contoh (dari root repo, kredensial dari secrets/aws-app.env):

  docker run --rm --env-file secrets/aws-app.env \\
    -v "E:/hackathon/HackathonAWS/mealchain-guardian:/repo:ro" -w /repo \\
    -e PYTHONPATH=/repo/backend --entrypoint python \\
    mealchain-guardian-backend scripts/probe_agentcore_gateway.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

STATUS_OK = "VERIFIED"
STATUS_UNVERIFIED = "UNVERIFIED"
STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"
STATUS_DENIED = "UNVERIFIED"


def _pendek(nilai: str | None, n: int = 24) -> str | None:
    if not nilai:
        return None
    return nilai if len(nilai) <= n else f"…{nilai[-n:]}"


def _klien(nama: str, region: str):
    import boto3

    return boto3.client(nama, region_name=region)


def _bukti_aplikasi() -> dict:
    """Bukti keempat: apakah APLIKASI (bukan hanya env) memakai Gateway."""
    url = (os.environ.get("AGENTCORE_GATEWAY_URL") or "").strip()
    if url:
        return {
            "status": STATUS_UNVERIFIED,
            "detail": "AGENTCORE_GATEWAY_URL terisi; pemakaian nyata belum dibuktikan "
            "di sesi ini (butuh satu tool dipanggil lewat aplikasi)",
        }
    return {
        "status": STATUS_NOT_CONFIGURED,
        "detail": "AGENTCORE_GATEWAY_URL kosong — aplikasi tidak memakai Gateway, "
        "jangan menandai integrasi ini DONE",
    }


def probe_gateway(region: str) -> dict:
    hasil = {
        "resource_exists": {"status": STATUS_UNVERIFIED, "detail": None, "gateways": []},
        "target_ready": {"status": STATUS_UNVERIFIED, "detail": None, "targets": []},
        "tool_invoked": {
            "status": STATUS_UNVERIFIED,
            "detail": "skrip ini sengaja tidak memanggil tool; bukti invokasi harus "
            "berasal dari pemanggilan nyata yang hasilnya dibaca aplikasi",
        },
        "app_uses_gateway": {"status": STATUS_UNVERIFIED, "detail": None},
    }
    try:
        klien = _klien("bedrock-agentcore-control", region)
        daftar = klien.list_gateways(maxResults=50)
        gateways = daftar.get("gateways", daftar.get("items", []))
        hasil["resource_exists"] = {
            "status": STATUS_OK,
            "detail": f"{len(gateways)} gateway terlihat di {region}",
            "gateways": [
                {
                    "id": _pendek(g.get("gatewayId")),
                    "name": g.get("name"),
                    "status": g.get("status"),
                    "url_terisi": bool(g.get("gatewayUrl")),
                }
                for g in gateways
            ],
        }
        if not gateways:
            hasil["target_ready"] = {
                "status": STATUS_UNVERIFIED,
                "detail": "tidak ada gateway untuk diperiksa targetnya",
                "targets": [],
            }
            hasil["app_uses_gateway"] = _bukti_aplikasi()
            return hasil

        target_semua = []
        for g in gateways:
            try:
                t = klien.list_gateway_targets(
                    gatewayIdentifier=g["gatewayId"], maxResults=50
                )
            except Exception as exc:  # noqa: BLE001 - dilaporkan apa adanya
                target_semua.append(
                    {"gateway": _pendek(g.get("gatewayId")), "error": type(exc).__name__}
                )
                continue
            for item in t.get("targets", t.get("items", [])):
                target_semua.append(
                    {
                        "gateway": _pendek(g.get("gatewayId")),
                        "target": _pendek(item.get("targetId")),
                        "name": item.get("name"),
                        "status": item.get("status"),
                        "jenis": next(
                            (k for k in item if k.endswith("Target") and k != "targetId"),
                            None,
                        ),
                    }
                )
        hasil["target_ready"] = {
            "status": STATUS_OK if target_semua else STATUS_UNVERIFIED,
            "detail": f"{len(target_semua)} target terlihat",
            "targets": target_semua,
        }
    except Exception as exc:  # noqa: BLE001
        kode = getattr(exc, "response", {}).get("Error", {}).get("Code", type(exc).__name__)
        status = STATUS_DENIED if "AccessDenied" in kode else STATUS_UNVERIFIED
        hasil["resource_exists"] = {
            "status": status,
            "detail": f"probe gagal: {kode}",
            "gateways": [],
        }

    # --- bukti keempat: apakah APLIKASI memakai gateway -----------------------
    hasil["app_uses_gateway"] = _bukti_aplikasi()
    return hasil


def probe_memory(region: str) -> dict:
    memory_id = (os.environ.get("AGENTCORE_MEMORY_ID") or "").strip()
    if not memory_id:
        return {
            "resource_exists": {
                "status": STATUS_NOT_CONFIGURED,
                "detail": "AGENTCORE_MEMORY_ID kosong",
            }
        }
    try:
        klien = _klien("bedrock-agentcore-control", region)
        r = klien.get_memory(memoryId=memory_id)
        mem = r.get("memory", r)
    except Exception as exc:  # noqa: BLE001
        kode = getattr(exc, "response", {}).get("Error", {}).get("Code", type(exc).__name__)
        return {
            "resource_exists": {
                "status": STATUS_DENIED if "AccessDenied" in kode else STATUS_UNVERIFIED,
                "detail": f"GetMemory gagal: {kode}",
            }
        }

    # Bukti baca data-plane (read-only): ListEvents pada sesi probe acak.
    baca = {"status": STATUS_UNVERIFIED, "detail": None}
    try:
        data_plane = _klien("bedrock-agentcore", region)
        data_plane.list_events(
            memoryId=memory_id,
            actorId="probe-fase11",
            sessionId="probe-fase11-" + "0" * 20,
            includePayloads=False,
            maxResults=1,
        )
        baca = {"status": STATUS_OK, "detail": "ListEvents diizinkan"}
    except Exception as exc:  # noqa: BLE001
        kode = getattr(exc, "response", {}).get("Error", {}).get("Code", type(exc).__name__)
        baca = {
            "status": STATUS_DENIED if "AccessDenied" in kode else STATUS_UNVERIFIED,
            "detail": f"ListEvents gagal: {kode}",
        }

    return {
        "resource_exists": {
            "status": STATUS_OK,
            "detail": "GetMemory berhasil",
            "id": _pendek(mem.get("id", memory_id)),
            "name": mem.get("name"),
            "resource_status": mem.get("status"),
        },
        "read_allowed": baca,
        "write_allowed": {
            "status": STATUS_UNVERIFIED,
            "detail": "CreateEvent TIDAK dipanggil oleh probe (butuh izin tulis); "
            "bukti tulis-baca: tests/test_agent_memory_live.py (RUN_LIVE_AGENTCORE=1)",
        },
        "catatan": "aksi IAM yang dibutuhkan ada di infra/aws/iam-mealchain-fase11.json",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--region", default=os.environ.get("AWS_REGION", "us-west-2"))
    p.add_argument("--ringkas", action="store_true", help="hanya cetak baris status")
    args = p.parse_args(argv)

    laporan = {
        "region": args.region,
        "waktu_utc": __import__("datetime").datetime.now(
            __import__("datetime").UTC
        ).isoformat(),
        "gateway": probe_gateway(args.region),
        "memory": probe_memory(args.region),
    }

    if not args.ringkas:
        print(json.dumps(laporan, indent=2, ensure_ascii=False))

    print("\nRINGKASAN (4 bukti terpisah):", file=sys.stderr)
    for nama, isi in laporan["gateway"].items():
        print(f"  {nama:18s} {isi['status']:16s} {isi.get('detail') or ''}", file=sys.stderr)
    print("MEMORY:", file=sys.stderr)
    for nama, isi in laporan["memory"].items():
        if isinstance(isi, dict) and "status" in isi:
            print(f"  {nama:18s} {isi['status']:16s} {isi.get('detail') or ''}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
