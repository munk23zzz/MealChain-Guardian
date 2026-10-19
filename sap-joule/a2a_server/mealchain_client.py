"""Klien HTTP BACA-SAJA ke backend MealChain Guardian v0.2.0 — jembatan A2A untuk SAP Joule.

Pindah garis kerja (2026-10-11). Jembatan ini dulu menulis untuk backend v0.1.0 yang hanya
punya `/ui/*` dan login `{username, password}` → `token`. Sekarang proyek dikembangkan di
klon (a) `mealchain-guardian` (v0.2.0), jadi klien ini membaca API-nya:

    POST /auth/login {email, password}            → {access_token, role, expires_in}
    GET  /health                                  (publik, tanpa token)
    GET  /admin/locations                         → {locations: [{id, name, region, …}]}
    GET  /batches                                 → {batches: [{location, commodity, …}]}
    GET  /suppliers?limit=<n>                     → {items: [{name, location, commodity, …}]}
    GET  /balance/map?commodity=<nama>            → {commodity, locations: [supply/demand/…]}
    GET  /kpi?start=<iso>&end=<iso>               → {metrics: [{name, unit, state, value, reason}]}
    GET  /decisions                               → {items: [{decision_id, status, …}]}
    GET  /decisions/{id}/approval-summary          → {source_location, target_location, commodity, …}
    GET  /sap/purchase-orders?limit=<n>           → {items: [{po_number, status, …}]}

Tiga alasan modul ini tidak punya jalan tulis sama sekali:

1. `Rules.md` §1.1 — LLM tidak pernah menghitung angka safety-critical. Modul ini juga tidak
   menjumlahkan, merata-rata, atau menaksir apa pun: angka sudah dihitung modul murni
   `backend/app/core/*` dan diteruskan apa adanya.
2. `Rules.md` §1.2 — tidak ada auto-execute. Akun yang dipakai berperan `bgn_monitor`
   (baca-saja, tanpa hak approve/execute), jadi andai Joule salah memanggil aksi tulis,
   backend tetap menjawab 403.
3. Read model di klon (a) memisahkan daftar keputusan (`/decisions`) dari detailnya
   (`/decisions/{id}/approval-summary`), sehingga asal→tujuan dan komoditas baru diketahui
   setelah satu panggilan per keputusan. Karena itu jumlah keputusan yang dilengkapi dibatasi
   (`DETAIL_LIMIT`) — bukan mengambil 100+ ringkasan setiap kali Joule ditanya.

Kegagalan TIDAK pernah disamarkan menjadi nol atau daftar kosong — angka 0 terbaca seperti
"tidak ada masalah". Semua masalah melempar `MealchainUnavailable` supaya Joule menampilkan
penyebabnya.
"""

from __future__ import annotations

import datetime as _dt
import os
from typing import Any

import httpx

DEFAULT_API_URL = "http://localhost:8000"
READ_USERNAME_ENV = "MEALCHAIN_READ_USERNAME"
READ_PASSWORD_ENV = "MEALCHAIN_READ_PASSWORD"

#: Status keputusan yang belum tuntas — yang perlu dilihat manusia di antrean.
PENDING_STATUSES = ("proposed", "pending_approval", "verifier_flagged", "approved")

#: Berapa keputusan teratas yang dilengkapi ringkasan (satu panggilan HTTP per keputusan).
DETAIL_LIMIT = 12

#: Jendela KPI default (hari) bila pemanggil tidak menentukan.
KPI_DEFAULT_DAYS = 7

#: Batas PO yang ditarik sekali baca. Backend menjepit ke 200 (BATAS_MAKS), jadi angka ini
#: sama dengan plafon backend: cukup untuk seluruh PO demo, dan tetap satu panggilan HTTP.
PO_LIMIT = 200

#: Batas direktori pemasok sekali baca. Backend menjepit `limit` ke 200; 60 pemasok demo
#: muat dalam satu panggilan, jadi Joule tidak perlu memaginasi.
SUPPLIER_LIMIT = 200


class MealchainUnavailable(RuntimeError):
    """Backend tidak bisa dihubungi, kredensial baca belum diisi, atau token tidak bisa dibuat."""


class MealchainRejected(MealchainUnavailable):
    """Backend menjawab, tetapi menolak permintaan (HTTP 4xx/5xx). Pesannya diteruskan apa adanya."""


def _detail(response: httpx.Response) -> str:
    """Ambil `detail` dari body JSON FastAPI; kalau tidak ada, pakai potongan teks mentah."""
    try:
        body = response.json()
    except ValueError:
        return (response.text or "").strip()[:300] or "(tanpa body)"
    if isinstance(body, dict) and "detail" in body:
        return str(body["detail"])[:300]
    return str(body)[:300]


