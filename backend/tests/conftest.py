"""Konfigurasi koleksi test backend.

Pemisahan test host vs container (temuan audit feasibility Sprint 1):
beberapa test Sprint 0 bersifat host-only karena mengimpor modul dari
direktori repo yang tidak di-mount ke container (agent/, infra/).
Di dalam container, modul-modul itu dikoleksi-skip; di host tetap jalan.
"""

from pathlib import Path

import bcrypt
import pytest
from sqlalchemy import create_engine, text

# Test yang butuh modul host-only (agent/, infra/) atau file root repo
# (compose, .env.example, .gitignore, struktur) — tidak tersedia di container.
HOST_ONLY_MODULES = [
    "test_supervisor_agent.py",
    "test_verify_agentcore_access.py",
    "test_verify_bedrock_access.py",
    "test_compose_contract.py",
    "test_environment_contract.py",
    "test_structure.py",
]

# Test yang butuh infrastruktur Docker (Postgres via psycopg sync, env container).
DOCKER_ONLY_MODULES = [
    "test_master_data_schema.py",
]

_backend_dir = Path(__file__).resolve().parents[1]
_repo_root = _backend_dir.parent

_host_sources_present = all(
    (_repo_root / dirname).exists() for dirname in ("agent", "infra")
)

if _host_sources_present:
    collect_ignore = list(DOCKER_ONLY_MODULES)
else:
    collect_ignore = list(HOST_ONLY_MODULES)


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


@pytest.fixture(scope="session")
def auth_headers():
    engine = create_engine(
        "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
    )
    pw = "TestPass#2026"
    digest = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            # Idempoten: bersihkan sisa run sebelumnya bila ada.
            conn.execute(
                text("DELETE FROM users WHERE email = :e"), {"e": _LEGACY_RBAC_EMAIL}
            )
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
            conn.execute(
                text("DELETE FROM users WHERE email = :e"), {"e": _LEGACY_RBAC_EMAIL}
            )
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


@pytest.fixture(scope="session")
def monitor_headers():
    engine = create_engine(
        "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
    )
    pw = "TestPass#2026"
    digest = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM users WHERE email = :e"), {"e": _MONITOR_EMAIL}
            )
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
            conn.execute(
                text("DELETE FROM users WHERE email = :e"), {"e": _MONITOR_EMAIL}
            )
        engine.dispose()


_FAR_NUT_EMAIL = "pytest-far-nutritionist@test.local"


@pytest.fixture(scope="session")
def far_nutritionist_headers():
    """Ahli gizi di SPPG LAIN (Bogor) — untuk menguji aturan cakupan.

    Sengaja dibuat di sini, bukan memakai akun demo: sejak Ruling 2026-10-14
    KEDUA akun approver demo berada di satu SPPG (Jakarta) supaya matriks AND
    bisa didemokan. Tes aturan scope karena itu tidak boleh bergantung pada
    lokasi akun demo — ia menyiapkan sendiri peran "SPPG lain".
    """
    engine = create_engine(
        "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
    )
    pw = "TestPass#2026"
    digest = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM users WHERE email = :e"), {"e": _FAR_NUT_EMAIL}
            )
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
            conn.execute(
                text("DELETE FROM users WHERE email = :e"), {"e": _FAR_NUT_EMAIL}
            )
        engine.dispose()


def pytest_collection_modifyitems(config, items):
    """Skip test live di sesi biasa (hanya jalan via `pytest -m live`)."""
    if config.getoption("-m") and "live" in config.getoption("-m"):
        return
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(pytest.mark.skip(reason="live probe: jalankan dengan -m live"))
