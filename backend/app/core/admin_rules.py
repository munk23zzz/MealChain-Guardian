"""Aturan admin (S4-11) — MURNI, tanpa DB/HTTP.

Dipakai endpoint `/admin/*` di `app/api/admin.py`. Aturan ini MENCERMINKAN
CHECK constraint DB (`app/models/users.py`) supaya pesan errornya jelas sebelum
Postgres menolak:

    (role IN ('sppg_head','sppg_nutritionist') AND location_id IS NOT NULL)
    OR (role = 'bgn_monitor' AND location_id IS NULL)

Keputusan yang diambil sadar (dan bisa diubah kalau pemilik proyek menambah
peran baru): **tidak ada peran `admin`** di skema (Schema.md §1: 3 peran final),
jadi pengelolaan pengguna/lokasi diberikan ke `bgn_monitor` — satu-satunya peran
nasional yang memang tidak terikat satu lokasi. `sppg_*` TIDAK boleh mengubah
data pengguna/lokasi.
"""

from __future__ import annotations

from typing import Any

VALID_ROLES = ("sppg_head", "sppg_nutritionist", "bgn_monitor")
SPPG_ROLES = ("sppg_head", "sppg_nutritionist")
MONITOR_ROLE = "bgn_monitor"

UNSET = object()


class AdminRuleError(ValueError):
    """Pelanggaran aturan admin (dipetakan ke HTTP 422 oleh lapisan API)."""


def resolve_user_update(
    *,
    current_role: str,
    current_location_id: str | None,
    role: str | None = None,
    location_id: Any = UNSET,
    location_exists: bool | None = None,
) -> tuple[str, str | None]:
    """Hitung (role, location_id) yang SAH untuk sebuah perubahan pengguna.

    - `role` None → peran lama dipertahankan.
    - `location_id` UNSET → lokasi lama dipertahankan (kecuali peran jadi
      monitor: lokasi dipaksa NULL mengikuti kontrak DB).
    - Lokasi yang tidak ada (`location_exists=False`) ditolak — jangan simpan
      FK yang menggantung.
    """
    efektif = (role or current_role or "").strip()
    if efektif not in VALID_ROLES:
        raise AdminRuleError(f"role tidak dikenal: {role!r}")

    if efektif == MONITOR_ROLE:
        if location_id is not UNSET and location_id is not None:
            raise AdminRuleError(
                "bgn_monitor tidak boleh terikat satu lokasi (location_id harus null)"
            )
        return efektif, None

    target = current_location_id if location_id is UNSET else location_id
    if target is None or not str(target).strip():
        raise AdminRuleError(f"{efektif} wajib punya location_id")
    if location_id is not UNSET and location_exists is False:
        raise AdminRuleError("lokasi tidak ditemukan")
    return efektif, str(target).strip()


def resolve_location_update(
    *,
    name: str | None = None,
    region: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:
    """Validasi perubahan lokasi; hanya field yang DIKIRIM yang dikembalikan.

    Tidak ada penghapusan lokasi di endpoint admin (lokasi dipakai keputusan &
    batch historis) — jadi tidak ada jalur yang bisa merusak integritas.
    """
    perubahan: dict[str, Any] = {}
    if name is not None:
        bersih = name.strip()
        if not bersih:
            raise AdminRuleError("nama lokasi tidak boleh kosong")
        perubahan["name"] = bersih
    if region is not None:
        bersih = region.strip()
        if not bersih:
            raise AdminRuleError("wilayah tidak boleh kosong")
        perubahan["region"] = bersih
    if latitude is not None:
        if not -90.0 <= float(latitude) <= 90.0:
            raise AdminRuleError("latitude di luar rentang -90..90")
        perubahan["latitude"] = float(latitude)
    if longitude is not None:
        if not -180.0 <= float(longitude) <= 180.0:
            raise AdminRuleError("longitude di luar rentang -180..180")
        perubahan["longitude"] = float(longitude)
    if not perubahan:
        raise AdminRuleError("tidak ada field yang diubah")
    return perubahan
