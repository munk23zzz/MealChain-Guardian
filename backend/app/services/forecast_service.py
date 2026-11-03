"""Satu pintu peramalan kebutuhan (SAP-RPT-1.6 → cadangan statistik).

Kenapa modul ini ada
--------------------
Sebelumnya tiga jalur memanggil `run_forecast` sendiri-sendiri (endpoint
`/demand/forecast`, orkestrator Event 1, orkestrator pengadaan demo). Tiga salinan
logika berarti tiga tempat yang bisa menyimpang: satu membatasi waktu, dua tidak;
satu memakai 3 titik riwayat, dua memakai seluruh riwayat.

Modul ini adalah SATU-SATUNYA tempat yang boleh memanggil `run_forecast` dan
membangun pemanggil SAP AI Core. Ia menambahkan yang sebelumnya tidak ada:

- jendela riwayat yang sama untuk semua jalur (28 hari terakhir, tanpa baris
  bertanggal masa depan),
- ambang minimum riwayat (7 titik) — di bawah itu model tabular tidak dipanggil,
- cache TTL per (lokasi, komoditas, horizon, tanggal jendela) supaya satu
  halaman tidak memicu puluhan inferensi berbayar,
- batas panggilan per menit dan circuit breaker sederhana,
- log terstruktur + penghitung untuk audit,
- pembulatan 2 desimal sebelum angka keluar dari service.

Batas peran (`Rules.md` §1.1): modul ini HANYA menghasilkan angka kebutuhan.
Ia tidak boleh dipakai oleh — dan tidak mengimpor — modul biaya, kesegaran, atau
keamanan pangan. Ada tes arsitektur yang menegakkan itu
(`tests/test_forecast_role_boundary.py`).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_providers.forecast_client import run_forecast, sap_rpt_caller_from_env
from app.core.forecasting_fallback import statistical_forecast
from app.core.kpi import quantize2
from app.models import DemandRecord

log = logging.getLogger(__name__)

#: Jendela riwayat yang dikirim ke model (hari terakhir).
HISTORY_DAYS = 28
#: Di bawah ini model tabular tidak dipanggil: datanya terlalu tipis.
MIN_HISTORY = 7
#: Label sumber yang boleh muncul di respons — jangan menambah tanpa kontrak.
SUMBER_MODEL = "SAP-RPT-1.6"
SUMBER_CADANGAN = "statistical_fallback"

#: Nilai `FORECAST_PROVIDER` yang mematikan panggilan model (rem biaya).
_PROVIDER_MATI = {"statistical", "statistik", "off", "matikan"}

_DARI_ENV = object()


def _env_int(nama: str, bawaan: int) -> int:
    try:
        return int(os.getenv(nama, str(bawaan)))
    except ValueError:
        return bawaan


def _env_float(nama: str, bawaan: float) -> float:
    try:
        return float(os.getenv(nama, str(bawaan)))
    except ValueError:
        return bawaan


@dataclass
class ForecastHasil:
    """Hasil peramalan + label sumber yang jujur + jejak audit."""

    qty_kg: float | None
    method: str
    source: str
    fallback_used: bool
    confidence: float | None = None
    sample_count: int = 0
    window_days: int = HISTORY_DAYS
    cache_hit: bool = False
    reason: str | None = None
    attempts: list = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "forecast_qty_kg": self.qty_kg,
            "method": self.method,
            "source": self.source,
            "confidence": self.confidence,
            "fallback_used": self.fallback_used,
            "sample_count": self.sample_count,
            "cache_hit": self.cache_hit,
        }


# ---------------------------------------------------------------- status proses
_cache: dict[tuple, tuple[float, ForecastHasil]] = {}
_lock = threading.Lock()
_panggilan: deque[float] = deque()
_breakers: dict[str, dict[str, float]] = {}
_counter = {
    "forecast_calls_total": 0,
    "forecast_fallback_total": 0,
    "forecast_cache_hit_total": 0,
    "forecast_breaker_open_total": 0,
}


def reset_state() -> None:
    """Kosongkan cache/penghitung (dipakai tes; juga saat restart)."""
    with _lock:
        _cache.clear()
        _panggilan.clear()
        _breakers.clear()
        for k in _counter:
            _counter[k] = 0


def statistik() -> dict[str, Any]:
    """Penghitung in-process + status konfigurasi untuk `/health`.

    Tanpa secret: hanya angka dan boolean. `sap_rpt_configured` sudah cukup bagi
    operator/juri untuk membedakan "RPT tersambung" dari "selalu statistik".
    """
    with _lock:
        angka: dict[str, Any] = dict(_counter)
    angka["sap_rpt_configured"] = sap_rpt_caller_from_env() is not None
    angka["cache_entries"] = len(_cache)
    angka["breaker_open"] = sum(
        1 for b in _breakers.values() if b["open_until"] > time.monotonic()
    )
    return angka


def _diizinkan_memanggil() -> tuple[bool, str | None]:
    """Batas panggilan per menit. False = jangan sentuh jaringan."""
    batas = _env_int("FORECAST_MAX_CALLS_PER_MINUTE", 20)
    if batas <= 0:
        return True, None
    sekarang = time.monotonic()
    with _lock:
        while _panggilan and sekarang - _panggilan[0] > 60:
            _panggilan.popleft()
        if len(_panggilan) >= batas:
            return False, f"batas {batas} panggilan peramalan per menit tercapai"
        _panggilan.append(sekarang)
    return True, None


def _model_diizinkan() -> bool:
    """Rem darurat: `FORECAST_PROVIDER=statistical` mematikan panggilan model."""
    return os.getenv("FORECAST_PROVIDER", "sap_rpt").strip().lower() not in _PROVIDER_MATI


def _breaker_terbuka(kunci: str) -> bool:
    with _lock:
        b = _breakers.get(kunci)
        if not b or b["open_until"] <= time.monotonic():
            return False
        return True


def _catat_hasil(kunci: str, gagal: bool) -> None:
    ambang = _env_int("FORECAST_BREAKER_FAILS", 5)
    durasi = _env_float("FORECAST_BREAKER_SECONDS", 300.0)
    with _lock:
        b = _breakers.setdefault(kunci, {"gagal": 0.0, "open_until": 0.0})
        if gagal:
            b["gagal"] += 1
            if ambang > 0 and b["gagal"] >= ambang:
                b["open_until"] = time.monotonic() + durasi
                b["gagal"] = 0.0
                _counter["forecast_breaker_open_total"] += 1
        else:
            b["gagal"] = 0.0


def _statistik(
    history: list[float], horizon_days: int, *, reason: str | None = None
) -> ForecastHasil:
    if not history:
        return ForecastHasil(
            qty_kg=None,
            method=SUMBER_CADANGAN,
            source=SUMBER_CADANGAN,
            fallback_used=True,
            confidence=None,
            sample_count=0,
            reason=reason or "histori demand kosong",
        )
    stat = statistical_forecast(history, horizon_days=horizon_days)
    conf = stat.get("confidence")
    return ForecastHasil(
        qty_kg=float(quantize2(Decimal(str(stat["forecast_qty_kg"])))),
        method=str(stat["method"]),
        source=SUMBER_CADANGAN,
        fallback_used=True,
        confidence=float(conf) if isinstance(conf, (int, float)) else None,
        sample_count=len(history),
        reason=reason,
    )


async def _muat_riwayat(
    db: AsyncSession,
    location_id: UUID,
    commodity_id: UUID,
    batas: datetime,
) -> list[float]:
    """Riwayat TERAKHIR yang sudah terjadi (baris masa depan tidak ikut)."""
    rows = (
        (
            await db.execute(
                select(DemandRecord.quantity_kg)
                .where(
                    DemandRecord.location_id == location_id,
                    DemandRecord.commodity_id == commodity_id,
                    DemandRecord.recorded_at <= batas,
                )
                .order_by(DemandRecord.recorded_at.desc(), DemandRecord.id.desc())
                .limit(HISTORY_DAYS)
            )
        )
        .scalars()
        .all()
    )
    return [float(v) for v in reversed(rows)]


async def forecast_kebutuhan(
    db: AsyncSession,
    *,
    location_id: UUID | None,
    commodity_id: UUID | None,
    horizon_days: int = 7,
    caller: Callable[[str], str] | None | object = _DARI_ENV,
    batas: datetime | None = None,
    pakai_cache: bool = True,
) -> ForecastHasil:
    """Peramalan kebutuhan: SAP-RPT-1.6 bila tersedia, statistik bila tidak.

    `caller`:
      - tidak diisi  → bangun dari env (`SAP_AI_CORE_*`); None bila belum lengkap
      - callable     → dipakai apa adanya (tes / provider lain)
      - None         → paksa jalur statistik tanpa menyentuh jaringan
    """
    batas = batas or datetime.now(timezone.utc)
    if location_id is None or commodity_id is None:
        # Keputusan tanpa target/komoditas tidak punya riwayat untuk diramal.
        # Dulu jalur ini diam-diam menghasilkan "histori kosong"; sekarang
        # alasannya eksplisit supaya trace keputusan tidak menebak.
        return ForecastHasil(
            qty_kg=None,
            method=SUMBER_CADANGAN,
            source=SUMBER_CADANGAN,
            fallback_used=True,
            reason="lokasi/komoditas keputusan tidak lengkap",
        )
    # Setelah guard di atas keduanya pasti terisi; `assert` membuat type-checker
    # ikut yakin tanpa mengubah perilaku runtime.
    assert location_id is not None and commodity_id is not None
    kunci_cache = (
        str(location_id),
        str(commodity_id),
        int(horizon_days),
        batas.astimezone(timezone.utc).date().isoformat(),
    )

    if pakai_cache:
        ttl = _env_float("FORECAST_CACHE_TTL_SECONDS", 900.0)
        if ttl > 0:
            with _lock:
                kena = _cache.get(kunci_cache)
                if kena and kena[0] > time.monotonic():
                    _counter["forecast_cache_hit_total"] += 1
                    return replace(kena[1], cache_hit=True)

    history = await _muat_riwayat(db, location_id, commodity_id, batas)

    if len(history) < MIN_HISTORY:
        hasil = _statistik(
            history,
            horizon_days,
            reason=f"riwayat kurang dari {MIN_HISTORY} hari ({len(history)} titik)",
        )
        _simpan_cache(kunci_cache, hasil, pakai_cache)
        return hasil

    aktif: Callable[[str], str] | None
    alasan_tanpa_model = "provider peramalan tidak dikonfigurasi"
    if not _model_diizinkan():
        # Rem darurat biaya: `FORECAST_PROVIDER=statistical` mematikan model untuk
        # SEMUA jalur, termasuk pemanggil yang sudah terbangun. Dipakai saat
        # latihan demo atau ketika AI Core sedang bermasalah.
        aktif = None
        alasan_tanpa_model = "dimatikan oleh FORECAST_PROVIDER"
    elif caller is _DARI_ENV:
        aktif = sap_rpt_caller_from_env()
    else:
        aktif = cast(Callable[[str], str] | None, caller)
    if aktif is None:
        hasil = _statistik(history, horizon_days, reason=alasan_tanpa_model)
        _simpan_cache(kunci_cache, hasil, pakai_cache)
        return hasil

    kunci_breaker = f"{kunci_cache[0]}:{kunci_cache[1]}:{kunci_cache[2]}"
    if _breaker_terbuka(kunci_breaker):
        hasil = _statistik(
            history,
            horizon_days,
            reason="circuit breaker terbuka setelah kegagalan berulang; memakai cadangan",
        )
        return hasil  # sengaja TIDAK di-cache: biar cepat pulih saat breaker menutup

    boleh, alasan_batas = _diizinkan_memanggil()
    if not boleh:
        hasil = _statistik(history, horizon_days, reason=alasan_batas)
        return hasil  # tidak di-cache: batas per menit bersifat sementara

    mulai = time.monotonic()
    with _lock:
        _counter["forecast_calls_total"] += 1
    hasil_run = run_forecast(history, horizon_days=horizon_days, sap_rpt=aktif)
    durasi_ms = int((time.monotonic() - mulai) * 1000)

    gagal = hasil_run.method == SUMBER_CADANGAN
    _catat_hasil(kunci_breaker, gagal)
    if gagal:
        with _lock:
            _counter["forecast_fallback_total"] += 1

    if gagal:
        hasil = _statistik(history, horizon_days, reason="provider peramalan gagal; pakai cadangan")
        hasil.attempts = hasil_run.attempts
    else:
        qty = hasil_run.forecast_qty_kg
        hasil = ForecastHasil(
            qty_kg=float(quantize2(Decimal(str(qty)))),
            method=hasil_run.method,
            source=SUMBER_MODEL if hasil_run.method == "sap_rpt_1_6" else hasil_run.provider,
            fallback_used=False,
            confidence=hasil_run.confidence,
            sample_count=len(history),
            attempts=hasil_run.attempts,
        )

    log.info(
        "forecast location=%s commodity=%s horizon=%s source=%s fallback=%s "
        "samples=%s duration_ms=%s cache_hit=%s",
        location_id,
        commodity_id,
        horizon_days,
        hasil.source,
        hasil.fallback_used,
        hasil.sample_count,
        durasi_ms,
        False,
    )
    _simpan_cache(kunci_cache, hasil, pakai_cache)
    return hasil


def _simpan_cache(
    kunci: tuple, hasil: ForecastHasil, pakai_cache: bool
) -> None:
    if not pakai_cache:
        return
    ttl = _env_float("FORECAST_CACHE_TTL_SECONDS", 900.0)
    if ttl <= 0:
        return
    with _lock:
        _cache[kunci] = (time.monotonic() + ttl, replace(hasil, cache_hit=False))
