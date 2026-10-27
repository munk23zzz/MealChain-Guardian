"""Generator baris kasus replay/realtime (Fase 7 MG).

Satu pintu untuk tiga hal yang sebelumnya tersebar/berbeda tiap pemanggil:

1. **Identitas** baris kasus. Replay harus menghasilkan ID yang SAMA setiap kali
   dibangun dari dataset kanon (supaya dua pembuatan replay identik dan rerun
   tidak menggandakan baris); realtime harus BERBEDA setiap sesi, karena jangkar
   waktunya berbeda. Karena itu identitas realtime memasukkan
   `evaluation_anchor` + `dataset_version`, dan replay hanya memasukkan versi
   kanon.
2. **Waktu kejadian simulasi** — panen, kirim, sampel suhu, jejak, dan
   `generated_at` keputusan dihitung sebagai offset dari `evaluation_anchor`.
   Fungsi `event_at()` MENOLAK offset positif: peristiwa simulasi yang berada di
   masa depan relatif jangkar adalah data yang tidak mungkin ada, dan
   membiarkannya lolos membuat replay tidak bisa direproduksi.
3. **Bentuk baris** batch/kebutuhan/harga yang lengkap untuk satu kasus, dengan
   arti yang sama untuk replay dan realtime: log suhu selalu berlabel
   `simulated_replay`/`simulated_realtime` (bukan `sensor`), masa layak dan skor
   kesegaran DIHITUNG dari profil komoditas, bukan angka tulisan tangan.

Modul ini tidak menyentuh DB dan tidak mengimpor FastAPI/SQLAlchemy: seluruh
aturannya bisa diuji tanpa database, dan pemanggil (seeder) yang menulis baris.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.core.commodity_policy import CommodityPolicy
from app.core.freshness import compute_freshness_score, compute_usable_until
from app.services.scenario_specs import (
    SCENARIO_VERSION,
    BatchSpec,
    ScenarioCaseSpec,
)

__all__ = [
    "MODE_SIMULASI",
    "FutureEventError",
    "event_at",
    "identitas_kasus",
    "id_batch",
    "id_demand",
    "id_decision",
    "id_harga",
    "log_suhu",
    "pemeriksaan_konsistensi",
    "provenance",
    "rencana_batch",
    "rencana_demand",
    "rencana_harga",
    "stable_uuid",
]

#: Label asal log suhu per mode. TIDAK ADA nilai `sensor`: repo ini tidak punya
#: satu pun jalur penulisan log dari sensor sungguhan, dan menyebut "sensor
#: aktif" untuk data simulasi adalah klaim palsu.
MODE_SIMULASI = {
    "replay": "simulated_replay",
    "realtime": "simulated_realtime",
}

#: Namespace UUID tetap: semua id kasus adalah fungsi murni dari identitasnya.
#: Dibuat sekali di sini (bukan `uuid4`) supaya replay benar-benar dapat diulang.
NAMESPACE = uuid.UUID("8f6d9a52-5c31-4a77-9f24-2f0b7f3c9d10")


class FutureEventError(ValueError):
    """Peristiwa simulasi diminta berada di masa depan relatif jangkar."""


def stable_uuid(*parts: object) -> uuid.UUID:
    """UUID deterministik dari bagian-bagian identitas (uuid5)."""
    return uuid.uuid5(NAMESPACE, "|".join(str(bagian) for bagian in parts))


def _mode_sah(mode: str) -> str:
    nilai = (mode or "").strip().lower()
    if nilai not in MODE_SIMULASI:
        raise ValueError(
            f"mode tidak dikenal: {mode!r}; pilihan: {', '.join(sorted(MODE_SIMULASI))}"
        )
    return nilai


def event_at(anchor: datetime, offset_min: int, *, label: str = "peristiwa") -> datetime:
    """Waktu peristiwa simulasi = jangkar + offset (offset tidak boleh positif).

    `anchor` tanpa tzinfo ditolak: waktu naif membuat perbandingan dengan
    timestamp DB (timestamptz) bergantung zona mesin.
    """
    if anchor.tzinfo is None:
        raise ValueError("evaluation_anchor wajib timezone-aware")
    if offset_min > 0:
        raise FutureEventError(
            f"{label}: offset {offset_min} menit berada di masa depan relatif jangkar"
        )
    return anchor + timedelta(minutes=offset_min)


def identitas_kasus(
    spec: ScenarioCaseSpec,
    *,
    mode: str,
    anchor: datetime,
    dataset_version: str,
    target: str,
) -> str:
    """Identitas baris kasus: replay stabil, realtime unik per sesi.

    Kota tujuan ikut masuk karena satu kasus ditanam untuk kota pemanggil —
    tanpa itu dua kota berbagi ID dan saling menimpa.
    """
    nilai = _mode_sah(mode)
    if nilai == "replay":
        # Kanon: versi skenario + versi dataset. Tanggal jangkar TIDAK masuk,
        # supaya replay yang dibangun kapan pun menghasilkan ID yang sama.
        return f"{SCENARIO_VERSION}|replay|{dataset_version}|{spec.key}|{target}"
    if anchor.tzinfo is None:
        raise ValueError("evaluation_anchor wajib timezone-aware")
    jangkar = anchor.astimezone(timezone.utc).isoformat()
    return f"{SCENARIO_VERSION}|realtime|{dataset_version}|{jangkar}|{spec.key}|{target}"


def id_decision(identitas: str, *, iteration: int) -> uuid.UUID:
    """ID keputusan untuk satu iterasi kasus."""
    return stable_uuid(identitas, "decision", f"v{int(iteration)}")


def id_batch(identitas: str, batch: BatchSpec) -> uuid.UUID:
    """ID batch milik kasus."""
    return stable_uuid(identitas, "batch", batch.label)


def id_demand(identitas: str) -> uuid.UUID:
    """ID baris kebutuhan (`demand_records`) kasus."""
    return stable_uuid(identitas, "demand")


def id_harga(identitas: str) -> uuid.UUID:
    """ID sinyal harga acuan (PIHPS) kasus."""
    return stable_uuid(identitas, "price", "pihps_reference")


def log_suhu(batch: BatchSpec, *, anchor: datetime, mode: str) -> list[dict]:
    """Log suhu JSONB untuk satu batch: sampel sah + entri rusak yang disengaja.

    Setiap entri sah membawa `source` mode-nya (`simulated_replay` /
    `simulated_realtime`). Entri rusak sengaja tidak punya bentuk yang bisa
    dibaca parser: itulah bukti "ada data tetapi tidak bisa dipakai" pada kasus
    `on_hold`.
    """
    nilai = _mode_sah(mode)
    sumber = MODE_SIMULASI[nilai]
    entri: list[dict] = []
    for offset, suhu in zip(batch.temperature_offsets_min, batch.temperatures_c):
        entri.append(
            {
                "timestamp": event_at(
                    anchor, offset, label=f"log suhu {batch.label}"
                ).isoformat(),
                "temperature_c": float(suhu),
                "source": sumber,
            }
        )
    for rusak in range(batch.malformed_samples):
        # `temperature_c` bukan angka: parser menandainya `malformed`, bukan
        # menganggapnya 0 °C (0 °C akan terbaca sebagai rantai dingin sempurna).
        entri.append(
            {
                "timestamp": None,
                "temperature_c": f"tidak-terbaca-{rusak + 1}",
                "source": sumber,
            }
        )
    return entri


def rencana_batch(
    spec: ScenarioCaseSpec,
    batch: BatchSpec,
    *,
    anchor: datetime,
    mode: str,
    policy: CommodityPolicy,
) -> dict:
    """Rencana satu baris `batches` — semua angka dihitung dari profil.

    `freshness_score` dan `usable_until` TIDAK ditulis tangan: keduanya hasil
    `core.freshness` atas panen relatif jangkar dan log yang benar-benar
    ditulis. Mengarang keduanya adalah cara termudah membuat kasus "usable"
    yang secara data sudah kedaluwarsa.
    """
    log = log_suhu(batch, anchor=anchor, mode=mode)
    harvested_at = event_at(anchor, batch.harvest_offset_min, label=f"panen {batch.label}")
    dispatched_at = (
        event_at(anchor, batch.dispatched_offset_min, label=f"kirim {batch.label}")
        if batch.dispatched_offset_min is not None
        else None
    )
    skor = compute_freshness_score(
        harvested_at,
        anchor,
        policy=policy,
        temperature_log=log,
    )
    # Skor disimpan pada presisi kolom (`Numeric(3,2)`) dan `usable_until`
    # dihitung dari NILAI YANG SAMA. Kalau masa layak dihitung dari skor penuh
    # sementara tabel menyimpan skor bulat, pembaca yang mengulang rumus dari
    # kolom DB mendapat selisih jam-an — audit yang tidak bisa direproduksi.
    skor_simpan = round(skor, 2)
    usable_until = compute_usable_until(harvested_at, policy.shelf_life_days, skor_simpan)
    return {
        "label": batch.label,
        "quantity_kg": f"{batch.quantity_kg:.2f}",
        "harvested_at": harvested_at,
        "dispatched_at": dispatched_at,
        "usable_until": usable_until,
        "freshness_score": f"{skor_simpan:.2f}",
        "certification_status": batch.certificate,
        "safety_status": batch.safety_status,
        "temperature_log": log,
        "policy_version": policy.policy_version,
        "policy_kind": policy.policy_kind,
        "temperature_source": MODE_SIMULASI[_mode_sah(mode)],
    }


def rencana_demand(
    spec: ScenarioCaseSpec,
    *,
    anchor: datetime,
    mode: str,
) -> dict | None:
    """Rencana baris `demand_records` (kebutuhan) untuk satu kasus.

    `needed_by` adalah TENGGAT, bukan peristiwa: ia boleh berada setelah jangkar
    (kebutuhan yang harus dipenuhi beberapa jam ke depan). Yang tidak boleh
    adalah tenggat yang sudah lewat untuk kasus `usable` — dijaga
    `pemeriksaan_konsistensi`.
    """
    if spec.demand_needed_by_offset_min is None:
        return None
    _mode_sah(mode)
    needed_by = anchor + timedelta(minutes=spec.demand_needed_by_offset_min)
    return {
        "quantity_kg": f"{spec.quantity_kg:.2f}",
        "needed_by": needed_by,
        "recorded_at": event_at(
            anchor,
            spec.demand_recorded_offset_min,
            label=f"pencatatan kebutuhan {spec.key}",
        ),
    }


def rencana_harga(
    spec: ScenarioCaseSpec,
    *,
    anchor: datetime,
    mode: str,
) -> dict | None:
    """Rencana sinyal harga acuan (PIHPS) kasus; `None` bila kasus tidak punya."""
    if spec.price_per_kg is None or spec.price_offset_min is None:
        return None
    _mode_sah(mode)
    return {
        "price_per_kg": f"{spec.price_per_kg:.2f}",
        "recorded_at": event_at(anchor, spec.price_offset_min, label="sinyal harga"),
        "source": "pihps_reference",
    }


def pemeriksaan_konsistensi(
    spec: ScenarioCaseSpec,
    baris_batch: list[dict],
    *,
    anchor: datetime,
    travel_minutes: int,
) -> tuple[str, ...]:
    """Daftar masalah konsistensi kasus (kosong = konsisten).

    Empat hal yang diperiksa, semuanya dari rencana yang benar-benar akan
    ditulis:

    1. masa layak batch masih di depan jangkar (batch layak dievaluasi);
    2. tiba (kirim + waktu tempuh) sebelum tenggat kebutuhan;
    3. masa layak batch tidak lebih pendek dari kedatangan;
    4. kasus `usable` tidak punya tenggat yang sudah lewat.

    Waktu tempuh diberikan pemanggil (dari cache rute/estimator logistik) —
    modul ini tidak mengarang durasi perjalanan.
    """
    masalah: list[str] = []
    if not baris_batch:
        return ("tanpa_batch",)

    demand = rencana_demand(spec, anchor=anchor, mode="replay")
    for baris in baris_batch:
        if baris["usable_until"] <= anchor:
            masalah.append(f"{baris['label']}:usable_until_lewat")
        if baris.get("harvested_at", anchor) > anchor:
            masalah.append(f"{baris['label']}:panen_di_masa_depan")
        log = baris.get("temperature_log") or []
        for entri in log:
            stempel = entri.get("timestamp")
            if stempel and datetime.fromisoformat(stempel) > anchor:
                masalah.append(f"{baris['label']}:log_di_masa_depan")
                break

        tiba = None
        if baris.get("dispatched_at") is not None:
            tiba = baris["dispatched_at"] + timedelta(minutes=travel_minutes)
        if tiba is not None and baris["usable_until"] < tiba:
            masalah.append(f"{baris['label']}:layak_sebelum_tiba")

        if demand is not None and tiba is not None:
            if demand["needed_by"] < tiba:
                masalah.append(f"{baris['label']}:tenggat_sebelum_tiba")
            if demand["needed_by"] > baris["usable_until"]:
                masalah.append(f"{baris['label']}:tenggat_setelah_layak")

    if demand is not None and spec.intended_outcome == "usable":
        if demand["needed_by"] <= anchor:
            masalah.append("kasus_usable:tenggat_sudah_lewat")

    return tuple(dict.fromkeys(masalah))


def provenance(
    spec: ScenarioCaseSpec,
    *,
    mode: str,
    anchor: datetime,
    dataset_version: str,
) -> dict:
    """Keterangan asal data kasus untuk API/report — bukan angka hasil hitung.

    Bentuk ini sengaja menyebut `simulated` dan sumber log secara eksplisit
    supaya UI/Joule tidak pernah menyebut "sensor aktif" atau "SAP production"
    untuk dataset ini.
    """
    nilai = _mode_sah(mode)
    return {
        "case": spec.key,
        "scenario_version": SCENARIO_VERSION,
        "mode": nilai,
        "evaluation_anchor": anchor.astimezone(timezone.utc).isoformat(),
        "dataset_version": dataset_version,
        "intended_outcome": spec.intended_outcome,
        "temperature_source": MODE_SIMULASI[nilai],
        "simulated": True,
        "policy_note": spec.policy_note,
    }
