"""Konfigurasi koleksi test backend.

Pemisahan test host vs container (temuan audit feasibility Sprint 1):
beberapa test Sprint 0 bersifat host-only karena mengimpor modul dari
direktori repo yang tidak di-mount ke container (agent/, infra/).
Di dalam container, modul-modul itu dikoleksi-skip; di host tetap jalan.
"""

import asyncio
import importlib
import os
import sys
from pathlib import Path

import bcrypt
import pytest
from sqlalchemy import create_engine, text

from tests.dsn import DSN_ASYNC, DSN_SYNC  # DSN mengikuti DATABASE_URL
from tests.gate_lock import ambil_kunci, dsn_psycopg, lepas_kunci

# Suite ini menguji permukaan demo. Password demo hanya boleh dipasang bila
# `DEMO_MODE` aktif (temuan D-01). Nilai ambient (mis. `.env` yang di-source
# operator) tidak boleh membuat tes gagal, jadi proses tes menetapkannya
# sendiri; aplikasi & seeder produksi tetap default mati (`.env`/compose).
os.environ["DEMO_MODE"] = "true"

# Enforcement sesi demo MENYALA secara bawaan sejak 25 Okt 2026 (keputusan
# owner): endpoint mutasi menolak 409 tanpa sesi aktif. Suite ini menyemai data
# tanpa sesi di 1.200+ tes, jadi proses tes mematikannya secara EKSPLISIT di
# sini. Ini bukan melumpuhkan fitur: tes yang memang menguji sesi menyalakannya
# sendiri (monkeypatch `settings.demo_session_enforce`) dan berkas destruktif
# `test_demo_session.py` hanya berjalan dengan opt-in `DEMO_SESSION_TESTS_ENFORCE=1`.
if os.environ.get("DEMO_SESSION_TESTS_ENFORCE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}:
    os.environ["DEMO_SESSION_ENFORCE"] = "true"
else:
    os.environ["DEMO_SESSION_ENFORCE"] = "false"

# psycopg async menolak ProactorEventLoop bawaan Windows.
if sys.platform == "win32":  # pragma: no cover - hanya Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Tes yang butuh PAKET `agent` (runtime terpisah di akar repo). Di dev, compose
# me-mount `./agent:/agent:ro`, jadi paket itu tersedia dan tes ini BENAR-BENAR
# berjalan. Di image tanpa mount, hanya tes ini yang dilewati.
AGENT_MODULES = [
    "test_agent_contracts.py",
    "test_agent_workers.py",
    "test_agent_workers_p3.py",
    "test_agent_validation.py",
    "test_agent_orchestrator.py",
    "test_agent_runtime_task.py",
    "test_agent_golden_cases.py",
    "test_agent_verify.py",
    "test_agent_verifier.py",
]

# Tes yang butuh BERKAS AKAR REPO (compose, .env.example, .gitignore, struktur).
# Kontainer backend hanya memuat backend/, jadi daftar ini tetap diabaikan di
# sana — tidak bergantung pada keberadaan direktori `agent/`.
HOST_ONLY_MODULES = [
    "test_supervisor_agent.py",
    "test_supervisor_tools.py",
    "test_verify_agentcore_access.py",
    "test_verify_bedrock_access.py",
    "test_compose_contract.py",
    "test_environment_contract.py",
    "test_structure.py",
]

# Test yang butuh infrastruktur Docker (Postgres via psycopg sync, env container).
DOCKER_ONLY_MODULES = [
    "test_master_data_schema.py",
    # Kunci gerbang hidup di server Postgres: hanya bisa diuji dalam kontainer.
    "test_gate_lock.py",
]

_backend_dir = Path(__file__).resolve().parents[1]
_repo_root = _backend_dir.parent

collect_ignore = list(DOCKER_ONLY_MODULES)

# Paket `agent` dianggap tersedia bila bisa DIIMPOR, bukan bila direktorinya
# ada: di kontainer, `agent` datang dari mount /agent (lihat docker-compose).
try:
    importlib.import_module("agent")
except Exception:  # noqa: BLE001 - apa pun penyebabnya: paket tidak siap
    collect_ignore += AGENT_MODULES

# Berkas akar repo (compose, .env.example, struktur) hanya ada di checkout host.
if not all((_repo_root / nama).exists() for nama in ("docker-compose.yml", "infra")):
    collect_ignore += HOST_ONLY_MODULES


# ---------------------------------------------------------------------------
# Isolasi env model provider untuk unit test (permintaan Roy: model live di
# .env tidak boleh membuat test unit memanggil jaringan).
#
# Kontrak:
# - default: SEMUA key model/provider dianggap KOSONG selama pytest berjalan
#   → verifier UNAVAILABLE, forecast statistical fallback, rantai kosong
# - test yang butuh chain tertentu memakai monkeypatch.setenv eksplisit
# - test yang MAU memanggil provider nyata ditandai @pytest.mark.live dan
#   di-skip otomatis (jalankan eksplisit: pytest -m live)
# ---------------------------------------------------------------------------

MODEL_ENV_KEYS = [
    "AGENTCORE_RUNTIME_ARN",
    "AGENTCORE_GATEWAY_URL",
    "AGENTCORE_MEMORY_ID",
    "SUPERVISOR_MODEL_PRIMARY",
    "SUPERVISOR_MODEL_FALLBACK",
]
MODEL_ENV_KEYS += [f"SUPERVISOR_MODEL_FALLBACK_{i}" for i in range(1, 13)]
MODEL_ENV_KEYS += ["VERIFIER_MODEL_PRIMARY"]
MODEL_ENV_KEYS += [f"VERIFIER_MODEL_FALLBACK_{i}" for i in range(1, 13)]
MODEL_ENV_KEYS += ["FORECAST_MODEL"]
MODEL_ENV_KEYS += [f"FORECAST_MODEL_FALLBACK_{i}" for i in range(1, 13)]
# S4-10: SAP AI Core = provider NYATA. Kredensialnya ikut diisolasi supaya
# suite tetap hermetik (tanpa jaringan); test yang memang mau memanggil AI
# Core ditandai @pytest.mark.live.
MODEL_ENV_KEYS += [
    "SAP_AI_CORE_AUTH_URL",
    "SAP_AI_CORE_API_URL",
    "SAP_AI_CORE_CLIENT_ID",
    "SAP_AI_CORE_CLIENT_SECRET",
    "SAP_AI_CORE_RESOURCE_GROUP",
    "SAP_AI_CORE_DEPLOYMENT_ID_LLM",
    "SAP_AI_CORE_DEPLOYMENT_ID_RPT",
]


@pytest.fixture(autouse=True)
def _isolate_model_env(monkeypatch, request):
    if request.node.get_closest_marker("live"):
        yield  # test live: env asli dipertahankan
        return
    for key in MODEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield


# ---------------------------------------------------------------------------
# Helper auth untuk test yang memanggil endpoint terproteksi JWT.
#
# RBAC endpoint legacy Sprint 1/2 (residual debt, arah Roy 2026-10-08):
# semua endpoint butuh JWT valid → test legacy yang selama ini memanggil
# tanpa token kini memakai fixture ini (user DB asli + login JWT nyata,
# bukan token palsu). Role sppg_head + location Jakarta (constraint DB:
# user SPPG wajib punya location).
# ---------------------------------------------------------------------------

_LEGACY_RBAC_EMAIL = "pytest-legacy-rbac@test.local"


def _hapus_user(conn, email: str) -> None:
    """Hapus user uji beserta approval miliknya.

    `approvals.approved_by` memakai aturan NO ACTION, jadi `DELETE FROM users`
    gagal begitu ada satu tes yang menyetujui keputusan sebagai user tersebut.
    Gejalanya khas: sederet `ERROR at setup` di suite penuh, padahal berkas yang
    sama lulus saat dijalankan sendiri.
    """
    conn.execute(
        text(
            "DELETE FROM approvals WHERE approved_by IN "
            "(SELECT id FROM users WHERE email = :e)"
        ),
        {"e": email},
    )
    conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})


