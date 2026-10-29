"""Dossier harus membawa BUKTI, bukan hanya tanda tangan (audit 29 Okt 2026).

Panel "Bukti kepatuhan tersimpan" menghitung dari `dossier.evidence`, tetapi
endpoint hanya mengirim empat kunci (decision_id, content_address, signature,
verify). Akibatnya panel selalu menulis "Lolos 0 · Gagal 0 · Perlu verifikasi 0
— Belum ada bukti pengukuran" walaupun tabel decision_evidence berisi 61 baris
untuk 44 keputusan.
"""

import pytest

from tests.dsn import DSN_SYNC


def test_dossier_membawa_baris_bukti(auth_headers):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text

    from app.main import app

    eng = create_engine(DSN_SYNC)
    try:
        with TestClient(app) as c:
            me = c.get("/auth/me", headers=auth_headers).json()
            loc_id = me.get("location_id")
            if not loc_id:
                pytest.skip("user fixture tanpa lokasi")
            with eng.begin() as conn:
                row = conn.execute(
                    text(
                        "SELECT d.id, count(e.id) AS n FROM decisions d "
                        "JOIN decision_evidence e ON e.decision_id = d.id "
                        "WHERE d.target_location_id = :loc GROUP BY d.id "
                        "ORDER BY n DESC LIMIT 1"
                    ),
                    {"loc": loc_id},
                ).fetchone()
            if not row:
                pytest.skip("tidak ada keputusan berbukti dalam cakupan user")

            r = c.get(f"/decisions/{row[0]}/dossier", headers=auth_headers)
            assert r.status_code == 200, r.text
            data = r.json()
            assert isinstance(data.get("evidence"), list), data.keys()
            assert len(data["evidence"]) == row[1]
            contoh = data["evidence"][0]
            for kunci in ("id", "evidence_type", "payload", "recorded_at"):
                assert kunci in contoh, kunci
            # address tetap konten-addressed dan stabil antar panggilan
            assert data["content_address"].startswith("mc1-")
            r2 = c.get(f"/decisions/{row[0]}/dossier", headers=auth_headers)
            assert r2.json()["content_address"] == data["content_address"]
    finally:
        eng.dispose()
