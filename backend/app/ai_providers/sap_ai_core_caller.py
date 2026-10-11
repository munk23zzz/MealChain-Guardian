"""Caller SAP AI Core (S4-10) — LLM (`/invoke`) dan SAP-RPT-1.6 (`/predict`).

Kontrak yang DIUKUR live 2026-10-11 (bukan dugaan; probe tersimpan di sesi):
- Token: `POST {SAP_AI_CORE_AUTH_URL}/oauth/token`, grant `client_credentials`,
  Basic auth `client_id:client_secret` → `{access_token, expires_in}`.
- LLM (`anthropic--claude-4.6-sonnet`): `POST {API}/v2/inference/deployments/{id}/invoke`
  dengan body **gaya Bedrock** (`anthropic_version`, `max_tokens`, `messages`);
  jawaban teks digabung dari `content[].text`. Subpath `chat/completions` dan
  `messages` dijawab `Subpath ... is not allowed` — jangan dipakai.
- SAP-RPT-1.6: `POST {API}/v2/inference/deployments/{id}/predict` dengan
  `{"prediction_config": {"target_columns": [{"name": <kolom>,
  "prediction_placeholder": null}]}, "rows": [...]}`. WAJIB ada baris QUERY
  (kolom target = placeholder) — tanpa itu 400 "No query rows provided".
  Jawaban: `predictions[i][kolom][0] = {"prediction", "confidence_interval"}`.

Aturan keras (sejalan dengan `Rules.md`/`ONBOARDING.md`):
- Rahasia HANYA di header Authorization; tidak pernah masuk URL, prompt, log,
  atau pesan error (`_sanitize` menyapu kemunculannya dari teks error).
- Angka total forecast DIJUMLAHKAN KODE secara deterministik, bukan oleh model.
- env tidak lengkap → `RuntimeError` saat build (jujur, TANPA panggilan jaringan),
  sehingga rantai fallback bisa mencatat slot mati dan lanjut.
- HTTP non-200 → `SapAiCoreError` dengan `status_code` (rantai memutuskan retry).
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.error
import urllib.parse
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Mapping
from urllib.request import Request, urlopen

DEFAULT_TARGET_COLUMN = "demand_kg"
DEFAULT_MAX_TOKENS = 2048
ANTHROPIC_VERSION = "bedrock-2023-05-31"
TOKEN_EXPIRY_MARGIN_SECONDS = 60
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_RESOURCE_GROUP = "default"

ENV_AUTH_URL = "SAP_AI_CORE_AUTH_URL"
ENV_API_URL = "SAP_AI_CORE_API_URL"
ENV_CLIENT_ID = "SAP_AI_CORE_CLIENT_ID"
ENV_CLIENT_SECRET = "SAP_AI_CORE_CLIENT_SECRET"
ENV_RESOURCE_GROUP = "SAP_AI_CORE_RESOURCE_GROUP"
ENV_DEPLOYMENT_LLM = "SAP_AI_CORE_DEPLOYMENT_ID_LLM"
ENV_DEPLOYMENT_RPT = "SAP_AI_CORE_DEPLOYMENT_ID_RPT"

_PURPOSE_ENV = {"llm": ENV_DEPLOYMENT_LLM, "rpt": ENV_DEPLOYMENT_RPT}


class SapAiCoreError(RuntimeError):
    """Kegagalan SAP AI Core (status_code HTTP bila ada)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class SapAiCoreConfig:
    """Konfigurasi klien dari env (satu sumber, tanpa default rahasia)."""

    auth_url: str
    api_url: str
    client_id: str
    client_secret: str
    resource_group: str = DEFAULT_RESOURCE_GROUP
    deployment_llm: str = ""
    deployment_rpt: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "SapAiCoreConfig":
        sumber = os.environ if env is None else env
        nilai = {}
        for kunci in (
            ENV_AUTH_URL,
            ENV_API_URL,
            ENV_CLIENT_ID,
            ENV_CLIENT_SECRET,
            ENV_DEPLOYMENT_LLM,
            ENV_DEPLOYMENT_RPT,
        ):
            nilai[kunci] = (sumber.get(kunci) or "").strip()
        kosong = [k for k, v in nilai.items() if not v]
        if kosong:
            raise RuntimeError(
                "SAP AI Core belum dikonfigurasi sepenuhnya: "
                + ", ".join(kosong)
            )
        return cls(
            auth_url=nilai[ENV_AUTH_URL].rstrip("/"),
            api_url=nilai[ENV_API_URL].rstrip("/"),
            client_id=nilai[ENV_CLIENT_ID],
            client_secret=nilai[ENV_CLIENT_SECRET],
            resource_group=(
                (sumber.get(ENV_RESOURCE_GROUP) or "").strip() or DEFAULT_RESOURCE_GROUP
            ),
            deployment_llm=nilai[ENV_DEPLOYMENT_LLM],
            deployment_rpt=nilai[ENV_DEPLOYMENT_RPT],
        )

    def deployment(self, purpose: str) -> str:
        """Id deployment untuk `llm`/`rpt` (purpose tak dikenal → error)."""
        if purpose not in _PURPOSE_ENV:
            raise SapAiCoreError(f"purpose tidak dikenal: {purpose}")
        nilai = self.deployment_llm if purpose == "llm" else self.deployment_rpt
        if not nilai:
            raise RuntimeError(f"{_PURPOSE_ENV[purpose]} belum diisi")
        return nilai


