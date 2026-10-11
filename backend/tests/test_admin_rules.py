"""Tes aturan admin (S4-11) — murni, tanpa DB/HTTP."""

from __future__ import annotations

import pytest

from app.core.admin_rules import (
    UNSET,
    AdminRuleError,
    resolve_location_update,
    resolve_user_update,
)


def test_peran_sppg_wajib_punya_lokasi():
    with pytest.raises(AdminRuleError) as exc:
        resolve_user_update(
            current_role="sppg_head", current_location_id="loc-1", location_id=None
        )
    assert "location_id" in str(exc.value)


def test_naikkan_peran_ke_monitor_melepas_lokasi():
    role, loc = resolve_user_update(
        current_role="sppg_head", current_location_id="loc-1", role="bgn_monitor"
    )
    assert role == "bgn_monitor"
    assert loc is None


def test_monitor_tidak_boleh_diberi_lokasi():
    with pytest.raises(AdminRuleError):
        resolve_user_update(
            current_role="bgn_monitor",
            current_location_id=None,
            role="bgn_monitor",
            location_id="loc-1",
        )


def test_tanpa_peran_baru_lokasi_lama_dipertahankan():
    role, loc = resolve_user_update(
        current_role="sppg_head", current_location_id="loc-1"
    )
    assert (role, loc) == ("sppg_head", "loc-1")


def test_pindah_lokasi_diterima():
    role, loc = resolve_user_update(
        current_role="sppg_nutritionist", current_location_id="loc-1", location_id="loc-2"
    )
    assert (role, loc) == ("sppg_nutritionist", "loc-2")


def test_lokasi_tidak_ada_ditolak():
    with pytest.raises(AdminRuleError):
        resolve_user_update(
            current_role="sppg_head",
            current_location_id="loc-1",
            location_id="loc-hantu",
            location_exists=False,
        )


def test_role_tak_dikenal_ditolak():
    with pytest.raises(AdminRuleError):
        resolve_user_update(
            current_role="sppg_head", current_location_id="loc-1", role="admin"
        )


def test_perubahan_lokasi_hanya_field_terkirim():
    assert resolve_location_update(name="  SPPG Baru  ") == {"name": "SPPG Baru"}
    assert resolve_location_update(latitude=-6.2, longitude=106.8) == {
        "latitude": -6.2,
        "longitude": 106.8,
    }


def test_perubahan_lokasi_tidak_valid_ditolak():
    with pytest.raises(AdminRuleError):
        resolve_location_update(name="   ")
    with pytest.raises(AdminRuleError):
        resolve_location_update(latitude=91.0)
    with pytest.raises(AdminRuleError):
        resolve_location_update(longitude=-200.0)
    with pytest.raises(AdminRuleError):
        resolve_location_update()