@pytest.fixture()
def auth_headers():
    engine = create_engine(
        DSN_SYNC
    )
    pw = "TestPass#2026"
    digest = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            # Idempoten: bersihkan sisa run sebelumnya bila ada.
            _hapus_user(conn, _LEGACY_RBAC_EMAIL)
            loc_id = conn.execute(
                text("SELECT id FROM locations WHERE name = 'Jakarta'")
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (gen_random_uuid(), 'Test Legacy RBAC', :e, :h, 'sppg_head', :l)"
                ),
                {"e": _LEGACY_RBAC_EMAIL, "h": digest, "l": str(loc_id)},
            )
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as c:
            resp = c.post(
                "/auth/login", json={"email": _LEGACY_RBAC_EMAIL, "password": pw}
            )
            assert resp.status_code == 200, resp.text
            token = resp.json()["access_token"]
        yield {"Authorization": f"Bearer {token}"}
    finally:
        with engine.begin() as conn:
            _hapus_user(conn, _LEGACY_RBAC_EMAIL)
        engine.dispose()


# ---------------------------------------------------------------------------
# Fixture `monitor_headers` — bgn_monitor TANPA lokasi (cakupan nasional).
#
# Sejak Ruling 2026-10-14 cakupan lokasi ditegakkan di server, test yang
# subjeknya data lintas lokasi (semantik supply/demand/price, peta nasional)
# TIDAK boleh memakai token kepala SPPG lagi — memakainya akan 403. Peran yang
# memang berhak membaca nasional adalah bgn_monitor (read-only), jadi test
# seperti itu memakai fixture ini. Test yang justru menguji penguncian lokasi
# tetap memakai `auth_headers` (kepala SPPG Jakarta).
# ---------------------------------------------------------------------------

