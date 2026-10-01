"""Konfigurasi koleksi test backend.

Pemisahan test host vs container (temuan audit feasibility Sprint 1):
beberapa test Sprint 0 bersifat host-only karena mengimpor modul dari
direktori repo yang tidak di-mount ke container (agent/, infra/).
Di dalam container, modul-modul itu dikoleksi-skip; di host tetap jalan.
"""

from pathlib import Path

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
