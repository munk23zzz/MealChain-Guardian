"""Price Agent — quote, referensi, deviasi kanonik, dan SDC dari API.

Tidak menjumlah ulang rumus harga. Deviasi dihitung endpoint komputasi
`POST /price/deviation`; SDC dibaca dari read model keputusan.
"""

from __future__ import annotations

from time import monotonic
from urllib.parse import quote

from ..api_client import AgentApiError
from ..contracts import AgentFinding, AgentName
from .base import ReadOnlyWorker, WorkerContext, as_number


class PriceWorker(ReadOnlyWorker):
    name = AgentName.PRICE

    def run(self, context: WorkerContext) -> AgentFinding:
        started = monotonic()
        try:
            location, commodity = self._target(context)
            api = self._api(context)
        except (AgentApiError, ValueError) as exc:
            return self._error(str(exc), latency_ms=self._latency_ms(started))

        if not context.decision_id.strip():
            return self._error("decision_id wajib diisi untuk Price Agent", latency_ms=self._latency_ms(started))

        loc = quote(location, safe="")
        com = quote(commodity, safe="")
        quotes_path = f"/price/quotes/{loc}/{com}"
        reference_path = f"/price/{loc}/{com}"
        decision_path = f"/decisions/{quote(context.decision_id, safe='')}/approval-summary"

        warnings: list[str] = []
        quotes: list[dict] = []
        reference_price = None
        try:
            quotes_payload = api.get(quotes_path)
            raw_quotes = quotes_payload.get("quotes")
            quotes = [item for item in raw_quotes if isinstance(item, dict)] if isinstance(raw_quotes, list) else []
            if not isinstance(raw_quotes, list):
                warnings.append("respons price quotes tidak memuat daftar quotes")
            reference = quotes_payload.get("reference")
            if isinstance(reference, dict):
                reference_price = as_number(reference.get("price_per_kg"))
        except AgentApiError as exc:
            latency = self._latency_ms(started)
            if exc.status_code == 404:
                return self._degraded(
                    "Harga referensi/quotes tidak ditemukan untuk lokasi dan komoditas ini.",
                    facts={
                        "location": location,
                        "commodity": commodity,
                        "quote_count": None,
                        "latest_quote_price": None,
                        "reference_price": None,
                        "deviation_pct": None,
                        "classification": None,
                        "flagged": None,
                        "safe_delivered_cost": None,
                        "quantity_kg": None,
                        "can_execute": None,
                        "valid": None,
                        "supplier_name": None,
                    },
                    warnings=[f"api_404: {exc}"],
                    latency_ms=latency,
                )
            return self._error(str(exc), latency_ms=latency)

        if reference_price is None:
            try:
                reference_payload = api.get(reference_path)
                reference_price = as_number(reference_payload.get("price_per_kg"))
            except AgentApiError as exc:
                warnings.append(f"harga referensi tidak terbaca: {exc}")

        latest = quotes[0] if quotes else None
        latest_price = as_number(latest.get("price_per_kg")) if latest else None
        deviation_pct = None
        classification = None
        flagged = None
        if latest_price is not None and reference_price is not None:
            try:
                deviation = api.post_compute(
                    "/price/deviation",
                    {
                        "location": location,
                        "commodity": commodity,
                        "supplier_price": latest_price,
                    },
                )
                raw_pct = deviation.get("deviation_pct")
                deviation_pct = str(raw_pct) if raw_pct is not None else None
                raw_classification = deviation.get("classification")
                classification = str(raw_classification) if raw_classification is not None else None
                raw_flagged = deviation.get("flagged")
                flagged = raw_flagged if isinstance(raw_flagged, bool) else None
            except AgentApiError as exc:
                warnings.append(f"deviasi harga tidak dapat dihitung: {exc}")
        else:
            warnings.append("quote terbaru atau harga referensi tidak tersedia; deviasi tidak dihitung")

        approval = None
        approval_error = None
        try:
            approval = api.get(decision_path)
        except AgentApiError as exc:
            approval_error = str(exc)
            warnings.append(f"approval-summary tidak terbaca: {exc}")

        sdc = as_number(approval.get("safe_delivered_cost")) if approval else None
        quantity = as_number(approval.get("quantity_kg")) if approval else None
        can_execute = approval.get("can_execute") if approval else None
        valid = None
        expiry = approval.get("expiry") if approval else None
        if isinstance(expiry, dict):
            raw_valid = expiry.get("valid")
            valid = raw_valid if isinstance(raw_valid, bool) else None
        supplier = approval.get("supplier") if approval else None
        supplier_name = supplier.get("name") if isinstance(supplier, dict) else None

        if supplier_name is None:
            warnings.append("supplier tidak dapat dipastikan (supplier_unknown); tidak ditebak")
        if valid is False:
            warnings.append("keputusan kedaluwarsa; jangan menyarankan eksekusi")
        if flagged is True:
            warnings.append("harga janggal: quote berbeda jauh dari referensi; jangan menyimpulkan aman")
        if approval_error:
            warnings.append("SDC/status eksekusi tidak tersedia")

        facts = {
            "location": location,
            "commodity": commodity,
            "quote_count": len(quotes),
            "latest_quote_price": latest_price,
            "reference_price": reference_price,
            "deviation_pct": deviation_pct,
            "classification": classification,
            "flagged": flagged,
            "safe_delivered_cost": sdc,
            "quantity_kg": quantity,
            "can_execute": can_execute if isinstance(can_execute, bool) else None,
            "valid": valid,
            "supplier_name": supplier_name,
        }
        citations = [
            self._citation("quote_count", quotes_path, "quotes (count)", len(quotes)),
        ]
        if latest_price is not None:
            citations.append(
                self._citation("latest_quote_price", quotes_path, "quotes[0].price_per_kg", latest_price)
            )
        if reference_price is not None:
            citations.append(
                self._citation("reference_price", quotes_path, "reference.price_per_kg", reference_price)
            )
        if sdc is not None:
            citations.append(
                self._citation("safe_delivered_cost", decision_path, "safe_delivered_cost", sdc)
            )
        if quantity is not None:
            citations.append(
                self._citation("quantity_kg", decision_path, "quantity_kg", quantity)
            )

        if not quotes:
            warnings.append("tidak ada quote untuk lokasi/komoditas ini")
        if reference_price is None:
            warnings.append("harga referensi tidak tersedia")
        if sdc is None:
            warnings.append("safe delivered cost tidak tersedia")

        degraded = bool(
            not quotes
            or reference_price is None
            or deviation_pct is None
            or flagged is True
            or sdc is None
            or supplier_name is None
        )
        summary = (
            f"{len(quotes)} quote; quote terbaru "
            f"{f'{latest_price}' if latest_price is not None else 'tidak tersedia'}; "
            f"referensi {f'{reference_price}' if reference_price is not None else 'tidak tersedia'}; "
            f"deviasi {deviation_pct if deviation_pct is not None else 'tidak tersedia'} "
            f"({classification or 'tidak diketahui'}); "
            f"SDC {f'{sdc}' if sdc is not None else 'tidak tersedia'}."
        )
        if degraded:
            return self._degraded(
                summary,
                facts=facts,
                citations=citations,
                warnings=warnings,
                blocking=False,
                latency_ms=self._latency_ms(started),
            )
        return self._ok(
            summary,
            facts=facts,
            citations=citations,
            warnings=warnings,
            blocking=False,
            latency_ms=self._latency_ms(started),
        )