_MONITOR_EMAIL = "pytest-monitor-national@test.local"


@pytest.fixture()
def monitor_headers():
    engine = create_engine(
        DSN_SYNC
    )
    pw = "TestPass#2026"
    digest = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            _hapus_user(conn, _MONITOR_EMAIL)
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (gen_random_uuid(), 'Test Monitor Nasional', :e, :h, "
                    "'bgn_monitor', NULL)"
                ),
                {"e": _MONITOR_EMAIL, "h": digest},
            )
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as c:
            resp = c.post(
                "/auth/login", json={"email": _MONITOR_EMAIL, "password": pw}
            )
            assert resp.status_code == 200, resp.text
            token = resp.json()["access_token"]
        yield {"Authorization": f"Bearer {token}"}
    finally:
        with engine.begin() as conn:
            _hapus_user(conn, _MONITOR_EMAIL)
        engine.dispose()


_FAR_NUT_EMAIL = "pytest-far-nutritionist@test.local"


@pytest.fixture()
def far_nutritionist_headers():
    """Ahli gizi di SPPG LAIN (Bogor) — untuk menguji aturan cakupan.

    Sengaja dibuat di sini, bukan memakai akun demo: sejak Ruling 2026-10-14
    KEDUA akun approver demo berada di satu SPPG (Jakarta) supaya matriks AND
    bisa didemokan. Tes aturan scope karena itu tidak boleh bergantung pada
    lokasi akun demo — ia menyiapkan sendiri peran "SPPG lain".
    """
    engine = create_engine(
        DSN_SYNC
    )
    pw = "TestPass#2026"
    digest = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            _hapus_user(conn, _FAR_NUT_EMAIL)
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "SELECT gen_random_uuid(), 'Far Nutritionist', :e, :h, "
                    "'sppg_nutritionist', id FROM locations WHERE name = 'Bogor'"
                ),
                {"e": _FAR_NUT_EMAIL, "h": digest},
            )
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as c:
            resp = c.post(
                "/auth/login", json={"email": _FAR_NUT_EMAIL, "password": pw}
            )
            assert resp.status_code == 200, resp.text
            token = resp.json()["access_token"]
        yield {"Authorization": f"Bearer {token}"}
    finally:
        with engine.begin() as conn:
            _hapus_user(conn, _FAR_NUT_EMAIL)
        engine.dispose()


def pytest_collection_modifyitems(config, items):
    """Skip test live di sesi biasa (hanya jalan via `pytest -m live`)."""
    if config.getoption("-m") and "live" in config.getoption("-m"):
        return
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(pytest.mark.skip(reason="live probe: jalankan dengan -m live"))


