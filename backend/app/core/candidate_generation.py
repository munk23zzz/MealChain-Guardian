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

from decimal import ROUND_CEILING, Decimal

from app.core.candidate import BalancingCandidate, PriceInfo

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
) -> list:
    _require_mapping(source_records, "source_records")
    _require_mapping(destination_records, "destination_records")
    _require_mapping(logistics_by_pair, "logistics_by_pair")
    _require_mapping(prices, "prices")

    # Batches eligible per (location, commodity): buang fail di sini.
    eligible = {}
    for b in batches:
        if b["safety_status"] == "fail" or b["freshness_status"] == "fail":
            continue
        # Batch yang DITAHAN (karantina) tidak boleh menyumbang kilogram ke
        # kandidat sama sekali — beda dari needs_verification yang tetap masuk
        # sebagai review-required. Setelah dilepas, batch kembali dihitung.
        if b.get("quarantine_status") == "quarantined":
            continue
        if "supplier_id" in b and not b["supplier_id"]:
            continue  # supplier_unknown: explicit identity cannot be inferred
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
        if demand <= supply_d:
            continue  # destinasi surplus/balanced → tidak ada shortage
        shortage = demand - supply_d

        source_keys = sorted(
            (s_loc, s_com) for (s_loc, s_com) in source_records if s_com == d_com and s_loc != d_loc
        )
        for s_loc, s_com in source_keys:
            supply_s = _to_decimal(source_records[(s_loc, s_com)], "supply_kg")
            demand_s = _to_decimal(destination_records.get((s_loc, s_com), 0), "demand_kg")
            if supply_s <= demand_s:
                continue  # sumber tanpa surplus
            surplus_s = supply_s - demand_s

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
                    )
                )
    return candidates


def _candidates_for_group(
    group, supplier_id, surplus_s, shortage, s_loc, d_loc, d_com, logistics_by_pair, prices
):
    candidates = []
    agg = _aggregate_batches(group)
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
        return []  # delivery window terlampaui → exclude

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

    candidates.append(
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
            batch_ids=tuple(sorted(str(b["batch_id"]) for b in group if b.get("batch_id"))),
        )
    )
    return candidates
