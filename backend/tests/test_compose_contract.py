"""Kontrak docker-compose.yml Sprint 0: tepat 4 service sesuai plan."""

from pathlib import Path

import yaml

COMPOSE_FILE = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def _load_compose() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def test_compose_has_exactly_four_services() -> None:
    compose = _load_compose()
    services = set(compose["services"].keys())
    assert services == {"postgres", "backend", "frontend", "mock-sap"}


def test_postgres_is_major_version_16() -> None:
    compose = _load_compose()
    image = compose["services"]["postgres"]["image"]
    assert image.startswith("postgres:16")


def test_demo_mode_is_not_enabled_by_default() -> None:
    compose = _load_compose()
    for name, svc in compose["services"].items():
        env = svc.get("environment") or {}
        demo = env.get("DEMO_MODE", "false")
        assert str(demo).lower() != "true", f"DEMO_MODE aktif di service {name}"


def test_mock_sap_runs_mock_service_app() -> None:
    compose = _load_compose()
    cmd = compose["services"]["mock-sap"]["command"]
    command = cmd if isinstance(cmd, str) else " ".join(cmd)
    assert "app.sap_integration.mock_service:app" in command


def test_backend_uses_asyncpg_url() -> None:
    compose = _load_compose()
    env = compose["services"]["backend"]["environment"]
    database_url = env["DATABASE_URL"] if isinstance(env, dict) else str(env)
    assert "postgresql+asyncpg://" in database_url


def test_backend_mounts_data_seed_readonly() -> None:
    compose = _load_compose()
    volumes = compose["services"]["backend"]["volumes"]
    assert any(
        v.startswith("./data:") and v.endswith(":ro") for v in volumes
    ), "backend wajib mount ./data read-only untuk seed"


def test_postgres_host_port_not_5432_default() -> None:
    """Port host 5432 dipakai postgres proyek lain — MealChain wajib 15432."""
    compose = _load_compose()
    ports = compose["services"]["postgres"]["ports"]
    joined = " ".join(str(p) for p in ports)
    assert "15432:5432" in joined


def test_mock_sap_service_exposed_port_8001() -> None:
    compose = _load_compose()
    ports = compose["services"]["mock-sap"]["ports"]
    joined = " ".join(str(p) for p in ports)
    assert "8001:8001" in joined