# ---------------------------------------------------------------------------
# Jaring pengaman kebersihan DB kerja.
#
# Banyak test membuat user LANGSUNG ke database yang sama dengan aplikasi
# (mis. tests/test_auth.py) tanpa pembersihan. Akibatnya tabel `users` di DB
# demo menumpuk 1206 user sampah `@test.local` dan tidak lagi mencerminkan data
# demo (dibersihkan manual 2026-10-16). Fixture autouse di bawah menyapu sisa
# itu di AWAL dan AKHIR setiap sesi pytest, sehingga kebersihan tidak lagi
# bergantung pada tiap test mengurus dirinya sendiri — dan tetap jalan walau
# ada test yang gagal.
#
# Akun demo memakai domain `demo.local`, jadi TIDAK PERNAH cocok dengan pola
# `%@test.local`: sapuan ini tidak bisa menyentuh data demo.
# ---------------------------------------------------------------------------

_SISA_TEST_LIKE = "%@test.local"

# Dua sesi bisa menjalankan pytest BERSAMAAN pada DB yang sama. Sapuan tanpa
# batas umur pernah menghapus user milik suite yang sedang berjalan: login
# berikutnya di suite itu 401 "email atau password salah", dan approval yang
# menunjuk user terhapus memunculkan galat pagar yang terbaca seperti regresi.
# Karena itu sapuan hanya menyentuh sisa yang LEBIH TUA dari masa tenggang —
# user run berjalan (baru dibuat) tidak pernah tersentuh, sisa run yang mati
# tetap dibersihkan pada run berikutnya.
_SISA_UMUR_TENGGANG = "15 minutes"


def _sapu_sisa_test() -> int:
    """Hapus user sisa test + approval yang menahannya.

    Urutan penting: `approvals.approved_by` menunjuk users dengan aturan
    NO ACTION, jadi baris approval harus dibuang lebih dulu atau DELETE user
    akan gagal. Mengembalikan 0 bila tidak ada sisa / DB tidak terjangkau
    (sesi dijalankan dari host, di luar jaringan compose).
    """
    try:
        engine = create_engine(
            DSN_SYNC
        )
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "DELETE FROM approvals WHERE approved_by IN "
                        "(SELECT id FROM users WHERE email LIKE :p "
                        " AND created_at < now() - interval '"
                        + _SISA_UMUR_TENGGANG
                        + "')"
                    ),
                    {"p": _SISA_TEST_LIKE},
                )
                hasil = conn.execute(
                    text(
                        "DELETE FROM users WHERE email LIKE :p "
                        "AND created_at < now() - interval '"
                        + _SISA_UMUR_TENGGANG
                        + "'"
                    ),
                    {"p": _SISA_TEST_LIKE},
                )
            return int(hasil.rowcount or 0)
        finally:
            engine.dispose()
    except Exception as exc:  # jalur host tanpa Postgres: sapuan dilewati
        print(f"[conftest] sapu sisa test dilewati: {exc}")
        return 0


@pytest.fixture(scope="session", autouse=True)
def bersihkan_sisa_test():
    """Sapu user sisa test sebelum dan sesudah sesi (lihat catatan di atas)."""
    _sapu_sisa_test()
    yield
    sisa = _sapu_sisa_test()
    if sisa:
        print(f"[conftest] {sisa} user sisa test dibersihkan dari DB kerja")


# ---------------------------------------------------------------------------
# Jaring pengaman DERET DEMO KANONIK.
#
# `purge_demo_rows()` — dipakai `tests/test_timeseries_db.py` dan
# `tests/test_demo_timeseries_api.py` — menghapus SELURUH baris `origin='demo'`,
# termasuk deret kanonik 1 Sep–5 Nov (rencana 3.900 baris supply · 4.040 harga ·
# 660 rencana menu; terisi sebagai 3.870/4.010/590 baris demo karena stamp
# 8 Okt 12:00 dipegang baris kanonik) DAN peristiwa 8 Okt–5 Nov (290 kiriman ·
# 58 catatan limbah; kanonik 70/20 di 1–7 Okt tidak ikut dihitung).
# Ketika pemulihan di berkas tes itu gagal (dulu: teardown memakai token HTTP
# yang sudah tidak sah → 401), DB kerja tertinggal kosong: puluhan tes lain gagal
# berantai dan data presentasi juri lenyap (kejadian 2026-10-16 malam).
#
# Fixture di bawah mencatat jumlah baris demo di AWAL sesi dan memulihkannya di
# AKHIR sesi bila berkurang, memakai generator resmi yang sama — jadi satu sesi
# pytest tidak bisa lagi meninggalkan DB tanpa deret kanonik, walau ada tes yang
# gagal separuh jalan.
# ---------------------------------------------------------------------------


