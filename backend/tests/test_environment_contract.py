"""Kontrak environment Sprint 0 (S0-08).

- `.env.example` wajib memuat semua key yang dibutuhkan kontrak Sprint 0
- Tidak boleh ada secret nyata / pola kredensial AWS di file template
- DEMO_MODE WAJIB default false (Rules.md §1.4)
- Semua SAP mode WAJIB default mock (Architecture.md §9.2)
- .gitignore wajib mengabaikan .env
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = REPO_ROOT / ".env.example"
GITIGNORE = REPO_ROOT / ".gitignore"

REQUIRED_KEYS = [
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_PORT",
    "DATABASE_URL",
    "JWT_SECRET",
    "JWT_ALGORITHM",
    "JWT_EXPIRE_MINUTES",
    "AWS_REGION",
    "AWS_PROFILE",
    "SUPERVISOR_MODEL_PRIMARY",
    "SUPERVISOR_MODEL_FALLBACK",
    "AGENTCORE_RUNTIME_ARN",
    "AGENTCORE_GATEWAY_URL",
    "SAP_AI_CORE_AUTH_URL",
    "SAP_AI_CORE_API_URL",
    "SAP_AI_CORE_CLIENT_ID",
    "SAP_AI_CORE_CLIENT_SECRET",
    "VERIFIER_MODEL_PRIMARY",
    "VERIFIER_MODEL_FALLBACK_1",
    "VERIFIER_MODEL_FALLBACK_2",
    "FORECAST_MODEL",
    "SAP_MATERIAL_STOCK_MODE",
    "SAP_PURCHASE_ORDER_MODE",
    "SAP_MATERIAL_DOCUMENT_MODE",
    "SAP_BUSINESS_PARTNER_MODE",
    "SAP_PRODUCT_MASTER_MODE",
    "DEMO_MODE",
    "DEBUG",
    "NEXT_PUBLIC_API_URL",
    "BACKEND_PORT",
    "FRONTEND_PORT",
    "MOCK_SAP_PORT",
]

SAP_MODE_KEYS = [k for k in REQUIRED_KEYS if k.startswith("SAP_") and k.endswith("_MODE")]

SECRET_PATTERNS = [
    "AKIA",
    "aws_access_key_id=",
    "aws_secret_access_key=",
]


def _env_lines() -> list[str]:
    return ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()


def _env_value(key: str) -> str:
    for line in _env_lines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def test_env_example_contains_all_required_keys() -> None:
    lines = _env_lines()
    keys = {
        line.split("=", 1)[0]
        for line in lines
        if "=" in line and not line.strip().startswith("#")
    }
    missing = [k for k in REQUIRED_KEYS if k not in keys]
    assert not missing, f"Key kontrak hilang di .env.example: {missing}"


def test_demo_mode_defaults_to_false() -> None:
    assert _env_value("DEMO_MODE") == "false"


def test_all_sap_modes_default_to_mock() -> None:
    for key in SAP_MODE_KEYS:
        assert _env_value(key) == "mock", f"{key} harus default mock"


def test_env_example_has_no_real_credentials() -> None:
    content = ENV_EXAMPLE.read_text(encoding="utf-8").lower()
    for pattern in SECRET_PATTERNS:
        assert pattern.lower() not in content, f"Pola secret terdeteksi: {pattern}"


def test_gitignore_excludes_env_file() -> None:
    content = GITIGNORE.read_text(encoding="utf-8")
    assert any(line.strip() == ".env" for line in content.splitlines())
