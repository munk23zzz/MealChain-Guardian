"""Safety Guardian — membaca batch SUMBER dan exclusion ber-cakupan.

Tidak memanggil /safety/evaluate (worker hanya membaca).

Perbaikan AUD-9B-29 (P0):

- Batch yang dinilai adalah batch **sumber** (himpunan `source_batch_ids`
  binding, atau lokasi sumber + komoditas), bukan batch lokasi tujuan. Dulu
  batch tujuan yang aman dipakai untuk melaporkan "pass" sementara batch
  sumber yang `fail` tidak pernah terlihat (probe 3e2e3cc7).
- Exclusion hanya memveto bila cakupannya cocok (`supplier_id` = pemasok
  keputusan, `scope_location_id` = lokasi tujuan). Satu exclusion Jakarta/telur
  tidak lagi memveto semua review (probe e7150da4).
- Batch sumber tak dapat diidentifikasi → `degraded` + `blocking=True`
  (fail-closed), bukan "aman".
- Karantina (`quarantined`/`failed`) pada batch sumber ikut memblokir — fakta
  keras yang sama dengan `penghalang_sumber` di backend.
"""

from __future__ import annotations

from time import monotonic

from ..api_client import AgentApiError
from ..contracts import AgentFinding, AgentName
from .base import ReadOnlyWorker, WorkerContext
from .sumber import pilih_batch_sumber, pisahkan_exclusion

#: Status karantina yang membuat batch tidak boleh dipakai — cermin
#: `app.core.quarantine` (`QUARANTINED`/`FAILED`) dan `KARANTINA_BLOKIR` di
#: `app.core.safety_gate`.
KARANTINA_BLOKIR = ("quarantined", "failed")


