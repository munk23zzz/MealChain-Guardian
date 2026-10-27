"""Batas suhu aman per komoditas dipakai SAFETY dan FRESHNESS.

Bug yang dikunci (20 Okt 2026): `/safety/evaluate` memakai `settings` 0–8 °C
untuk semua komoditas, sedangkan `/freshness/evaluate` sudah memakai 15–30 °C
untuk beras. Akibatnya mencatat penerimaan beras pada 27 °C langsung `fail` dan
tidak bisa disetujui. Sekarang keduanya memakai profil komoditas yang sama.

KONTRAK DIUBAH pada Fase 3 MG (27 Okt 2026) — bukan dilonggarkan:

- `safe_temp_for("beras")` kini **None**, bukan `(15, 30)`. Profil beras adalah
  `cold_chain_required=False`: komoditas ambient tidak diukur terhadap rentang
  sama sekali, karena rentang 15–30 °C masih menuduh suhu ruang 32 °C sebagai
  excursion padahal penyimpanannya benar. Rencana Fase 3, gerbang keluar:
  "Tidak ada rentang 0–8 °C universal" dan "Jika rentang min/max null untuk
  komoditas ambient, jangan mengukur excursion terhadap rentang tersebut".
- Komoditas tak dikenal **ditolak** (`KeyError`), bukan diberi bawaan 0–8 °C.
  Bawaan diam-diam itulah yang membuat setiap komoditas baru otomatis dianggap
  rantai dingin tanpa dasar.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.core.commodity_limits import cold_chain_required, safe_temp_for
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DSN_SYNC = DSN_SYNC


def test_peta_suhu_per_komoditas():
    # Rantai dingin: punya rentang.
    assert safe_temp_for("ayam") == (0.0, 8.0)
    assert safe_temp_for("telur") == (0.0, 8.0)
    assert safe_temp_for("wortel") == (0.0, 8.0)
    # Ambient: TIDAK diukur terhadap rentang (None), bukan rentang lebar.
    assert safe_temp_for("beras") is None
    assert cold_chain_required("beras") is False
    # Huruf besar/kecil tidak mengubah arti.
    assert safe_temp_for("AYAM") == (0.0, 8.0)
    assert safe_temp_for("Beras") is None


def test_komoditas_tak_dikenal_ditolak():
    """Tanpa profil, tidak ada rentang yang boleh dikarang."""
    with pytest.raises(KeyError):
        safe_temp_for("jagung")
    with pytest.raises(KeyError):
        safe_temp_for(None)


def test_beras_suhu_ruang_tidak_dinilai_gagal(auth_headers):
    """Batch beras dengan log 26–28 °C harus PASS, bukan FAIL."""
    import json
    from datetime import datetime, timedelta, timezone

    from fastapi.testclient import TestClient

    from app.main import app

    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            baris = conn.execute(
                text(
                    "SELECT b.id, b.safety_status, b.temperature_log FROM batches b "
                    "JOIN commodities c ON c.id = b.commodity_id "
                    "WHERE c.name = 'beras' ORDER BY b.quantity_kg DESC LIMIT 1"
                )
            ).one_or_none()
        if baris is None:
            return  # DB tanpa batch beras — tidak ada yang bisa dibuktikan.
        batch_id, semula, log_semula = str(baris[0]), baris[1], baris[2]
        # Log dibuat eksplisit: data seed bisa memakai kunci `at` (bukan
        # `timestamp`) sehingga evaluator menyebutnya "log tidak lengkap".
        awal = datetime.now(timezone.utc) - timedelta(hours=3)
        log = [
            {
                "timestamp": (awal + timedelta(minutes=30 * i)).isoformat(),
                "temperature_c": 27.0 + i / 10,
            }
            for i in range(3)
        ]
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE batches SET safety_status = 'fail', "
                    "temperature_log = CAST(:log AS jsonb) WHERE id = :i"
                ),
                {"log": json.dumps(log), "i": batch_id},
            )

        with TestClient(app) as c:
            resp = c.post(
                "/safety/evaluate",
                headers=auth_headers,
                json={"batch_id": batch_id},
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["safety_status"] == "PASS"
    finally:
        with engine.begin() as conn:
            if "batch_id" in locals():
                conn.execute(
                    text(
                        "UPDATE batches SET safety_status = :s, "
                        "temperature_log = CAST(:log AS jsonb) WHERE id = :i"
                    ),
                    {"s": semula, "log": json.dumps(log_semula), "i": batch_id},
                )
        engine.dispose()
