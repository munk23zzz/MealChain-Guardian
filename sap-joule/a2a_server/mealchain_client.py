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
    GET  /supply/<location>/<commodity>           → {quantity_kg, recorded_at, source}
    GET  /demand/<location>/<commodity>           → {quantity_kg, needed_by}
    GET  /demand/forecast/<location>/<commodity>  → {forecast_qty_kg, method, confidence}
    GET  /price/<location>/<commodity>            → {price_per_kg, recorded_at, source}
    GET  /price/quotes/<location>/<commodity>     → {quotes: [{supplier_name, price_per_kg, …}]}
    GET  /waste/summary                           → {recorded, diverted, unassigned, partners}
    GET  /supplier-exclusions                     → {items: [{supplier_id, status, reason, …}]}
    GET  /supplier-routes?limit=<n>               → {routes: [{… road, journey}], summary}
    GET  /decisions/{id}/compliance               → {decision, evidence, approvals, traces, signature}
    GET  /decisions/{id}/chain                    → {anchor_id, chain: [...]}
    GET  /decisions/{id}/traces                   → {steps: [...]}
    GET  /integrations/status                     → {components: [{id, name, category_label, …}]}
    GET  /ledger/verify                           → {valid, blocks, linked_ratio, …}
    GET  /sap/purchase-orders/summary             → {by_status, count, total_value, scope}
    GET  /receipts?batch_id=<id>                  → {receipts: [...]}

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
from urllib.parse import quote

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

#: Batas batch sekali baca. Backend menjepit `limit` ke 500 DAN mengirim `total`, jadi angka
#: ini = plafon backend: satu panggilan memuat seluruh inventaris demo (158 batch). Sebelum
#: 2026-10-20 backend memakai `.limit(50)` di kode, sehingga 158 batch tampak seperti 50.
BATCH_LIMIT = 500

#: Batas rute kiriman sekali baca (plafon backend 200).
ROUTE_LIMIT = 200

#: Berapa pasangan (SPPG, komoditas) yang diperiksa untuk laporan harga/kebutuhan.
#: Satu pasangan = 1-2 panggilan HTTP; Joule menunggu sinkron maksimal 60 detik, jadi
#: jumlahnya dibatasi dan sisanya disebut apa adanya di laporan.
PAIR_LIMIT = 8