def _jumlah_deret_demo() -> dict[str, int]:
    """Jumlah baris `origin='demo'` per tabel; {} bila DB tidak terjangkau."""
    try:
        import asyncio

        from app.seed.timeseries import demo_data_status

        status = asyncio.run(demo_data_status())
        return {nama: int(nilai["demo"]) for nama, nilai in status["tables"].items()}
    except Exception as exc:  # jalur host tanpa Postgres: dilewati
        print(f"[conftest] status deret demo dilewati: {exc}")
        return {}


@pytest.fixture(scope="session", autouse=True)
def kunci_gerbang():
    """Satu suite pytest pada satu waktu untuk satu database.

    Semua tes memakai DB kerja yang sama dengan aplikasi demo. Dua suite
    bersamaan saling menghapus baris dan mencabut token, lalu menghasilkan
    kegagalan di berkas yang tidak disentuh siapa pun. Kalau suite lain sudah
    memegang kunci, berhenti dengan kode 3 dan pesan jelas — angka dari run
    bersamaan tidak boleh dipakai sebagai baseline.

    Di host tanpa Postgres kunci dilewati: test sisi agent tidak memakai DB.
    """
    import os

    dsn = dsn_psycopg(
        os.environ.get(
            "DATABASE_URL",
            DSN_ASYNC,
        )
    )
    try:
        pegangan = ambil_kunci(dsn)
    except Exception as exc:  # DB tidak terjangkau: host tanpa Postgres
        print(f"[conftest] kunci gerbang dilewati: {exc}")
        yield
        return

    if pegangan is None:
        pytest.exit(
            "suite pytest lain sedang memakai database ini "
            "(kunci gerbang dipegang). Tunggu sampai selesai lalu ulangi; "
            "hasil run bersamaan bukan baseline.",
            returncode=3,
        )
    assert pegangan is not None  # pytest.exit di atas sudah berhenti
    print("[conftest] kunci gerbang dipegang")
    try:
        yield
    finally:
        lepas_kunci(pegangan)


def _semai_demo_ringkas() -> None:
    """Aktivitas + keputusan demo + harga hari ini, TANPA batch `jakarta_lengkap`.

    Dipakai di awal sesi. `jakarta_lengkap.seed_batches` sengaja tidak ikut: ia
    menambah pemasok di luar data kanonik, dan invariant "seed demo tidak boleh
    menambah pemasok" (`test_demo_batch_pemasok_tunggal`) langsung merah. Modul
    pengadaan yang butuh batch kaya tetap memakai `_semai_kiriman_demo()` lewat
    `_MODUL_BUTUH_KANDIDAT`.
    """
    import asyncio
    from datetime import UTC, datetime

    async def _jalankan() -> None:
        from app.core.config import settings as _settings
        from app.db import create_engine as _engine
        from app.db import create_session_maker
        from app.seed.demo_activity import (
            seed_demo_activity,
            seed_demo_completed_decisions,
            seed_demo_daily_prices,
        )

        eng = _engine(_settings.database_url)
        try:
            async with create_session_maker(eng)() as sesi:
                sekarang = datetime.now(UTC)
                await seed_demo_activity(sesi, sekarang)
                await seed_demo_completed_decisions(sesi, sekarang)
                await seed_demo_daily_prices(sesi, sekarang)
                await sesi.commit()
        finally:
            await eng.dispose()

    asyncio.run(_jalankan())


def _ada_kiriman_demo_hari_ini() -> bool:
    """True bila ada batch `origin='demo'` bertanggal hari ini (WIB).

    Batch demo yang tertinggal di hari kemarin membuat keputusan demo, PO, dan
    metrik KPI "hari ini" kosong — persis kegagalan yang terukur pada gerbang
    21 Okt 2026. DB yang tak terjangkau dianggap "ada" agar tes tidak dihalangi.
    """
    import os

    try:
        dsn = dsn_psycopg(
            os.environ.get(
                "DATABASE_URL",
                DSN_ASYNC,
            )
        )
        engine = create_engine(dsn, pool_pre_ping=True)
        try:
            with engine.begin() as conn:
                n = conn.execute(
                    text(
                        "SELECT count(*) FROM batches "
                        "WHERE origin = 'demo' AND "
                        "(created_at AT TIME ZONE 'Asia/Jakarta')::date = "
                        "(now() AT TIME ZONE 'Asia/Jakarta')::date"
                    )
                ).scalar_one()
            return int(n) > 0
        finally:
            engine.dispose()
    except Exception as exc:  # host tanpa Postgres
        print(f"[conftest] cek kiriman demo hari ini dilewati: {exc}")
        return True


