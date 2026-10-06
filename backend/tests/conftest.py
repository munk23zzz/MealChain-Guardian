"""Konfigurasi koleksi test backend.

Pemisahan test host vs container (temuan audit feasibility Sprint 1):
beberapa test Sprint 0 bersifat host-only karena mengimpor modul dari
direktori repo yang tidak di-mount ke container (agent/, infra/).
Di dalam container, modul-modul itu dikoleksi-skip; di host tetap jalan.
"""

from pathlib import Path

import pytest

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
MODEL_ENV_KEYS += [f"SUPERVISOR_MODEL_FALLBACK_{i}" for i in range(1, 10)]
MODEL_ENV_KEYS += ["VERIFIER_MODEL_PRIMARY"]
MODEL_ENV_KEYS += [f"VERIFIER_MODEL_FALLBACK_{i}" for i in range(1, 10)]
MODEL_ENV_KEYS += ["FORECAST_MODEL"]
MODEL_ENV_KEYS += [f"FORECAST_MODEL_FALLBACK_{i}" for i in range(1, 10)]


@pytest.fixture(autouse=True)
def _isolate_model_env(monkeypatch, request):
    if request.node.get_closest_marker("live"):
        yield  # test live: env asli dipertahankan
        return
    for key in MODEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield


def pytest_collection_modifyitems(config, items):
    """Skip test live di sesi biasa (hanya jalan via `pytest -m live`)."""
    if config.getoption("-m") and "live" in config.getoption("-m"):
        return
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(pytest.mark.skip(reason="live probe: jalankan dengan -m live"))
