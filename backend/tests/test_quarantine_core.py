"""Karantina batch — mesin status deterministik (kontrol proposal §kewenangan agent).

Karantina berarti batch DITAHAN dari kandidat alokasi sampai manusia memverifikasi.
Agent hanya boleh mengusulkan; melepas atau menyatakan gagal adalah aksi manusia.
"""

import pytest

from app.core.quarantine import (
    AKSI_GAGAL,
    AKSI_LEPAS,
    AKSI_TAHAN,
    FAILED,
    NONE,
    QUARANTINED,
    RELEASED,
    boleh_ditahan,
    status_setelah,
)


class TestTransisi:
    def test_batch_belum_karantina_ditahan(self):
        assert status_setelah(NONE, AKSI_TAHAN) == QUARANTINED

    def test_batch_karantina_dilepas_kembali_ke_pool(self):
        assert status_setelah(QUARANTINED, AKSI_LEPAS) == RELEASED

    def test_batch_karantina_dinyatakan_gagal(self):
        assert status_setelah(QUARANTINED, AKSI_GAGAL) == FAILED

    def test_batch_yang_sudah_dilepas_boleh_ditahan_lagi(self):
        # Kejadian baru atas batch yang sama harus bisa ditahan ulang.
        assert status_setelah(RELEASED, AKSI_TAHAN) == QUARANTINED

    def test_batch_yang_sudah_gagal_tidak_bisa_kembali(self):
        for aksi in (AKSI_TAHAN, AKSI_LEPAS, AKSI_GAGAL):
            with pytest.raises(ValueError):
                status_setelah(FAILED, aksi)

    def test_menahan_batch_yang_sudah_ditahan_ditolak(self):
        # Idempoten bukan berarti sah: user harus tahu statusnya sudah ditahan.
        with pytest.raises(ValueError):
            status_setelah(QUARANTINED, AKSI_TAHAN)

    def test_melepas_batch_yang_tidak_ditahan_ditolak(self):
        for status in (NONE, RELEASED):
            with pytest.raises(ValueError):
                status_setelah(status, AKSI_LEPAS)

    def test_status_tak_dikenal_ditolak(self):
        with pytest.raises(ValueError):
            status_setelah("hilang", AKSI_TAHAN)
        with pytest.raises(ValueError):
            status_setelah(NONE, "bakar")


class TestKelayakanDitahan:
    def test_batch_needs_verification_boleh_ditahan(self):
        assert boleh_ditahan("needs_verification") == (True, "")

    def test_batch_pass_boleh_ditahan_bila_ada_kejadian_baru(self):
        assert boleh_ditahan("pass") == (True, "")

    def test_batch_fail_tidak_perlu_ditahan(self):
        ok, alasan = boleh_ditahan("fail")
        assert ok is False
        assert "fail" in alasan

    def test_status_tak_dikenal_ditolak(self):
        with pytest.raises(ValueError):
            boleh_ditahan("entah")