#: Berapa keputusan terakhir yang bukti/jejaknya dibuka saat pengguna tidak menyebut satu id.
EVIDENCE_LIMIT = 3


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

    def batches(self, limit: int = BATCH_LIMIT) -> list[dict[str, Any]]:
        """Inventaris batch: lokasi, komoditas, kg, status keamanan, kesegaran, masa pakai.

        `limit` dikirim eksplisit (plafon backend 500) supaya laporan memakai SELURUH
        inventaris, bukan 50 baris terbaru yang dulu dipotong diam-diam di backend.
        """
        batas = max(1, min(int(limit), BATCH_LIMIT))
        return self._rows(self._get("/batches", params={"limit": batas}), "batches")

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
                    "id": row.get("id"),
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

    def kpi(
        self,
        days: int = KPI_DEFAULT_DAYS,
        *,
        scope: str = "operational",
        demo_session_id: str | None = None,
    ) -> dict[str, Any]:
        """Envelope KPI untuk jendela `days` hari terakhir, dalam SATU cakupan data.

        Jendela ditolak di sini kalau tidak masuk akal: `/kpi` mensyaratkan
        `start <= end` dan akan menjawab 422 tanpa penjelasan yang berguna bagi pengguna Joule.

        Cakupan (Fase 8): `operational` = fakta kerja saja (backend menyaring
        `demo_session_id IS NULL`); `demo` = satu sesi demo yang HARUS disebut
        eksplisit. Tidak ada jalur "sesi terbaru" — backend menolak
        `include_demo=true` tanpa `demo_session_id`, dan menebak id di sini akan
        menyaring data sesi lain lalu menampilkan angka yang salah pemiliknya.
        """
        if days <= 0:
            raise ValueError("jendela KPI harus lebih dari 0 hari")
        cakupan = str(scope or "").strip().lower()
        if cakupan not in ("operational", "demo"):
            raise ValueError("scope KPI harus 'operational' atau 'demo'")
        end = _dt.datetime.now(_dt.timezone.utc)
        start = end - _dt.timedelta(days=days)
        params: dict[str, Any] = {"start": _rfc3339(start), "end": _rfc3339(end)}
        if cakupan == "demo":
            sesi = str(demo_session_id or "").strip()
            if not sesi:
                raise ValueError("cakupan demo butuh demo_session_id eksplisit")
            params["include_demo"] = "true"
            params["demo_session_id"] = sesi
        payload = self._get("/kpi", params=params)
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

    # --- read model per (lokasi, komoditas) ----------------------------------------------
    #
    # Endpoint `/supply`, `/demand`, `/demand/forecast`, `/price`, `/price/quotes` semuanya
    # berpasangan (lokasi, komoditas), jadi jembatan memanggilnya per pasangan yang benar-benar
    # ada di inventaris. Tidak ada daftar pasangan yang ditanam di kode: sumbernya `/batches`.

    @staticmethod
    def _pair_path(prefix: str, location_id: str, commodity: str) -> str:
        """Path per pasangan dengan segmen di-quote (nama komoditas bisa ber-spasi)."""
        return f"{prefix}/{quote(str(location_id), safe='')}/{quote(str(commodity), safe='')}"

    def supply_point(self, location_id: str, commodity: str) -> dict[str, Any]:
        """Satu baris pasokan terakhir untuk (SPPG, komoditas) — `GET /supply/…`.

        Dipakai sebagai pemeriksaan silang laporan pasokan: `/balance/map` sudah memuat
        `supply_kg` hasil hitungan backend, sedangkan endpoint ini menyebut baris sumbernya
        (kg apa adanya + `source` + waktu catat) tanpa agregasi.
        """
        payload = self._get(self._pair_path("/supply", location_id, commodity))
        return payload if isinstance(payload, dict) else {}

    def demand(self, location_id: str, commodity: str) -> dict[str, Any]:
        """Kebutuhan terakhir untuk (SPPG, komoditas) — `GET /demand/…`."""
        payload = self._get(self._pair_path("/demand", location_id, commodity))
        return payload if isinstance(payload, dict) else {}

    def demand_forecast(self, location_id: str, commodity: str) -> dict[str, Any]:
        """Prakiraan kebutuhan (SPPG, komoditas) — `GET /demand/forecast/…`.

        `method` ikut dibawa apa adanya: `statistical_fallback` berarti model peramal tidak
        dipakai, dan itu harus terbaca di laporan — bukan disembunyikan sebagai angka pasti.
        """
        payload = self._get(self._pair_path("/demand/forecast", location_id, commodity))
        return payload if isinstance(payload, dict) else {}

    def price(self, location_id: str, commodity: str) -> dict[str, Any]:
        """Harga acuan terakhir (SPPG, komoditas) — `GET /price/…`."""
        payload = self._get(self._pair_path("/price", location_id, commodity))
        return payload if isinstance(payload, dict) else {}

    def price_quotes(self, location_id: str, commodity: str) -> dict[str, Any]:
        """Kuotasi pemasok untuk (SPPG, komoditas) — `GET /price/quotes/…`.

        Kuotasi diteruskan berurutan seperti dikirim backend (terbaru lebih dulu). Jembatan
        TIDAK menghitung termurah/rata-rata: itu aritmetika atas data harga, dan angka
        safety-critical tetap milik modul deterministik backend.
        """
        payload = self._get(self._pair_path("/price/quotes", location_id, commodity))
        if not isinstance(payload, dict):
            return {}
        quotes = payload.get("quotes")
        return {
            "location": payload.get("location"),
            "commodity": payload.get("commodity"),
            "reference": payload.get("reference"),
            "quotes": [row for row in (quotes or []) if isinstance(row, dict)],
        }

    # --- limbah & pengalihan --------------------------------------------------------------

    def waste_summary(self, days: int = 30) -> dict[str, Any]:
        """Limbah pangan `days` hari terakhir — `GET /waste/summary`.

        `recorded` dipecah backend menjadi `diverted` (punya mitra) dan `unassigned`
        (tercatat tanpa mitra); jembatan meneruskan ketiganya, tidak menjumlah ulang.
        """
        jendela = max(1, min(int(days), 365))
        payload = self._get("/waste/summary", params={"days": jendela})
        return payload if isinstance(payload, dict) else {}

    # --- risiko pemasok & rute ------------------------------------------------------------

    def supplier_exclusions(self) -> list[dict[str, Any]]:
        """Eksklusi pemasok di hub (`GET /supplier-exclusions`) — semua status.

        Hanya id yang dikirim backend untuk pemasok & lokasi; penerjemahan ke nama dikerjakan
        `server.py` dengan direktori yang sama-sama dibaca dari backend (bukan tabel nama
        yang ditanam di jembatan).
        """
        return self._rows(self._get("/supplier-exclusions"), "items")

    def supplier_routes(self, limit: int = ROUTE_LIMIT) -> dict[str, Any]:
        """Kiriman aktif + rute jalan (`GET /supplier-routes`), tanpa geometri.

        `road.geometry` (ratusan titik LineString) DIBUANG di sini: Joule menerima teks chat,
        dan mengirim polylines hanya memperlambat tanpa menambah jawaban. Angka jarak, durasi,
        rasio jalan-vs-garis-lurus, dan keadaan perjalanan tetap diambil dari backend.
        """
        batas = max(1, min(int(limit), ROUTE_LIMIT))
        payload = self._get("/supplier-routes", params={"limit": batas})
        if not isinstance(payload, dict):
            return {"routes": [], "summary": {}}
        hasil: list[dict[str, Any]] = []
        for row in self._rows(payload, "routes"):
            raw_road = row.get("road")
            raw_journey = row.get("journey")
            road: dict[str, Any] = raw_road if isinstance(raw_road, dict) else {}
            journey: dict[str, Any] = raw_journey if isinstance(raw_journey, dict) else {}
            hasil.append(
                {
                    "supplierName": row.get("supplier_name"),
                    "originName": (row.get("origin") or {}).get("name"),
                    "destinationName": row.get("destination_name"),
                    "commodity": row.get("commodity"),
                    "quantityKg": row.get("quantity_kg"),
                    "safetyStatus": row.get("safety_status"),
                    "usableUntil": row.get("usable_until"),
                    "straightKm": row.get("straight_km"),
                    "roadKm": (road or {}).get("distance_km"),
                    "roadMinutes": (road or {}).get("duration_min"),
                    "ratioVsStraight": (road or {}).get("ratio_vs_straight"),
                    "journeyState": journey.get("state_label") or journey.get("state"),
                    "etaAt": journey.get("eta_at"),
                    "remainingMinutes": journey.get("remaining_min"),
                    "arrivesBeforeUsableUntil": journey.get("arrives_before_usable_until"),
                }
            )
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        return {"routes": hasil, "summary": summary}

    # --- bukti & jejak keputusan ----------------------------------------------------------

    def decision_compliance(self, decision_id: str) -> dict[str, Any]:
        """Berkas kepatuhan satu keputusan (`/decisions/{id}/compliance`): bukti, approval,
        jejak agen, tanda tangan kriptografis, dan hasil verifikasi."""
        payload = self._get(f"/decisions/{quote(str(decision_id), safe='')}/compliance")
        return payload if isinstance(payload, dict) else {}

    def decision_chain(self, decision_id: str) -> dict[str, Any]:
        """Rantai iterasi keputusan (`/decisions/{id}/chain`) — termasuk yang ditolak."""
        payload = self._get(f"/decisions/{quote(str(decision_id), safe='')}/chain")
        return payload if isinstance(payload, dict) else {}

    def decision_traces(self, decision_id: str) -> dict[str, Any]:
        """Jejak langkah agen (`/decisions/{id}/traces`) — tool apa dipanggil, ringkasan."""
        payload = self._get(f"/decisions/{quote(str(decision_id), safe='')}/traces")
        return payload if isinstance(payload, dict) else {}

    # --- status sistem & integrasi --------------------------------------------------------

    def integrations_status(self) -> dict[str, Any]:
        """Status komponen integrasi (`GET /integrations/status`): SAP AI Core, mock SAP,
        AgentCore, observability — beserta bukti dan catatan apa adanya."""
        payload = self._get("/integrations/status")
        return payload if isinstance(payload, dict) else {}

    def ledger_verify(self) -> dict[str, Any]:
        """Verifikasi rantai blok ledger (`GET /ledger/verify`) — `valid`, jumlah blok,
        rasio blok terhubung, dan peringatan cakupan bila ada."""
        payload = self._get("/ledger/verify")
        return payload if isinstance(payload, dict) else {}

    def po_summary(self) -> dict[str, Any]:
        """Ringkasan purchase order (`GET /sap/purchase-orders/summary`): jumlah per status,
        total nilai, dan cakupan akun — semuanya dihitung backend."""
        payload = self._get("/sap/purchase-orders/summary")
        return payload if isinstance(payload, dict) else {}

    def receipts(self, batch_id: str) -> list[dict[str, Any]]:
        """Penerimaan barang (goods receipt) satu batch — `GET /receipts?batch_id=…`.

        Backend mewajibkan `batch_id`; jembatan tidak menarik seluruh tabel dengan memanggil
        satu per satu untuk semua batch (158 panggilan), jadi jalur ini hanya dipakai bila
        pengguna menyebut satu batch.

        Backend menjawab `{items: […]}` (bukan `receipts`); setiap baris berisi `checked`
        (suhu/catatan/kemasan/berat_kg), `other_note`, `recorded_by_name`, `recorded_at`.
        """
        payload = self._get("/receipts", params={"batch_id": str(batch_id), "limit": 50})
        return self._rows(payload, "items")

    def receipts_menunggu(self) -> dict[str, Any]:
        """Antrean penerimaan barang: sudah dicatat, belum diputuskan.

        `GET /receipts/menunggu` menjawab `{items: […], total: n}` — satu baris per
        batch (catatan terbaru), sudah di-scope backend ke lokasi pengguna. Endpoint
        ini lama tidak dipakai skill mana pun, sehingga pertanyaan "penerimaan barang
        mana yang menunggu persetujuan" dijawab antrean KEPUTUSAN (domain lain).
        """
        payload = self._get("/receipts/menunggu")
        items = self._rows(payload, "items")
        total = payload.get("total") if isinstance(payload, dict) else None
        return {"items": items, "total": total if isinstance(total, int) else len(items)}
