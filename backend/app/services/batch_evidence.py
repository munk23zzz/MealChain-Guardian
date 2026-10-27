"""Evaluasi bukti satu batch untuk API — satu tempat, dipakai daftar DAN detail.

Rencana Fase 3 butir 5: `GET /batches` dan `GET /batches/{id}` mengembalikan
profil, observasi, `evidence_state`, `source`, dan waktu observasi; Goods
Receipt menjelaskan apakah bukti suhu cukup.

Kalau daftar dan detail menyusun blok bukti masing-masing, dua endpoint bisa
bercerita berbeda tentang batch yang sama — kelas bug yang sudah pernah terjadi
di repo ini (`_baris` di `api/batches.py` sengaja dipakai kedua endpoint supaya
bentuknya satu). Modul ini memperluas aturan itu ke blok bukti.

`source` di sini menjawab "dari mana bukti suhunya", bukan "dari mana profilnya":

- `seed`        — log ditulis penyemai (simulasi), bukan sensor;
- `demo`        — log ditulis jalur demo;
- `unrecorded`  — batch tanpa jejak asal log.

Rencana meminta label "log simulasi" muncul untuk seed, bukan "sensor aktif".
Karena itu `source` diteruskan apa adanya dari `batches.origin` dan TIDAK
ditebak menjadi "sensor".
"""

from __future__ import annotations

from datetime import datetime

from app.core.commodity_policy import CommodityPolicy
from app.core.safety import evaluate_safety

__all__ = [
    "EVIDENCE_SOURCE_LABEL",
    "blok_bukti_batch",
    "blok_bukti_profil_hilang",
    "sumber_bukti",
    "weakest_observation",
    "blok_bukti_kandidat",
]

#: Label yang dibaca UI/Joule. `seed` dan `demo` sama-sama simulasi: repo ini
#: tidak punya satu pun jalur penulisan log dari sensor sungguhan.
EVIDENCE_SOURCE_LABEL = {
    "seed": "log simulasi",
    "demo": "log simulasi",
    "unrecorded": "tanpa jejak asal log",
}


def sumber_bukti(origin: str | None) -> str:
    """Asal log suhu, apa adanya dari `batches.origin` (tidak ditebak)."""
    nilai = (origin or "").strip().lower()
    if nilai in EVIDENCE_SOURCE_LABEL:
        return nilai
    return "unrecorded"


def blok_bukti_batch(
    *,
    temperature_log: list[dict] | None,
    policy: CommodityPolicy,
    policy_source: str,
    origin: str | None,
    evaluation_time: datetime,
    safety_status: str | None = None,
) -> dict:
    """Blok bukti suhu + profil untuk satu batch.

    `safety_status` (nilai TERSIMPAN di DB) ikut dikirim bersama hasil evaluasi
    supaya pembaca bisa melihat kalau keduanya berbeda; perbedaan itu bukan
    sesuatu yang boleh disembunyikan dengan menampilkan yang lebih ramah.
    """
    evaluasi = evaluate_safety(
        temperature_log, policy=policy, evaluation_time=evaluation_time
    )
    observation = str(evaluasi["temperature_observation"])
    evidence_state = str(evaluasi["evidence_state"])
    reasons = evaluasi["reasons"]
    alasan = [str(r) for r in reasons] if isinstance(reasons, list | tuple) else []
    source = sumber_bukti(origin)
    last_sample_at = evaluasi["last_sample_at"]

    return {
        # ── profil yang dipakai ───────────────────────────────────────────
        "commodity_profile": policy.to_dict(),
        "profile_source": policy_source,
        # ── hasil observasi (bukan verdict) ───────────────────────────────
        "temperature_observation": observation,
        "evidence_state": evidence_state,
        "sample_count": evaluasi["sample_count"],
        "observed_at": (
            last_sample_at.isoformat() if isinstance(last_sample_at, datetime) else None
        ),
        "evaluation_time": evaluation_time.isoformat(),
        # ── asal log ──────────────────────────────────────────────────────
        "source": source,
        "source_label": EVIDENCE_SOURCE_LABEL.get(source, "tanpa jejak asal log"),
        # ── apa artinya untuk pekerjaan penerimaan ────────────────────────
        "evidence_sufficient": evidence_state == "sufficient",
        "evidence_reasons": alasan,
        # Verdict yang TERSIMPAN, dikirim berdampingan dengan evaluasi sekarang.
        "stored_safety_status": safety_status,
        "evaluated_safety_status": str(evaluasi["safety_status"]),
    }


