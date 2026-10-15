"""Unit test helper cakupan lokasi (Ruling 2026-10-14).

Murni — tanpa DB, tanpa HTTP: user cukup objek dengan `role`/`location_id`.
Yang diuji adalah aturan, bukan tata letak kode:
- peran SPPG tanpa lokasi = gagal-tertutup (403), bukan "lihat semua";
- `bgn_monitor` = tanpa batas;
- target di luar cakupan = 403, dan pesannya menyebut SPPG Anda;
- `apply_location_scope` benar-benar menambahkan klausa WHERE (bukan hanya
  terlihat seperti menambahkan) dan tidak menyaring apa pun untuk nasional.
"""

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.scope import (
    apply_location_scope,
    assert_in_scope,
    in_scope,
    is_national_scope,
    scope_location_id,
)
from app.models import Decision

JAKARTA = uuid.UUID("11111111-1111-1111-1111-111111111111")
BANDUNG = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _user(role: str, location_id=JAKARTA):
    return SimpleNamespace(role=role, location_id=location_id)


def test_scope_location_id_sppg_memakai_lokasinya():
    assert scope_location_id(_user("sppg_head")) == JAKARTA
    assert scope_location_id(_user("sppg_nutritionist")) == JAKARTA


def test_scope_location_id_monitor_tanpa_batas():
    assert scope_location_id(_user("bgn_monitor", None)) is None
    assert is_national_scope(_user("bgn_monitor", None)) is True
    assert is_national_scope(_user("sppg_head")) is False


def test_scope_location_id_sppg_tanpa_lokasi_gagal_tertutup():
    with pytest.raises(HTTPException) as exc:
        scope_location_id(_user("sppg_head", None))
    assert exc.value.status_code == 403
    assert "belum terikat lokasi" in exc.value.detail


def test_in_scope_target_sendiri_true_asing_false():
    user = _user("sppg_head")
    assert in_scope(user, JAKARTA) is True
    assert in_scope(user, BANDUNG) is False
    # target NULL bukan milik siapa pun → tidak boleh terlihat
    assert in_scope(user, None) is False


def test_in_scope_monitor_selalu_true():
    user = _user("bgn_monitor", None)
    assert in_scope(user, JAKARTA) is True
    assert in_scope(user, BANDUNG) is True
    assert in_scope(user, None) is True


def test_assert_in_scope_melempar_403_dengan_pesan_jelas():
    user = _user("sppg_head")
    assert_in_scope(user, JAKARTA)  # tidak melempar
    with pytest.raises(HTTPException) as exc:
        assert_in_scope(user, BANDUNG, what="keputusan")
    assert exc.value.status_code == 403
    assert exc.value.detail == "keputusan di cakupan lokasi di luar SPPG Anda"


def test_assert_in_scope_monitor_tidak_pernah_melempar():
    assert_in_scope(_user("bgn_monitor", None), BANDUNG)
    assert_in_scope(_user("bgn_monitor", None), None)


def test_apply_location_scope_menambah_where_untuk_sppg():
    stmt = apply_location_scope(select(Decision), Decision.target_location_id, _user("sppg_head"))
    sql = str(stmt)
    assert "WHERE" in sql.upper()
    assert "target_location_id" in sql
    # parameter lokasi benar-benar terikat (bukan klausa kosong)
    assert [str(v) for v in stmt.compile().params.values()] == [str(JAKARTA)]


def test_apply_location_scope_tanpa_filter_untuk_monitor():
    stmt = apply_location_scope(
        select(Decision), Decision.target_location_id, _user("bgn_monitor", None)
    )
    assert "WHERE" not in str(stmt).upper()


def test_apply_location_scope_sppg_tanpa_lokasi_melempar_403():
    with pytest.raises(HTTPException) as exc:
        apply_location_scope(
            select(Decision), Decision.target_location_id, _user("sppg_head", None)
        )
    assert exc.value.status_code == 403
