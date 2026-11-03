"""Generator kandidat cross-regional deterministik (Task 3 Sprint 2).

Kontrak plan Task 3:
- quantity = min(source_surplus, destination_shortage,
  available_eligible_quantity)
- Exclude: source tanpa surplus (shortage), destinasi tanpa shortage
  (surplus/balanced), commodity mismatch, safety fail, freshness fail,
  logistics infeasible. needs_verification tetap masuk (review-required).
- Batas kapasitas & delivery window dijaga persis (inklusif) — feasibility
  diputuskan caller lewat estimate_logistics yang sudah boundary-exact.
- Engine murni: caller menyuplai mapping siap pakai (agregasi latest
  record, pemilihan harga, hasil estimate_logistics).

Interface (diputuskan ruling, ledger 2026-10-05):
- source_records: Mapping[(location, commodity) -> supply_kg] untuk SEMUA
  lokasi (calon source sekaligus pasokan lokal destinasi).
- destination_records: Mapping[(location, commodity) -> demand_kg] untuk
  semua lokasi.
- surplus sumber = max(supply - demand lokal sumber, 0); shortage
  destinasi = max(demand - supply lokal destinasi, 0). Nilai nol =
  exclusi per kontrak.
- demand_fit = quantity / shortage destinasi; supply_availability =
  quantity / surplus sumber (rasio konsisten definisi quantity; tidak ada
  formula tambahan di luar plan).
- prices: Mapping[(source, destination, commodity) -> PriceInfo] — wajib
  ada untuk pasangan yang menghasilkan kandidat, else ValueError.
- logistics_by_pair: Mapping[(source, destination) -> dict hasil
  estimate_logistics] — wajib ada, else ValueError.

Ruling data uji (ledger 2026-10-05): gabungan batch konservatif —
freshness_status = needs_verification bila ada anggotanya; safety mengikuti
status terburuk non-fail (pending > needs_verification > pass); freshness
skor = rata-rata tertimbang quantity. Batch fail tidak pernah ikut.
logistics_time_min dibulatkan KE ATAS ke menit penuh (konservatif,
deterministik) karena model mewajibkan integer.
"""

from dataclasses import replace
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal

from app.core.batch_eligibility import (
    DELIVERY_WINDOW_EXCEEDED,
    POLICY_BAWAAN,
    REJECTED,
    USABLE,
    BatchPolicy,
    batch_policy_from,
    fuse_evidence,
)
from app.core.candidate import BalancingCandidate, PriceInfo
from app.core.menu_hierarchy import shortage_setelah_gizi, surplus_setelah_kontinuitas
from app.core.proposal_explain import held_candidate

__all__ = ["generate_candidates"]

_SAFETY_WORST_ORDER = {"pass": 0, "needs_verification": 1, "pending": 2}