@pytest.fixture(scope="session", autouse=True)
def jaring_deret_demo(kunci_gerbang):
    """Pulihkan deret demo kanonik bila sesi ini menghabiskannya.

    Menyegarkan di AWAL sesi (bukan hanya per modul di `_MODUL_BUTUH_KANDIDAT`):
    modul di luar daftar itu dulu memakai baris yang sudah dibuang tes lain,
    sehingga `Event 1` kehabisan kandidat dan PO demo "belum ada".
    """
    awal = _jumlah_deret_demo()
    if not _ada_kiriman_demo_hari_ini():
        print("[conftest] menyegarkan aktivitas demo di awal sesi")
        _semai_demo_ringkas()
        awal = _jumlah_deret_demo()
    yield
    akhir = _jumlah_deret_demo()
    if not awal or not akhir:
        return
    if all(akhir.get(nama, 0) >= nilai for nama, nilai in awal.items()):
        return

    import asyncio

    from app.seed.timeseries import pastikan_deret_demo

    hasil = asyncio.run(pastikan_deret_demo())
    print(
        "[conftest] deret demo kanonik dipulihkan: "
        f"{hasil['sebelum']} -> {hasil['sesudah']} (harapan {hasil['harapan']})"
    )


# ---------------------------------------------------------------------------
# Jaring pengaman KIRIMAN DEMO (batch), bukan cuma deret timeseries.
#
# `purge_demo_rows()` dan tes yang menghapus batch demo (`test_demo_activity`,
# `test_seed_load_db`, `test_perluasan_kirim_limbah`, ...) membuang seluruh baris
# `origin='demo'` di tengah suite. Batch kanonik seed dijangkar `CANONICAL_REF`
# 8 Okt 12:00 UTC (lihat app/seed/seed_data.py), jadi beberapa hari setelah REF
# kesegaran telur turun di bawah `PASS_THRESHOLD` 0,85 (shelf 28 hari) dan TIDAK
# ada kandidat eligible. Tes yang memanggil Event 1 sesudahnya gagal dengan
# "tidak ada kandidat eligible untuk Event 1 (telur -> Jakarta)" — padahal tidak
# ada kode yang berubah (terukur 19 Okt 2026: 28 gagal, lalu 9 gagal setelah
# urutan purge pertama diperbaiki).
#
# Karena itu tes yang menuntut kandidat menyemai ulang kiriman demo lebih dulu,
# memakai generator resmi yang sama dengan tombol "Segarkan ke hari ini".
# ---------------------------------------------------------------------------

_MODUL_BUTUH_KANDIDAT = frozenset(
    {
        "test_action_boundary_e2e.py",
        "test_decision_read_endpoints.py",
        "test_demo_event1_api.py",
        "test_event1_e2e_acceptance.py",
        "test_event1_supervisor_flow.py",
        "test_event3_api.py",
        "test_evidence_consistency_wiring.py",
        "test_kpi_act_trace.py",
        "test_kpi_safe_delivered_cost.py",
        "test_peran_lanjutan_head_only.py",
        "test_s4_verifier_independence.py",
        "test_scope_matrix.py",
        "test_supervisor_narration.py",
        "test_supplier_procurement_eval.py",
        "test_demo_batch_pemasok_tunggal.py",
        "test_demo_harian.py",
        "test_api_domain_tools.py",
        # 26 Okt 2026: /balance/analyze & /evidence/fuse membangun kandidat dari
        # BATCH, bukan dari deret timeseries. Modul ini dulu ikut merah di suite
        # penuh ("minimal 1 rekomendasi") karena tes lain sudah mem-purge batch
        # `origin='demo'`; `pastikan_deret_demo()` tidak memulihkan batch.
        "test_tool_contracts.py",
    }
)


