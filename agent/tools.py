"""Empat tool baca untuk Supervisor Agent — jembatan ke API MealChain.

Kenapa HTTP, bukan impor `app.*`: image AgentCore hanya membawa folder `agent/`
(lihat Dockerfile), sedangkan mesin keputusan ada di backend FastAPI. Tool di
sini karena itu memanggil endpoint yang SUDAH terbukti dipakai UI, bukan
menghitung ulang angka apa pun.

Pemetaan ke tujuh domain proposal:
- supply + demand        -> get_supply_demand
- safety + freshness     -> get_safety_freshness
- price + logistics      -> get_cost_eligibility (SDC & rincian biaya)
- evidence fusion        -> get_evidence_digest

Semua tool READ-ONLY. Tidak ada tool yang menulis, menyetujui, atau
mengeksekusi; aksi berisiko tetap lewat approval manusia.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ENV_API_URL = "MEALCHAIN_API_URL"
ENV_TOKEN = "MEALCHAIN_API_TOKEN"
DEFAULT_API_URL = "http://backend:8000"
TIMEOUT_SECONDS = 15.0


class ToolError(RuntimeError):
    """Kegagalan tool yang harus dilaporkan apa adanya, bukan ditebak."""


def _base_url() -> str:
    return (os.environ.get(ENV_API_URL) or DEFAULT_API_URL).rstrip("/")


def _token() -> str:
    token = (os.environ.get(ENV_TOKEN) or "").strip()
    if not token:
        raise ToolError(
            "missing_config: MEALCHAIN_API_TOKEN belum diset — tool tidak bisa "
            "membaca API tanpa token; jangan mengarang angka"
        )
    return token


def _request(path: str, method: str = "GET", body: dict | None = None) -> dict:
    """Panggil API dan kembalikan JSON. Error menjadi ToolError yang jelas."""
    url = f"{_base_url()}{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise ToolError(f"HTTP {exc.code} pada {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ToolError(
            f"tidak dapat menghubungi API di {_base_url()} ({exc.reason})"
        ) from exc
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ToolError(f"respons {path} bukan JSON yang sah") from exc
    if not isinstance(parsed, dict):
        raise ToolError(f"respons {path} bukan objek JSON")
    return parsed


def _num(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def get_supply_demand(location: str, commodity: str) -> dict:
    """Ambil pasokan, permintaan, surplus/kekurangan satu lokasi-komoditas.

    Args:
        location: Nama lokasi seed, mis. "Jakarta".
        commodity: Nama komoditas, mis. "telur".
    """
    loc = urllib.parse.quote(location, safe="")
    com = urllib.parse.quote(commodity, safe="")
    path = f"/balance/{loc}/{com}"
    data = _request(path)
    return {
        "lokasi": data.get("location", location),
        "komoditas": data.get("commodity", commodity),
        "pasokan_kg": _num(data.get("supply_kg")),
        "permintaan_kg": _num(data.get("demand_kg")),
        "surplus_kg": _num(data.get("surplus_kg")),
        "kekurangan_kg": _num(data.get("shortage_kg")),
        "status": data.get("status"),
        "keadaan_data": data.get("data_state"),
        "sumber": path,
    }


def get_safety_freshness(location: str, commodity: str | None = None) -> dict:
    """Ringkas keamanan dan kesegaran batch di satu lokasi (opsional per komoditas).

    Args:
        location: Nama lokasi, mis. "Jakarta".
        commodity: Nama komoditas; kosongkan untuk semua komoditas di lokasi itu.
    """
    data = _request("/batches")
    batches = data.get("batches") or []
    if not isinstance(batches, list):
        raise ToolError("respons /batches tidak memuat daftar 'batches'")

    lokasi = location.strip().lower()
    komoditas = (commodity or "").strip().lower()
    dipilih = [
        b
        for b in batches
        if str(b.get("location", "")).strip().lower() == lokasi
        and (not komoditas or str(b.get("commodity", "")).strip().lower() == komoditas)
    ]

    hitung: dict[str, int] = {}
    total_kg = 0.0
    freshness: list[float] = []
    kedaluwarsa_48 = 0
    batas = datetime.now(timezone.utc) + timedelta(hours=48)
    for b in dipilih:
        status = str(b.get("safety_status") or "tidak_diketahui")
        hitung[status] = hitung.get(status, 0) + 1
        total_kg += _num(b.get("quantity_kg")) or 0.0
        skor = _num(b.get("freshness_score"))
        if skor is not None:
            freshness.append(skor)
        usable = b.get("usable_until")
        if isinstance(usable, str):
            try:
                if datetime.fromisoformat(usable) <= batas:
                    kedaluwarsa_48 += 1
            except ValueError:
                pass

    terburuk = sorted(
        dipilih,
        key=lambda b: (_num(b.get("freshness_score")) is None,
                       _num(b.get("freshness_score")) or 1.0),
    )[:5]
    return {
        "lokasi": location,
        "komoditas": commodity,
        "jumlah_batch": len(dipilih),
        "status_keamanan": hitung,
        "ada_yang_gagal": hitung.get("fail", 0) > 0,
        "kesegaran_terburuk": min(freshness) if freshness else None,
        "batch_kedaluwarsa_48_jam": kedaluwarsa_48,
        "total_kg": round(total_kg, 2),
        "batch_terburuk": [
            {
                "id": b.get("id"),
                "komoditas": b.get("commodity"),
                "kg": _num(b.get("quantity_kg")),
                "keamanan": b.get("safety_status"),
                "kesegaran": _num(b.get("freshness_score")),
                "layak_sampai": b.get("usable_until"),
            }
            for b in terburuk
        ],
        "sumber": "/batches",
    }


def get_cost_eligibility(decision_id: str) -> dict:
    """Ambil Safe Delivered Cost, rincian biaya, pemasok, dan kelayakan keputusan.

    Args:
        decision_id: UUID keputusan yang sedang diperiksa.
    """
    path = f"/decisions/{urllib.parse.quote(decision_id, safe='')}/approval-summary"
    data = _request(path)
    safety = data.get("safety") or {}
    verifier = data.get("verifier") or {}
    supplier = data.get("supplier") or {}
    return {
        "decision_id": data.get("decision_id", decision_id),
        "jenis": data.get("decision_type"),
        "status": data.get("status"),
        "dari": data.get("source_location"),
        "ke": data.get("target_location"),
        "komoditas": data.get("commodity"),
        "kuantitas_kg": _num(data.get("quantity_kg")),
        "safe_delivered_cost": _num(data.get("safe_delivered_cost")),
        "rincian_biaya": data.get("cost_breakdown"),
        "supplier": supplier.get("name"),
        "keandalan_supplier": _num(supplier.get("reliability_score")),
        "safety_terburuk": safety.get("worst_status"),
        "safety_blocked": safety.get("blocked"),
        "verdict_verifier": verifier.get("verdict"),
        "can_execute": data.get("can_execute"),
        "alasan_tertahan": data.get("blocking_reasons") or [],
        "sumber": path,
    }


def get_evidence_digest(decision_id: str) -> dict:
    """Ringkas jejak langkah dan tanda tangan bukti satu keputusan.

    Args:
        decision_id: UUID keputusan yang sedang diperiksa.
    """
    did = urllib.parse.quote(decision_id, safe="")
    traces = _request(f"/decisions/{did}/traces")
    dossier = _request(f"/decisions/{did}/dossier")
    steps = traces.get("steps") or []
    signature = dossier.get("signature") or {}
    return {
        "decision_id": decision_id,
        "jumlah_langkah": len(steps) if isinstance(steps, list) else 0,
        "langkah": [
            s.get("step_name") for s in steps if isinstance(s, dict)
        ],
        "alat": [
            s.get("tool_called") for s in steps if isinstance(s, dict)
        ],
        "waktu_langkah": [
            s.get("step_at") for s in steps if isinstance(s, dict)
        ],
        "alamat_konten": dossier.get("content_address"),
        "tanda_tangan": signature.get("state"),
        "algoritma": signature.get("algorithm"),
        "verifikasi_tanda_tangan": dossier.get("verify"),
        "sumber": f"/decisions/{decision_id}/traces + /decisions/{decision_id}/dossier",
    }
