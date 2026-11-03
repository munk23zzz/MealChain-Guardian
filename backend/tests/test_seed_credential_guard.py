"""Guard kredensial demo (temuan D-01).

Kontrak: jalur seed TIDAK boleh memasang password default yang bisa ditebak
kecuali demonstrasi memang dinyalakan (`DEMO_MODE=true`) atau operator
menyuplai password sendiri lewat environment. Pada mesin produksi
(`DEMO_MODE` false/kosong) seed harus MENOLAK, bukan diam-diam memakai
password yang tertulis di repository.
"""

import pytest

from app.seed.demo_credentials import DemoCredentialError, resolve_demo_password


def test_tanpa_demo_mode_dan_tanpa_password_env_menolak():
    with pytest.raises(DemoCredentialError):
        resolve_demo_password("sppg_head", env={})


@pytest.mark.parametrize("nilai", ["false", "0", "no", ""])
def test_demo_mode_nonaktif_menolak(nilai):
    with pytest.raises(DemoCredentialError):
        resolve_demo_password("sppg_head", env={"DEMO_MODE": nilai})


def test_demo_mode_aktif_memakai_password_juri_yang_terdokumentasi():
    sandi = resolve_demo_password("sppg_head", env={"DEMO_MODE": "true"})
    sandi_gizi = resolve_demo_password("sppg_nutritionist", env={"DEMO_MODE": "true"})

    assert sandi and sandi_gizi
    assert sandi != sandi_gizi, "password tiap peran harus berbeda"


def test_password_dari_environment_dipakai_tanpa_demo_mode():
    sandi = resolve_demo_password(
        "bgn_monitor", env={"DEMO_PASSWORD_BGN_MONITOR": "S3cret-dari-env"}
    )
    assert sandi == "S3cret-dari-env"


def test_password_env_menang_atas_password_juri():
    sandi = resolve_demo_password(
        "sppg_head", env={"DEMO_MODE": "true", "DEMO_PASSWORD_SPPG_HEAD": "S3cret-dari-env"}
    )
    assert sandi == "S3cret-dari-env"


def test_peran_tidak_dikenal_ditolak():
    with pytest.raises(DemoCredentialError):
        resolve_demo_password("role_karangan", env={"DEMO_MODE": "true"})