class SafetyWorker(ReadOnlyWorker):
    name = AgentName.SAFETY

    def run(self, context: WorkerContext) -> AgentFinding:
        started = monotonic()
        try:
            location, commodity = self._target(context)
            api = self._api(context)
        except (AgentApiError, ValueError) as exc:
            return self._error(str(exc), latency_ms=self._latency_ms(started))

        try:
            batches = api.semua_batch()
        except AgentApiError as exc:
            latency = self._latency_ms(started)
            if exc.status_code == 404:
                return self._degraded(
                    "Daftar batch tidak tersedia; status keamanan tidak diketahui.",
                    facts={
                        "location": location,
                        "source_location": context.source_location,
                        "commodity": commodity,
                        "batch_count": None,
                        "failed_count": None,
                        "pending_count": None,
                        "pass_count": None,
                        "quarantined_count": None,
                        "active_exclusion_count": None,
                        "worst_status": None,
                        "failed_batch_ids": [],
                        "quarantined_batch_ids": [],
                        "active_exclusion_ids": [],
                        "ignored_exclusion_ids": [],
                    },
                    warnings=[f"api_404: {exc}"],
                    latency_ms=latency,
                )
            return self._error(str(exc), latency_ms=latency)

        sumber = pilih_batch_sumber(context, batches)
        selected = sumber.batches

        counts = {"pass": 0, "pending": 0, "fail": 0}
        failed_ids: list[str] = []
        quarantined_ids: list[str] = []
        unknown = 0
        for batch in selected:
            status = str(batch.get("safety_status") or "").strip().lower()
            if status in counts:
                counts[status] += 1
            else:
                unknown += 1
            if status == "fail" and batch.get("id") is not None:
                failed_ids.append(str(batch["id"]))
            if (
                str(batch.get("quarantine_status") or "").strip().lower()
                in KARANTINA_BLOKIR
                and batch.get("id") is not None
            ):
                quarantined_ids.append(str(batch["id"]))

        worst_status = (
            "fail" if counts["fail"] else "pending" if counts["pending"] else "pass" if counts["pass"] else None
        )

        active_ids: list[str] = []
        ignored_ids: list[str] = []
        tanpa_cakupan: list[str] = []
        exclusions_ok = False
        warnings: list[str] = []
        try:
            exclusions_payload = api.get("/supplier-exclusions")
            items = exclusions_payload.get("items") if isinstance(exclusions_payload, dict) else None
            if not isinstance(items, list):
                raise AgentApiError("respons /supplier-exclusions tidak memuat 'items'")
            active_ids, ignored_ids, tanpa_cakupan = pisahkan_exclusion(items, context)
            exclusions_ok = True
        except AgentApiError as exc:
            warnings.append(f"exclusion tidak terbaca: {exc}")

        latency = self._latency_ms(started)
        teridentifikasi = sumber.teridentifikasi
        facts = {
            "location": location,
            # Batch yang dinilai berasal dari sini — bukan dari `location`.
            "source_location": context.source_location,
            "commodity": commodity,
            # None = himpunan batch sumber tidak dapat diidentifikasi.
            "batch_count": len(selected) if teridentifikasi else None,
            "failed_count": counts["fail"] if teridentifikasi else None,
            "pending_count": counts["pending"] if teridentifikasi else None,
            "pass_count": counts["pass"] if teridentifikasi else None,
            "quarantined_count": len(quarantined_ids) if teridentifikasi else None,
            "active_exclusion_count": len(active_ids) if exclusions_ok else None,
            "worst_status": worst_status if teridentifikasi else None,
            "failed_batch_ids": failed_ids,
            "quarantined_batch_ids": quarantined_ids,
            "active_exclusion_ids": active_ids,
            # Exclusion aktif yang TIDAK berlaku untuk keputusan ini karena
            # cakupan lokasi/pemasok berbeda. Dilaporkan, bukan dipakai veto.
            "ignored_exclusion_ids": ignored_ids,
        }
        citations = []
        if teridentifikasi:
            citations = [
                self._citation(
                    "batch_count", "/batches", "batches[].safety_status (count)", len(selected)
                ),
                self._citation(
                    "failed_count", "/batches", "batches[].safety_status (count)", counts["fail"]
                ),
                self._citation(
                    "pending_count",
                    "/batches",
                    "batches[].safety_status (count)",
                    counts["pending"],
                ),
                self._citation(
                    "pass_count", "/batches", "batches[].safety_status (count)", counts["pass"]
                ),
                self._citation(
                    "quarantined_count",
                    "/batches",
                    "batches[].quarantine_status (count)",
                    len(quarantined_ids),
                ),
            ]
        if exclusions_ok:
            citations.append(
                self._citation(
                    "active_exclusion_count",
                    "/supplier-exclusions",
                    "items[].status (count)",
                    len(active_ids),
                )
            )

        if not teridentifikasi:
            warnings.append(f"batch sumber tidak dapat diidentifikasi: {sumber.alasan}")
        elif not selected:
            warnings.append("tidak ada batch sumber untuk lokasi/komoditas ini")
        if unknown:
            warnings.append(f"{unknown} batch memiliki safety_status tak dikenal")
        if not exclusions_ok:
            warnings.append("jumlah exclusion aktif tidak diketahui")
        elif ignored_ids:
            warnings.append(
                f"{len(ignored_ids)} exclusion aktif tidak berlaku untuk keputusan ini "
                f"(cakupan lokasi/pemasok berbeda): {', '.join(ignored_ids)}"
            )
        if quarantined_ids:
            warnings.append(
                f"{len(quarantined_ids)} batch sumber dikarantina/gagal: "
                f"{', '.join(quarantined_ids)}"
            )
        if tanpa_cakupan:
            warnings.append(
                "cakupan exclusion tidak terbaca (supplier_id/scope_location_id kosong) "
                f"sehingga tidak dapat dibuktikan tidak berlaku: {', '.join(tanpa_cakupan)}"
            )

        blocking = (
            not teridentifikasi
            or not selected
            or counts["fail"] > 0
            or bool(quarantined_ids)
            or len(active_ids) > 0
            # Exclusion governance tak terbaca = tidak dapat dibuktikan aman.
            or not exclusions_ok
        )
        if teridentifikasi:
            summary = (
                f"{len(selected)} batch sumber: {counts['pass']} pass, "
                f"{counts['pending']} pending, {counts['fail']} fail, "
                f"{len(quarantined_ids)} dikarantina; exclusion aktif berlaku "
                f"{len(active_ids) if exclusions_ok else 'tidak diketahui'}."
            )
        else:
            summary = (
                "Batch sumber tidak dapat diidentifikasi; status keamanan TIDAK dinilai "
                "— jangan simpulkan aman."
            )
        if teridentifikasi and exclusions_ok and selected:
            return self._ok(
                summary,
                facts=facts,
                citations=citations,
                warnings=warnings,
                blocking=blocking,
                latency_ms=latency,
            )
        return self._degraded(
            summary,
            facts=facts,
            citations=citations,
            warnings=warnings,
            blocking=blocking,
            latency_ms=latency,
        )

