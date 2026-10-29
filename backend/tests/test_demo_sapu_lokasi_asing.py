"""Residu uji berbentuk LOKASI tidak boleh masuk jaringan demo (29 Okt 2026).

Konteks temuan: `tests/test_approval_summary_receipt_gate.py` membuat lokasi
`F9-tgt-…`, pemasok `F9-sup-…`, dan akun `f9.*@uji-f9.local`. Teardown-nya tidak
sempat jalan (proses uji terhenti), dan karena tiga hal berikut residunya naik ke
layar demo:

1. pembersih akun uji hanya mengenal pola `@test.local` / `@uji-peran.local`;
2. langkah penyemai demo menganggap "lokasi yang punya user" = kota SPPG, lalu
   menaruh 5 batch (2.900 kg) di hub itu;
3. tidak ada yang menyapu lokasi di luar snapshot kanonik.

Akibat terukur di UI: pemilih cakupan BGN menulis "11 lokasi" (harusnya 10),
daftar pemasok 61 (harusnya 60) dengan satu baris "F9-sup-…" tanpa komoditas dan
sertifikasi, dan papan kiriman nasional 130 (harusnya 125).

Berkas ini mengunci perbaikannya: saringan kota demo, sapuan lokasi asing, dan
aturan "batch yang dirujuk bukti tidak boleh dihapus".
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

try:
    from sqlalchemy import text

    from app.core.config import settings
    from app.db import create_engine, create_session_maker
    from app.seed.demo_template import _sapu_lokasi_asing, pilih_kota_demo
    from app.seed.seed_data import nama_lokasi_kanonik
except Exception:  # pragma: no cover - guard impor
    text = None


def _url() -> str:
    return settings.database_url


def test_daftar_lokasi_kanonik_tanpa_residu_uji() -> None:
    """Snapshot kanonik = daftar SPPG yang sah; nama residu uji tidak ada di sana."""
    kanonik = nama_lokasi_kanonik()
    assert "Jakarta" in kanonik
    assert len(kanonik) == 10, sorted(kanonik)
    assert not [nama for nama in kanonik if nama.startswith("F9")], sorted(kanonik)
    assert not [nama for nama in kanonik if "uji" in nama.lower()], sorted(kanonik)


def test_kota_demo_harus_kanonik_dan_punya_akun() -> None:
    """Saring ganda: lokasi asing dengan akun uji TIDAK ikut disemai demo."""
    jakarta = SimpleNamespace(id=uuid.uuid4(), name="Jakarta")
    bandung = SimpleNamespace(id=uuid.uuid4(), name="Bandung")
    f9 = SimpleNamespace(id=uuid.uuid4(), name="F9-tgt-d8ec4354")
    # Cianjur punya pemasok tapi tidak punya akun SPPG demo → tidak ikut.
    cianjur = SimpleNamespace(id=uuid.uuid4(), name="Cianjur")

    dipilih = pilih_kota_demo(
        [jakarta, bandung, f9, cianjur],
        {jakarta.id, f9.id},
        nama_lokasi_kanonik(),
    )

    assert dipilih == {jakarta.id: "Jakarta"}
    assert f9.id not in dipilih, "lokasi residu uji tidak boleh jadi kota demo"


@pytest.mark.asyncio
@pytest.mark.skipif(text is None, reason="app/sqlalchemy tidak tersedia")
async def test_sapuan_menghapus_lokasi_asing_dan_akun_ujinya() -> None:
    """Lokasi asing + pemasok + akun + batch-nya hilang; lokasi kanonik utuh."""
    akhiran = uuid.uuid4().hex[:8]
    nama_lokasi = f"F9-tgt-{akhiran}"
    nama_pemasok = f"F9-sup-{akhiran}"
    id_lokasi = uuid.uuid4()
    id_pemasok = uuid.uuid4()
    id_user = uuid.uuid4()
    id_batch = uuid.uuid4()
    email = f"f9.sppg_head-{akhiran}@uji-{akhiran}.local"

    eng = create_engine(_url())
    try:
        async with eng.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO locations (id, name, region, latitude, longitude, "
                    "role_hint) VALUES (:l, :n, 'Uji F9', -6.2, 106.8, '')"
                ),
                {"l": id_lokasi, "n": nama_lokasi},
            )
            await conn.execute(
                text(
                    "INSERT INTO suppliers (id, name, location_id, reliability_score, "
                    "certification_status) VALUES (:s, :n, :l, 0.8, NULL)"
                ),
                {"s": id_pemasok, "n": nama_pemasok, "l": id_lokasi},
            )
            await conn.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, role, name, location_id) "
                    "VALUES (:u, :e, 'x', 'sppg_head', 'Uji F9', :l)"
                ),
                {"u": id_user, "e": email, "l": id_lokasi},
            )
            await conn.execute(
                text(
                    "INSERT INTO batches (id, location_id, supplier_id, commodity_id, "
                    "quantity_kg, harvested_at, usable_until, certification_status, "
                    "freshness_score, safety_status, origin, generated_at) "
                    "SELECT :b, :l, :s, id, 100, now(), now() + interval '10 days', "
                    "'none', 0.9, 'pass', 'demo', now() FROM commodities LIMIT 1"
                ),
                {"b": id_batch, "l": id_lokasi, "s": id_pemasok},
            )

        maker = create_session_maker(eng)
        async with maker() as ses:
            laporan = await _sapu_lokasi_asing(ses)
            await ses.commit()

        assert laporan["lokasi_asing_dihapus"] >= 1, laporan
        assert laporan["pemasok_asing_dihapus"] >= 1, laporan
        assert laporan["batch_asing_dihapus"] >= 1, laporan

        async with eng.connect() as conn:
            for tabel, kolom, nilai in (
                ("locations", "id", id_lokasi),
                ("suppliers", "id", id_pemasok),
                ("users", "id", id_user),
                ("batches", "id", id_batch),
            ):
                ada = (
                    await conn.execute(
                        text(f"SELECT count(*) FROM {tabel} WHERE {kolom} = :v"),
                        {"v": nilai},
                    )
                ).scalar_one()
                assert ada == 0, f"{tabel} menyisakan residu"

            # Kontrol positif: lokasi kanonik tidak ikut tersapu.
            jakarta = (
                await conn.execute(
                    text("SELECT count(*) FROM locations WHERE name = 'Jakarta'")
                )
            ).scalar_one()
            assert jakarta == 1
    finally:
        async with eng.begin() as conn:
            # Jaring pengaman bila asersi gagal di tengah: bersihkan dengan urutan FK.
            await conn.execute(
                text("DELETE FROM batches WHERE location_id = :l"), {"l": id_lokasi}
            )
            await conn.execute(
                text("DELETE FROM users WHERE location_id = :l"), {"l": id_lokasi}
            )
            await conn.execute(
                text("DELETE FROM suppliers WHERE location_id = :l"), {"l": id_lokasi}
            )
            await conn.execute(text("DELETE FROM locations WHERE id = :l"), {"l": id_lokasi})
        await eng.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(text is None, reason="app/sqlalchemy tidak tersedia")
async def test_batch_yang_dirujuk_bukti_tidak_dihapus() -> None:
    """Rantai bukti tidak boleh putus: batch di lokasi asing yang disebut
    `decision_evidence.payload` dipertahankan, dan lokasinya dilaporkan."""
    akhiran = uuid.uuid4().hex[:8]
    id_lokasi = uuid.uuid4()
    id_pemasok = uuid.uuid4()
    id_batch = uuid.uuid4()
    id_keputusan = uuid.uuid4()
    komoditas = None

    eng = create_engine(_url())
    try:
        async with eng.begin() as conn:
            komoditas = (
                await conn.execute(text("SELECT id FROM commodities LIMIT 1"))
            ).scalar_one()
            await conn.execute(
                text(
                    "INSERT INTO locations (id, name, region, latitude, longitude, "
                    "role_hint) VALUES (:l, :n, 'Uji F9', -6.2, 106.8, '')"
                ),
                {"l": id_lokasi, "n": f"F9-tgt-{akhiran}"},
            )
            await conn.execute(
                text(
                    "INSERT INTO suppliers (id, name, location_id, reliability_score) "
                    "VALUES (:s, :n, :l, 0.8)"
                ),
                {"s": id_pemasok, "n": f"F9-sup-{akhiran}", "l": id_lokasi},
            )
            await conn.execute(
                text(
                    "INSERT INTO batches (id, location_id, supplier_id, commodity_id, "
                    "quantity_kg, harvested_at, usable_until, certification_status, "
                    "freshness_score, safety_status, origin, generated_at) "
                    "VALUES (:b, :l, :s, :c, 100, now(), now() + interval '10 days', "
                    "'none', 0.9, 'pass', 'demo', now())"
                ),
                {"b": id_batch, "l": id_lokasi, "s": id_pemasok, "c": komoditas},
            )
            await conn.execute(
                text(
                    "INSERT INTO decisions (id, commodity_id, source_location_id, "
                    "target_location_id, supplier_id, decision_type, status, "
                    "quantity_kg, created_at, expires_at) "
                    "VALUES (:d, :c, :l, :l, :s, 'supplier_procurement', 'proposed', 100, now(), "
                    "now() + interval '1 day')"
                ),
                {"d": id_keputusan, "c": komoditas, "l": id_lokasi, "s": id_pemasok},
            )
            await conn.execute(
                text(
                    "INSERT INTO decision_evidence (decision_id, evidence_type, payload) "
                    "VALUES (:d, 'sap_goods_receipt', "
                    "jsonb_build_object('batch_ids', jsonb_build_array(CAST(:b AS text))))"
                ),
                {"d": id_keputusan, "b": str(id_batch)},
            )

        maker = create_session_maker(eng)
        async with maker() as ses:
            laporan = await _sapu_lokasi_asing(ses)
            await ses.commit()

        assert laporan["batch_asing_dipertahankan"] >= 1, laporan
        assert any("F9-tgt-" in baris for baris in laporan["lokasi_asing_dipertahankan"]), laporan

        async with eng.connect() as conn:
            ada = (
                await conn.execute(
                    text("SELECT count(*) FROM batches WHERE id = :b"), {"b": id_batch}
                )
            ).scalar_one()
            assert ada == 1, "batch yang dirujuk bukti dihapus — rantai bukti putus"
    finally:
        async with eng.begin() as conn:
            await conn.execute(
                text("DELETE FROM decision_evidence WHERE decision_id = :d"),
                {"d": id_keputusan},
            )
            await conn.execute(
                text("DELETE FROM decisions WHERE id = :d"), {"d": id_keputusan}
            )
            await conn.execute(
                text("DELETE FROM batches WHERE location_id = :l"), {"l": id_lokasi}
            )
            await conn.execute(
                text("DELETE FROM suppliers WHERE location_id = :l"), {"l": id_lokasi}
            )
            await conn.execute(text("DELETE FROM locations WHERE id = :l"), {"l": id_lokasi})
        await eng.dispose()
