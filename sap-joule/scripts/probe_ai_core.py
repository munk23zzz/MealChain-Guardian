"""Probe SAP AI Core / Generative AI Hub — bukti live, bukan klaim.

Dua hal yang dibuktikan skrip ini (dipakai untuk laporan ke juri dan untuk keputusan P2.3):

1. `--chat`  : model chat `gpt-5.4` bisa dipanggil (deployment `d1a82575de60e02a`).
2. `--rpt`   : `sap-rpt-1.6` (deployment `d76cf689a05d504f`) bisa memprediksi sel tabel —
   inilah kandidat provider peramalan kebutuhan (`/demand/forecast/*`) MealChain Guardian.

Kredensial diambil dari environment (JANGAN ditulis di berkas ini):

    AICORE_AUTH_URL       <url>/oauth/token
    AICORE_CLIENT_ID      dari keybroker: ai-core/<slug-tim>-key
    AICORE_CLIENT_SECRET  idem
    AICORE_BASE_URL       serviceurls.AI_API_URL
    AICORE_RESOURCE_GROUP default

Contoh:

    python probe_ai_core.py --chat
    python probe_ai_core.py --rpt
    python probe_ai_core.py --all

Skrip ini SENGAJA tidak menulis apa pun ke database dan tidak dipanggil aplikasi: ia hanya
membuktikan jalur kredensial + model. Integrasi ke kode MealChain baru setelah terbukti hijau
(pola yang sama dengan probe model chain yang sudah dipakai proyek ini).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

GPT_DEPLOYMENT = "d1a82575de60e02a"  # gpt-5.4
RPT_DEPLOYMENT = "d76cf689a05d504f"  # sap-rpt-1.6
DEFAULT_RESOURCE_GROUP = "default"

# Contoh payload RPT bergaya MealChain: permintaan porsi harian ([PREDICT] = sel yang diminta).
# Angka di sini CONTOH untuk membuktikan jalur model, bukan data operasional.
RPT_PAYLOAD = {
    "prediction_config": {
        "target_columns": [
            {
                "name": "KEBUTUHAN_KG",
                "prediction_placeholder": "[PREDICT]",
                "task_type": "regression",
            }
        ]
    },
    "index_column": "BARIS",
    "rows": [
        {"BARIS": "1", "SPPG": "Jakarta", "KOMODITAS": "Telur", "PORSI": 12000,
         "HARI": "Senin", "STOK_KG": 820, "KEBUTUHAN_KG": 1600},
        # Baris konteks kedua WAJIB ada: SAP-RPT menolak dengan
        # {"msg":"Not enough context rows provided. Minimum is 2."} bila hanya ada satu baris
        # yang sudah terisi (baris ber-[PREDICT] tidak dihitung sebagai konteks).
        {"BARIS": "2", "SPPG": "Cianjur", "KOMODITAS": "Telur", "PORSI": 9000,
         "HARI": "Senin", "STOK_KG": 1200, "KEBUTUHAN_KG": 1500},
        {"BARIS": "3", "SPPG": "Jakarta", "KOMODITAS": "Telur", "PORSI": 12500,
         "HARI": "Selasa", "STOK_KG": 640, "KEBUTUHAN_KG": "[PREDICT]"},
        {"BARIS": "4", "SPPG": "Bogor", "KOMODITAS": "Telur", "PORSI": 3000,
         "HARI": "Selasa", "STOK_KG": 1440, "KEBUTUHAN_KG": "[PREDICT]"},
    ],
}


def _env(nama: str) -> str:
    nilai = (os.environ.get(nama) or "").strip()
    if not nilai:
        print(
            f"Kredensial belum lengkap: environment `{nama}` kosong.\n"
            "Isi dari keybroker (BTP_Instructions/README.md bagian 3):\n"
            "  curl -s https://hackathon-keybroker.cfapps.ap10.hana.ondemand.com/ai-core/<slug-tim>-key",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return nilai


def token() -> str:
    """Tukar clientid/clientsecret jadi access token (client_credentials).

    AICORE_AUTH_URL boleh berisi base url saja (mis. https://<tenant>.authentication.<region>.hana.ondemand.com)
    atau sudah lengkap dengan /oauth/token — keduanya ditangani di sini. Sebelumnya skrip ini mem-POST nilai
    apa adanya, sehingga base url menghasilkan respons non-JSON dan `JSONDecodeError` yang membingungkan.
    """
    auth_url = _env("AICORE_AUTH_URL").rstrip("/")
    if not auth_url.endswith("/oauth/token"):
        auth_url = f"{auth_url}/oauth/token"
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            auth_url,
            auth=(_env("AICORE_CLIENT_ID"), _env("AICORE_CLIENT_SECRET")),
            data={"grant_type": "client_credentials"},
        )
    if response.status_code >= 400:
        print(f"Gagal mengambil token: HTTP {response.status_code} {response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)
    return response.json()["access_token"]


def _headers(bearer: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {bearer}",
        "AI-Resource-Group": os.environ.get("AICORE_RESOURCE_GROUP", DEFAULT_RESOURCE_GROUP),
        "Content-Type": "application/json",
    }


def chat(bearer: str) -> None:
    url = (
        f"{_env('AICORE_BASE_URL').rstrip('/')}/v2/inference/deployments/"
        f"{GPT_DEPLOYMENT}/chat/completions?api-version=2024-12-01-preview"
    )
    body = {
        "messages": [
            {"role": "system", "content": "Jawab singkat dalam bahasa Indonesia."},
            {"role": "user", "content": "Sebutkan satu komoditas pangan dan satu SPPG."},
        ],
        "max_completion_tokens": 60,
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=_headers(bearer), json=body)
    print(f"[chat gpt-5.4] HTTP {response.status_code}")
    if response.status_code >= 400:
        print(response.text[:500])
        return
    print("jawaban:", response.json()["choices"][0]["message"]["content"].strip())


def rpt(bearer: str) -> None:
    url = (
        f"{_env('AICORE_BASE_URL').rstrip('/')}/v2/inference/deployments/{RPT_DEPLOYMENT}/predict"
    )
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, headers=_headers(bearer), json=RPT_PAYLOAD)
    print(f"[sap-rpt-1.6] HTTP {response.status_code}")
    if response.status_code >= 400:
        print(response.text[:500])
        return
    data = response.json()
    print(json.dumps(data.get("predictions", data), ensure_ascii=False, indent=2)[:1500])


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe SAP AI Core (chat + RPT-1.6)")
    parser.add_argument("--chat", action="store_true", help="uji model gpt-5.4")
    parser.add_argument("--rpt", action="store_true", help="uji model sap-rpt-1.6")
    parser.add_argument("--all", action="store_true", help="uji keduanya")
    args = parser.parse_args()
    if not (args.chat or args.rpt or args.all):
        parser.print_help()
        return 1
    bearer = token()
    print("token AI Core: diperoleh\n")
    if args.chat or args.all:
        chat(bearer)
    if args.rpt or args.all:
        rpt(bearer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