def _to_decimal(value, name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:  # noqa: BLE001 - konversi generik disengaja
        raise ValueError(f"{name} bukan angka valid: {value!r}") from exc


def _require_mapping(value, name: str) -> None:
    if not hasattr(value, "items") or not hasattr(value, "__getitem__"):
        raise ValueError(f"{name} wajib mapping ber-key tuple")


def _worst_safety(statuses: set) -> str:
    return max(statuses, key=lambda s: _SAFETY_WORST_ORDER.get(s, 99))


def _aggregate_batches(batches) -> dict:
    """Gabungkan batch eligible satu lokasi secara konservatif.

    Batch berkuantitas <= 0 dilewati: tidak ada kilogram yang bisa dikirim, dan
    kalau ikut dijumlahkan, total_qty bisa 0 sehingga rata-rata berbobot menjadi
    0/0 — `decimal.InvalidOperation` (ArithmeticError, BUKAN ValueError) yang
    mematikan seluruh pipeline rekomendasi/Event 1/Event 3.
    """
    total_qty = Decimal("0")
    weighted_freshness = Decimal("0")
    freshness_statuses = set()
    safety_statuses = set()
    for b in batches:
        qty = _to_decimal(b["quantity_kg"], "quantity_kg")
        if qty <= 0:
            continue
        score = _to_decimal(b["freshness_score"], "freshness_score")
        total_qty += qty
        weighted_freshness += qty * score
        freshness_statuses.add(b["freshness_status"])
        safety_statuses.add(b["safety_status"])
    if total_qty <= 0:
        # Tidak ada kuantitas terkirim: skor tidak punya makna. Pemanggil
        # berhenti di `available_kg <= 0` (tanpa kandidat), jadi nilai di sini
        # tidak pernah dibaca sebagai hasil.
        return {
            "available_kg": Decimal("0"),
            "freshness_score": Decimal("0"),
            "freshness_status": "pass",
            "safety_status": "pass",
        }
    freshness_status = (
        "needs_verification" if "needs_verification" in freshness_statuses else "pass"
    )
    safety_status = _worst_safety(safety_statuses)
    return {
        "available_kg": total_qty,
        "freshness_score": weighted_freshness / total_qty,
        "freshness_status": freshness_status,
        "safety_status": safety_status,
    }


def generate_candidates(
    source_records,
    destination_records,
    batches,
    logistics_by_pair,
    *,
    prices,
    commodity=None,
    menu_requirements=None,
    continuity_reserve=None,
    policies=None,
    evaluation_time=None,
    held=None,
) -> list:
    """Kandidat yang LOLOS gerbang hierarki (Fase 6 butir 1 & 2).

    `policies` (opsional) = peta nama komoditas → profil berversi
    (`core.commodity_policy.CommodityPolicy`). `evaluation_time` wajib untuk
    menilai masa layak/bukti; bawaannya jam dinding UTC.

    `held` (opsional, list) diisi kandidat yang TERTAHAN gerbang beserta
    alasannya — informasi tidak dihapus, hanya tidak diberi peringkat. Kandidat
    yang lolos tetap menjalani ranking lama (`Candidate Score DESC`, lalu SDC
    ASC): hierarki berjalan SEBELUM ranking, bukan sebagai bobot baru.
    """
    _require_mapping(source_records, "source_records")
    _require_mapping(destination_records, "destination_records")
    _require_mapping(logistics_by_pair, "logistics_by_pair")
    _require_mapping(prices, "prices")
    waktu = evaluation_time or datetime.now(timezone.utc)

    # Batches per (location, commodity, supplier). `fail`/`quarantined` TIDAK
    # dibuang di sini: evaluator yang memutuskan dan alasannya ikut dilaporkan
    # (dulu batch seperti itu hilang tanpa jejak). Identitas pemasok yang tidak
    # dapat diketahui tetap dilewati — itu bukan soal bukti.
    eligible = {}
    for b in batches:
        if "supplier_id" in b and not b["supplier_id"]:
            continue  # supplier_unknown: explicit identity cannot be inferred
        if policies is None:
            # Jalur warisan (tanpa profil komoditas): aturan lama tetap berlaku
            # supaya perilaku pemanggil 6-tuple tidak berubah.
            if b["safety_status"] == "fail" or b["freshness_status"] == "fail":
                continue
            if b.get("quarantine_status") == "quarantined":
                continue
        key = (b["location"], b["commodity"], b.get("supplier_id"))
        if commodity is not None and b["commodity"] != commodity:
            continue
        eligible.setdefault(key, []).append(b)

    # Destinasi kandidat: punya shortage > 0, terurut deterministik.
    destination_keys = sorted(
        key for key in destination_records if commodity is None or key[1] == commodity
    )

    candidates: list[BalancingCandidate] = []
    for d_loc, d_com in destination_keys:
        demand = _to_decimal(destination_records[(d_loc, d_com)], "demand_kg")
        supply_d = _to_decimal(source_records.get((d_loc, d_com), 0), "supply_kg")
        # Lapis 2 hierarki: kebutuhan menu adalah LANTAI kekurangan destinasi.
        menu_d = _to_decimal(
            (menu_requirements or {}).get((d_loc, d_com), 0), "kebutuhan_menu_kg"
        )
        shortage = shortage_setelah_gizi(demand, supply_d, menu_d)
        if shortage <= 0:
            continue  # destinasi surplus/balanced (dan menunya sudah tertutup)

        source_keys = sorted(
            (s_loc, s_com) for (s_loc, s_com) in source_records if s_com == d_com and s_loc != d_loc
        )
        for s_loc, s_com in source_keys:
            supply_s = _to_decimal(source_records[(s_loc, s_com)], "supply_kg")
            demand_s = _to_decimal(destination_records.get((s_loc, s_com), 0), "demand_kg")
            # Lapis 3 hierarki: cadangan kontinuitas lokasi asal tidak diekspor.
            cadangan_s = _to_decimal(
                (continuity_reserve or {}).get((s_loc, s_com), 0), "cadangan_kg"
            )
            surplus_s = surplus_setelah_kontinuitas(supply_s, demand_s, cadangan_s)
            if surplus_s <= 0:
                continue  # sumber tanpa surplus yang boleh keluar

            groups = [
                (sid, [b for b in group if d_loc not in b.get("excluded_destinations", [])])
                for (loc, com, sid), group in eligible.items()
                if loc == s_loc and com == d_com
            ]
            for supplier_id, group in groups:
                if not group:
                    continue
                candidates.extend(
                    _candidates_for_group(
                        group,
                        supplier_id,
                        surplus_s,
                        shortage,
                        s_loc,
                        d_loc,
                        d_com,
                        logistics_by_pair,
                        prices,
                        policies=policies,
                        evaluation_time=waktu,
                        held=held,
                    )
                )
    return candidates


def _policy_untuk(profil, group) -> BatchPolicy:
    """Profil komoditas → `BatchPolicy`; warisan tanpa-bukti tetap sah.

    Pemanggil lama (`generate_candidates` 6-tuple Task 9) menyuplai fakta batch
    tanpa `temperature_log`/`temperature_evidence_complete`. Fakta yang tidak
    membawa informasi suhu TIDAK boleh dihukum sebagai "bukti hilang" — itu
    akan mematikan seluruh pipeline lama tanpa satu pun data yang berubah.
    Pipeline produksi (Fase 3+) selalu membawa bukti suhu, jadi di sana gerbang
    bukti benar-benar berjalan.
    """
    if profil is not None:
        return batch_policy_from(profil)
    ada_bukti = any(
        "temperature_log" in b or "temperature_evidence_complete" in b for b in group
    )
    return replace(POLICY_BAWAAN, require_temperature_log=ada_bukti)


def _candidates_for_group(
    group,
    supplier_id,
    surplus_s,
    shortage,
    s_loc,
    d_loc,
    d_com,
    logistics_by_pair,
    prices,
    *,
    policies=None,
    evaluation_time=None,
    held=None,
):
    waktu = evaluation_time or datetime.now(timezone.utc)
    # Gerbang bukti hanya aktif bila pemanggil menyerahkan profil komoditas.
    # Pemanggil warisan (tanpa profil) tetap memakai aturan lama; menyalakan
    # gerbang tanpa fakta bukti berarti menghukum data yang tidak ada.
    gerbang = policies is not None
    profil = (policies or {}).get(d_com)
    fisik_kg = sum(
        (_to_decimal(b["quantity_kg"], "quantity_kg") for b in group), Decimal("0")
    )

    def tahan(status: str, alasan) -> list:
        if held is not None:
            held.append(
                held_candidate(
                    source_location=s_loc,
                    destination_location=d_loc,
                    commodity=d_com,
                    supplier_id=str(supplier_id) if supplier_id else None,
                    quantity_kg=fisik_kg,
                    status=status,
                    reasons=alasan,
                    batch_ids=[
                        str(b.get("batch_id")) for b in group if b.get("batch_id")
                    ],
                )
            )
        return []

    if gerbang:
        fusion = fuse_evidence(
            group, policy=_policy_untuk(profil, group), evaluation_time=waktu
        )
        if fusion.status != USABLE:
            # Bukti tidak cukup (on_hold) atau ditolak: TIDAK ada kandidat aman.
            return tahan(fusion.status, fusion.blocking_reasons)
        usable_ids = set(fusion.usable_batch_ids)
    else:
        usable_ids = {str(b.get("batch_id")) for b in group}

    agg = _aggregate_batches(
        [b for b in group if str(b.get("batch_id")) in usable_ids]
    )
    quantity = min(surplus_s, shortage, agg["available_kg"])
    if quantity <= 0:
        return []

    pair = (s_loc, d_loc)
    if pair not in logistics_by_pair:
        raise ValueError(
            f"pasangan logistik tidak ditemukan: {pair} — "
            "logistics_by_pair wajib memuat semua pasangan kandidat"
        )
    logistics = logistics_by_pair[pair]
    if not logistics["feasible"]:
        # Lapis 2 hierarki: waktu tiba tidak memenuhi jendela → bukan kandidat.
        return tahan(REJECTED, (DELIVERY_WINDOW_EXCEEDED,))

    price_key = (s_loc, d_loc, d_com)
    if price_key not in prices:
        raise ValueError(
            f"harga tidak ditemukan untuk {price_key} — prices "
            "wajib memuat semua pasangan kandidat"
        )
    price = prices[price_key]
    if not isinstance(price, PriceInfo):
        price = PriceInfo(**price)

    if supplier_id is not None and price.supplier_id != str(supplier_id):
        price = PriceInfo(reference_price=price.reference_price)

    time_min = Decimal(str(logistics["estimated_time_min"]))
    time_min_int = int(time_min.to_integral_value(rounding=ROUND_CEILING))

    return [
        BalancingCandidate(
            source_location=s_loc,
            destination_location=d_loc,
            commodity=d_com,
            quantity_kg=quantity,
            demand_fit=quantity / shortage,
            supply_availability=quantity / surplus_s,
            freshness_score=agg["freshness_score"],
            freshness_status=agg["freshness_status"],
            safety_status=agg["safety_status"],
            supplier_reliability=Decimal("0.80"),
            logistics_feasible=True,
            logistics_distance_km=Decimal(str(logistics["distance_km"])),
            logistics_time_min=time_min_int,
            price=price,
            supplier_id=str(supplier_id) if supplier_id else None,
            # `usable_ids` dipakai, bukan seluruh `group`: batch yang ditahan
            # tidak boleh ikut tercatat sebagai bukti kandidat ini.
            batch_ids=tuple(
                sorted(
                    str(b["batch_id"])
                    for b in group
                    if b.get("batch_id") and str(b.get("batch_id")) in usable_ids
                )
            ),
        )
    ]
