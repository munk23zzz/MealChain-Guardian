"""Service rekomendasi deterministik (Task 9 Sprint 2).

Pipeline terkunci (plan): fetch facts → gaps → candidates → hard
elimination → Candidate Score → SDC → rank. Tanpa LLM/agent/SAP.

Ruling Task 9 (ledger progress.md):
1. fetch_facts() callable tanpa argumen, mengembalikan 6-tuple
   (supply, demand, refs, quotes, batches, reliability); pemilihan
   latest-record ada di fetcher produksi (recorded_at DESC, id DESC).
2. transport 300 Rp/km/ton x distance_km x ton; handling flat 150.000.
3. supplier_reliability dari DB (Task 4); fallback 0.80 bila quote
   tanpa supplier dikenal.
4. purchase_cost = supplier_quote bila ada, else pihps reference.

Fase 7d (keputusan pemilik 2026-10-15, plan §7.4 #4 + §7.4b) MENAMBAH satu
komponen biaya angkut TANPA mengubah kontrak di atas:
- transport = kaki pertama (pemasok → SPPG sumber, dari koordinat:
  `app/core/supplier_leg.py`) + linehaul (SPPG sumber → SPPG tujuan, matriks
  `logistics.py`, tarif tetap 300 Rp/km/ton).
- fetch_facts BOLEH mengembalikan elemen ke-7 = peta jarak pemasok
  {(supplier_id, nama lokasi) -> km}. 6-tuple lama tetap sah: tanpa peta itu
  kaki pertama ditandai "tidak diketahui" dan bernilai 0 — tidak ditebak.
- Jarak linehaul (`logistics_distance_km`) dan kelayakan delivery window
  TIDAK berubah: yang berubah hanya angka biaya, bukan eligibilitas.
"""

import inspect
from dataclasses import replace
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from app.core.candidate import PriceInfo
from app.core.candidate_generation import generate_candidates
from app.core.commodity_policy import policy_for
from app.core.config import settings
from app.core.delivery_policy import (
    TERLAMPAUI,
    arrival_due_at,
    jendela_kirim,
    muat_terlampaui,
)
from app.core.freshness import (
    compute_freshness_score,  # noqa: F401  (re-export
    evaluate_freshness,
)
from app.core.logistics import estimate_logistics
from app.core.menu_hierarchy import cadangan_kontinuitas_kg, kebutuhan_menu_kg
from app.core.policy_store import baca_semua_profil
from app.core.price import price_deviation
from app.core.proposal_explain import held_candidate
from app.core.ranking import ScoredCandidate, rank_candidates
from app.core.safe_delivered_cost import (
    SafeDeliveredCostInputs,
    calculate_safe_delivered_cost,
)
from app.core.scoring import CandidateScoreFactors, calculate_candidate_score
from app.core.supplier_leg import (
    LEG_REFERENCE_COORDINATES,
    LEG_REFERENCE_MISSING,
    LEG_REFERENCE_NO_SUPPLIER,
    supplier_leg_map,
)
from app.models import (
    Batch,
    Commodity,
    DemandRecord,
    Location,
    MenuPlan,
    PriceSignal,
    Supplier,
    SupplierExclusion,
    SupplyRecord,
)

# untuk pemanggil lama: fungsi pindah ke `core/freshness` saat profil komoditas
# masuk; tes snapshot & tool lain masih membaca `rs.compute_freshness_score`)
from app.services.decision_time import evaluation_clock

__all__ = ["build_recommendations", "fetch_operational_facts"]