def _ada_kiriman_demo() -> bool:
    """True bila masih ada batch `origin='demo'`; True juga bila DB tak terjangkau."""
    import os

    try:
        dsn = dsn_psycopg(
            os.environ.get(
                "DATABASE_URL",
                DSN_ASYNC,
            )
        )
        engine = create_engine(dsn, pool_pre_ping=True)
        try:
            with engine.begin() as conn:
                n = conn.execute(
                    text("SELECT count(*) FROM batches WHERE origin = 'demo'")
                ).scalar_one()
            return int(n) > 0
        finally:
            engine.dispose()
    except Exception as exc:  # host tanpa Postgres: jangan menghalangi tes
        print(f"[conftest] cek kiriman demo dilewati: {exc}")
        return True


def _semai_kiriman_demo() -> None:
    """Semai kiriman demo (batch segar) + keputusan selesai, sekali jalan."""
    import asyncio
    from datetime import UTC, datetime

    async def _jalankan() -> None:
        from app.core.config import settings as _settings
        from app.db import create_engine as _engine
        from app.db import create_session_maker
        from app.seed.demo_activity import (
            seed_demo_activity,
            seed_demo_completed_decisions,
            seed_demo_daily_prices,
        )
        from app.seed.jakarta_lengkap import seed_batches as _seed_batches
        from app.seed.jakarta_lengkap import seed_prices as _seed_prices

        eng = _engine(_settings.database_url)
        try:
            async with create_session_maker(eng)() as sesi:
                sekarang = datetime.now(UTC)
                await seed_demo_activity(sesi, sekarang)
                await seed_demo_completed_decisions(sesi, sekarang)
                await seed_demo_daily_prices(sesi, sekarang)
                # Batch kaya `jakarta_lengkap` (mis. telur Jakarta dari pemasok
                # yang TIDAK dikecualikan) ikut dipulihkan; tanpa ini modul
                # pengadaan hanya melihat batch kanonik 8 Okt yang sudah basi.
                await _seed_batches(sesi, sekarang)
                await _seed_prices(sesi, sekarang)
                await sesi.commit()
        finally:
            await eng.dispose()

    try:
        asyncio.run(_jalankan())
        print("[conftest] kiriman demo disemai ulang (batch segar untuk Event 1)")
    except Exception as exc:  # biarkan tes melaporkan sendiri kegagalannya
        print(f"[conftest] semai kiriman demo dilewati: {exc}")


@pytest.fixture(scope="module", autouse=True)
def jaga_deret_demo_utuh():
    """Bangun ulang deret demo bila modul sebelumnya sudah menghabiskannya.

    Tes yang mem-purge baris `origin='demo'` (dan rollback yang tidak sempat
    jalan) membuat modul berikutnya melihat DB kosong: agenda 2 Okt kehilangan
    `supply_records`, Event 1 kehabisan kandidat, PO demo "belum ada". Pemeriksaannya
    satu query ringan; generator hanya dijalankan bila deret memang habis.
    """
    try:
        jumlah = _jumlah_deret_demo()
    except Exception as exc:  # DB tak terjangkau: jangan halangi tes
        print(f"[conftest] cek deret demo dilewati: {exc}")
        return
    if jumlah:
        # Jangan hanya memeriksa `supply_records`: modul yang mem-purge bisa
        # meninggalkan tabel lain kosong (menu/limbah/kiriman), dan tes KPI
        # membaca tabel-tabel itu — gejalanya "angka 0" yang tampak seperti bug.
        kosong = sorted(nama for nama, n in jumlah.items() if int(n) == 0)
        if kosong:
            import asyncio

            from app.seed.timeseries import pastikan_deret_demo

            print(
                "[conftest] deret demo tidak utuh "
                f"({', '.join(kosong)}) — dibangun ulang sebelum modul ini"
            )
            asyncio.run(pastikan_deret_demo())


@pytest.fixture(scope="module", autouse=True)
def jaga_kiriman_demo(request):
    """Pastikan batch demo ada SEBELUM tes yang menuntut kandidat Event 1."""
    import os

    nama = os.path.basename(str(request.path))
    if nama not in _MODUL_BUTUH_KANDIDAT:
        yield
        return
    # Modul pengadaan butuh batch SEGAR, bukan sekadar "ada batch demo": suite
    # lain mem-purge/membasi-kan batch, dan batch lama tetap terhitung ada.
    # Selalu semai ulang (idempoten, tanggal diperbarui) untuk modul ini.
    if nama == "test_supplier_procurement_eval.py" or not _ada_kiriman_demo():
        _semai_kiriman_demo()
    yield