def _rfc3339(moment: _dt.datetime) -> str:
    """Timestamp bergaya RFC3339 ber-offset — bentuk yang diterima `/kpi` di v0.2.0."""
    return moment.astimezone(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


class MealchainClient:
    """Klien tipis di atas `/auth/login` + endpoint baca v0.2.0.

    `client=` dan `transport=` hanya dipakai test (`httpx.MockTransport`) supaya seluruh
    jalur HTTP bisa diuji tanpa backend hidup.
    """

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
        detail_limit: int = DETAIL_LIMIT,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("MEALCHAIN_API_URL") or DEFAULT_API_URL
        ).rstrip("/")
        # Nama variabel dipertahankan (`USERNAME`) supaya konfigurasi Cloud Foundry tidak perlu
        # diubah lagi, tetapi isinya ALAMAT EMAIL akun baca — itulah yang dikirim ke /auth/login.
        self.username = username if username is not None else os.environ.get(READ_USERNAME_ENV)
        self.password = password if password is not None else os.environ.get(READ_PASSWORD_ENV)
        self.timeout = timeout
        self.detail_limit = detail_limit
        self._client = client or httpx.Client(
            base_url=self.base_url, timeout=timeout, transport=transport
        )
        self._token: str | None = None

    # --- siklus hidup ---------------------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MealchainClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # --- internal ------------------------------------------------------------------------

    def _login(self) -> str:
        if not self.username or not self.password:
            raise MealchainUnavailable(
                "kredensial akun baca belum diisi: set "
                f"{READ_USERNAME_ENV} (alamat email) dan {READ_PASSWORD_ENV} "
                "(akun demo baca-saja: bgn.monitor@demo.local)"
            )
        try:
            response = self._client.post(
                "/auth/login",
                json={"email": self.username, "password": self.password},
            )
        except httpx.HTTPError as exc:
            raise MealchainUnavailable(
                f"backend MealChain tidak bisa dihubungi ({self.base_url}) saat login: {exc}"
            ) from exc
        if response.status_code >= 400:
            raise MealchainRejected(
                f"login ke backend MealChain ditolak (HTTP {response.status_code}): "
                f"{_detail(response)}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise MealchainRejected(f"respons login tanpa JSON: {exc}") from exc
        token = body.get("access_token") or body.get("token")
        if not token:
            raise MealchainRejected("respons login tidak memuat access_token")
        self._token = str(token)
        return self._token

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET terautentikasi dengan satu percobaan ulang saat token kedaluwarsa (401)."""
        token = self._token or self._login()
        for attempt in (1, 2):
            try:
                response = self._client.get(
                    path, params=params, headers={"Authorization": f"Bearer {token}"}
                )
            except httpx.HTTPError as exc:
                raise MealchainUnavailable(
                    f"backend MealChain tidak bisa dihubungi ({self.base_url}) untuk {path}: {exc}"
                ) from exc
            if response.status_code == 401 and attempt == 1:
                token = self._login()
                continue
            if response.status_code >= 400:
                raise MealchainRejected(
                    f"{path} ditolak backend (HTTP {response.status_code}): {_detail(response)}"
                )
            try:
                return response.json()
            except ValueError as exc:
                raise MealchainRejected(f"{path} tidak mengembalikan JSON: {exc}") from exc
        raise MealchainUnavailable(f"{path}: token ditolak berulang kali")

    @staticmethod
    def _rows(payload: Any, key: str) -> list[dict[str, Any]]:
        """Ambil daftar dari envelope v0.2.0 (`{locations: [...]}`, `{batches: [...]}`, …)."""
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        return []

    # --- endpoint baca -------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Status backend + mode SAP. Tanpa token: `/health` memang endpoint publik."""
        try:
            response = self._client.get("/health")
        except httpx.HTTPError as exc:
            raise MealchainUnavailable(f"/health tidak bisa dihubungi: {exc}") from exc
        if response.status_code >= 400:
            raise MealchainRejected(f"/health → HTTP {response.status_code}")
        return response.json()

    def locations(self) -> list[dict[str, Any]]:
        """Daftar lokasi SPPG (id + nama) untuk menerjemahkan id menjadi nama di laporan."""
        return self._rows(self._get("/admin/locations"), "locations")

    def batches(self) -> list[dict[str, Any]]:
        """Inventaris batch: lokasi, komoditas, kg, status keamanan, kesegaran, masa pakai."""
        return self._rows(self._get("/batches"), "batches")

    def suppliers(self, limit: int = SUPPLIER_LIMIT) -> list[dict[str, Any]]:
        """Direktori pemasok yang melayani tiap SPPG (`GET /suppliers`).

        Kolom dipetakan ke bentuk camelCase yang dipakai `report.py`; TIDAK ada
        perhitungan di sini — keandalan, kapasitas, dan ringkasan kiriman sudah
        dihitung backend. `shipping` boleh `None` (pemasok terdaftar tetapi belum
        mengirim); nilainya diteruskan apa adanya supaya perender bisa menulis `—`,
        bukan mengarang nol.
        """
        batas = max(1, min(int(limit), SUPPLIER_LIMIT))
        payload = self._get("/suppliers", params={"limit": batas})
        hasil: list[dict[str, Any]] = []
        for row in self._rows(payload, "items"):
            shipping = row.get("shipping")
            shipping = shipping if isinstance(shipping, dict) else {}
            hasil.append(
                {
                    "name": row.get("name"),
                    "location": row.get("location"),
                    "commodity": row.get("commodity"),
                    "reliability": row.get("reliability_score"),
                    "capacityKgPerWeek": row.get("capacity_kg_per_week"),
                    "certification": row.get("certification_status"),
                    "address": row.get("address"),
                    "contactName": row.get("contact_name"),
                    "excludedAtHub": row.get("excluded_at_hub"),
                    "shippingCount": shipping.get("count"),
                    "shippingKg": shipping.get("total_kg"),
                    "shippingUntil": shipping.get("until"),
                }
            )
        return hasil

    def balance_map(self, commodity: str) -> dict[str, Any]:
        """Kondisi pasokan/kebutuhan satu komoditas untuk semua lokasi (`/balance/map`)."""
        payload = self._get("/balance/map", params={"commodity": commodity})
        return payload if isinstance(payload, dict) else {}

    def kpi(self, days: int = KPI_DEFAULT_DAYS) -> dict[str, Any]:
        """Envelope KPI untuk jendela `days` hari terakhir.

        Jendela ditolak di sini kalau tidak masuk akal: `/kpi` mensyaratkan
        `start <= end` dan akan menjawab 422 tanpa penjelasan yang berguna bagi pengguna Joule.
        """
        if days <= 0:
            raise ValueError("jendela KPI harus lebih dari 0 hari")
        end = _dt.datetime.now(_dt.timezone.utc)
        start = end - _dt.timedelta(days=days)
        payload = self._get("/kpi", params={"start": _rfc3339(start), "end": _rfc3339(end)})
        return payload if isinstance(payload, dict) else {}

    def decisions(self) -> list[dict[str, Any]]:
        """Feed keputusan (cakupan ditentukan peran akun oleh backend)."""
        return self._rows(self._get("/decisions"), "items")

    def approval_summary(self, decision_id: str) -> dict[str, Any]:
        """Ringkasan satu keputusan — satu-satunya tempat asal→tujuan + komoditas dinamai."""
        payload = self._get(f"/decisions/{decision_id}/approval-summary")
        return payload if isinstance(payload, dict) else {}

    def purchase_orders(self, limit: int = PO_LIMIT) -> list[dict[str, Any]]:
        """Purchase order mock SAP yang boleh dibaca akun ini (`/sap/purchase-orders`).

        Baca-saja dan tanpa perhitungan: `totalValue` diterima dari backend (sudah
        `price × qty` di sana), jembatan tidak mengalikan ulang. Kolom dipetakan ke bentuk
        camelCase yang dipakai `report.py`, sama seperti `pending_decisions`.

        `origin` ikut dibawa: `execution` = lahir dari eksekusi keputusan, `demo` = baris
        impor SAP tanpa keputusan. Perender memakainya untuk tidak menampilkan PO impor
        seolah-olah melewati persetujuan.
        """
        batas = max(1, min(int(limit), PO_LIMIT))
        payload = self._get("/sap/purchase-orders", params={"limit": batas})
        return [
            {
                "poNumber": row.get("po_number"),
                "status": row.get("status"),
                "createdAt": row.get("created_at"),
                "locationName": row.get("location_name"),
                "supplierName": row.get("supplier_name"),
                "materialNumber": row.get("material_number"),
                "commodityName": row.get("commodity_name"),
                "quantityKg": row.get("ordered_quantity_kg"),
                "pricePerKg": row.get("price_per_kg"),
                "totalValue": row.get("total_value"),
                "decisionId": row.get("decision_id"),
                "decisionStatus": row.get("decision_status"),
                "origin": row.get("origin"),
            }
            for row in self._rows(payload, "items")
        ]

    def pending_decisions(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Keputusan belum tuntas, dilengkapi asal→tujuan + komoditas dari approval-summary.

        Ringkasan yang gagal TIDAK menggagalkan seluruh laporan dan TIDAK diisi karangan:
        baris tetap dikirim dengan `sourceLocation`/`targetLocation`/`commodity` bernilai
        `None`, yang oleh perender ditulis sebagai `—`.
        """
        batas = DETAIL_LIMIT if limit is None else max(0, limit)
        rows = [
            row
            for row in self.decisions()
            if str(row.get("status")) in PENDING_STATUSES
        ]
        hasil: list[dict[str, Any]] = []
        for row in rows[:batas]:
            decision_id = str(row.get("decision_id") or "")
            detail: dict[str, Any] = {}
            if decision_id:
                try:
                    detail = self.approval_summary(decision_id)
                except MealchainUnavailable:
                    detail = {}
            hasil.append(
                {
                    "id": decision_id,
                    "decisionType": row.get("decision_type"),
                    "status": row.get("status"),
                    "quantityKg": row.get("quantity_kg"),
                    "sourceLocation": detail.get("source_location"),
                    "targetLocation": detail.get("target_location"),
                    "commodity": detail.get("commodity"),
                }
            )
        return hasil
