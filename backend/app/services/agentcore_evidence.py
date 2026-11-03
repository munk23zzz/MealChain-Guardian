"""Bukti AgentCore sebagai status TERPISAH (Fase 11 MG butir 4-6).

Masalah yang dicegah berkas ini: satu kata "DONE" untuk empat hal berbeda.
`resource_exists`, `target_ready`, `tool_invoked`, dan `app_uses_gateway`
punya cara ukur sendiri; hanya `resource_exists` yang bisa dibuktikan dengan
konfigurasi + panggilan baca. `tool_invoked` menuntut satu pemanggilan nyata
yang hasilnya dibaca aplikasi, dan `app_uses_gateway` menuntut aplikasi
benar-benar memakai Gateway itu (bukan hanya env yang terisi).

Aturan status:
- `VERIFIED`          ada operasi nyata yang berhasil dan hasilnya dibaca;
- `UNVERIFIED`        belum bisa dibuktikan (termasuk AccessDenied — izin
                      belum ada; ini BUKAN `FAIL` dan BUKAN `WORKING`);
- `NOT_CONFIGURED`    fitur memang tidak diaktifkan.

Sumber tunggal kebenaran untuk `scripts/probe_agentcore_gateway.py` dan
`tests/test_agentcore_live_smoke.py`.
"""

from __future__ import annotations

from typing import Any, Iterable

STATUS_OK = "VERIFIED"
STATUS_UNVERIFIED = "UNVERIFIED"
STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"
# AccessDeniedException = izin belum ada → UNVERIFIED, bukan kegagalan produk.
STATUS_DENIED = STATUS_UNVERIFIED

STATUS_VOCAB = (STATUS_OK, STATUS_UNVERIFIED, STATUS_NOT_CONFIGURED)

GATEWAY_PROOFS: tuple[str, ...] = (
    "resource_exists",
    "target_ready",
    "tool_invoked",
    "app_uses_gateway",
)

MEMORY_PROOFS: tuple[str, ...] = (
    "resource_exists",
    "read_allowed",
    "write_allowed",
)


def error_code(exc: BaseException) -> str:
    """Kode error boto3 (`AccessDeniedException`, …) atau nama kelasnya."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        kode = (response.get("Error") or {}).get("Code")
        if kode:
            return str(kode)
    return type(exc).__name__


def status_from_error(exc: BaseException) -> str:
    """Petakan error cloud ke status bukti.

    AccessDenied → `UNVERIFIED` (izin belum ada; jangan ditandai `FAIL` atau
    `WORKING`). Error lain juga `UNVERIFIED` karena tidak ada bukti positif.
    """
    return STATUS_DENIED if "AccessDenied" in error_code(exc) else STATUS_UNVERIFIED


def app_uses_gateway(url: str | None) -> dict:
    """Bukti keempat: aplikasi memakai Gateway, bukan sekadar env terisi."""
    if (url or "").strip():
        return {
            "status": STATUS_UNVERIFIED,
            "detail": "AGENTCORE_GATEWAY_URL terisi; pemakaian nyata belum dibuktikan "
            "(butuh satu tool dipanggil lewat aplikasi dan hasilnya dibaca)",
        }
    return {
        "status": STATUS_NOT_CONFIGURED,
        "detail": "AGENTCORE_GATEWAY_URL kosong — aplikasi tidak memakai Gateway, "
        "jangan menandai integrasi ini DONE",
    }


def ringkas(proofs: dict, nama: Iterable[str] = GATEWAY_PROOFS) -> dict:
    """Ringkasan per-bukti; `integrasi_aktif` hanya bila SEMUA bukti VERIFIED."""
    per_bukti: dict[str, str] = {}
    for kunci in nama:
        entri = proofs.get(kunci) or {}
        status = entri.get("status") or STATUS_UNVERIFIED
        per_bukti[kunci] = status

    hitung: dict[str, int] = {}
    for status in per_bukti.values():
        hitung[status] = hitung.get(status, 0) + 1

    belum = [kunci for kunci, status in per_bukti.items() if status != STATUS_OK]
    return {
        "per_bukti": per_bukti,
        "hitung": hitung,
        "belum_terbukti": belum,
        "integrasi_aktif": not belum,
    }


def bukti_valid(proofs: dict, nama: Iterable[str] = GATEWAY_PROOFS) -> list[str]:
    """Nama bukti yang statusnya di luar kosakata yang diizinkan (harus kosong)."""
    salah = []
    for kunci in nama:
        status = (proofs.get(kunci) or {}).get("status")
        if status not in STATUS_VOCAB:
            salah.append(f"{kunci}={status!r}")
    return salah


def sanitasi_terbukti(payload: Any, kata_terlarang: Iterable[str]) -> bool:
    """True bila tidak ada kata terlarang (secret) di payload yang akan dikirim."""
    teks = repr(payload).lower()
    return not any(kata.lower() in teks for kata in kata_terlarang)