TRANSPORT_RATE = Decimal("300")  # Rp per km per ton
HANDLING_FLAT = Decimal("150000")
DEFAULT_RELIABILITY = Decimal("0.80")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _score(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


async def _latest_rows(db, model, as_of):
    """Baris terbaru per (lokasi, komoditas) yang SUDAH terjadi pada `as_of`.

    Batas waktu wajib: deret demo berjalan sampai 4 Nov, jadi tanpa filter ini
    alokasi memakai baris masa depan sementara peta memakai "sekarang".
    """
    rows = (
        (
            await db.execute(
                select(model)
                .where(model.recorded_at <= as_of)
                .order_by(model.recorded_at.desc(), model.id.desc())
            )
        )
        .scalars()
        .all()
    )
    latest = {}
    for row in rows:
        latest.setdefault((row.location_id, row.commodity_id), row)
    return latest


def _suhu_lengkap(log: list, policy, as_of) -> bool:
    """Bukti suhu memadai menurut profil komoditas (parser kanonik).

    - Profil ambient tanpa kewajiban rantai dingin (`has_temperature_band`
      False): tidak ada bukti suhu yang dituntut → `True`.
    - Profil rantai dingin: cukup bila parser menilai `sufficient`; sampel yang
      terlalu tua (`max_observation_age_minutes`) membuatnya TIDAK cukup, dan
      itu memang yang ingin ditahan gerbang.
    """
    if getattr(policy, "has_temperature_band", True) is False:
        return True
    from app.core.temperature import parse_temperature_log

    parsed = parse_temperature_log(list(log), policy=policy, evaluation_time=as_of)
    return parsed.evidence_state == "sufficient"


async def fetch_operational_facts(db, as_of):
    """Baca DB dan kembalikan facts untuk build_recommendations.

    7 elemen sejak Fase 7d: 6-tuple Task 9 + peta jarak pemasok→SPPG
    {(supplier_id, nama lokasi) -> km}. Peta ini dibangun dari koordinat
    NYATA (`suppliers.latitude/longitude` vs `locations.latitude/longitude`);
    pemasok tanpa koordinat sengaja TIDAK muncul di peta (bukan 0 km).
    """
    # `as_of=None` = jam dinding: kontrak fungsi ini adalah "baris yang sudah
    # terjadi sampai sekarang" (diuji `test_recommendation_as_of`). Jangkar
    # sesi demo adalah jam EVALUASI, bukan batas data: ia diberikan pemanggil
    # (`event1_orchestrator`, `/balance/*`) dan dipakai `build_recommendations`.
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    loc_rows = (await db.execute(select(Location))).scalars().all()
    locs = {loc.id: loc.name for loc in loc_rows}
    coms = {c.id: c.name for c in (await db.execute(select(Commodity))).scalars()}
    # Catatan Fase 3 MG: peta masa layak lokal (`_shelf_life_map()`) TIDAK lagi
    # dipakai di sini — masa layak kini milik profil komoditas
    # (`commodity_policies`), dibaca bersama rentang suhu dan batas usia sampel
    # supaya ketiganya tidak bisa saling bertentangan.

    supply = {}
    for (loc_id, com_id), row in (
        await _latest_rows(db, SupplyRecord, as_of)
    ).items():
        supply[(locs[loc_id], coms[com_id])] = Decimal(str(row.quantity_kg))

    demand = {}
    needed_by = {}
    for (loc_id, com_id), row in (
        await _latest_rows(db, DemandRecord, as_of)
    ).items():
        demand[(locs[loc_id], coms[com_id])] = Decimal(str(row.quantity_kg))
        # Fase 4 butir 6: `needed_by` = jam barang DIBUTUHKAN, dari baris yang
        # sama dengan kuantitas permintaan. Tanpa ini tidak ada dasar untuk
        # menyatakan sebuah kandidat masih bisa tiba tepat waktu.
        needed_by[(locs[loc_id], coms[com_id])] = row.needed_by

    refs, quotes = {}, {}
    # Harga: latest per (location, commodity, SOURCE) — pihps dan quote
    # hidup berdampingan untuk pasangan yang sama (disiplin dua lapis).
    price_rows = (
        (
            await db.execute(
                select(PriceSignal)
                .where(PriceSignal.recorded_at <= as_of)
                .order_by(PriceSignal.recorded_at.desc(), PriceSignal.id.desc())
            )
        )
        .scalars()
        .all()
    )
    price_latest: dict = {}
    for row in price_rows:
        price_latest.setdefault((row.location_id, row.commodity_id, row.source), row)
    for (loc_id, com_id, _source), row in price_latest.items():
        key = (locs[loc_id], coms[com_id])
        if row.source == "pihps_reference":
            refs[key] = Decimal(str(row.price_per_kg))
        else:
            quotes[key] = (Decimal(str(row.price_per_kg)), row.supplier_id)

    active_exclusions = (
        (await db.execute(select(SupplierExclusion).where(SupplierExclusion.status == "active")))
        .scalars()
        .all()
    )
    batches = []
    # A later read can see harvests newer than the captured evaluation time.
    # Exclude them at the query boundary, including for explicit historical as_of;
    # never advance the clock or award freshness to a future harvest.
    batch_query = select(Batch).where(Batch.harvested_at <= as_of)
    # Fase 3 MG: profil komoditas dibaca SEKALI dari `commodity_policies`
    # (fallback bawaan kode), bukan `settings.safe_temp_min_c/max_c` untuk semua
    # komoditas. Sebelumnya beras dinilai terhadap 0-8 °C sehingga log suhu ruang
    # 27 °C dihitung excursion dan skornya turun tanpa alasan domain.
    profil_komoditas = await baca_semua_profil(db)
    for b in (await db.execute(batch_query)).scalars():
        name = coms[b.commodity_id]
        policy, _asal = profil_komoditas.get(
            (name or "").strip().lower(), (policy_for(name), "bawaan")
        )
        hasil = evaluate_freshness(
            harvested_at=b.harvested_at,
            as_of=as_of,
            policy=policy,
            temperature_log=b.temperature_log or [],
        )
        batches.append(
            {
                "batch_id": str(b.id),
                "supplier_id": str(b.supplier_id) if b.supplier_id else None,
                "excluded_destinations": [
                    locs[e.scope_location_id]
                    for e in active_exclusions
                    if e.supplier_id == b.supplier_id
                ],
                "location": locs[b.location_id],
                "commodity": name,
                "quantity_kg": Decimal(str(b.quantity_kg)),
                "freshness_score": _score(Decimal(str(hasil.score))),
                # Status memakai gerbang bukti: batch rantai dingin tanpa bukti
                # suhu cukup tidak bisa `pass` hanya karena umurnya masih muda.
                "freshness_status": hasil.status,
                # Bukti suhu ikut dibawa supaya agregasi (dan Joule) bisa
                # menyebut bukti TERLEMAH, bukan hanya skor rata-rata.
                "temperature_observation": hasil.temperature_observation,
                "evidence_state": hasil.evidence_state,
                # Fase 6: gerbang kelayakan butuh jawaban "bukti suhu cukup?"
                # TANPA membawa log penuh ke generator (JSONB bisa besar).
                # Nilainya dari parser yang SAMA dengan gate dispatch, dan
                # `evidence_state` freshness TIDAK dipakai di sini: untuk
                # komoditas ambient (beras) state itu "insufficient" padahal
                # tidak ada bukti suhu yang diwajibkan.
                "temperature_evidence_complete": _suhu_lengkap(
                    b.temperature_log or [], policy, as_of
                ),
                "observed_at": (
                    hasil.observation.last_sample_at.isoformat()
                    if hasil.observation.last_sample_at
                    else None
                ),
                "policy_version": policy.policy_version,
                "safety_status": b.safety_status,
                # Karantina dibaca oleh generate_candidates: batch ditahan
                # dikeluarkan dari kandidat, jadi kilogramnya tidak masuk
                # available_kg walau stok fisik tetap tercatat.
                "quarantine_status": b.quarantine_status,
                # Fase 4 butir 6: masa layak dibawa supaya gerbang jendela bisa
                # menolak barang yang kedaluwarsa DI JALAN (tiba > usable_until),
                # bukan hanya yang sudah kedaluwarsa saat evaluasi.
                "usable_until": b.usable_until,
            }
        )

    supplier_rows = (await db.execute(select(Supplier))).scalars().all()
    reliability = {
        str(s.id): Decimal(str(s.reliability_score)) for s in supplier_rows
    }
    # Fase 7d: kaki pertama angkut = pemasok → SPPG tempat batch berada.
    supplier_legs = supplier_leg_map(
        {str(s.id): (s.latitude, s.longitude) for s in supplier_rows},
        {loc.name: (loc.latitude, loc.longitude) for loc in loc_rows},
    )
    # Lapis 2 & 3 hierarki: kebutuhan menu hari itu dan cadangan kontinuitas
    # per (lokasi, komoditas). Tanpa baris `menu_plans` → peta kosong, dan
    # generator berperilaku seperti sebelumnya (tidak ada angka karangan).
    menu_requirements, continuity_reserve = await _menu_hierarchy_maps(
        db, locs, as_of
    )
    # Fase 6: gerbang bukti memakai profil komoditas yang SAMA dengan evaluasi
    # freshness di atas — satu profil, bukan dua salinan aturan.
    policies = {nama: pol for nama, (pol, _asal) in profil_komoditas.items()}

    return (
        supply,
        demand,
        refs,
        quotes,
        batches,
        reliability,
        supplier_legs,
        {
            "menu_requirements": menu_requirements,
            "continuity_reserve": continuity_reserve,
            "policies": policies,
            "needed_by": needed_by,
        },
    )


_GRAM_PER_PORSI = {
    "telur": settings.menu_grams_telur,
    "ayam": settings.menu_grams_ayam,
    "wortel": settings.menu_grams_wortel,
}


async def _menu_hierarchy_maps(db, locs: dict, as_of):
    """Kebutuhan menu & cadangan kontinuitas per (lokasi, komoditas).

    Porsi diambil dari `menu_plans` untuk tanggal as_of menurut zona WIB (hari
    kerja dapur SPPG), dikali gram per porsi dari settings. Komoditas tanpa
    gram per porsi tidak menghasilkan kebutuhan (0), jadi tidak ada lokasi yang
    tiba-tiba "butuh" komoditas yang tidak masuk komposisi menunya.
    """
    from zoneinfo import ZoneInfo

    tanggal = as_of.astimezone(ZoneInfo("Asia/Jakarta")).date()
    rows = (
        await db.execute(
            select(MenuPlan).where(MenuPlan.plan_date == tanggal)
        )
    ).scalars().all()
    komoditas = [c.name for c in (await db.execute(select(Commodity))).scalars()]
    menu: dict = {}
    cadangan: dict = {}
    for plan in rows:
        lokasi = locs.get(plan.location_id)
        if lokasi is None:
            continue
        for nama in komoditas:
            gram = _GRAM_PER_PORSI.get(nama, 0.0)
            if gram <= 0:
                continue
            menu[(lokasi, nama)] = kebutuhan_menu_kg(plan.planned_portions, gram)
            cadangan[(lokasi, nama)] = cadangan_kontinuitas_kg(
                plan.planned_portions, gram, settings.continuity_reserve_days
            )
    return menu, cadangan


def _build_prices_map(refs, quotes):
    """PriceInfo per (source, dest, commodity); quote milik source."""
    prices = {}
    for (s_loc, com), ref in refs.items():
        quote, sid = quotes.get((s_loc, com), (None, None))
        for (d_loc, com2), _ref in refs.items():
            if com2 != com or d_loc == s_loc:
                continue
            prices[(s_loc, d_loc, com)] = PriceInfo(
                reference_price=ref,
                supplier_quote=quote,
                supplier_id=str(sid) if sid else None,
            )
    return prices


def _filter_commodity(
    supply: dict,
    demand: dict,
    refs: dict,
    quotes: dict,
    batches: list,
    commodity: str | None,
) -> tuple:
    """Ruling Owner 2026-10-08 (S4-05 p10): filter facts ke 1 komoditas.

    Dipakai /balance/analyze agar proposal mengikuti komoditas panel
    (bukan selalu rank-1 global). None = tanpa filter (perilaku lama —
    dipakai /balance/recommend dan orchestrator Event 1/3).
    """
    if not commodity:
        return supply, demand, refs, quotes, batches
    return (
        {k: v for k, v in supply.items() if k[1] == commodity},
        {k: v for k, v in demand.items() if k[1] == commodity},
        {k: v for k, v in refs.items() if k[1] == commodity},
        {k: v for k, v in quotes.items() if k[1] == commodity},
        [b for b in batches if b.get("commodity") == commodity],
    )


def _resolve_supplier_leg(supplier_legs, supplier_id, source_location):
    """Jarak kaki pertama untuk satu kandidat + label kejujurannya.

    Tiga kemungkinan, tidak ada tebakan:
    - tidak ada identitas pemasok → `no_supplier`;
    - pemasok ada tetapi tanpa koordinat lengkap (atau lokasi tanpa koordinat)
      → `supplier_coordinates_missing`;
    - ada di peta → km eksak + `supplier_coordinates`.
    """
    if not supplier_id:
        return None, LEG_REFERENCE_NO_SUPPLIER
    km = (supplier_legs or {}).get((str(supplier_id), str(source_location)))
    if km is None:
        return None, LEG_REFERENCE_MISSING
    return Decimal(str(km)), LEG_REFERENCE_COORDINATES


def _ke_utc(nilai):
    """Waktu dari DB bisa naif; bandingkan di zona yang sama, jangan menebak."""
    if nilai is None:
        return None
    if nilai.tzinfo is None:
        return nilai.replace(tzinfo=timezone.utc)
    return nilai


def _gerbang_jendela_kirim(
    candidates, *, needed_by, umur_batch, logistics_by_pair, evaluation_time, held
):
    """Saring kandidat dengan jendela kirim; kembalikan (lolos, peta jendela).

    `peta` menyimpan (JendelaKirim, waktu_tiba) per (sumber, tujuan, komoditas)
    supaya payload bisa menjelaskan ALASAN lolos/gugur, bukan hanya hasilnya.
    """
    lolos, peta = [], {}
    for cand in candidates:
        kunci = (cand.destination_location, cand.commodity)
        jendela = jendela_kirim(
            needed_by=needed_by.get(kunci), evaluation_time=evaluation_time
        )
        est = logistics_by_pair.get((cand.source_location, cand.destination_location)) or {}
        # Fase 4 butir 6: batas waktu DISERAHKAN ke `estimate_logistics()`, bukan
        # diperiksa di luarnya. Tanpa ini `feasible` selalu True semata karena
        # fungsi dipanggil tanpa batas, dan kandidat yang tak mungkin tiba
        # tetap lolos.
        try:
            hitung = estimate_logistics(
                cand.source_location,
                cand.destination_location,
                float(cand.quantity_kg or 1),
                delivery_window_min=jendela.window_min,
            )
        except ValueError:
            hitung = None
        dasar = hitung or est
        estimasi = float(dasar.get("estimated_time_min") or 0.0)
        tiba = arrival_due_at(evaluation_time, estimasi) if dasar else None

        if jendela.state == TERLAMPAUI:
            lewat = True
        elif hitung is not None:
            lewat = not bool(hitung["feasible"])
        else:
            lewat = muat_terlampaui(jendela, estimated_time_min=estimasi)

        alasan = []
        if lewat:
            alasan.append("delivery_window_exceeded")
        if tiba is not None:
            habis = [
                u
                for u in (_ke_utc(umur_batch.get(str(b))) for b in cand.batch_ids)
                if u is not None
            ]
            if habis and min(habis) < tiba:
                alasan.append("expired_before_arrival")
        if alasan:
            held.append(
                held_candidate(
                    source_location=cand.source_location,
                    destination_location=cand.destination_location,
                    commodity=cand.commodity,
                    supplier_id=cand.supplier_id,
                    quantity_kg=cand.quantity_kg,
                    status="held",
                    reasons=alasan,
                    batch_ids=cand.batch_ids,
                )
            )
            continue
        peta[(cand.source_location, cand.destination_location, cand.commodity)] = (
            jendela,
            tiba,
        )
        lolos.append(cand)
    return lolos, peta


async def build_recommendations(
    fetch_facts, as_of=None, logistics_by_pair=None, commodity: str | None = None
):
    """Pipeline deterministik penuh; hasil terurut rank 1..N.

    fetch_facts boleh sync (kembalikan 6-tuple) atau async (kembalikan
    coroutine 6-tuple) — pipeline tetap identik.
    `commodity` (opsional, ruling S4-05): filter facts ke 1 komoditas;
    None = global (perilaku lama).
    """
    facts = fetch_facts()
    if inspect.isawaitable(facts):
        facts = await facts
    supply, demand, refs, quotes, batches, reliability = facts[:6]
    # Fase 7d: elemen ke-7 (peta jarak pemasok) opsional — 6-tuple kontrak
    # Task 9 tetap sah; tanpa peta kaki pertama ditandai "tidak diketahui".
    supplier_legs = facts[6] if len(facts) > 6 else {}
    # Elemen ke-8 (peta hierarki gizi/menu & kontinuitas) juga opsional: kontrak
    # 6-tuple Task 9 tetap sah, dan pemanggil lama tidak berubah perilakunya.
    hierarki = facts[7] if len(facts) > 7 else {}
    menu_requirements = hierarki.get("menu_requirements") or None
    continuity_reserve = hierarki.get("continuity_reserve") or None
    policies = hierarki.get("policies") or None
    supply, demand, refs, quotes, batches = _filter_commodity(
        supply, demand, refs, quotes, batches, commodity
    )
    if as_of is None:
        as_of = evaluation_clock()

    prices_map = _build_prices_map(refs, quotes)
    held: list = []
    if logistics_by_pair is None:
        logistics_by_pair = {}
        for s_loc, d_loc, _com in prices_map:
            logistics_by_pair.setdefault(
                (s_loc, d_loc),
                estimate_logistics(s_loc, d_loc, 1.0),
            )

    candidates = generate_candidates(
        source_records=supply,
        destination_records=demand,
        batches=batches,
        logistics_by_pair=logistics_by_pair,
        prices=prices_map,
        menu_requirements=menu_requirements,
        continuity_reserve=continuity_reserve,
        # Fase 6: gerbang bukti + laporan kandidat yang tertahan.
        policies=policies,
        evaluation_time=as_of,
        held=held,
    )

    # Fase 4 butir 6: kandidat yang lolos gerbang bukti masih harus MUAT dalam
    # jendela kirim. Dua pemeriksaan, keduanya memakai modul murni yang sama
    # dengan tesnya: anggaran waktu vs estimasi angkut, dan masa layak batch vs
    # waktu tiba. Kandidat yang gugur masuk `held`, tidak hilang diam-diam.
    candidates, jendela_per_kunci = _gerbang_jendela_kirim(
        candidates,
        needed_by=hierarki.get("needed_by") or {},
        umur_batch={str(b.get("batch_id")): b.get("usable_until") for b in batches},
        logistics_by_pair=logistics_by_pair,
        evaluation_time=as_of,
        held=held,
    )

    scored = []
    breakdowns: dict = {}
    for cand in candidates:
        sid = cand.supplier_id or cand.price.supplier_id
        rel = reliability.get(sid, DEFAULT_RELIABILITY) if sid else DEFAULT_RELIABILITY
        if rel != cand.supplier_reliability:
            cand = replace(cand, supplier_reliability=rel)
        result = calculate_candidate_score(
            CandidateScoreFactors(
                demand_fit=cand.demand_fit,
                supply_availability=cand.supply_availability,
                freshness_score=cand.freshness_score,
                safety_status=cand.safety_status,
                supplier_reliability=rel,
                logistics_feasible=cand.logistics_feasible,
            )
        )
        unit = cand.price.supplier_quote or cand.price.reference_price
        # Fase 7d: biaya angkut = kaki pertama (pemasok → SPPG sumber) +
        # linehaul (SPPG sumber → SPPG tujuan); satu tarif 300 Rp/km/ton.
        linehaul_cost = _money(
            TRANSPORT_RATE * cand.logistics_distance_km * cand.quantity_kg / 1000
        )
        leg_km, leg_reference = _resolve_supplier_leg(
            supplier_legs, sid, cand.source_location
        )
        leg_cost = (
            _money(TRANSPORT_RATE * leg_km * cand.quantity_kg / 1000)
            if leg_km is not None
            else Decimal("0.00")
        )
        sdc = calculate_safe_delivered_cost(
            SafeDeliveredCostInputs(
                purchase_cost=_money(cand.quantity_kg * unit),
                transport_cost=linehaul_cost + leg_cost,
                handling_cost=HANDLING_FLAT,
                freshness_score=cand.freshness_score,
                safety_status=cand.safety_status,
            )
        )
        breakdown = {
            "purchase": str(sdc.purchase_cost),
            "transport": str(sdc.transport_cost),
            # "logistics" = alias total angkut untuk pembaca lama (label UI
            # "Logistik"); BUKAN komponen ketujuh — komponen SDC tetap 6.
            "logistics": str(sdc.transport_cost),
            "transport_linehaul": str(linehaul_cost),
            "transport_supplier_leg": str(leg_cost),
            "supplier_leg_km": str(leg_km) if leg_km is not None else None,
            "supplier_leg_reference": leg_reference,
            "handling": str(sdc.handling_cost),
            "expected_loss": str(sdc.expected_loss),
            "freshness_risk": str(sdc.freshness_risk_penalty),
            "safety_penalty": str(sdc.safety_risk_penalty),
        }
        scored.append(
            ScoredCandidate(
                candidate=cand,
                candidate_id=(
                    f"{cand.source_location}->{cand.destination_location}:"
                    f"{cand.commodity}" + (f":{cand.supplier_id}" if cand.supplier_id else "")
                ),
                score=_score(result.score),
                eligible=result.eligible,
                review_required=result.review_required,
                safe_delivered_cost=sdc.total,
            )
        )
        breakdowns[
            f"{cand.source_location}->{cand.destination_location}:"
            f"{cand.commodity}" + (f":{cand.supplier_id}" if cand.supplier_id else "")
        ] = breakdown

    ranked = rank_candidates(scored)
    recommendations = []
    for rc in ranked:
        cand = rc.candidate
        payload = rc.to_dict()
        payload["rank"] = rc.rank
        payload["cost_breakdown"] = breakdowns[rc.candidate_id]
        jendela, tiba = jendela_per_kunci.get(
            (cand.source_location, cand.destination_location, cand.commodity),
            (None, None),
        )
        if jendela is not None:
            payload["delivery_window"] = {
                "state": jendela.state,
                "needed_by": (
                    jendela.needed_by.isoformat() if jendela.needed_by else None
                ),
                "window_min": jendela.window_min,
                "arrival_due_at": tiba.isoformat() if tiba else None,
            }
        # Fase 7d: kaki pertama angkut dilaporkan eksplisit (auditable).
        leg_bd = breakdowns[rc.candidate_id]
        payload["supplier_leg"] = {
            "source_location": cand.source_location,
            "supplier_id": cand.supplier_id or cand.price.supplier_id,
            "km": leg_bd.get("supplier_leg_km"),
            "cost": leg_bd.get("transport_supplier_leg"),
            "reference": leg_bd.get("supplier_leg_reference"),
        }
        # Anomali harga: reuse engine price_deviation Sprint 1 (5%/15%).
        if cand.price.supplier_quote is not None:
            dev = price_deviation(cand.price.supplier_quote, cand.price.reference_price)
            payload["price_anomaly"] = {
                "status": dev["status"],
                "deviation_pct": str(
                    dev["deviation_pct"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ),
                "flagged": dev["flagged"],
            }
        else:
            payload["price_anomaly"] = {
                "status": "no_supplier_quote",
                "deviation_pct": None,
                "flagged": False,
            }
        # Evidence: batch sumber yang eligible + sumber harga terpakai.
        payload["evidence"] = {
            "batch_ids": list(cand.batch_ids)
            if cand.batch_ids
            else sorted(
                {
                    str(b["batch_id"])
                    for b in batches
                    if b.get("location") == cand.source_location
                    and b.get("commodity") == cand.commodity
                    and b.get("batch_id")
                }
            ),
            "price_sources": (
                ["pihps_reference", "supplier_quote"]
                if cand.price.supplier_quote is not None
                else ["pihps_reference"]
            ),
        }
        recommendations.append(payload)

    return {
        "generated_at": as_of.isoformat(),
        "facts": {
            "supply": {f"{k[0]}:{k[1]}": str(v) for k, v in supply.items()},
            "demand": {f"{k[0]}:{k[1]}": str(v) for k, v in demand.items()},
        },
        "recommendations": recommendations,
        # Fase 6: kandidat yang TERTAHAN gerbang (on_hold/ditolak) dilaporkan
        # terpisah. Mereka bukan usulan dan tidak punya `rank`; menghapusnya
        # dari respons akan menyembunyikan pekerjaan verifikasi yang tersisa.
        "held": [h.to_dict() for h in held],
    }
