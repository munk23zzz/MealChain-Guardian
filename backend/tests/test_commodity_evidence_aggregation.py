"""Agregasi bukti & penerusan ke Joule (Fase 3 butir 6).

Kontrak yang dikunci berkas ini (MG/phase-03-commodity-evidence.md butir 6):

1. **Campuran batch tidak boleh membuat bukti TERLEMAH hilang.** Grup kandidat
   yang berisi satu batch bersuhu sah dan satu batch tanpa log tidak boleh
   dilaporkan sebagai "bukti cukup" hanya karena rata-rata skornya tinggi.
2. Kandidat yang lolos membawa label observasi (`temperature_observation`),
   `evidence_state` per batch terlemah, dan waktu observasi — bukan hanya skor.
3. Joule meneruskan label itu APA ADANYA: laporan tidak menghitung skor baru dan
   tidak menyebut "sensor aktif"/"live" untuk log simulasi.
4. Ambient tetap boleh tanpa log: komoditas yang tidak mewajibkan bukti suhu
   tidak boleh tertahan oleh gerbang bukti.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.candidate import PriceInfo
from app.core.candidate_generation import generate_candidates
from app.core.commodity_policy import policy_for
from app.services.batch_evidence import (
    blok_bukti_batch,
    blok_bukti_kandidat,
    blok_bukti_profil_hilang,
)

AS_OF = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
EGG = policy_for("telur")
RICE = policy_for("beras")


def _stamp(jam_lalu: float, suhu: float) -> dict:
    return {
        "timestamp": (AS_OF - timedelta(hours=jam_lalu)).isoformat(),
        "temperature_c": suhu,
    }


LOG_SAH = [_stamp(2, 4.0), _stamp(1, 4.5)]
LOG_KOSONG: list = []
LOG_LAMA = [_stamp(24 * 5, 4.0), _stamp(24 * 5 - 0.5, 4.5)]
#: Satu jalur Cianjur → Jakarta; dipakai semua skenario di bawah.
JALUR = {
    ("Cianjur", "Jakarta"): {
        "feasible": True,
        "distance_km": 120.0,
        "estimated_time_min": 150.0,
    }
}


def _batch(
    *,
    batch_id: str,
    quantity_kg: str = "300",
    temperature_log: list | None = None,
    komoditas: str = "telur",
    safety_status: str = "pass",
    freshness_score: str = "0.95",
) -> dict:
    return {
        "batch_id": batch_id,
        "location": "Cianjur",
        "commodity": komoditas,
        "supplier_id": "sup-1",
        "quantity_kg": Decimal(quantity_kg),
        "freshness_score": Decimal(freshness_score),
        "freshness_status": "pass",
        "safety_status": safety_status,
        "quarantine_status": "none",
        "usable_until": AS_OF + timedelta(days=5),
        "temperature_log": LOG_SAH if temperature_log is None else temperature_log,
    }


def _inputs(batches):
    return (
        {("Cianjur", "telur"): Decimal("1000"), ("Jakarta", "telur"): Decimal("0")},
        {("Jakarta", "telur"): Decimal("500"), ("Cianjur", "telur"): Decimal("0")},
        batches,
        {("Cianjur", "Jakarta"): JALUR[("Cianjur", "Jakarta")]},
        {
            ("Cianjur", "Jakarta", "telur"): PriceInfo(
                reference_price=Decimal("25000"),
                supplier_quote=Decimal("26000"),
                supplier_id="sup-1",
            )
        },
    )


def _blok_dari(batch: dict) -> dict:
    """Blok bukti satu batch lewat jalur yang sama dengan API (`blok_bukti_batch`)."""
    return {
        "batch_id": batch["batch_id"],
        **blok_bukti_batch(
            temperature_log=batch["temperature_log"],
            policy=EGG if batch["commodity"] == "telur" else RICE,
            policy_source="commodity_policies",
            origin="seed",
            evaluation_time=AS_OF,
            safety_status=batch["safety_status"],
        ),
    }


def _generate(batches, *, policies=None, held=None):
    s, d, b, lg, p = _inputs(batches)
    return generate_candidates(
        s,
        d,
        b,
        lg,
        prices=p,
        policies=policies if policies is not None else {"telur": EGG},
        evaluation_time=AS_OF,
        held=held,
    )


# ── 1. Bukti terlemah tidak hilang dalam campuran ───────────────────────────


def test_campuran_hanya_kilogram_terbukti_yang_diusulkan():
    """300 kg bersuhu sah + 300 kg tanpa log → usulan 300 kg, bukan 600 kg.

    Kedua batch berskor kesegaran sama (0,95). Kalau generator menjumlah
    kilogram tanpa melihat bukti, usulan menjadi 600 kg dan separuhnya fiktif.
    """
    out = _generate(
        [
            _batch(batch_id="b-sah", quantity_kg="300"),
            _batch(batch_id="b-kosong", quantity_kg="300", temperature_log=LOG_KOSONG),
        ]
    )
    assert len(out) == 1
    assert out[0].quantity_kg == Decimal("300"), out[0]
    assert tuple(out[0].batch_ids) == ("b-sah",)


def test_batch_tertahan_dilaporkan_bukan_dihapus():
    """Batch 300 kg yang tertahan wajib meninggalkan jejak pada agregat bukti.

    Tanpa jejak, pembaca melihat "aman 300 kg" dan tidak tahu 300 kg lain
    menunggu verifikasi — persis "bukti terlemah hilang" yang dilarang butir 6.
    """
    blok_sah = _blok_dari(_batch(batch_id="b-sah", quantity_kg="300"))
    blok_kosong = _blok_dari(
        _batch(batch_id="b-kosong", quantity_kg="300", temperature_log=LOG_KOSONG)
    )
    agregat = blok_bukti_kandidat(
        batch_blok=[blok_sah, blok_kosong],
        batch_ids=["b-sah"],
        held_batch_ids=["b-kosong"],
    )
    assert agregat["held_batch_ids"] == ["b-kosong"], agregat
    assert agregat["weakest_observation"] in {"missing", "malformed", "stale"}, agregat
    # Sebagian terbukti, sebagian tertahan → `ambiguous`, bukan `sufficient`
    # (ada kg yang tidak boleh diusulkan) dan bukan `insufficient` (kg yang
    # diusulkan memang terbukti).
    assert agregat["evidence_state"] == "ambiguous", agregat
    assert agregat["evidence_sufficient"] is False, agregat


def test_semua_batch_tanpa_bukti_tidak_menghasilkan_kandidat():
    """Fail-closed: tidak ada batch terbukti → tidak ada usulan sama sekali."""
    held: list = []
    out = _generate(
        [
            _batch(batch_id="b-1", temperature_log=LOG_KOSONG),
            _batch(batch_id="b-2", temperature_log=LOG_KOSONG),
        ],
        held=held,
    )
    assert out == []
    assert held, "grup yang tertahan wajib dilaporkan"
    assert "temperature_evidence_incomplete" in set(held[0].blocking_reasons)


def test_dua_batch_sah_menghasilkan_kandidat_dibatasi_permintaan():
    """Regresi: gerbang bukti tidak boleh menghukum rantai dingin yang benar."""
    out = _generate(
        [
            _batch(batch_id="b-1", quantity_kg="300"),
            _batch(batch_id="b-2", quantity_kg="300"),
        ]
    )
    assert len(out) == 1
    # 600 kg terbukti, permintaan Jakarta 500 kg → usulan 500 kg.
    assert out[0].quantity_kg == Decimal("500")
    assert set(out[0].batch_ids) == {"b-1", "b-2"}


def test_log_lama_tidak_dihitung_sebagai_observasi_sah():
    """Sampel lima hari lalu bukan observasi real-time.

    Ditegakkan di lapisan bukti milik Fase 3: label wajib `stale`, bukan
    `observed`. Kalau fusi Fase 6 belum menahannya, itu dilaporkan terpisah —
    label yang salah tidak boleh lolos diam-diam.
    """
    blok = _blok_dari(_batch(batch_id="b-lama", temperature_log=LOG_LAMA))
    assert blok["temperature_observation"] == "stale", blok
    agregat = blok_bukti_kandidat(
        batch_blok=[blok], batch_ids=["b-lama"], held_batch_ids=[]
    )
    assert agregat["temperature_observation"] != "observed", agregat
    assert agregat["evidence_sufficient"] is False, agregat


def test_komoditas_ambient_tanpa_log_tetap_boleh():
    """Beras tidak diwajibkan bukti suhu — gerbang tidak boleh menahannya."""
    batches = [
        {
            **_batch(batch_id="b-beras", temperature_log=LOG_KOSONG, komoditas="beras"),
        }
    ]
    s = {("Cianjur", "beras"): Decimal("1000"), ("Jakarta", "beras"): Decimal("0")}
    d = {("Jakarta", "beras"): Decimal("500"), ("Cianjur", "beras"): Decimal("0")}
    lg = {("Cianjur", "Jakarta"): dict(JALUR[("Cianjur", "Jakarta")])}
    p = {
        ("Cianjur", "Jakarta", "beras"): PriceInfo(
            reference_price=Decimal("15000"), supplier_quote=None, supplier_id="sup-1"
        )
    }
    out = generate_candidates(
        s, d, batches, lg, prices=p, policies={"beras": RICE}, evaluation_time=AS_OF
    )
    assert len(out) == 1, "komoditas ambient tertahan oleh gerbang bukti suhu"


# ── 2. Label observasi ikut pada payload kandidat ───────────────────────────


def test_agregat_membawa_label_observasi_dan_waktu():
    """Joule butuh label + waktu; menghitung ulang di sana = dua definisi."""
    blok_1 = _blok_dari(_batch(batch_id="b-1", quantity_kg="450"))
    blok_2 = _blok_dari(_batch(batch_id="b-2", quantity_kg="450"))
    agregat = blok_bukti_kandidat(
        batch_blok=[blok_1, blok_2], batch_ids=["b-1", "b-2"], held_batch_ids=[]
    )
    assert agregat["temperature_observation"] == "observed", agregat
    assert agregat["evidence_state"] == "sufficient", agregat
    assert agregat["observed_at"] is not None, agregat
    assert agregat["sample_count"] == 4, agregat
    assert agregat["source_label"] == "log simulasi", agregat
    per_batch = agregat["batch_evidence"]
    assert {b["batch_id"] for b in per_batch} == {"b-1", "b-2"}
    assert all(b["temperature_observation"] == "observed" for b in per_batch)


def test_agregat_tanpa_profil_mengaku_bukan_mengarang_rentang():
    """Komoditas tanpa profil tidak boleh mengaku `observed`/cukup."""
    blok = blok_bukti_profil_hilang(
        komoditas="kangkung", origin="seed", evaluation_time=AS_OF
    )
    agregat = blok_bukti_kandidat(
        batch_blok=[{"batch_id": "b-k", **blok}],
        batch_ids=["b-k"],
        held_batch_ids=[],
    )
    assert agregat["profile_source"] == "tidak ada", agregat
    assert agregat["temperature_observation"] != "observed", agregat
    assert agregat["evidence_state"] == "insufficient", agregat