def _sanitize(text: str, *rahasia: str) -> str:
    """Buang kemunculan rahasia dari teks yang akan dipakai di pesan error."""
    hasil = text
    for item in rahasia:
        if item and len(item) >= 4:
            hasil = hasil.replace(item, "[REDACTED]")
    return hasil


def default_transport(
    method: str, url: str, headers: dict, body: bytes | None, timeout: float
) -> tuple[int, bytes]:
    """Transport HTTP standar (urllib). HTTPError → (status, body), bukan raise."""
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:  # status dipertahankan untuk taksonomi
        return exc.code, exc.read()


def _day_labels(count: int) -> list[str]:
    """Label hari (ISO) untuk `count` baris, berakhir hari ini (deterministik)."""
    akhir = date.today()
    return [
        (akhir - timedelta(days=count - 1 - i)).isoformat() for i in range(count)
    ]


class SapAiCoreClient:
    """Klien tipis SAP AI Core: token + invoke (LLM) + predict (RPT-1.6)."""

    def __init__(
        self,
        config: SapAiCoreConfig,
        *,
        transport: Callable[..., tuple[int, bytes]] | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._config = config
        self._transport = transport or default_transport
        self._timeout = timeout
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._lock = threading.Lock()

    # --- internal ---------------------------------------------------------

    def _rahasia(self) -> tuple[str, str]:
        return self._config.client_secret, self._config.client_id

    def _post(
        self,
        url: str,
        payload: dict | None,
        headers: dict,
        *,
        raw_body: bytes | None = None,
    ) -> bytes:
        """POST (JSON atau body mentah); non-200 → SapAiCoreError.

        `raw_body` dipakai endpoint form-urlencoded (`/oauth/token`): SAP
        MENOLAK 400 `invalid_request` bila `grant_type` tidak dikirim di body.
        """
        if raw_body is not None:
            body = raw_body
        else:
            body = None if payload is None else json.dumps(payload).encode("utf-8")
        try:
            status, raw = self._transport(
                "POST", url, headers, body, self._timeout
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SapAiCoreError(
                _sanitize(f"{type(exc).__name__}: {exc}", *self._rahasia()),
                status_code=None,
            ) from exc
        if status != 200:
            raise SapAiCoreError(f"sap ai core http {status}", status_code=status)
        return raw

    def _auth_headers(self, token: str) -> dict:
        """Header inference untuk SATU token yang sudah diambil.

        Token diperoleh SEKALI di pemanggil (`invoke`/`predict`) — memanggil
        `self.token()` di sini akan mengambil token lagi ketika masa berlakunya
        sudah lewat margin, dan itu membuat urutan request/response kacau.
        """
        return {
            "Authorization": f"Bearer {token}",
            "AI-Resource-Group": self._config.resource_group,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # --- token ------------------------------------------------------------

    def token(self) -> str:
        """Token OAuth (di-cache sampai ~1 menit sebelum kedaluwarsa)."""
        with self._lock:
            sekarang = time.monotonic()
            if self._token and sekarang < self._token_expiry:
                return self._token
            dasar = base64.b64encode(
                f"{self._config.client_id}:{self._config.client_secret}".encode()
            ).decode()
            raw = self._post(
                f"{self._config.auth_url}/oauth/token",
                None,
                {
                    "Authorization": f"Basic {dasar}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                raw_body=urllib.parse.urlencode(
                    {"grant_type": "client_credentials"}
                ).encode("utf-8"),
            )
            try:
                data = json.loads(raw.decode("utf-8"))
                token = data["access_token"]
                expires_in = float(data.get("expires_in") or 3600)
            except (ValueError, KeyError, TypeError) as exc:
                raise SapAiCoreError(
                    "struktur response token tidak dikenal"
                ) from exc
            if not isinstance(token, str) or not token:
                raise SapAiCoreError("token kosong dari SAP AI Core")
            self._token = token
            self._token_expiry = sekarang + max(
                0.0, expires_in - TOKEN_EXPIRY_MARGIN_SECONDS
            )
            return token

    # --- LLM --------------------------------------------------------------

    def invoke(
        self,
        prompt: str,
        *,
        deployment_id: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        system: str | None = None,
    ) -> str:
        """Panggil LLM AI Core (`/invoke`, body gaya Bedrock) → teks jawaban."""
        dep = deployment_id or self._config.deployment("llm")
        payload = {
            "anthropic_version": ANTHROPIC_VERSION,
            "max_tokens": int(max_tokens),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        raw = self._post(
            f"{self._config.api_url}/v2/inference/deployments/{dep}/invoke",
            payload,
            self._auth_headers(self.token()),
        )
        try:
            data = json.loads(raw.decode("utf-8"))
            bagian = data["content"]
            teks = "".join(
                blok.get("text", "")
                for blok in bagian
                if isinstance(blok, dict) and blok.get("type") in (None, "text")
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise SapAiCoreError("struktur response invoke tidak dikenal") from exc
        if not isinstance(teks, str) or not teks:
            raise SapAiCoreError("response invoke tanpa teks")
        return teks

    # --- RPT-1.6 ----------------------------------------------------------

    def predict(
        self,
        history: list[float],
        horizon: int,
        *,
        target_column: str = DEFAULT_TARGET_COLUMN,
        deployment_id: str | None = None,
    ) -> dict:
        """Prediksi tabular RPT-1.6 → `{predictions, total_kg, confidence}`.

        Total dijumlahkan KODE. `confidence` DITURUNKAN dari
        `confidence_interval` milik model (bukan angka yang diklaim model) —
        `1 - (rata-rata setengah lebar / rata-rata prediksi)`, dijepit 0..1.
        """
        if not history:
            raise SapAiCoreError("riwayat demand kosong; tanpa baris konteks")
        if int(horizon) < 1:
            raise SapAiCoreError("horizon minimal 1 hari")

        dep = deployment_id or self._config.deployment("rpt")
        jumlah = len(history) + int(horizon)
        label = _day_labels(jumlah)
        rows = [
            {"day": label[i], target_column: float(v)}
            for i, v in enumerate(history)
        ]
        rows += [
            {"day": label[len(history) + i], target_column: None}
            for i in range(int(horizon))
        ]
        payload = {
            "prediction_config": {
                "target_columns": [
                    {"name": target_column, "prediction_placeholder": None}
                ]
            },
            "rows": rows,
        }
        raw = self._post(
            f"{self._config.api_url}/v2/inference/deployments/{dep}/predict",
            payload,
            self._auth_headers(self.token()),
        )

        try:
            data = json.loads(raw.decode("utf-8"))
            entri = data["predictions"]
        except (ValueError, KeyError, TypeError) as exc:
            raise SapAiCoreError("struktur response predict tidak dikenal") from exc

        prediksi: list[float] = []
        interval: list[tuple[float, float]] = []
        for item in entri:
            sel = item.get(target_column) if isinstance(item, dict) else None
            if not isinstance(sel, list) or not sel or not isinstance(sel[0], dict):
                raise SapAiCoreError("response predict tanpa kolom target")
            nilai = sel[0].get("prediction")
            if not isinstance(nilai, (int, float)) or isinstance(nilai, bool):
                raise SapAiCoreError("prediction bukan angka")
            prediksi.append(float(nilai))
            batas = sel[0].get("confidence_interval")
            if (
                isinstance(batas, list)
                and len(batas) == 2
                and all(isinstance(x, (int, float)) for x in batas)
            ):
                interval.append((float(batas[0]), float(batas[1])))

        if not prediksi:
            raise SapAiCoreError("response predict kosong")

        total = sum(prediksi)
        confidence: float | None = None
        if len(interval) == len(prediksi):
            rata_pred = sum(prediksi) / len(prediksi)
            setengah = sum((hi - lo) / 2.0 for lo, hi in interval) / len(interval)
            if rata_pred > 0:
                confidence = max(0.0, min(1.0, 1.0 - setengah / rata_pred))
        return {
            "predictions": prediksi,
            "total_kg": total,
            "confidence": confidence,
        }


# --- factory: kontrak rantai `Callable[[str], str]` -------------------------


def _client_atau_build(
    cfg: SapAiCoreConfig | None, client: SapAiCoreClient | None
) -> SapAiCoreClient:
    if client is not None:
        return client
    return SapAiCoreClient(cfg or SapAiCoreConfig.from_env())


def build_llm_caller(
    *,
    cfg: SapAiCoreConfig | None = None,
    client: SapAiCoreClient | None = None,
    deployment_id: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Callable[[str], str]:
    """Caller prompt → teks untuk LLM AI Core (rantai verifier)."""
    aktif = _client_atau_build(cfg, client)

    def _call(prompt: str) -> str:
        return aktif.invoke(prompt, deployment_id=deployment_id, max_tokens=max_tokens)

    return _call


def build_rpt_caller(
    *,
    cfg: SapAiCoreConfig | None = None,
    client: SapAiCoreClient | None = None,
    deployment_id: str | None = None,
    target_column: str = DEFAULT_TARGET_COLUMN,
) -> Callable[[str], str]:
    """Caller prompt-forecast → JSON `forecast_qty_kg`/`confidence` (RPT-1.6).

    Prompt yang dipakai `forecast_client._build_prompt` berbentuk JSON
    (`history_daily_kg`, `horizon_days`); prompt yang tidak terbaca ditolak
    TANPA panggilan jaringan supaya rantai bisa jatuh ke fallback jujur.
    """
    aktif = _client_atau_build(cfg, client)

    def _call(prompt: str) -> str:
        try:
            data = json.loads(prompt)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise SapAiCoreError(
                "prompt forecast bukan JSON; RPT-1.6 butuh history_daily_kg"
            ) from exc
        if not isinstance(data, dict):
            raise SapAiCoreError("prompt forecast bukan objek JSON")
        history = data.get("history_daily_kg")
        horizon = data.get("horizon_days")
        if not isinstance(history, list) or not history:
            raise SapAiCoreError("prompt forecast tanpa history_daily_kg")
        if not isinstance(horizon, int) or isinstance(horizon, bool):
            raise SapAiCoreError("prompt forecast tanpa horizon_days")
        hasil = aktif.predict(
            [float(v) for v in history],
            horizon,
            target_column=target_column,
            deployment_id=deployment_id,
        )
        keluaran = {"forecast_qty_kg": hasil["total_kg"]}
        if hasil["confidence"] is not None:
            keluaran["confidence"] = hasil["confidence"]
        return json.dumps(keluaran)

    return _call
