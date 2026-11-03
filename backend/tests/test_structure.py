"""Struktur Sprint 0 harus sesuai Architecture.md §4."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_required_sprint_zero_directories_exist() -> None:
    required = [
        "agent/prompts",
        "backend/app/api",
        "backend/app/core",
        "backend/app/models",
        "backend/app/sap_integration",
        "backend/tests",
        "data/seed",
        "frontend/app",
        "infra/aws",
        "infra/docker",
    ]
    missing = [p for p in required if not (REPO_ROOT / p).is_dir()]
    assert not missing, f"Struktur Sprint 0 belum lengkap: {missing}"
