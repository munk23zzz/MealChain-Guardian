"""Kontrak mode + `evaluation_anchor` sesi demo (Fase 2 MG).

Yang dikunci berkas ini (rencana `MG/phase-02-session-time.md` butir 1–6):

1. **Mode eksplisit.** `POST /demo/seed` menerima `mode` (`replay`/`realtime`);
   nilai lain ditolak 422 oleh kontrak request, bukan diabaikan diam-diam.
2. **Anchor milik sesi, bukan tanggal global.** `replay` memakai jangkar kanon
   `2026-10-08T12:00:00+00:00`; `realtime` memakai waktu saat sesi dibuka dan
   `dataset_version` yang berbeda. Jangkar kanon tidak pernah digeser.
3. **Kepemilikan baris.** Setiap keputusan hasil `_seed_demo_cases()` membawa
   `demo_session_id` milik sesi yang memintanya — termasuk baris `rejected`
   (yang lahir lebih dulu di seeder).
4. **Dua sesi tidak saling menimpa.** Menyemai sesi kedua tidak mengubah
   kepemilikan baris sesi pertama, dan reset sesi pertama tidak menghapus
   keputusan/PO/kiriman/fakta sesi kedua.
5. **`decision_now()`**: anchor sesi bila ada relasinya termuat, jam dinding
   bila tidak ada sesi (tanpa lazy-load).
6. **`GET /demo/session`** memuat `mode`, `evaluation_anchor`,
   `dataset_version` (bentuk sama dengan blok `session` respons seed).

Catatan cakupan: `GET /kpi?demo_session=` (cakupan demo vs operasional pada
KPI) milik **Fase 8**, bukan fase ini — tidak diuji di sini.

Berkas ini MENULIS ke database (menyemai kasus demo, membuat sesi uji), jadi
jalankan pada DB sekali-pakai: `DATABASE_URL=.../<klon> pytest
tests/test_session_modes.py`. Setiap sesi/baris yang dibuat dibersihkan di
`finally`; sesi aktif milik operator tidak ditutup permanen (statusnya
dipulihkan).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.main import app
from app.models import Decision
from app.services import decision_time, demo_purge
from tests.dsn import DSN_ASYNC, DSN_SYNC

EMAIL = "sppg.head@demo.local"
PASSWORD = "Demo#SPPG2026"
REPLAY_ANCHOR = "2026-10-08T12:00:00+00:00"

KASUS_SKRIP = (
    "rejection-loop-kuota",
    "shortage-darurat",
    "supplier-janggal",
    "gangguan-logistik",
)


def _db():
    return create_engine(DSN_SYNC)


def _login(client) -> dict:
    resp = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _buat_sesi(
    *,
    mode: str,
    anchor: datetime | None = None,
    dataset_version: str | None = None,
    status: str = "ended",
) -> uuid.UUID:
    """Sisipkan satu baris `demo_sessions` uji (status bawaan `ended`).

    Status `ended` dipakai supaya tidak bentrok dengan indeks unik parsial
    `uq_demo_sessions_satu_aktif` milik sesi operator. Sesi `ended` tetap sah
    sebagai pemilik baris — kepemilikan tidak bergantung pada status.
    """
    sid = uuid.uuid4()
    saat = datetime.now(UTC)
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO demo_sessions "
                    "(id, status, started_at, expires_at, anchor_now, ended_at, "
                    " mode, evaluation_anchor, dataset_version, template_version) "
                    "VALUES (:id, :st, :saat, :exp, :saat, :saat, :mode, :anchor, "
                    " :ver, 'uji-fase2')"
                ),
                {
                    "id": sid,
                    "st": status,
                    "saat": saat,
                    "exp": saat + timedelta(minutes=120),
                    "mode": mode,
                    "anchor": anchor,
                    "ver": dataset_version,
                },
            )
    finally:
        engine.dispose()
    return sid


def _hapus_sesi(*ids: uuid.UUID) -> None:
    """Hapus baris milik sesi uji + sesinya (bukan milik orang lain)."""
    engine = _db()
    try:
        with engine.begin() as conn:
            for sid in ids:
                conn.execute(
                    text("DELETE FROM approvals WHERE decision_id IN "
                         "(SELECT id FROM decisions WHERE demo_session_id = :s)"),
                    {"s": sid},
                )
                conn.execute(
                    text("DELETE FROM sap_mock_purchase_orders WHERE demo_session_id = :s"),
                    {"s": sid},
                )
                conn.execute(
                    text("DELETE FROM decisions WHERE demo_session_id = :s"), {"s": sid}
                )
                for tabel in (
                    "delivery_events",
                    "disposal_events",
                    "price_signals",
                    "menu_plans",
                    "supply_records",
                    "batch_receipts",
                    "batches",
                ):
                    conn.execute(
                        text(f"DELETE FROM {tabel} WHERE demo_session_id = :s"), {"s": sid}
                    )
                conn.execute(text("DELETE FROM demo_sessions WHERE id = :s"), {"s": sid})
    finally:
        engine.dispose()


def _keputusan_sesi(sid: uuid.UUID) -> list[tuple]:
    engine = _db()
    try:
        with engine.begin() as conn:
            return conn.execute(
                text(
                    "SELECT id, demo_case, status, origin FROM decisions "
                    "WHERE demo_session_id = :s ORDER BY created_at, id"
                ),
                {"s": sid},
            ).all()
    finally:
        engine.dispose()


def _demo_case_tanpa_sesi() -> list[tuple]:
    """Baris demo kota uji yang TIDAK berstempel (sisa jalur lama)."""
    engine = _db()
    try:
        with engine.begin() as conn:
            return conn.execute(
                text(
                    "SELECT id FROM decisions d JOIN locations l ON l.id = d.target_location_id "
                    "WHERE d.demo_case = ANY(:k) AND l.name = 'Jakarta' "
                    "AND d.demo_session_id IS NULL"
                ),
                {"k": list(KASUS_SKRIP)},
            ).all()
    finally:
        engine.dispose()


@pytest.fixture()
def tanpa_sesi_aktif():
    """Kosongkan slot `active` selama tes, lalu pulihkan.

    `POST /demo/seed` tanpa `demo_session` memakai sesi aktif sebagai pemilik
    baris baru. Supaya tes bisa menguji jalur "belum ada sesi" (dan tidak
    mengubah sesi operator), status sesi aktif disimpan lalu dikembalikan.
    Hanya dijalankan pada DB sekali-pakai.
    """
    engine = _db()
    dipulihkan: list[uuid.UUID] = []
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("SELECT id FROM demo_sessions WHERE status = 'active'")
            ).scalars().all()
            dipulihkan = list(rows)
            if dipulihkan:
                conn.execute(
                    text("UPDATE demo_sessions SET status = 'ended' WHERE id = ANY(:i)"),
                    {"i": dipulihkan},
                )
        yield
    finally:
        with engine.begin() as conn:
            # Sesi uji yang masih 'active' harus turun dulu: indeks unik parsial
            # menolak dua sesi aktif sekaligus.
            conn.execute(
                text(
                    "UPDATE demo_sessions SET status = 'ended' "
                    "WHERE status = 'active' AND template_version = 'uji-fase2'"
                )
            )
            if dipulihkan:
                conn.execute(
                    text("UPDATE demo_sessions SET status = 'active' WHERE id = ANY(:i)"),
                    {"i": dipulihkan},
                )
        engine.dispose()


# --------------------------------------------------------------- 1. mode 422


def test_mode_tidak_sah_ditolak_422(tanpa_sesi_aktif):
    with TestClient(app) as client:
        head = _login(client)
        for mode in ("chaos", "REPLAY", ""):
            resp = client.post(
                "/demo/seed", json={"force": True, "mode": mode}, headers=head
            )
            assert resp.status_code == 422, (mode, resp.status_code, resp.text)
        # `mode=None` = "tidak menyebut mode": bukan nilai tak sah, jadi 200
        # (jalur lama; sesi aktif yang menentukan mode).
        assert client.post(
            "/demo/seed", json={"force": True, "mode": None}, headers=head
        ).status_code == 200


def test_demo_session_tidak_dikenal_ditolak_404(tanpa_sesi_aktif):
    with TestClient(app) as client:
        head = _login(client)
        resp = client.post(
            "/demo/seed",
            json={"force": True, "mode": "replay", "demo_session": str(uuid.uuid4())},
            headers=head,
        )
        assert resp.status_code == 404, resp.text


# ------------------------------------------ 2. anchor sesi (replay/realtime)


def test_seed_replay_memakai_jangkar_kanon(tanpa_sesi_aktif):
    sid = _buat_sesi(mode="replay", anchor=datetime(2026, 10, 8, 12, tzinfo=UTC))
    try:
        with TestClient(app) as client:
            head = _login(client)
            resp = client.post(
                "/demo/seed",
                json={"force": True, "mode": "replay", "demo_session": str(sid)},
                headers=head,
            )
            assert resp.status_code == 200, resp.text
            sesi = resp.json()["session"]
        assert sesi["id"] == str(sid)
        assert sesi["mode"] == "replay"
        assert sesi["evaluation_anchor"] == REPLAY_ANCHOR
        assert sesi["dataset_version"] == decision_time.REPLAY_DATASET_VERSION
        assert _keputusan_sesi(sid), "seed replay tidak menulis keputusan milik sesinya"
    finally:
        _hapus_sesi(sid)


def test_seed_realtime_membawa_anchor_dan_versi_dataset_sendiri(tanpa_sesi_aktif):
    anchor = datetime.now(UTC).replace(microsecond=0)
    sid = _buat_sesi(
        mode="realtime",
        anchor=anchor,
        dataset_version=decision_time.dataset_version_untuk("realtime", anchor),
    )
    try:
        with TestClient(app) as client:
            head = _login(client)
            resp = client.post(
                "/demo/seed",
                json={"force": True, "mode": "realtime", "demo_session": str(sid)},
                headers=head,
            )
            assert resp.status_code == 200, resp.text
            sesi = resp.json()["session"]
        assert sesi["mode"] == "realtime"
        assert sesi["evaluation_anchor"] != REPLAY_ANCHOR
        assert sesi["dataset_version"] != decision_time.REPLAY_DATASET_VERSION
        # Semua keputusan hasil seed (termasuk yang `rejected`) milik sesi ini.
        baris = _keputusan_sesi(sid)
        # 4 kasus skrip, 7 baris: rantai penolakan membuat v1/v2 kuota dan
        # g1 logistik ikut tersimpan.
        assert len(baris) == 7
        assert {r[1] for r in baris} == set(KASUS_SKRIP)
        assert all(r[3] == "demo" for r in baris)
        tolak = [r for r in baris if r[2] == "rejected"]
        assert tolak, "seed harus tetap membuat baris rejected (chain penolakan)"
    finally:
        _hapus_sesi(sid)


def test_mode_sesi_harus_cocok_dengan_payload(tanpa_sesi_aktif):
    sid = _buat_sesi(mode="replay", anchor=datetime(2026, 10, 8, 12, tzinfo=UTC))
    try:
        with TestClient(app) as client:
            head = _login(client)
            resp = client.post(
                "/demo/seed",
                json={"force": True, "mode": "realtime", "demo_session": str(sid)},
                headers=head,
            )
        assert resp.status_code == 422, resp.text
        assert "mode" in resp.json()["detail"].lower()
        assert not _keputusan_sesi(sid), "penolakan tidak boleh menulis baris"
    finally:
        _hapus_sesi(sid)


# ------------------------------------------- 3. dua sesi & kepemilikan baris


def test_sesi_kedua_tidak_menimpa_kepemilikan_sesi_pertama(tanpa_sesi_aktif):
    sid_a = _buat_sesi(mode="replay", anchor=datetime(2026, 10, 8, 12, tzinfo=UTC))
    sid_b: uuid.UUID | None = None
    try:
        with TestClient(app) as client:
            head = _login(client)
            pertama = client.post(
                "/demo/seed",
                json={"force": True, "mode": "replay", "demo_session": str(sid_a)},
                headers=head,
            )
            assert pertama.status_code == 200, pertama.text
            id_keputusan_a = {r[0] for r in _keputusan_sesi(sid_a)}
            assert id_keputusan_a

            anchor_b = datetime.now(UTC).replace(microsecond=0)
            sid_b = _buat_sesi(
                mode="realtime",
                anchor=anchor_b,
                dataset_version=decision_time.dataset_version_untuk("realtime", anchor_b),
            )
            kedua = client.post(
                "/demo/seed",
                json={"force": True, "mode": "realtime", "demo_session": str(sid_b)},
                headers=head,
            )
            assert kedua.status_code == 200, kedua.text
            assert kedua.json()["session"]["id"] == str(sid_b)
            assert str(sid_b) != str(sid_a)

        # Baris sesi pertama tetap ada dan tetap milik sesi pertama.
        milik_a = _keputusan_sesi(sid_a)
        assert {r[0] for r in milik_a} == id_keputusan_a, (
            "menyemai sesi kedua mengubah/menghapus baris sesi pertama"
        )
        milik_b = _keputusan_sesi(sid_b)
        assert milik_b and {r[0] for r in milik_b}.isdisjoint(id_keputusan_a)
    finally:
        _hapus_sesi(sid_a, *( [sid_b] if sid_b else [] ))


def test_reset_sesi_pertama_tidak_menghapus_data_sesi_kedua(tanpa_sesi_aktif):
    sid_a = _buat_sesi(mode="replay", anchor=datetime(2026, 10, 8, 12, tzinfo=UTC))
    sid_b: uuid.UUID | None = None
    try:
        with TestClient(app) as client:
            head = _login(client)
            assert client.post(
                "/demo/seed",
                json={"force": True, "mode": "replay", "demo_session": str(sid_a)},
                headers=head,
            ).status_code == 200

            anchor_b = datetime.now(UTC).replace(microsecond=0)
            sid_b = _buat_sesi(
                mode="realtime",
                anchor=anchor_b,
                dataset_version=decision_time.dataset_version_untuk("realtime", anchor_b),
            )
            assert client.post(
                "/demo/seed",
                json={"force": True, "mode": "realtime", "demo_session": str(sid_b)},
                headers=head,
            ).status_code == 200
            milik_b = {r[0] for r in _keputusan_sesi(sid_b)}
            assert milik_b

            # Reset sesi PERTAMA: hapus+lazy semai ulang kasus skrip miliknya.
            reset = client.post(
                "/demo/seed",
                json={"force": True, "mode": "replay", "demo_session": str(sid_a)},
                headers=head,
            )
            assert reset.status_code == 200, reset.text

        assert {r[0] for r in _keputusan_sesi(sid_b)} == milik_b, (
            "reset sesi pertama menghapus/mengubah baris sesi kedua"
        )
        assert _keputusan_sesi(sid_a), "reset sesi pertama harus menyemai ulang miliknya"
    finally:
        _hapus_sesi(sid_a, *( [sid_b] if sid_b else [] ))


# ------------------------------------------------- 4. resolver waktu evaluasi


def _keputusan_ringkas(**nilai):
    """Objek Decision lepas (tanpa DB) untuk menguji resolver murni."""
    dasar = {
        "id": uuid.uuid4(),
        "demo_case": None,
        "demo_session_id": None,
        "expires_at": datetime.now(UTC) + timedelta(minutes=30),
    }
    dasar.update(nilai)
    return Decision(**dasar)


class _BarisSesi:
    """Pengganti `DemoSession` untuk relasi yang sudah termuat."""

    def __init__(self, anchor):
        self.evaluation_anchor = anchor


def test_decision_now_memakai_anchor_sesi(monkeypatch):
    anchor = datetime(2026, 10, 8, 12, tzinfo=UTC)
    d = _keputusan_ringkas(demo_session_id=uuid.uuid4())
    # Relasi "sudah dimuat" = ada di `__dict__` instance (hasil selectinload).
    d.__dict__["demo_session"] = _BarisSesi(anchor)
    assert decision_time.decision_now(d) == anchor


def test_decision_now_jam_dinding_tanpa_sesi(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
    d = _keputusan_ringkas(demo_case="shortage-darurat")
    sebelum = datetime.now(UTC)
    hasil = decision_time.decision_now(d)
    assert abs((hasil - sebelum).total_seconds()) < 5


def test_decision_now_legacy_demo_case_hanya_saat_demo_mode(monkeypatch):
    """`demo_case` tidak boleh menyamarkan operasional.

    Keputusan demo LAMA (tanpa sesi) hanya memakai jangkar kanon bila mode demo
    menyala; dengan `DEMO_MODE=False` jawabannya jam dinding.
    """
    d = _keputusan_ringkas(demo_case="shortage-darurat")
    monkeypatch.setattr(settings, "demo_mode", True)
    assert decision_time.decision_now(d) == decision_time.REPLAY_ANCHOR
    monkeypatch.setattr(settings, "demo_mode", False)
    assert decision_time.decision_now(d) != decision_time.REPLAY_ANCHOR


def test_decision_now_tidak_lazy_load_saat_relasi_belum_dimuat():
    """Sesi tertaut tetapi relasi belum dimuat → jam dinding, tanpa SELECT."""
    d = _keputusan_ringkas(demo_session_id=uuid.uuid4())
    hasil = decision_time.decision_now(d)
    assert abs((hasil - datetime.now(UTC)).total_seconds()) < 5


def test_anchor_dan_versi_dataset_per_mode():
    assert decision_time.anchor_untuk("replay") == decision_time.REPLAY_ANCHOR
    assert decision_time.dataset_version_untuk("replay", decision_time.REPLAY_ANCHOR) == (
        decision_time.REPLAY_DATASET_VERSION
    )
    saat = datetime(2026, 10, 27, 9, 30, tzinfo=UTC)
    assert decision_time.anchor_untuk("realtime", saat=saat) == saat
    versi = decision_time.dataset_version_untuk("realtime", saat)
    assert versi != decision_time.REPLAY_DATASET_VERSION
    assert "20261027T093000" in versi
    with pytest.raises(ValueError):
        decision_time.anchor_untuk("chaos")


# ---------------------------------------------------------- 5. hapus per sesi


def test_purge_session_hanya_menghapus_milik_sesi_itu(tanpa_sesi_aktif):
    sid_a = _buat_sesi(mode="replay", anchor=datetime(2026, 10, 8, 12, tzinfo=UTC))
    sid_b: uuid.UUID | None = None
    try:
        with TestClient(app) as client:
            head = _login(client)
            for sid, mode in ((sid_a, "replay"),):
                assert client.post(
                    "/demo/seed",
                    json={"force": True, "mode": mode, "demo_session": str(sid)},
                    headers=head,
                ).status_code == 200
            anchor_b = datetime.now(UTC).replace(microsecond=0)
            sid_b = _buat_sesi(
                mode="realtime",
                anchor=anchor_b,
                dataset_version=decision_time.dataset_version_untuk("realtime", anchor_b),
            )
            assert client.post(
                "/demo/seed",
                json={"force": True, "mode": "realtime", "demo_session": str(sid_b)},
                headers=head,
            ).status_code == 200
        milik_b = {r[0] for r in _keputusan_sesi(sid_b)}

        async def _skenario():
            engine = create_async_engine(DSN_ASYNC)
            maker = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with maker() as db:
                    hasil = await demo_purge.purge_session(db, sid_a)
                    assert hasil["decisions"] >= 1, hasil
                    # `purge_session` tidak commit (pemanggil yang menentukan
                    # transaksi) — tanpa commit di sini, DELETE-nya di-rollback
                    # dan tes akan "gagal" karena alasan yang salah.
                    await db.commit()
            finally:
                await engine.dispose()

        asyncio.run(_skenario())
        assert not _keputusan_sesi(sid_a), "purge sesi A menyisakan baris milik A"
        assert {r[0] for r in _keputusan_sesi(sid_b)} == milik_b, (
            "purge sesi A menghapus baris milik sesi B"
        )
    finally:
        _hapus_sesi(sid_a, *( [sid_b] if sid_b else [] ))


# ------------------------------------------- 6. bentuk respons sesi + KPI


def test_get_session_memuat_mode_anchor_dan_versi(tanpa_sesi_aktif):
    anchor = datetime.now(UTC).replace(microsecond=0)
    sid = _buat_sesi(
        mode="realtime",
        anchor=anchor,
        dataset_version=decision_time.dataset_version_untuk("realtime", anchor),
        status="active",
    )
    try:
        with TestClient(app) as client:
            head = _login(client)
            body = client.get(f"/demo/session?session_id={sid}", headers=head).json()
        assert body["session_id"] == str(sid)
        assert body["mode"] == "realtime"
        assert body["evaluation_anchor"].startswith(
            anchor.isoformat().replace("+00:00", "")
        )
        assert body["dataset_version"]
        assert body["anchor_now"] and body["expires_at"]
    finally:
        _hapus_sesi(sid)


# ------------------------------------ 7. propagasi sesi ke PO / fakta turunan


def test_fakta_settlement_membawa_sesi_induk(tanpa_sesi_aktif):
    """PO + fakta KPI mewarisi `demo_session_id` dari induknya, bukan sesi aktif."""
    sid = _buat_sesi(mode="replay", anchor=datetime(2026, 10, 8, 12, tzinfo=UTC))
    try:
        with TestClient(app) as client:
            head = _login(client)
            assert client.post(
                "/demo/seed",
                json={"force": True, "mode": "replay", "demo_session": str(sid)},
                headers=head,
            ).status_code == 200

            engine = _db()
            try:
                with engine.begin() as conn:
                    baris = conn.execute(
                        text(
                            "SELECT id, target_location_id, commodity_id, supplier_id "
                            "FROM decisions WHERE demo_session_id = :s "
                            "AND supplier_id IS NOT NULL LIMIT 1"
                        ),
                        {"s": sid},
                    ).one()
            finally:
                engine.dispose()

            async def _skenario():
                from decimal import Decimal

                from app.services import settlement

                engine_a = create_async_engine(DSN_ASYNC)
                maker = async_sessionmaker(engine_a, expire_on_commit=False)
                try:
                    async with maker() as db:
                        decision = await db.get(Decision, baris[0])
                        assert decision is not None
                        await settlement.catat_po_terbit(
                            db,
                            decision=decision,
                            po_number=f"UJI-SESI-{uuid.uuid4().hex[:8]}",
                            supplier_id=baris[3],
                            harga_per_kg=Decimal("1000"),
                            sekarang=datetime.now(UTC),
                        )
                        await db.commit()
                finally:
                    await engine_a.dispose()

            asyncio.run(_skenario())

            engine = _db()
            try:
                with engine.begin() as conn:
                    sesi_fakta = conn.execute(
                        text(
                            "SELECT demo_session_id FROM price_signals "
                            "WHERE source_ref LIKE 'po:UJI-SESI-%' ORDER BY recorded_at DESC "
                            "LIMIT 1"
                        )
                    ).scalar_one_or_none()
            finally:
                engine.dispose()
            assert sesi_fakta == sid, (
                "fakta KPI tidak mewarisi sesi dari keputusan induknya"
            )
    finally:
        engine = _db()
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM price_signals WHERE source_ref LIKE 'po:UJI-SESI-%'")
                )
        finally:
            engine.dispose()
        _hapus_sesi(sid)


# ------------------------------------- 7. propagasi sesi ke writer pipeline


def _sesi_keputusan(decision_id) -> uuid.UUID | None:
    """Sesi pemilik satu baris `decisions` (pembanding jalur tulis nyata)."""
    engine = _db()
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT demo_session_id FROM decisions WHERE id = CAST(:i AS uuid)"),
                {"i": str(decision_id)},
            ).scalar_one()
    finally:
        engine.dispose()


def test_run_event1_menurunkan_sesi_pemilik_ke_keputusan(tanpa_sesi_aktif, monkeypatch):
    """`run_event1` menerima `demo_session_id` dan MENURUNKANNYA ke Decision.

    Tanpa ini, keputusan hasil analisis agent tidak punya pemilik eksplisit:
    kolom `decisions.demo_session_id` hanya terisi bila penjaga `before_flush`
    kebetulan menstempelnya dari sesi AKTIF — bukan dari sesi yang meminta
    analisis (rencana Fase 2 butir 5).

    Masukan engine rekomendasi DIGANTI (satu kandidat terkendali) supaya tes ini
    menguji PROPAGASI sesi, bukan kebijakan kelayakan kandidat yang sedang
    berubah di fase lain. Seluruh jalur tulis (Decision, trace, commit) tetap
    yang asli.
    """
    sid = _buat_sesi(mode="replay", anchor=datetime(2026, 10, 8, 12, tzinfo=UTC))
    from app.services import event1_orchestrator as orch

    async def _rekomendasi_terkendali(_fetch, **_kw):
        # `**_kw` disengaja: orkestrator menambah parameter pada mesin
        # rekomendasi dari fase lain (mis. `as_of`). Tes ini menguji PROPAGASI
        # sesi, jadi ia harus tahan terhadap parameter tambahan itu.
        return {
            "recommendations": [
                {
                    "rank": 1,
                    "eligible": True,
                    "candidate_id": str(uuid.uuid4()),
                    "score": 0.9,
                    "safe_delivered_cost": "1000000",
                    "cost_breakdown": None,
                    "evidence": None,
                    "candidate": {
                        "commodity": "telur",
                        "source_location": "Cianjur",
                        "destination_location": "Jakarta",
                        "quantity_kg": "100",
                        "safety_status": "pass",
                        "freshness_score": "0.90",
                        "logistics_distance_km": 60.0,
                        "logistics_time_min": 90,
                        "logistics_feasible": True,
                        "supplier_id": None,
                    },
                }
            ]
        }

    monkeypatch.setattr(orch.rs, "build_recommendations", _rekomendasi_terkendali)
    try:
        outcome = orch.run_event1(
            commodity="telur", target_location="Jakarta", demo_session_id=sid
        )
        assert outcome["decision_id"]
        assert _sesi_keputusan(outcome["decision_id"]) == sid, (
            "keputusan hasil run_event1 tidak mewarisi sesi pemanggil"
        )
    finally:
        _hapus_sesi(sid)


def test_event1_endpoint_meneruskan_sesi(tanpa_sesi_aktif, monkeypatch):
    """`POST /demo/event1` meneruskan sesi ke orkestrator, bukan membuangnya."""
    sid = _buat_sesi(mode="replay", anchor=datetime(2026, 10, 8, 12, tzinfo=UTC))
    dipanggil: dict = {}

    def _fake(commodity, target_location, **kwargs):
        dipanggil.update(
            commodity=commodity, target_location=target_location, **kwargs
        )
        return {
            "decision_id": "00000000-0000-0000-0000-0000000000f2",
            "detect": {"commodity": commodity},
            "verifier": {"verdict": "PASS"},
            "forecast": {"forecast_qty_kg": None},
            "supervisor": {"status": "fallback", "summary": "uji", "attempts": []},
            "mode": "regional_balance",
            "suppliers": {"candidates": [], "ranked": [], "chosen": None},
            "decision_snapshot": {"status": "proposed", "approved": False},
            "trace_steps": ["DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE", "DECIDE"],
        }

    monkeypatch.setattr("app.api.demo.run_event1", _fake)
    try:
        with TestClient(app) as client:
            head = _login(client)
            resp = client.post(
                "/demo/event1",
                json={
                    "commodity": "telur",
                    "target_location": "Jakarta",
                    "demo_session": str(sid),
                },
                headers=head,
            )
        assert resp.status_code == 201, resp.text
        assert dipanggil.get("demo_session_id") == sid, (
            "endpoint membuang sesi yang diminta klien"
        )
    finally:
        _hapus_sesi(sid)


def test_agent_run_meneruskan_sesi(tanpa_sesi_aktif, monkeypatch):
    """`POST /demo/agent/run` meneruskan sesi ke orkestrator pengadaan.

    Endpoint ini menulis Decision lewat jalur yang berbeda (`supplier_procurement`),
    jadi propagasi harus diuji di seam-nya sendiri — bukan diasumsikan ikut
    terbawa dari jalur seed.
    """
    sid = _buat_sesi(mode="replay", anchor=datetime(2026, 10, 8, 12, tzinfo=UTC))
    dipanggil: dict = {}

    def _fake(commodity, target_location, **kwargs):
        dipanggil.update(
            commodity=commodity, target_location=target_location, **kwargs
        )
        return {
            "decision_id": "00000000-0000-0000-0000-0000000000f3",
            "detect": {"commodity": commodity},
            "verifier": {"verdict": "PASS"},
            "forecast": {"forecast_qty_kg": None},
            "supervisor": {"status": "fallback", "summary": "uji", "attempts": []},
            "mode": "supplier_procurement",
            "suppliers": {"candidates": [], "ranked": [], "chosen": None},
            "decision_snapshot": {"status": "proposed", "approved": False},
            "trace_steps": ["DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE",
                            "DECIDE", "SUPERVISE"],
        }

    monkeypatch.setattr("app.api.demo.run_supplier_procurement", _fake)
    try:
        with TestClient(app) as client:
            head = _login(client)
            resp = client.post(
                "/demo/agent/run",
                json={"demo_session": str(sid)},
                headers=head,
            )
        assert resp.status_code == 201, resp.text
        assert dipanggil.get("demo_session_id") == sid, (
            "analisis demo membuang sesi yang diminta klien"
        )
    finally:
        _hapus_sesi(sid)


def test_agent_run_sesi_tidak_dikenal_ditolak_404(tanpa_sesi_aktif, monkeypatch):
    """Sesi yang tidak ada dijawab 404 — bukan diam-diam memakai sesi aktif."""

    def _fake(*_a, **_kw):  # pragma: no cover - tidak boleh terpanggil
        raise AssertionError("orkestrator dipanggil padahal sesinya tidak ada")

    monkeypatch.setattr("app.api.demo.run_supplier_procurement", _fake)
    with TestClient(app) as client:
        head = _login(client)
        resp = client.post(
            "/demo/agent/run",
            json={"demo_session": str(uuid.uuid4())},
            headers=head,
        )
    assert resp.status_code == 404, resp.text


def test_penulis_po_memakai_sesi_dari_keputusan():
    """Penjaga sumber: INSERT PO di `actions.py` wajib menulis `demo_session_id`."""
    from pathlib import Path

    sumber = Path(__file__).resolve().parents[1] / "app" / "api" / "actions.py"
    teks = sumber.read_text(encoding="utf-8")
    awal = teks.index("INSERT INTO sap_mock_purchase_orders")
    potongan = teks[awal : awal + 700]
    assert "demo_session_id" in potongan, (
        "PO hasil eksekusi tidak menyimpan sesi induk; kepemilikan baris hilang "
        "begitu keputusan dihapus (FK ON DELETE SET NULL)"
    )


# ------------------------------------- 8. mode pada analisis + penerimaan


def _payload_pengadaan(commodity: str) -> dict:
    """Balasan minimal `run_supplier_procurement` untuk uji seam endpoint."""
    return {
        "decision_id": "00000000-0000-0000-0000-0000000000f4",
        "detect": {"commodity": commodity},
        "verifier": {"verdict": "PASS"},
        "forecast": {"forecast_qty_kg": None},
        "supervisor": {"status": "fallback", "summary": "uji", "attempts": []},
        "mode": "supplier_procurement",
        "suppliers": {"candidates": [], "ranked": [], "chosen": None},
        "decision_snapshot": {"status": "proposed", "approved": False},
        "trace_steps": ["DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE",
                        "DECIDE", "SUPERVISE"],
    }


def test_agent_run_mode_cocok_diterima(tanpa_sesi_aktif, monkeypatch):
    """`POST /demo/agent/run` menerima `mode` yang cocok dengan sesi pemiliknya.

    Mode disebut eksplisit supaya analisis tidak diam-diam berjalan di mode
    sesi lain: klien yang mengira sedang realtime tidak boleh menulis ke sesi
    replay (dan sebaliknya).
    """
    sid = _buat_sesi(mode="replay", anchor=datetime(2026, 10, 8, 12, tzinfo=UTC))
    monkeypatch.setattr(
        "app.api.demo.run_supplier_procurement",
        lambda commodity, target_location, **_kw: _payload_pengadaan(commodity),
    )
    try:
        with TestClient(app) as client:
            head = _login(client)
            resp = client.post(
                "/demo/agent/run",
                json={"demo_session": str(sid), "mode": "replay"},
                headers=head,
            )
        assert resp.status_code == 201, resp.text
    finally:
        _hapus_sesi(sid)


def test_agent_run_mode_bertentangan_ditolak_422(tanpa_sesi_aktif, monkeypatch):
    """Mode permintaan yang bertentangan dengan sesi dijawab 422, bukan diabaikan."""

    def _fake(*_a, **_kw):  # pragma: no cover - tidak boleh terpanggil
        raise AssertionError("analisis dijalankan padahal mode-nya bertentangan")

    monkeypatch.setattr("app.api.demo.run_supplier_procurement", _fake)
    sid = _buat_sesi(mode="replay", anchor=datetime(2026, 10, 8, 12, tzinfo=UTC))
    try:
        with TestClient(app) as client:
            head = _login(client)
            resp = client.post(
                "/demo/agent/run",
                json={"demo_session": str(sid), "mode": "realtime"},
                headers=head,
            )
        assert resp.status_code == 422, resp.text
    finally:
        _hapus_sesi(sid)


def test_penerimaan_mewarisi_sesi_batch_bukan_sesi_aktif(tanpa_sesi_aktif, monkeypatch):
    """`POST /receipts` menuliskan sesi BATCH-nya, bukan sesi yang sedang aktif.

    Inilah pembeda yang diminta rencana: penjaga `before_flush` menstempel dari
    sesi AKTIF, sehingga penerimaan atas barang sesi pertama ikut tercatat milik
    sesi kedua begitu operator membuka sesi baru.
    """
    batch_id = _batch_untuk_penerimaan()
    sesi_batch = _buat_sesi(mode="replay", anchor=datetime(2026, 10, 8, 12, tzinfo=UTC))
    sesi_aktif = _buat_sesi(mode="realtime", anchor=datetime.now(UTC), status="active")
    _set_sesi_batch(batch_id, sesi_batch)
    # Kelayakan batch diuji di berkas Fase 4; di sini yang diuji kepemilikan.
    monkeypatch.setattr(
        "app.api.receipts.evaluasi_batch",
        lambda _batch: type("_E", (), {"status": "usable", "blocking_reasons": ()})(),
    )
    try:
        with TestClient(app) as client:
            head = _login(client)
            resp = client.post(
                "/receipts",
                json={"batch_id": str(batch_id), "checked": {"kualitas": True}},
                headers=head,
            )
        assert resp.status_code == 201, resp.text
        receipt_id = resp.json()["id"]
        assert _sesi_penerimaan(receipt_id) == sesi_batch, (
            "penerimaan tidak mewarisi sesi batch induk — kemungkinan distempel "
            "dari sesi aktif"
        )
        assert _sesi_penerimaan(receipt_id) != sesi_aktif
    finally:
        _hapus_penerimaan_uji(batch_id)
        _set_sesi_batch(batch_id, None)
        _hapus_sesi(sesi_batch, sesi_aktif)


def _batch_untuk_penerimaan() -> uuid.UUID:
    """Batch di lokasi akun uji yang bisa dipakai mencatat penerimaan."""
    engine = _db()
    try:
        with engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT b.id FROM batches b JOIN users u ON u.location_id = b.location_id "
                    "WHERE u.email = :e AND u.location_id IS NOT NULL "
                    "ORDER BY b.created_at DESC LIMIT 1"
                ),
                {"e": EMAIL},
            ).scalar_one()
    finally:
        engine.dispose()


def _set_sesi_batch(batch_id: uuid.UUID, sid: uuid.UUID | None) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE batches SET demo_session_id = :s WHERE id = :b"),
                {"s": sid, "b": batch_id},
            )
    finally:
        engine.dispose()


def _sesi_penerimaan(receipt_id: str) -> uuid.UUID | None:
    engine = _db()
    try:
        with engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT demo_session_id FROM batch_receipts "
                    "WHERE id = CAST(:i AS uuid)"
                ),
                {"i": receipt_id},
            ).scalar_one()
    finally:
        engine.dispose()


def _hapus_penerimaan_uji(batch_id: uuid.UUID) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM batch_receipts WHERE batch_id = :b"),
                {"b": batch_id},
            )
    finally:
        engine.dispose()
