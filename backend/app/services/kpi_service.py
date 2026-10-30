"""KPI service (S4-03) — agregasi deterministik dari records aplikasi.

Ruling O-KPI (plan addendum §23): state available/no_data/unavailable +
reason eksplisit; TANPA fake 0/proxy. Definisi per worksheet §10:
- Meal Continuity Rate: porsi terkirim TERCATAT ÷ porsi rencana, KEDUA sisi
  memakai sumbu `plan_date` (tanggal rencana WIB, batas inklusif) dari facts
  `menu_plans` ⋈ `delivery_events`; `no_data` hanya bila tak ada rencana.
  Sejak Fase 8 (27 Okt 2026) metrik ini TIDAK lagi memakai porsi hasil konversi
  penerimaan bahan: kg yang diterima bukan porsi tersaji. Proyeksi porsi dari
  bahan diterima dilaporkan terpisah di blok `estimate` (evidence_kind
  `simulated_estimate`) dan tidak pernah masuk nilai metrik.
- Avoidable Food Loss: kg buangan ÷ (buangan + pasokan tercatat) dari
  `disposal_events` ⋈ `supply_records`; `no_data` bila penyebut nol. Angka ini
  adalah DISPOSAL TERCATAT, bukan estimasi dari skor freshness. Estimasi susut
  (freshness × kg diterima) hanya muncul di blok `estimate`.
- Regional Imbalance Resolution Rate: root lineage (supersedes chain)
  dedupe; denominator DETECT root cases; numerator root dengan status
  executed di window.
- Safe Delivered Cost: mean SDC decision yang PO-nya committed pada
  window (anchor eksekusi = PO.created_at, bukan decision.created_at).
  Rata-rata harga invoice PO dilaporkan TERPISAH di `facts` — dua basis
  berbeda (SDC analitis vs harga komersial) tidak boleh dibaca sebagai satu
  angka (Fase 8).
- Procurement Price Deviation: magnitudo absolut mean, pairing quote →
  referensi PIHPS terakhir pada lokasi+komoditas sama sebelum quote
  (O-NUM: absolut di aggregate, tanpa mengubah signed contract core).
- Decision Time: mean (first DETECT → last ACT) per decision; ACT hanya
  dihitung bila committed (PO ada); coverage = sample/eligible.
- Evidence Completeness: % decision dengan ≥2 distinct evidence type
  is_consistent SEBELUM approval-complete cutoff; bukti sesudah cutoff
  tidak dihitung; dua salinan tipe sama bukan dua sumber.

Semua query period `[start, end)`. Omit location untuk SPPG difilter di
API layer (service menerima location_id=None = global).

Provenance (Fase 8, 27 Okt 2026): setiap metrik membawa `provenance` dengan
kunci `source` (tabel.kolom yang benar-benar dibaca, bukan prosa), `period`
(rentang + BASIS waktu), `sample_count`, `coverage`, `definition`, `formula`,
`method_version`, `evidence_kind`, dan `baseline`. Baseline yang tidak ada
ditulis `kind="no_baseline"` + `reason`; ia TIDAK diganti nol.

Pemisahan demo vs operasional: `include_demo=False` (bawaan) menyaring SETIAP
tabel fakta dengan `demo_session_id IS NULL`; `include_demo=True` menyaring ke
SATU sesi yang disebut eksplisit. Tidak ada jalur "sesi terbaru" — sesi lain
bisa dibuka bersamaan (lihat `services/demo_session.py`).
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.kpi import quantize2, resolve_root
from app.core.safe_delivered_cost import FORMULA_VERSION
from app.core.storage_window import BASIS_ASUMSI, DEFAULT_STORAGE_DAYS


def _daftar_metrik() -> tuple[str, ...]:
    """Satu-satunya daftar nama metrik yang dipakai API, tes, dan UI."""
    return (
        "Meal Continuity Rate",
        "Avoidable Food Loss",
        "Regional Imbalance Resolution Rate",
        "Safe Delivered Cost",
        "Procurement Price Deviation",
        "Decision Time",
        "Evidence Completeness",
    )


METRIC_NAMES = _daftar_metrik()

#: Versi metode agregasi. Naikkan bila rumus/definisi metrik berubah, ATAU bila
#: shape provenance berubah sehingga angka lama tidak bisa dibandingkan langsung
#: dengan angka baru. 28 Okt 2026: provenance menambah `data_basis` +
#: `classification` (asal baris historical_seed), jadi versinya dinaikkan.
METHOD_VERSION = "kpi-2026.10.28"

#: Kelas bukti yang boleh muncul pada sebuah nilai.
EVIDENCE_KINDS = ("recorded_fact", "derived", "simulated_estimate")


def _prov(
    *,
    source: str,
    period: dict,
    definition: str,
    formula: str,
    evidence_kind: str,
    baseline_reason: str | None = None,
    baseline_value=None,
    sample_count: int = 0,
    coverage=None,
) -> dict:
    """Provenance satu metrik — sumber, periode, metode, dan tingkat bukti.

    `baseline` sengaja TIDAK memberi nilai bawaan 0: baseline yang tidak ada
    ditulis `no_baseline` + alasannya. Mengganti baseline hilang dengan nol
    membuat pembaca mengira ada pembanding yang terukur.
    """
    assert evidence_kind in EVIDENCE_KINDS, evidence_kind
    if baseline_value is None:
        baseline = {
            "kind": "no_baseline",
            "value": None,
            "reason": baseline_reason
            or "belum ada baseline/target yang disepakati untuk metrik ini",
        }
    else:
        baseline = {
            "kind": "value",
            "value": str(quantize2(baseline_value)),
            "reason": baseline_reason,
        }
    return {
        "source": source,
        "period": period,
        "sample_count": sample_count,
        "coverage": None if coverage is None else str(quantize2(coverage)),
        "definition": definition,
        "formula": formula,
        "method_version": METHOD_VERSION,
        "evidence_kind": evidence_kind,
        "baseline": baseline,
    }


def _metric(name, unit, state, value=None, reason=None, sample_count=0,
            coverage=None, previous_value=None, trend=None, *, provenance=None,
            estimate=None, facts=None):
    m = {
        "name": name,
        "unit": unit,
        "state": state,
        "value": None if value is None else str(quantize2(value)),
        "reason": reason,
        "sample_count": sample_count,
        "coverage": None if coverage is None else str(quantize2(coverage)),
        "previous_value": (
            None if previous_value is None else str(quantize2(previous_value))
        ),
        "trend": trend,
    }
    if provenance is not None:
        m["provenance"] = provenance
    if estimate is not None:
        m["estimate"] = estimate
    if facts is not None:
        m["facts"] = facts
    return m


def _no_data(name, unit, sample_count=0, reason=None, **kwargs):
    return _metric(
        name, unit, "no_data", reason=reason or "tidak ada record pada periode ini",
        sample_count=sample_count, **kwargs,
    )


def _estimasi(*, source: str, definition: str, method: str) -> dict:
    """Blok `estimate` — angka proyeksi yang TIDAK boleh dibaca sebagai fakta.

    Bentuknya sama untuk semua metrik (`state`/`value`/`reason`) supaya UI tidak
    perlu tahu metrik mana yang punya proyeksi, dan `evidence_kind` ikut di
    payload supaya klaim "ini estimasi" bukan hanya komentar kode.
    """
    return {
        "state": "no_data",
        "value": None,
        "unit": None,
        "source": source,
        "definition": definition,
        "method": method,
        "method_version": METHOD_VERSION,
        "evidence_kind": "simulated_estimate",
        "coverage": None,
        "reason": None,
    }


def _isi_estimasi(blok: dict, *, value=None, unit: str | None = None,
                  reason: str | None = None, coverage=None) -> dict:
    blok["state"] = "available" if value is not None else "no_data"
    blok["value"] = None if value is None else str(quantize2(value))
    blok["unit"] = unit if value is not None else None
    blok["coverage"] = None if coverage is None else str(quantize2(coverage))
    blok["reason"] = None if value is not None else (
        reason or "tidak ada bahan/proyeksi yang bisa dihitung pada periode ini"
    )
    return blok


def _periode(start: datetime, end: datetime, basis: str) -> dict:
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "basis": basis,
        "window": "[start, end)",
    }


def _scope(alias: str, include_demo: bool) -> str:
    """Predikat pemisah fakta demo vs operasional untuk satu alias tabel.

    `include_demo=False` → `alias.demo_session_id IS NULL` (fakta operasional).

    `include_demo=True` → fakta sesi yang diminta **DITAMBAH template cetakan**.
    Kenapa cetakan ikut (demo 29 Okt 2026): template demo disimpan berstempel
    sesi sentinel `cetakan` supaya "Akhiri sesi" tidak menghapusnya. Sebelum ini
    cakupan simulasi hanya membaca id sesi OPERATOR — yang tidak memiliki satu
    pun fakta template — sehingga tombol "Simulasi" di halaman KPI menjawab
    0/7 metrik di ketiga jendela sesaat setelah "Siapkan data demo", padahal
    43 keputusan demo ada di DB. Isolasi antar-sesi operator tetap: sesi
    operator LAIN tidak ikut terbaca.
    """
    if include_demo:
        # Impor di dalam fungsi: `demo_session` juga mengimpor layanan lain,
        # dan kpi_service dipakai sangat awal saat aplikasi dimuat.
        from app.services.demo_session import CETAKAN_ID

        return (
            f" AND ({alias}.demo_session_id = :demo_session_id "
            f"OR {alias}.demo_session_id = '{CETAKAN_ID}'::uuid) "
        )
    # 30 Okt 2026 — cakupan OPERASIONAL ikut membaca baris CETAKAN. Dataset
    # cetakan adalah template demo yang disiapkan untuk aplikasi ini, bukan milik
    # sesi operator mana pun; sebelum aturan ini, menstempel rencana menu/kiriman
    # dengan sesi cetakan (supaya terlihat di mode simulasi) justru membuat KPI
    # operasional — yang dipakai Joule secara bawaan — kehilangan data yang sama.
    # Yang tetap TIDAK terbaca: sesi operator lain.
    from app.services.demo_session import CETAKAN_ID

    return (
        f" AND ({alias}.demo_session_id IS NULL "
        f"OR {alias}.demo_session_id = '{CETAKAN_ID}'::uuid) "
    )


async def _rows(db: AsyncSession, stmt: str, params: dict | None = None):
    result = await db.execute(text(stmt), params or {})
    return result.fetchall()


#: Jam kirim rencana dalam UTC — 14:00 UTC = 21:00 WIB. Sama dengan aturan
#: generator (`app/seed/timeseries.py:kiriman_sudah_terjadi`): rencana hari ini
#: baru "terjadi" setelah jam ini.
JAM_KIRIM_UTC = 14
_ZONA_WIB = timezone(timedelta(hours=7))


def tanggal_kiriman_terakhir(acuan: datetime) -> date:
    """Tanggal rencana terakhir yang jendela kirimnya SUDAH lewat pada `acuan`.

    Dipakai sebagai batas atas `plan_date` pada Meal Continuity (26 Okt 2026).
    Tanpa batas ini, rencana hari ini ikut penyebut sejak pukul 00:00 WIB —
    pembilangnya nol karena kiriman hari ini belum berjalan — sehingga metrik
    terbaca `0,00%` selama pagi, padahal datanya belum "gagal" melainkan belum
    terjadi. Aturan proyek: keadaan belum diketahui ditulis "—", bukan 0.

    Pengecualiannya data, bukan jam: kalau rencana itu SUDAH punya baris
    `delivery_events`, ia tetap dinilai walau jam kirim belum lewat — kiriman
    yang tercatat berarti rencananya memang berjalan (lihat pemakaian di
    `compute_kpis`: `mp.plan_date <= :tanggal_kirim OR de.delivered IS NOT NULL`).
    """
    hari_ini = acuan.astimezone(_ZONA_WIB).date()
    jam_kirim = datetime.combine(hari_ini, time(JAM_KIRIM_UTC), tzinfo=UTC)
    if acuan >= jam_kirim:
        return hari_ini
    return hari_ini - timedelta(days=1)


def _plan_date_range(alias: str = "") -> str:
    """Predikat rentang `plan_date` (tanggal rencana, WIB) — inklusif dua ujung.

    `start`/`end` adalah instan; `plan_date` adalah date WIB. Konversi dilakukan
    di SQL (instan → Asia/Jakarta → date) supaya batas atas "hari ini" benar
    walau jam server UTC (00:30 WIB masih tanggal kemarin di UTC).
    Batas atas inklusif: `end` = sekarang, jadi `<` akan membuang rencana hari
    ini dan membuat kartu 24 jam selalu kosong (audit 2026-10-23, KPI-01).
    """
    kol = f"{alias}plan_date"
    return (
        f"{kol} >= (CAST(:start AS timestamptz) AT TIME ZONE 'Asia/Jakarta')::date "
        f"AND {kol} <= (CAST(:end AS timestamptz) AT TIME ZONE 'Asia/Jakarta')::date"
    )


async def _proyeksi_porsi_penerimaan(
    db: AsyncSession,
    start: datetime,
    end: datetime,
    location_id: uuid.UUID | None,
    include_demo: bool,
    demo_session_id: uuid.UUID | None,
) -> dict:
    """Proyeksi porsi dari BAHAN YANG DITERIMA (bukan porsi tersaji).

    Kg yang diterima dikonversi dengan gram/porsi komoditas
    (`settings.menu_grams_*`). Hasilnya hanya boleh muncul sebagai `estimate`;
    ia tidak pernah menambah nilai Meal Continuity — itu persis klaim yang
    dilarang gate Fase 8.

    Dua koreksi kontrak (demo "kasus pengiriman", 29 Okt 2026):

    - **Kg yang dihitung adalah TIMBANGAN** (`batch_receipts.accepted_kg`), bukan
      berat pesanan batch. Baris lama tanpa timbangan jatuh ke
      `batches.quantity_kg`. Memakai berat pesanan berarti mengklaim bahan yang
      tidak pernah sampai di dapur (Dok 05 §5.1).
    - **Cakupan ditentukan baris PENERIMAAN saja.** Dulu batch ikut disyaratkan
      cocok cakupan; karena penerimaan berstempel sesi sementara batch-nya
      sering baris kanonik tanpa stempel, baris itu hilang dari cakupan
      operasional (dia berstempel) maupun demo (batch tidak berstempel) —
      terukur: menyetujui penerimaan tidak menggerakkan satu pun KPI.
    """
    rows = await _rows(
        db,
        "SELECT c.name, SUM(COALESCE(r.accepted_kg, b.quantity_kg)) "
        "FROM batch_receipts r "
        "JOIN batches b ON b.id = r.batch_id "
        "JOIN commodities c ON c.id = b.commodity_id "
        "WHERE r.status = 'disetujui' "
        "AND r.reviewed_at >= :start AND r.reviewed_at < :end "
        + ("AND b.location_id = :loc " if location_id else "")
        + _scope("r", include_demo)
        + "GROUP BY c.name",
        {"start": start, "end": end, "demo_session_id": demo_session_id,
         **({"loc": location_id} if location_id else {})},
    )
    from app.services.settlement import _gram_per_porsi

    porsi = Decimal(0)
    tanpa_gram_kg = Decimal(0)
    total_kg = Decimal(0)
    for nama, kg in rows:
        kg = Decimal(str(kg or 0))
        total_kg += kg
        gram = _gram_per_porsi(nama)
        if not gram:
            tanpa_gram_kg += kg
            continue
        porsi += kg * Decimal(1000) / Decimal(str(gram))
    return {
        "porsi": porsi,
        "total_kg": total_kg,
        "tanpa_gram_kg": tanpa_gram_kg,
    }


async def _estimasi_susut(
    db: AsyncSession,
    start: datetime,
    end: datetime,
    location_id: uuid.UUID | None,
    include_demo: bool,
    demo_session_id: uuid.UUID | None,
) -> dict:
    """Estimasi susut dari skor freshness bahan yang diterima (PROYEKSI).

    `estimated_shrinkage_kg = Σ kg_diterima × (1 − freshness_score)`. Ini
    estimasi model, BUKAN disposal aktual: tidak ada satu baris pun yang ditulis
    ke `disposal_events` dari jalur ini.

    `kg_diterima` = `batch_receipts.accepted_kg` (timbangan), cadangan berat
    pesanan batch untuk baris lama. Cakupan diambil dari baris PENERIMAAN saja —
    alasan lengkapnya di `_proyeksi_porsi_penerimaan` (bug cakupan yang membuat
    penerimaan tidak pernah terlihat KPI).
    """
    rows = await _rows(
        db,
        "SELECT "
        "SUM(s.kg) FILTER (WHERE s.freshness IS NOT NULL), "
        "SUM(s.kg * (1 - s.freshness)) FILTER (WHERE s.freshness IS NOT NULL), "
        "SUM(s.kg), "
        "COUNT(*) "
        "FROM ("
        "  SELECT COALESCE(r.accepted_kg, b.quantity_kg) AS kg, "
        "         b.freshness_score AS freshness, "
        "         b.location_id "
        "  FROM batch_receipts r JOIN batches b ON b.id = r.batch_id "
        "  WHERE r.status = 'disetujui' "
        "  AND r.reviewed_at >= :start AND r.reviewed_at < :end "
        + _scope("r", include_demo)
        + ") s "
        "WHERE 1=1 "
        + ("AND s.location_id = :loc " if location_id else ""),
        {"start": start, "end": end, "demo_session_id": demo_session_id,
         **({"loc": location_id} if location_id else {})},
    )
    kg_terukur = (
        Decimal(str(rows[0][0])) if rows and rows[0][0] is not None else Decimal(0)
    )
    susut = (
        Decimal(str(rows[0][1])) if rows and rows[0][1] is not None else Decimal(0)
    )
    kg_total = (
        Decimal(str(rows[0][2])) if rows and rows[0][2] is not None else Decimal(0)
    )
    n = int(rows[0][3] or 0) if rows else 0
    coverage = (kg_terukur / kg_total) if kg_total > 0 else None
    return {"susut_kg": susut, "kg_terukur": kg_terukur, "kg_total": kg_total,
            "sample_count": n, "coverage": coverage}


#: Tabel fakta + kolom waktu yang menyusun tiap metrik. Dipakai untuk
#: mengklasifikasi ASAL baris (spesifikasi Fase 8 baris 23): baris hasil seed
#: historis tidak boleh terbaca sebagai fakta operasional baru.
_ASAL_PER_METRIK: dict[str, tuple[tuple[str, str], ...]] = {
    "Meal Continuity Rate": (("menu_plans", "plan_date"), ("delivery_events", "delivered_at")),
    "Avoidable Food Loss": (("disposal_events", "disposed_at"),),
    "Regional Imbalance Resolution Rate": (("decisions", "created_at"),),
    "Safe Delivered Cost": (
        ("decisions", "created_at"),
        ("sap_mock_purchase_orders", "created_at"),
    ),
    "Procurement Price Deviation": (("price_signals", "recorded_at"),),
    "Decision Time": (("decisions", "created_at"),),
    "Evidence Completeness": (("decisions", "created_at"),),
}

#: Tabel yang punya kolom `location_id` sendiri. Filter lokasi hanya berlaku di
#: tabel ini; memaksakannya ke tabel lain akan error, bukan lebih teliti.
_TABEL_LOKASI = frozenset({"menu_plans", "disposal_events", "price_signals"})


def _basis_asal(seed: int, live: int) -> str:
    """Basis asal baris sebuah angka — bukan tingkat bukti, tapi ASAL barisnya."""
    if seed and live:
        return "campuran"
    if seed:
        return "historical_seed"
    if live:
        return "live"
    return "tidak_ada_data"


async def _hitung_asal(
    db,
    tabel: str,
    kolom_waktu: str,
    *,
    start: datetime,
    end: datetime,
    location_id,
    demo_session_id=None,
) -> dict[str, int]:
    """Hitung baris per `origin` pada tabel sumber, di jendela yang sama.

    Operasional (`demo_session_id=None`) menyaring `demo_session_id IS NULL`
    seperti query metrik; cakupan demo menyaring ke satu sesi. Yang dihitung
    adalah BARIS SUMBER, jadi angkanya lebih besar dari `sample_count` metrik
    yang menghitung unit analisis (mis. per lokasi-hari).
    """
    kondisi = [f"{kolom_waktu} >= :start", f"{kolom_waktu} < :end"]
    params: dict = {}
    if kolom_waktu.endswith("_date"):
        # `plan_date` bertipe date; membandingkannya dengan timestamptz membuat
        # batas jendela bergeser satu hari di zona waktu non-UTC.
        params["start"] = start.date()
        params["end"] = end.date()
    else:
        params["start"] = start
        params["end"] = end
    if demo_session_id is not None:
        kondisi.append("demo_session_id = :sesi")
        params["sesi"] = demo_session_id
    else:
        kondisi.append("demo_session_id IS NULL")
    if location_id is not None and tabel in _TABEL_LOKASI:
        kondisi.append("location_id = :loc")
        params["loc"] = location_id
    rows = (
        await db.execute(
            text(
                f"SELECT origin, count(*) FROM {tabel} "
                f"WHERE {' AND '.join(kondisi)} GROUP BY 1"
            ),
            params,
        )
    ).all()
    return {str(r[0]): int(r[1]) for r in rows}


async def _tempel_klasifikasi_asal(
    db, metrics, *, start: datetime, end: datetime, location_id, demo_session_id=None
) -> None:
    """Tambahkan `data_basis` + `classification` ke provenance setiap metrik.

    Tanpa ini seluruh angka operasional (yang di DB demo 100% berasal dari baris
    `origin='seed'`) tampil seolah catatan lapangan hari ini. Klasifikasi tidak
    mengubah nilai: ia menyatakan asalnya, supaya pembaca bisa menilai sendiri.
    """
    for m in metrics:
        prov = m.get("provenance")
        if not isinstance(prov, dict):
            continue
        if demo_session_id is not None:
            prov["data_basis"] = "sesi_demo"
            continue
        seed = lain = 0
        for tabel, kolom in _ASAL_PER_METRIK.get(m["name"], ()):
            mix = await _hitung_asal(
                db,
                tabel,
                kolom,
                start=start,
                end=end,
                location_id=location_id,
            )
            seed += mix.get("seed", 0)
            lain += sum(v for k, v in mix.items() if k != "seed")
        prov["data_basis"] = _basis_asal(seed, lain)
        prov["classification"] = {"historical_seed": seed, "live": lain}


async def compute_kpis(
    db: AsyncSession,
    start: datetime,
    end: datetime,
    location_id: uuid.UUID | None,
    *,
    include_demo: bool = False,
    demo_session_id: uuid.UUID | None = None,
) -> dict:
    """Hitung tujuh KPI pada [start, end). Read-only.

    `include_demo=False` (bawaan) = fakta operasional saja
    (`demo_session_id IS NULL`). `include_demo=True` wajib menyebut
    `demo_session_id` eksplisit.
    """
    if include_demo and demo_session_id is None:
        raise ValueError(
            "include_demo=True membutuhkan demo_session_id eksplisit"
        )

    loc_param = {"loc": location_id} if location_id else {}
    dasar = {**loc_param, "demo_session_id": demo_session_id}
    loc_filter_dec = (
        "AND (d.source_location_id = :loc OR d.target_location_id = :loc)"
        if location_id else ""
    )

    metrics: list[dict] = []

    # ---- 1. Meal Continuity Rate (porsi terkirim TERCATAT / porsi rencana) ---
    # Numerator hanya `delivery_events` yang benar-benar tercatat. Konversi kg
    # penerimaan → porsi DIPINDAHKAN ke blok `estimate` (Fase 8): bahan diterima
    # bukan porsi tersaji, dan mencampurnya membuat kartu mengklaim makanan
    # tersaji yang tidak pernah dicatat.
    de_inner = (
        "SELECT menu_plan_id, SUM(delivered_portions) AS delivered "
        "FROM delivery_events WHERE 1=1 "
        + _scope("delivery_events", include_demo)
        + "GROUP BY menu_plan_id"
    )
    mc_rows = await _rows(
        db,
        "SELECT SUM(mp.planned_portions), "
        "SUM(LEAST(COALESCE(de.delivered, 0), mp.planned_portions)) "
        f"FROM menu_plans mp LEFT JOIN ({de_inner}) de ON de.menu_plan_id = mp.id "
        f"WHERE {_plan_date_range()} "
        "AND (mp.plan_date <= :tanggal_kirim OR de.delivered IS NOT NULL) "
        + _scope("mp", include_demo)
        + ("AND mp.location_id = :loc " if location_id else ""),
        {
            "start": start,
            "end": end,
            "tanggal_kirim": tanggal_kiriman_terakhir(end),
            **dasar,
        },
    )
    planned_total = mc_rows[0][0] if mc_rows else None
    delivered_total = mc_rows[0][1] if mc_rows else None

    proyeksi = await _proyeksi_porsi_penerimaan(
        db, start, end, location_id, include_demo, demo_session_id
    )
    estimasi_mc = _estimasi(
        source="batch_receipts.status/reviewed_at, batches.quantity_kg, "
               "commodities.name, config menu_grams_*",
        definition=(
            "Proyeksi porsi yang bisa disajikan dari BAHAN YANG DITERIMA "
            "(kg ÷ gram per porsi). BUKAN porsi tersaji dan tidak menambah "
            "nilai Meal Continuity."
        ),
        method="Σ (kg_diterima × 1000 ÷ gram_per_porsi) per komoditas",
    )
    if proyeksi["porsi"] > 0:
        _isi_estimasi(
            estimasi_mc,
            value=proyeksi["porsi"],
            unit="porsi",
            coverage=(
                (proyeksi["total_kg"] - proyeksi["tanpa_gram_kg"])
                / proyeksi["total_kg"]
                if proyeksi["total_kg"] > 0 else None
            ),
        )
        if proyeksi["tanpa_gram_kg"] > 0:
            estimasi_mc["definition"] += (
                f". {quantize2(proyeksi['tanpa_gram_kg'])} kg komoditas tanpa "
                "gram/porsi tidak diproyeksikan"
            )
    else:
        _isi_estimasi(
            estimasi_mc,
            reason="tidak ada penerimaan disetujui pada periode ini — "
                   "proyeksi porsi tidak bisa dihitung",
        )

    prov_mc = dict(
        source="menu_plans.plan_date, menu_plans.planned_portions, "
               "delivery_events.menu_plan_id, delivery_events.delivered_portions",
        period=_periode(start, end, "plan_date (tanggal rencana, Asia/Jakarta)"),
        definition=(
            "Porsi terkirim TERCATAT ÷ porsi rencana pada tanggal rencana. "
            "Ini bukan porsi tersaji: penerimaan bahan tidak menulis porsi. "
            "Rencana yang jendela kirimnya belum lewat tidak dinilai."
        ),
        formula="SUM(LEAST(delivered_portions, planned_portions)) ÷ "
                "SUM(planned_portions) × 100",
        evidence_kind="derived",
        baseline_reason=(
            "tidak ada target kontinuitas resmi di dataset; pembanding antar-"
            "periode belum disepakati pemilik"
        ),
    )
    if planned_total and int(planned_total) > 0:
        mc_rate = Decimal(delivered_total) * 100 / Decimal(planned_total)
        plan_days = await _rows(
            db,
            "SELECT COUNT(*) FROM menu_plans mp LEFT JOIN "
            f"({de_inner}) de ON de.menu_plan_id = mp.id "
            f"WHERE {_plan_date_range('mp.')} "
            "AND (mp.plan_date <= :tanggal_kirim OR de.delivered IS NOT NULL) "
            + _scope("mp", include_demo)
            + ("AND mp.location_id = :loc " if location_id else ""),
            {"start": start, "end": end,
             "tanggal_kirim": tanggal_kiriman_terakhir(end), **dasar},
        )
        sampel = int(plan_days[0][0]) if plan_days else 0
        mc_metric = _metric(
            "Meal Continuity Rate", "percent", "available",
            value=mc_rate,
            sample_count=sampel,
            coverage=Decimal(1),
            provenance=_prov(**prov_mc, sample_count=sampel, coverage=Decimal(1)),
            estimate=estimasi_mc,
            facts={
                "planned_portions": int(planned_total),
                "delivered_portions": int(delivered_total or 0),
            },
        )
    else:
        # KPI-02 (audit 24 Okt 2026): "belum ada data" harus dibedakan dari
        # "ada data tetapi penyebutnya nol" — dua sebab, dua tindakan.
        cek_rencana = await _rows(
            db,
            "SELECT COUNT(*), COALESCE(SUM(mp.planned_portions), 0) "
            "FROM menu_plans mp LEFT JOIN "
            f"({de_inner}) de ON de.menu_plan_id = mp.id "
            f"WHERE {_plan_date_range('mp.')} "
            "AND (mp.plan_date <= :tanggal_kirim OR de.delivered IS NOT NULL) "
            + _scope("mp", include_demo)
            + ("AND mp.location_id = :loc " if location_id else ""),
            {"start": start, "end": end,
             "tanggal_kirim": tanggal_kiriman_terakhir(end), **dasar},
        )
        jml_rencana = int(cek_rencana[0][0] or 0) if cek_rencana else 0
        cek_semua = await _rows(
            db,
            f"SELECT COUNT(*) FROM menu_plans WHERE {_plan_date_range()} "
            + _scope("menu_plans", include_demo)
            + ("AND location_id = :loc " if location_id else ""),
            {"start": start, "end": end, **dasar},
        )
        jml_semua = int(cek_semua[0][0] or 0) if cek_semua else 0
        if jml_rencana == 0 and jml_semua > 0:
            mc_metric = _no_data(
                "Meal Continuity Rate", "percent",
                sample_count=jml_semua,
                reason=(
                    f"{jml_semua} rencana menu ada, tetapi jendela kirimnya belum "
                    "tiba (kiriman hari ini baru terjadi setelah 21.00 WIB) — "
                    "belum ada yang bisa dinilai"
                ),
                provenance=_prov(**prov_mc, sample_count=jml_semua),
                estimate=estimasi_mc,
            )
        elif jml_rencana > 0:
            mc_metric = _no_data(
                "Meal Continuity Rate", "percent",
                sample_count=jml_rencana,
                reason=(
                    f"{jml_rencana} menu plan ada, tetapi total porsi rencana 0 — "
                    "penyebut nol, bukan data hilang"
                ),
                provenance=_prov(**prov_mc, sample_count=jml_rencana),
                estimate=estimasi_mc,
            )
        else:
            mc_metric = _no_data(
                "Meal Continuity Rate", "percent",
                reason=(
                    "tidak ada menu plan fakta operasional pada periode ini"
                ),
                provenance=_prov(**prov_mc),
                estimate=estimasi_mc,
            )
    metrics.append(mc_metric)

    # ---- 2. Avoidable Food Loss (DISPOSAL TERCATAT / input makanan) ---------
    # `value` HANYA dari `disposal_events` yang benar-benar dicatat. Skor
    # freshness tidak pernah membuat disposal aktual — ia hanya memberi
    # `estimate` susut di bawah.
    fl_rows = await _rows(
        db,
        "SELECT (SELECT COALESCE(SUM(quantity_kg),0) FROM disposal_events "
        "WHERE disposed_at >= :start AND disposed_at < :end"
        + _scope("disposal_events", include_demo)
        + ("AND location_id = :loc " if location_id else "")
        + ") AS disposed_kg, "
        "(SELECT COALESCE(SUM(quantity_kg),0) FROM supply_records "
        "WHERE recorded_at >= :start AND recorded_at < :end"
        + _scope("supply_records", include_demo)
        + ("AND location_id = :loc " if location_id else "")
        + ") AS supply_kg, "
        "(SELECT COUNT(*) FROM disposal_events "
        "WHERE disposed_at >= :start AND disposed_at < :end"
        + _scope("disposal_events", include_demo)
        + ("AND location_id = :loc " if location_id else "")
        + ") AS disposal_events",
        {"start": start, "end": end, **dasar},
    )
    disposed_kg = Decimal(str(fl_rows[0][0] or 0)) if fl_rows else Decimal(0)
    supply_kg = Decimal(str(fl_rows[0][1] or 0)) if fl_rows else Decimal(0)
    disposal_count = int(fl_rows[0][2] or 0) if fl_rows else 0

    susut = await _estimasi_susut(
        db, start, end, location_id, include_demo, demo_session_id
    )
    estimasi_fl = _estimasi(
        source="batch_receipts.status/reviewed_at, batches.quantity_kg, "
               "batches.freshness_score",
        definition=(
            "Estimasi susut dari skor freshness bahan yang diterima. Ini "
            "PROYEKSI model, bukan disposal aktual: tidak ada baris "
            "`disposal_events` yang ditulis dari jalur ini."
        ),
        method="Σ kg_diterima × (1 − freshness_score)",
    )
    if susut["susut_kg"] > 0:
        _isi_estimasi(
            estimasi_fl, value=susut["susut_kg"], unit="kg",
            coverage=susut["coverage"],
        )
    else:
        _isi_estimasi(
            estimasi_fl,
            reason=(
                "tidak ada bahan diterima dengan skor freshness pada periode ini"
                if susut["sample_count"] == 0
                else "skor freshness bahan yang diterima sempurna (1,00) — "
                     "estimasi susut 0 kg"
            ),
        )

    prov_fl = dict(
        source="disposal_events.disposed_at, disposal_events.quantity_kg, "
               "supply_records.recorded_at, supply_records.quantity_kg",
        period=_periode(start, end, "disposed_at / recorded_at (jam dinding)"),
        definition=(
            "Kg pangan yang DIBUANG dan dicatat ÷ (dibuang + pasokan tercatat). "
            "Angka ini hanya bergerak bila ada bukti pembuangan; estimasi susut "
            "dari freshness dilaporkan terpisah di `estimate`."
        ),
        formula="SUM(disposal_events.quantity_kg) ÷ "
                "(SUM(disposal_events.quantity_kg) + "
                "SUM(supply_records.quantity_kg)) × 100",
        evidence_kind="recorded_fact",
        baseline_reason=(
            "tidak ada ambang susut yang disepakati; angka hanya bisa "
            "dibandingkan antar-periode"
        ),
    )
    if disposed_kg > 0:
        denom = disposed_kg + supply_kg
        fl_rate = disposed_kg * 100 / denom if denom > 0 else None
        fl_metric = _metric(
            "Avoidable Food Loss", "percent", "available",
            value=fl_rate,
            sample_count=disposal_count,
            coverage=Decimal(1),
            provenance=_prov(**prov_fl, sample_count=disposal_count,
                             coverage=Decimal(1)),
            estimate=estimasi_fl,
            facts={"disposed_kg": str(quantize2(disposed_kg)),
                   "supply_kg": str(quantize2(supply_kg))},
        )
    elif disposed_kg == 0 and supply_kg > 0:
        fl_metric = _no_data(
            "Avoidable Food Loss", "percent",
            reason="tidak ada disposal event pada periode ini",
            provenance=_prov(**prov_fl),
            estimate=estimasi_fl,
            facts={"disposed_kg": "0.00", "supply_kg": str(quantize2(supply_kg))},
        )
    else:
        fl_metric = _no_data(
            "Avoidable Food Loss", "percent",
            reason=(
                "tidak ada disposal event maupun pasokan tercatat pada periode "
                "ini — penyebut nol"
            ),
            provenance=_prov(**prov_fl),
            estimate=estimasi_fl,
        )
    metrics.append(fl_metric)

    # ---- 3. Regional Imbalance Resolution Rate (dedupe root lineage) -------
    det_rows = await _rows(
        db,
        "SELECT d.id, d.supersedes_id, d.status FROM decisions d "
        "JOIN agent_traces t ON t.decision_id = d.id AND t.step_name = 'DETECT' "
        "WHERE t.step_at >= :start AND t.step_at < :end "
        "AND d.demo_case IS NULL " + _scope("d", include_demo) + loc_filter_dec,
        {"start": start, "end": end, **dasar},
    )
    imbalance_rate = None
    imbalance_count = 0
    if det_rows:
        parent_map = {str(r[0]): str(r[1]) for r in det_rows if r[1]}
        root_status: dict[str, str] = {}
        for did, _sup, status in det_rows:
            root_status[str(did)] = status
        roots: dict[str, bool] = {}
        for did, status in root_status.items():
            root = resolve_root(parent_map, did)
            roots[root] = roots.get(root, False) or (status == "executed")
        imbalance_count = len(roots)
        executed = sum(1 for ok in roots.values() if ok)
        imbalance_rate = Decimal(executed) * 100 / Decimal(imbalance_count)
    prov_imb = dict(
        source="decisions.id, decisions.supersedes_id, decisions.status, "
               "agent_traces.decision_id, agent_traces.step_name, "
               "agent_traces.step_at",
        period=_periode(start, end, "agent_traces.step_at (DETECT)"),
        definition=(
            "Akar lineage (rantai `supersedes_id`) yang selesai ÷ akar yang "
            "terdeteksi di jendela. Kasus `demo_case` dikecualikan sebagai "
            "anti-noise; fakta sesi demo dikecualikan oleh filter sesi."
        ),
        formula="COUNT(root dengan status='executed') ÷ COUNT(root) × 100",
        evidence_kind="derived",
        baseline_reason="belum ada target penyelesaian yang disepakati",
    )
    metrics.append(
        _metric(
            "Regional Imbalance Resolution Rate", "percent",
            "available" if imbalance_rate is not None else "no_data",
            value=imbalance_rate,
            sample_count=imbalance_count,
            coverage=Decimal(1),
            reason=None if imbalance_rate is not None
            else "tidak ada DETECT pada periode ini",
            provenance=_prov(**prov_imb, sample_count=imbalance_count,
                             coverage=Decimal(1)),
        )
    )

    # ---- 4. Safe Delivered Cost (analitis) + invoice TERPISAH --------------
    sdc_rows = await _rows(
        db,
        "SELECT d.safe_delivered_cost FROM decisions d "
        "JOIN sap_mock_purchase_orders po ON po.decision_id = d.id "
        "WHERE po.created_at >= :start AND po.created_at < :end "
        f"AND d.safe_delivered_cost IS NOT NULL {loc_filter_dec} "
        + _scope("d", include_demo) + _scope("po", include_demo),
        {"start": start, "end": end, **dasar},
    )
    invoice_rows = await _rows(
        db,
        "SELECT po.price FROM sap_mock_purchase_orders po "
        "JOIN decisions d ON d.id = po.decision_id "
        "WHERE po.created_at >= :start AND po.created_at < :end "
        # Cakupan lokasi WAJIB, sama seperti kueri SDC di atasnya. Audit
        # 28 Okt 2026: tanpa `loc_filter_dec` kartu ini menampilkan rata-rata
        # 12 PO impor SAP yang target_location_id-nya NULL — angka yang tidak
        # bisa dibuka pengguna di daftar PO-nya sendiri (scope jakarta = 0).
        f"{loc_filter_dec}"
        + _scope("d", include_demo)
        + _scope("po", include_demo),
        {"start": start, "end": end, **dasar},
    )
    sdc_values = [Decimal(str(r[0])) for r in sdc_rows]
    invoice_values = [
        Decimal(str(r[0])) for r in invoice_rows if r[0] is not None
    ]
    prov_sdc = dict(
        source="decisions.safe_delivered_cost, sap_mock_purchase_orders."
               "decision_id, sap_mock_purchase_orders.created_at, "
               "sap_mock_purchase_orders.price",
        period=_periode(start, end, "sap_mock_purchase_orders.created_at"),
        definition=(
            "Rata-rata biaya kirim AMAN (SDC analitis: invoice + expected loss "
            "+ risiko freshness + penalti safety) untuk keputusan yang PO-nya "
            "terbit di jendela. Rata-rata harga invoice PO dilaporkan terpisah "
            "di `facts` — dua basis berbeda tidak digabung."
        ),
        formula="AVG(decisions.safe_delivered_cost) atas PO committed",
        evidence_kind="derived",
        baseline_reason="belum ada patokan biaya kirim aman yang disepakati",
    )
    sdc_facts = {
        "invoice_unit_price_mean_idr": (
            str(quantize2(sum(invoice_values) / Decimal(len(invoice_values))))
            if invoice_values else None
        ),
        "invoice_sample_count": len(invoice_values),
        # Versi rumus + basis jendela simpan (konsep Performance & Audit §5.4):
        # panel audit membacanya dari sini supaya UI tidak menulis ulang rumus.
        # `storage_*` adalah nilai yang DIPAKAI saat keputusan dihitung; angka
        # di DB tidak menyimpan per-baris, jadi yang dilaporkan adalah default
        # mesin beserta basisnya — bukan tebakan per keputusan.
        "formula_version": FORMULA_VERSION,
        "storage_default_days": str(DEFAULT_STORAGE_DAYS),
        "storage_default_basis": BASIS_ASUMSI,
        "note": "invoice_unit_price_mean_idr = harga komersial PO (tanpa "
                "expected loss/freshness/safety), bukan SDC",
    }
    if sdc_values:
        sdc_mean = sum(sdc_values) / Decimal(len(sdc_values))
        sdc_metric = _metric(
            "Safe Delivered Cost", "IDR", "available",
            value=sdc_mean, sample_count=len(sdc_values),
            coverage=Decimal(1),
            provenance=_prov(**prov_sdc, sample_count=len(sdc_values),
                             coverage=Decimal(1)),
            facts=sdc_facts,
        )
    else:
        sdc_metric = _no_data(
            "Safe Delivered Cost", "IDR",
            reason=(
                "tidak ada PO committed dengan biaya pada periode ini "
                "(penyebut kosong)"
            ),
            provenance=_prov(**prov_sdc),
            facts=sdc_facts,
        )
    metrics.append(sdc_metric)

    # ---- 5. Procurement Price Deviation (harga BAHAN vs acuan) ------------
    ps_rows = await _rows(
        db,
        "SELECT ps.location_id, ps.commodity_id, ps.price_per_kg, ps.recorded_at "
        "FROM price_signals ps WHERE ps.source = 'supplier_quote' "
        "AND ps.recorded_at >= :start AND ps.recorded_at < :end "
        + _scope("ps", include_demo)
        + ("AND ps.location_id = :loc " if location_id else ""),
        {"start": start, "end": end, **dasar},
    )
    deviations: list[Decimal] = []
    for loc, com, quote, recorded_at in ps_rows:
        ref = await _rows(
            db,
            "SELECT ps.price_per_kg FROM price_signals ps "
            "WHERE ps.source='pihps_reference' AND ps.location_id=:loc "
            "AND ps.commodity_id=:com AND ps.recorded_at <= :t "
            + _scope("ps", include_demo)
            + "ORDER BY ps.recorded_at DESC LIMIT 1",
            {"loc": loc, "com": com, "t": recorded_at,
             "demo_session_id": demo_session_id},
        )
        if not ref:
            continue  # unpaired → excluded, bukan dianggap 0%
        reference = Decimal(str(ref[0][0]))
        if reference == 0:
            continue
        q = Decimal(str(quote))
        deviations.append(abs(q - reference) / reference * Decimal("100"))
    prov_price = dict(
        source="price_signals.source, price_signals.price_per_kg, "
               "price_signals.recorded_at, price_signals.location_id, "
               "price_signals.commodity_id",
        period=_periode(start, end, "price_signals.recorded_at"),
        definition=(
            "Simpangan absolut harga BAHAN (kutipan pemasok) terhadap acuan "
            "PIHPS terakhir pada lokasi+komoditas yang sama. Biaya logistik "
            "invoice tidak dihitung sebagai deviasi harga bahan."
        ),
        formula="AVG(|harga_bahan − harga_acuan| ÷ harga_acuan × 100)",
        evidence_kind="derived",
        baseline_reason="tidak ada ambang deviasi harga yang disepakati",
    )
    if deviations:
        price_mean = sum(deviations) / Decimal(len(deviations))
        price_metric = _metric(
            "Procurement Price Deviation", "percent", "available",
            value=price_mean, sample_count=len(deviations),
            coverage=Decimal(1),
            provenance=_prov(**prov_price, sample_count=len(deviations),
                             coverage=Decimal(1)),
        )
    else:
        if ps_rows:
            price_metric = _no_data(
                "Procurement Price Deviation", "percent",
                sample_count=len(ps_rows),
                reason=(
                    f"{len(ps_rows)} kutipan pemasok ada, tetapi tidak ada "
                    "pembanding harga referensi (PIHPS) — penyebut nol"
                ),
                provenance=_prov(**prov_price, sample_count=len(ps_rows)),
            )
        else:
            price_metric = _no_data(
                "Procurement Price Deviation", "percent",
                reason="tidak ada kutipan pemasok (supplier_quote) pada periode ini",
                provenance=_prov(**prov_price),
            )
    metrics.append(price_metric)

    # ---- 6. Decision Time: mean first DETECT → last ACT (ACT committed) ---
    dt_rows = await _rows(
        db,
        "SELECT d.id, "
        "MIN(t.step_at) FILTER (WHERE t.step_name='DETECT') AS detect_at, "
        "MAX(t.step_at) FILTER (WHERE t.step_name='ACT') AS act_at "
        "FROM decisions d JOIN agent_traces t ON t.decision_id = d.id "
        "WHERE t.step_at >= :start AND t.step_at < :end "
        + _scope("d", include_demo) + loc_filter_dec + " GROUP BY d.id",
        {"start": start, "end": end, **dasar},
    )
    durations: list[Decimal] = []
    committed = await _rows(
        db,
        "SELECT po.decision_id FROM sap_mock_purchase_orders po "
        "WHERE po.created_at >= :start AND po.created_at < :end "
        + _scope("po", include_demo),
        {"start": start, "end": end, "demo_session_id": demo_session_id},
    )
    committed_ids = {str(r[0]) for r in committed}
    eligible = 0
    for did, detect_at, act_at in dt_rows:
        if detect_at is None:
            continue
        eligible += 1
        if act_at is None or str(did) not in committed_ids:
            continue  # ACT belum committed → exclusion, bukan proxy
        durations.append(
            Decimal(str((act_at - detect_at).total_seconds())) / Decimal("60")
        )
    prov_dt = dict(
        source="agent_traces.step_at, agent_traces.step_name, decisions.id, "
               "sap_mock_purchase_orders.decision_id, "
               "sap_mock_purchase_orders.created_at",
        period=_periode(start, end, "agent_traces.step_at (DETECT & ACT)"),
        definition=(
            "Rata-rata selang DETECT pertama → ACT terakhir per keputusan, "
            "hanya untuk ACT yang punya PO (committed). Tanpa PO, ACT tidak "
            "dihitung dan bagiannya dilaporkan lewat `coverage`."
        ),
        formula="AVG((last ACT − first DETECT) dalam menit)",
        evidence_kind="recorded_fact",
        baseline_reason="tidak ada SLA waktu keputusan di dataset",
    )
    if durations:
        dt_mean = sum(durations) / Decimal(len(durations))
        dt_coverage = (
            (Decimal(len(durations)) / Decimal(eligible)) if eligible else None
        )
        dt_metric = _metric(
            "Decision Time", "minutes", "available",
            value=dt_mean,
            sample_count=len(durations),
            coverage=dt_coverage,
            provenance=_prov(**prov_dt, sample_count=len(durations),
                             coverage=dt_coverage),
        )
    else:
        if eligible:
            dt_metric = _no_data(
                "Decision Time", "minutes",
                sample_count=eligible,
                reason=(
                    f"{eligible} keputusan punya jejak DETECT, tetapi belum ada "
                    "ACT yang committed — penyebut nol"
                ),
                provenance=_prov(**prov_dt, sample_count=eligible),
            )
        else:
            dt_metric = _no_data(
                "Decision Time", "minutes",
                reason="tidak ada keputusan dengan jejak DETECT pada periode ini",
                provenance=_prov(**prov_dt),
            )
    metrics.append(dt_metric)

    # ---- 7. Evidence Completeness: ≥2 distinct consistent sebelum cutoff --
    ev_rows = await _rows(
        db,
        "SELECT d.id, d.status, "
        "MIN(a.approved_at) FILTER (WHERE a.approved IS TRUE) AS first_approve "
        "FROM decisions d "
        "LEFT JOIN approvals a ON a.decision_id = d.id "
        "WHERE d.created_at >= :start AND d.created_at < :end "
        + _scope("d", include_demo) + loc_filter_dec + " GROUP BY d.id",
        {"start": start, "end": end, **dasar},
    )
    ev_details = await _rows(
        db,
        "SELECT e.decision_id, e.evidence_type, e.is_consistent, e.recorded_at "
        "FROM decision_evidence e JOIN decisions d ON d.id = e.decision_id "
        "WHERE d.created_at >= :start AND d.created_at < :end "
        + _scope("d", include_demo) + loc_filter_dec,
        {"start": start, "end": end, **dasar},
    )
    ev_by_decision: dict[str, list[tuple]] = {}
    for did, etype, consistent, recorded_at in ev_details:
        ev_by_decision.setdefault(str(did), []).append(
            (etype, consistent, recorded_at)
        )
    complete = 0
    judged = 0
    # Penyebut = keputusan yang PUNYA cutoff approval, yaitu yang bisa dinilai
    # "bukti lengkap sebelum disetujui". Keputusan tanpa approval tidak bisa
    # dinilai lengkap/tidak → keluar dari penyebut, dan bagiannya dilaporkan
    # lewat `coverage`, bukan disembunyikan.
    for did, _status, first_approve in ev_rows:
        if first_approve is None:
            continue  # belum ada approval → belum ada cutoff untuk dibandingkan
        judged += 1
        cutoff = first_approve  # approval-complete cutoff (konservatif: pertama)
        cutoff = cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=start.tzinfo)
        distinct = set()
        for etype, consistent, recorded_at in ev_by_decision.get(str(did), []):
            if consistent is not True or recorded_at is None:
                continue
            rec = (
                recorded_at
                if recorded_at.tzinfo
                else recorded_at.replace(tzinfo=start.tzinfo)
            )
            if rec < cutoff:
                distinct.add(etype)
        if len(distinct) >= 2:
            complete += 1
    prov_ev = dict(
        source="decisions.created_at, approvals.approved_at, "
               "approvals.approved, decision_evidence.evidence_type, "
               "decision_evidence.is_consistent, "
               "decision_evidence.recorded_at",
        period=_periode(
            start, end,
            "decisions.created_at (cutoff: approvals.approved_at)",
        ),
        definition=(
            "Keputusan dengan ≥2 TIPE bukti berbeda yang konsisten SEBELUM "
            "approval pertama ÷ keputusan yang punya approval (yang bisa "
            "dinilai). Keputusan tanpa approval keluar dari penyebut dan "
            "bagiannya dilaporkan di `coverage`. `on_hold` tidak dihitung "
            "lengkap karena `is_consistent=false` tidak masuk himpunan."
        ),
        formula="COUNT(keputusan dengan ≥2 tipe bukti konsisten sebelum cutoff) "
                "÷ COUNT(keputusan ber-approval) × 100",
        evidence_kind="derived",
        baseline_reason="tidak ada target kelengkapan bukti yang disepakati",
    )
    if judged:
        ev_rate = Decimal(complete) * 100 / Decimal(judged)
        ev_coverage = (
            (Decimal(judged) / Decimal(len(ev_rows))) if ev_rows else None
        )
        ev_metric = _metric(
            "Evidence Completeness", "percent", "available",
            value=ev_rate,
            sample_count=judged,
            coverage=ev_coverage,
            provenance=_prov(**prov_ev, sample_count=judged,
                             coverage=ev_coverage),
        )
    else:
        ev_metric = _no_data(
            "Evidence Completeness", "percent",
            sample_count=0,
            reason=(
                "tidak ada keputusan pada periode ini"
                if not ev_rows
                else (
                    f"{len(ev_rows)} keputusan ada, tetapi belum satu pun "
                    "disetujui — tanpa approval tidak ada cutoff untuk menilai bukti"
                )
            ),
            provenance=_prov(**prov_ev),
        )
    metrics.append(ev_metric)

    # Kontrak tujuh metrik: urutan dan nama harus sama dengan `_daftar_metrik()`.
    assert [m["name"] for m in metrics] == list(_daftar_metrik())
    await _tempel_klasifikasi_asal(
        db,
        metrics,
        start=start,
        end=end,
        location_id=location_id,
        demo_session_id=demo_session_id if include_demo else None,
    )
    return metrics