def blok_bukti_profil_hilang(
    *,
    komoditas: str | None,
    origin: str | None,
    evaluation_time: datetime,
    safety_status: str | None = None,
) -> dict:
    """Blok bukti untuk komoditas yang BELUM punya profil.

    Komoditas tak dikenal tidak dinilai dengan rentang karangan: itulah bug yang
    Fase 3 tutup (bawaan 0-8 °C untuk semua). Karena itu blok ini menyatakan
    buktinya `insufficient` dengan alasan eksplisit, BUKAN `pass` dengan penalti
    nol — "tidak bisa dinilai" tidak sama dengan "aman".
    """
    source = sumber_bukti(origin)
    alasan = (
        f"komoditas {komoditas!r} belum punya profil suhu; "
        "tidak ada rentang yang bisa dipakai menilai bukti"
    )
    return {
        "commodity_profile": None,
        "profile_source": "tidak ada",
        "temperature_observation": "missing",
        "evidence_state": "insufficient",
        "sample_count": 0,
        "observed_at": None,
        "evaluation_time": evaluation_time.isoformat(),
        "source": source,
        "source_label": EVIDENCE_SOURCE_LABEL.get(source, "tanpa jejak asal log"),
        "evidence_sufficient": False,
        "evidence_reasons": [alasan],
        "stored_safety_status": safety_status,
        # Tanpa profil tidak ada verdict yang bisa dihitung: None, bukan "pass".
        "evaluated_safety_status": None,
    }


# ── agregasi bukti untuk kandidat (Fase 3 butir 6) ──────────────────────────

# Urutan "terlemah lebih dulu": dipakai memilih label agregat grup.
_KELEMAHAN = {
    "missing": 0,
    "malformed": 1,
    "stale": 2,
    "observed": 3,
}


def weakest_observation(blok_blok: list[dict]) -> str | None:
    """Label observasi TERLEMAH dari sekumpulan blok bukti batch.

    Grup campuran (satu batch terverifikasi + satu batch tanpa log) tidak boleh
    dirangkum dengan label batch terbaiknya: itu mengubah bukti terlemah menjadi
    "cukup" hanya karena ada satu batch yang bagus.
    """
    terbawah: tuple[int, str] | None = None
    for blok in blok_blok:
        kode = str(blok.get("temperature_observation") or "").strip().lower()
        pangkat = _KELEMAHAN.get(kode)
        if pangkat is None:
            continue
        if terbawah is None or pangkat < terbawah[0]:
            terbawah = (pangkat, kode)
    return terbawah[1] if terbawah else None


def blok_bukti_kandidat(
    *,
    batch_blok: list[dict],
    batch_ids: list[str],
    held_batch_ids: list[str],
) -> dict:
    """Rangkum bukti per batch menjadi blok bukti satu kandidat.

    Butir 6 MG: "Campuran batch tidak boleh membuat bukti terlemah hilang."
    Karena itu blok ini SELALU membawa:
    - `batch_evidence`: label tiap batch pengikut (bukan hanya agregatnya),
    - `held_batch_ids`: batch yang TIDAK masuk kandidat dan alasannya,
    - `weakest_observation`: label terlemah di antara batch pengikut.
    """
    pengikut = [b for b in batch_blok if str(b.get("batch_id")) in set(batch_ids)]
    semua = weakest_observation(pengikut)
    label_terlemah = semua
    if held_batch_ids:
        # Batch yang tertahan punya bukti lebih lemah; sertakan agar agregatnya
        # tidak terlihat lebih baik daripada kenyataan.
        tertahan = [
            b for b in batch_blok if str(b.get("batch_id")) in set(held_batch_ids)
        ]
        gabungan = weakest_observation(tertahan)
        if gabungan is not None and (
            label_terlemah is None
            or _KELEMAHAN.get(gabungan, 99) < _KELEMAHAN.get(label_terlemah, 99)
        ):
            label_terlemah = gabungan

    cukup = all(bool(b.get("evidence_sufficient")) for b in pengikut) and bool(pengikut)
    sumber = sorted({str(b.get("source")) for b in pengikut if b.get("source")})
    waktu = [b.get("observed_at") for b in pengikut if b.get("observed_at")]

    # Tiga keadaan, bukan dua: sebagian bukti grup terverifikasi dan sebagian
    # tertahan BUKAN "sufficient" (ada kilogram yang tidak boleh diusulkan) dan
    # juga bukan "insufficient" (kilogram yang diusulkan memang terbukti).
    if not pengikut:
        keadaan = "insufficient"
    elif not cukup:
        keadaan = "insufficient"
    elif held_batch_ids:
        keadaan = "ambiguous"
    else:
        keadaan = "sufficient"

    return {
        "temperature_observation": label_terlemah,
        "weakest_observation": label_terlemah,
        "evidence_state": keadaan,
        "evidence_sufficient": keadaan == "sufficient",
        "sample_count": sum(int(b.get("sample_count") or 0) for b in pengikut),
        "observed_at": max(waktu) if waktu else None,
        "source": sumber[0] if len(sumber) == 1 else ("mixed" if sumber else "unrecorded"),
        "source_label": (
            EVIDENCE_SOURCE_LABEL.get(sumber[0], "tanpa jejak asal log")
            if len(sumber) == 1
            else ("campuran sumber log" if sumber else "tanpa jejak asal log")
        ),
        "profile_source": (
            str(pengikut[0].get("profile_source")) if pengikut else "tidak ada"
        ),
        "batch_evidence": [
            {
                "batch_id": str(b.get("batch_id")),
                "temperature_observation": b.get("temperature_observation"),
                "evidence_state": b.get("evidence_state"),
                "sample_count": b.get("sample_count"),
                "observed_at": b.get("observed_at"),
                "source_label": b.get("source_label"),
            }
            for b in pengikut
        ],
        "held_batch_ids": [str(x) for x in held_batch_ids],
    }
