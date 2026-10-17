"""Papan status integrasi per komponen (PLAN-012 · 2026-10-17).

Tujuan: memindahkan bukti status integrasi dari dokumen ke satu permukaan yang
bisa ditunjukkan, TANPA mengklaim lebih dari yang benar-benar diperiksa.

Aturan kejujuran yang dipaku modul ini:

- Kategori hanya menyebut JENIS BUKTI yang dimiliki komponen: `configured`
  (env/isian ada), `provisioned` (resource disediakan), `contract_tested` (ada
  tes kontraknya), `artifacts_ready` (artefak siap, deploy belum), `fail_closed`
  (gagal secara eksplisit), `unavailable` (tidak ada), `not_started` (belum
  dimulai).
- **Tidak ada komponen yang boleh berlabel `operational`/`probe_passed` tanpa
  probe nyata.** Endpoint ini TIDAK melakukan probe jaringan (supaya deterministik
  dan tidak memanggil layanan berbayar saat UI dibuka), sehingga `probes_run`
  selalu 0 dan kategori itu tidak pernah muncul dari sini.
- Setiap komponen membawa `evidence` (apa yang diperiksa), `artifact` (dokumen/
  berkas sumber), dan `checked_at` (kapan diperiksa).

Read-only: hanya butuh JWT (semua peran yang sah boleh melihat), tanpa mutasi.
"""

import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.models import User

router = APIRouter()

#: Kategori yang boleh dipakai — dipakai juga oleh tes sebagai kontrak.
KATEGORI = (
    "configured",
    "provisioned",
    "contract_tested",
    "artifacts_ready",
    "fail_closed",
    "unavailable",
    "not_started",
)

#: Label Indonesia untuk UI; satu sumber supaya backend & panel tidak menyimpang.
LABEL_KATEGORI = {
    "configured": "terkonfigurasi",
    "provisioned": "tersedia (provisioned)",
    "contract_tested": "kontrak diuji",
    "artifacts_ready": "artefak siap",
    "fail_closed": "gagal-tertutup",
    "unavailable": "tidak tersedia",
    "not_started": "belum dimulai",
}


def _env(nama: str) -> bool:
    """Nilai env terisi (panjang > 0). Nilai rahasia TIDAK pernah dikembalikan."""
    return bool(os.environ.get(nama, "").strip())


def _komponen() -> list[dict]:
    """Daftar komponen + kategori buktinya (dihitung saat dipanggil)."""
    sap_siap = _env("SAP_AI_CORE_CLIENT_ID")
    arn_siap = _env("AGENTCORE_RUNTIME_ARN")
    gateway_siap = _env("AGENTCORE_GATEWAY_URL")
    memory_siap = _env("AGENTCORE_MEMORY_ID")
    return [
        {
            "id": "sap_ai_core",
            "name": "SAP AI Core (SAP-RPT-1.6)",
            "category": "contract_tested" if sap_siap else "unavailable",
            "evidence": "env SAP_AI_CORE_CLIENT_ID terisi" if sap_siap else "env SAP_AI_CORE_CLIENT_ID kosong",
            "artifact": "docs/verification/fase-12.md",
            "note": "Peramal deret resmi; kontrak pemanggil diuji di backend/tests.",
        },
        {
            "id": "mock_sap",
            "name": "Mock SAP (sap_integration)",
            "category": "contract_tested",
            "evidence": "layanan mock-sap + tes kontrak PO",
            "artifact": "backend/app/sap_integration/mock_service.py",
            "note": "Jalur default MVP: PO ditulis ke mock, bukan S/4HANA nyata.",
        },
        {
            "id": "agentcore_runtime",
            "name": "AgentCore Runtime (Strands supervisor)",
            "category": "artifacts_ready" if not arn_siap else "configured",
            "evidence": (
                "env AGENTCORE_RUNTIME_ARN terisi"
                if arn_siap
                else "env AGENTCORE_RUNTIME_ARN kosong; artefak agent/ siap"
            ),
            "artifact": "agent/README-deploy.md",
            "note": (
                "Deploy belum dijalankan; orkestrator memakai slot ini setelah ARN terisi."
                if not arn_siap
                else "Runtime terdaftar; pemanggilan belum diprobe dari endpoint ini."
            ),
        },
        {
            "id": "agentcore_gateway",
            "name": "AgentCore Gateway",
            "category": "configured" if gateway_siap else "not_started",
            "evidence": "env AGENTCORE_GATEWAY_URL" + (" terisi" if gateway_siap else " kosong"),
            "artifact": "docs/Roadmap.md",
            "note": "Belum ada gateway yang dibuat untuk alur ini." if not gateway_siap else "URL gateway terisi.",
        },
        {
            "id": "agentcore_memory",
            "name": "AgentCore Memory",
            "category": "provisioned" if memory_siap else "unavailable",
            "evidence": "env AGENTCORE_MEMORY_ID" + (" terisi" if memory_siap else " kosong"),
            "artifact": "agent/README-deploy.md",
            "note": (
                "Resource disediakan, tetapi adapter aplikasi belum memakainya."
                if memory_siap
                else "Memory belum disediakan."
            ),
        },
        {
            "id": "observability",
            "name": "Observability",
            "category": "fail_closed",
            "evidence": "kebijakan: tanpa kredensial → galat eksplisit, bukan laporan palsu",
            "artifact": "backend/app/core/observability.py",
            "note": "Kegagalan dilaporkan apa adanya; tidak ada status hijau tanpa data.",
        },
        {
            "id": "aws_for_sap_mcp",
            "name": "AWS for SAP MCP",
            "category": "not_started",
            "evidence": "belum ada implementasi/tenant",
            "artifact": "docs/Roadmap.md",
            "note": "Tertahan akses tenant SAP S/4HANA; dijadwalkan on-demand.",
        },
    ]


@router.get("/integrations/status")
async def status_integrasi(_user: User = Depends(get_current_user)):
    """Papan status integrasi (read-only) — sumber: env + artefak, bukan probe."""
    sekarang = datetime.now(UTC).isoformat()
    komponen = []
    for item in _komponen():
        entry = dict(item)
        entry["category_label"] = LABEL_KATEGORI[entry["category"]]
        entry["checked_at"] = sekarang
        komponen.append(entry)
    return {
        "checked_at": sekarang,
        # Endpoint ini tidak memanggil layanan mana pun: kalau angka ini bukan 0,
        # berarti ada probe yang benar-benar dijalankan dan kategorinya sah.
        "probes_run": 0,
        "categories": list(KATEGORI),
        "components": komponen,
    }
