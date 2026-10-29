"""KPI cakupan "Simulasi" harus memuat data CETAKAN (template), bukan hanya sesi operator.

Kenapa ada (demo 29 Okt 2026): template demo disimpan berstempel sesi sentinel
`cetakan` (`demo_session.CETAKAN_ID`) supaya "Akhiri sesi" tidak menghapusnya.
Akibatnya cakupan Simulasi — yang dikirim UI dengan id sesi OPERATOR — tidak
memuat satu pun fakta template: terukur 0/7 metrik di ketiga jendela (hari ini,
7 hari, 1 bulan) sesaat setelah "Siapkan data demo", padahal 43 keputusan demo,
5 penerimaan, dan 2 eksklusi ada di DB.

Kontrak sekarang: cakupan simulasi = cetakan (template beku) + baris sesi
operator (adonan). Cakupan operasional TETAP tidak memuat keduanya.
"""

from __future__ import annotations

import pytest

from app.services.demo_session import CETAKAN_ID, cetakan
from app.services.kpi_service import compute_kpis
from tests.test_kpi_penerimaan_scope import (
    AKHIR,
    AWAL,
    _batch_dan_penerimaan,
    _bersihkan,
    _jalankan,
    _metrik,
    _sesi_demo,
)


def test_cakupan_simulasi_memuat_cetakan():
    """Fakta template berstempel `cetakan` WAJIB terhitung di cakupan simulasi."""

    async def _skenario(db):
        await cetakan(db)  # pastikan baris sesi sentinel ada (FK)
        sesi_operator = await _sesi_demo(db)  # sesi ini sendiri tidak punya fakta
        batch = await _batch_dan_penerimaan(
            db,
            sesi=CETAKAN_ID,
            pesanan_kg=600,
            timbangan_kg=None,
        )
        await db.commit()
        try:
            simulasi = _metrik(
                await compute_kpis(
                    db,
                    AWAL,
                    AKHIR,
                    None,
                    include_demo=True,
                    demo_session_id=sesi_operator,
                )
            )
            operasional = _metrik(
                await compute_kpis(db, AWAL, AKHIR, None, include_demo=False)
            )
            return simulasi, operasional
        finally:
            await _bersihkan(db, batch)

    simulasi, operasional = _jalankan(_skenario)
    est = simulasi["Meal Continuity Rate"]["estimate"]
    assert est["state"] == "available", est
    assert float(est["value"]) == pytest.approx(6000.0), est
    # Template bukan fakta lapangan: cakupan operasional tetap kosong.
    assert operasional["Meal Continuity Rate"]["estimate"]["state"] == "no_data"
