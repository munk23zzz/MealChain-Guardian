"""Himpunan batch SUMBER untuk guardian Safety/Freshness (AUD-9B-29).

Guardian harus menilai barang yang benar-benar akan dikirim untuk keputusan
itu — yaitu batch di lokasi **sumber**, atau lebih tepat lagi `batch_ids` yang
terikat di bukti keputusan (`allocation_binding`, himpunan yang sama dengan
`backend/app/services/supplier_eligibility.py::batch_sumber_transfer`).

Sebelum perbaikan ini kedua worker menyaring `/batches` dengan
`context.location`, yaitu lokasi **tujuan**. Pada data demo itu berarti batch
Jakarta/telur yang aman dipakai untuk menilai keputusan Cianjur→Jakarta, dan
batch Cianjur/telur yang `fail` tidak pernah terlihat (probe 3e2e3cc7).

Modul ini sengaja kecil dan murni (tanpa I/O) supaya aturan pemilihan batch
bisa diuji tanpa transport API.

Prinsip: **fail-closed**. Bila himpunan batch sumber tidak dapat
diidentifikasi — tidak ada `batch_ids` terikat, lokasi sumber tidak diketahui,
atau batch terikat hilang dari `/batches` — hasilnya `belum_teridentifikasi`
berisi alasan, dan pemanggil wajib melaporkan `blocking=True`, bukan "aman".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .base import WorkerContext


@dataclass(frozen=True)
class BatchSumber:
    """Hasil pemilihan batch sumber.

    `alasan` `None` berarti himpunan berhasil diidentifikasi (boleh kosong bila
    memang tidak ada batch sumber — itu dibaca "tidak ada bukti" oleh pemanggil
    dan tetap fail-closed).
    """

    batches: list[dict] = field(default_factory=list)
    alasan: str | None = None

    @property
    def teridentifikasi(self) -> bool:
        return self.alasan is None


def _teks(nilai: Any) -> str:
    return str(nilai or "").strip().lower()


def _cocok_lokasi(batch: dict, nama: str) -> bool:
    return _teks(batch.get("location")) == _teks(nama)


def pilih_batch_sumber(context: WorkerContext, batches: Iterable[dict]) -> BatchSumber:
    """Pilih batch sumber untuk satu keputusan; tidak pernah memakai lokasi tujuan."""
    baris = [b for b in batches if isinstance(b, dict)]

    terikat = tuple(str(v) for v in (context.source_batch_ids or ()) if str(v).strip())
    if terikat:
        ids = set(terikat)
        dipilih = [b for b in baris if str(b.get("id")) in ids]
        ditemukan = {str(b.get("id")) for b in dipilih}
        hilang = sorted(ids - ditemukan)
        if hilang:
            return BatchSumber(
                batches=dipilih,
                alasan=(
                    "batch sumber terikat tidak ditemukan di /batches: "
                    f"{', '.join(hilang)}"
                ),
            )
        return BatchSumber(batches=dipilih)

    if not context.source_location or not context.source_location.strip():
        return BatchSumber(
            alasan=(
                "lokasi sumber keputusan tidak diketahui; batch sumber tidak dapat "
                "diidentifikasi (batch lokasi tujuan TIDAK dipakai sebagai pengganti)"
            )
        )

    dipilih = [
        b
        for b in baris
        if _cocok_lokasi(b, context.source_location)
        and _teks(b.get("commodity")) == _teks(context.commodity)
    ]
    # Pemasok dipakai sebagai penyaring hanya bila payload batch MEMANG memuat
    # `supplier_id`. Endpoint /batches saat ini tidak mengirimnya; menebaknya
    # dari lokasi akan melanggar aturan "pemasok tidak boleh ditebak".
    pemasok = (context.supplier_id or "").strip()
    if pemasok and any("supplier_id" in b for b in dipilih):
        dipilih = [
            b
            for b in dipilih
            if not b.get("supplier_id") or str(b.get("supplier_id")) == pemasok
        ]

    if not dipilih:
        # Lokasi sumber DIKETAHUI tetapi tidak ada batch di sana: itu nol yang
        # nyata (bukan "tidak diketahui") — tetap fail-closed di pemanggil.
        return BatchSumber(batches=[])
    return BatchSumber(batches=dipilih)


def exclusion_berlaku(item: dict, context: WorkerContext) -> bool:
    """Apakah satu baris exclusion menyangkut keputusan ini?

    Cakupan yang tersedia di skema `supplier_exclusions` hanya
    `supplier_id` + `scope_location_id` (tidak ada kolom komoditas), jadi:

    - `supplier_id` berbeda dari pemasok keputusan → tidak berlaku;
    - `scope_location_id` berbeda dari lokasi tujuan → tidak berlaku;
    - kolom cakupan yang ADA tetapi identitas pembandingnya tidak diketahui di
      konteks (mis. konteks lama tanpa id), atau kolomnya tidak ada sama
      sekali → **berlaku**. Exclusion yang tidak dapat dibuktikan tidak
      berlaku tetap memveto; ini sikap konservatif, bukan pelonggaran.
    """
    supplier = item.get("supplier_id")
    scope = item.get("scope_location_id")
    if supplier is not None and supplier != "":
        if not context.supplier_id:
            # Identitas pemasok keputusan tidak diketahui: tidak dapat
            # dibuktikan exclusion ini TIDAK berlaku → anggap berlaku.
            return True
        if str(supplier) != str(context.supplier_id):
            return False
    if scope is not None and scope != "":
        if not context.target_location_id:
            return True
        if str(scope) != str(context.target_location_id):
            return False
    return True


def pisahkan_exclusion(
    items: Iterable[dict], context: WorkerContext
) -> tuple[list[str], list[str], list[str]]:
    """`(berlaku, diabaikan, cakupannya tak terbaca)` untuk exclusion `active`.

    `cakupannya tak terbaca` = baris aktif yang tidak memuat
    `supplier_id`/`scope_location_id`; baris seperti itu tetap dihitung
    berlaku (konservatif) dan WAJIB dilaporkan supaya tidak lolos diam-diam.
    """
    berlaku: list[str] = []
    diabaikan: list[str] = []
    tanpa_cakupan: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("status") != "active":
            continue
        nama = str(item.get("id")) if item.get("id") is not None else "?"
        if exclusion_berlaku(item, context):
            berlaku.append(nama)
            if not item.get("supplier_id") or not item.get("scope_location_id"):
                tanpa_cakupan.append(nama)
        else:
            diabaikan.append(nama)
    return berlaku, diabaikan, tanpa_cakupan
