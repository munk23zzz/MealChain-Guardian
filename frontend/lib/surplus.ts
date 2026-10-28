// Halaman "Surplus & Limbah" — meniru halaman /surplus di aplikasi acuan
// (E:\hackathon\HackathonBil\MealchainGuardian), DISESUAIKAN: sumber angka =
// GET /balance/map?commodity=... (surplus_kg, shortage_kg, koordinat, region).
//
// Di acuan ada panel "rencana alokasi surplus" + pembahasan limbah (Peraturan
// BGN No. 1/2026). Di repo ini tidak ada tabel limbah/disposal, jadi bagian
// limbah ditulis "—" dengan alasan yang jujur, dan alokasi dihitung dari
// surplus nyata (greedy: kebutuhan terbesar diisi surplus terbesar).

const DASH = "—";

export type BalanceNode = {
  location?: string | null;
  region?: string | null;
  latitude?: number | string | null;
  longitude?: number | string | null;
  surplus_kg?: number | string | null;
  shortage_kg?: number | string | null;
  status?: string | null;
  /** Asal nilai per sisi (PLAN-023). Tidak ada = respons lama → dianggap terukur. */
  supply_state?: string | null;
  demand_state?: string | null;
};

export type SurplusSummary = {
  surplusKg: number | null;
  surplusCount: number;
  shortageKg: number | null;
  shortageCount: number;
  balancedCount: number;
  /** Lokasi yang salah satu sisinya tidak tercatat (bukan spekulasi angka). */
  unmeasuredCount: number;
};

/** Sisi tanpa baris → angka 0-nya hasil pengisian, bukan fakta (PLAN-023). */
function tanpaCatatan(state: unknown): boolean {
  return state === "tidak_ada_baris";
}

function surplusTerukur(node: BalanceNode): boolean {
  return !tanpaCatatan(node.demand_state);
}

function kekuranganTerukur(node: BalanceNode): boolean {
  return !tanpaCatatan(node.supply_state);
}

function lengkap(node: BalanceNode): boolean {
  return !tanpaCatatan(node.supply_state) && !tanpaCatatan(node.demand_state);
}

export function surplusSummary(locations: unknown): SurplusSummary {
  const list = nodes(locations);
  // Surplus hanya dihitung bila PERMINTAANNYA terukur: tanpa itu, "surplus"
  // hanyalah selisih terhadap angka 0 yang diisi engine (nyata: Bandung &
  // Cianjur untuk telur). Sisi cerminnya berlaku untuk kekurangan.
  const surplus = list.filter(
    (node) => number(node.surplus_kg) > 0 && surplusTerukur(node)
  );
  const shortage = list.filter(
    (node) => number(node.shortage_kg) > 0 && kekuranganTerukur(node)
  );
  const surplusKg = sumOrNull(surplus.map((node) => number(node.surplus_kg)).filter((n) => n > 0));
  const shortageKg = sumOrNull(shortage.map((node) => number(node.shortage_kg)).filter((n) => n > 0));
  return {
    surplusKg,
    surplusCount: surplus.length,
    shortageKg,
    shortageCount: shortage.length,
    balancedCount: list.filter(
      (node) => String(node.status ?? "") === "balanced" && lengkap(node)
    ).length,
    unmeasuredCount: list.filter((node) => !lengkap(node)).length,
  };
}

/** Jarak lingkaran besar (km) — dipakai untuk mengurutkan pasangan alokasi. */
export function haversineKm(
  a: { latitude?: unknown; longitude?: unknown },
  b: { latitude?: unknown; longitude?: unknown }
): number | null {
  const lat1 = Number(a?.latitude);
  const lon1 = Number(a?.longitude);
  const lat2 = Number(b?.latitude);
  const lon2 = Number(b?.longitude);
  if (![lat1, lon1, lat2, lon2].every((n) => Number.isFinite(n))) return null;
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLon = (lon2 - lon1) * rad;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return Math.round(2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h))));
}

export type Allocation = {
  from: string;
  to: string;
  kg: number;
  distanceKm: number | null;
  region: string | null;
  /**
   * (penanganan Rp150.000 + angkut) ÷ nilai barang, dalam persen. `null` bila
   * harga acuan komoditas atau jarak lokasi tidak tersedia — bukan 0.
   */
  costSharePct?: number | null;
};

/**
 * Rencana alokasi: kebutuhan terbesar diisi dari surplus terbesar, sampai salah
 * satu sisi habis. Urutan tujuan = kekurangan terbesar lebih dulu.
 */
export function allocationPlan(locations: unknown, limit = 5): Allocation[] {
  const list = nodes(locations);
  // Pemasok hanya dari lokasi yang permintaannya TERUKUR (sisi lain cerminnya):
  // surplus di atas permintaan yang tidak tercatat bukan fakta, jadi jangan
  // dialirkan sebagai rencana pengalihan (PLAN-023).
  const pools = list
    .filter((node) => surplusTerukur(node))
    .map((node) => ({ node, left: number(node.surplus_kg) }))
    .filter((pool) => pool.left > 0)
    .sort((a, b) => b.left - a.left);
  const needs = list
    .filter((node) => kekuranganTerukur(node))
    .map((node) => ({ node, left: number(node.shortage_kg) }))
    .filter((need) => need.left > 0)
    .sort((a, b) => b.left - a.left);

  const rows: Allocation[] = [];
  for (const need of needs) {
    for (const pool of pools) {
      if (need.left <= 0) break;
      if (pool.left <= 0) continue;
      const kg = Math.min(pool.left, need.left);
      if (kg <= 0) continue;
      pool.left -= kg;
      need.left -= kg;
      rows.push({
        from: name(pool.node),
        to: name(need.node),
        kg,
        distanceKm: haversineKm(pool.node, need.node),
        region: region(need.node),
      });
      if (rows.length >= limit) return rows;
    }
  }
  return rows;
}

export type AllocationPlan = {
  rows: Allocation[];
  /** Server bilang ada pasangan DAN barisnya terurai. */
  available: boolean;
  /** `tidak_ada_sisi_terukur` | `tidak_ada_surplus_terukur` | … | null */
  reason: string | null;
  /**
   * Jumlah lokasi bersurplus / berkekurangan di SELURUH jaringan (bukan hanya
   * yang lolos cakupan peta akun ini). Dipakai lencana halaman supaya angka
   * "0 lokasi surplus" tidak berdampingan dengan rencana yang punya sumber.
   */
  surplusLocations: number | null;
  shortageLocations: number | null;
  /** Ambang surplus per lokasi agar layak masuk rencana (server: 150 kg). */
  minSurplusKg: number | null;
};

type AllocationPairWire = {
  from?: string | null;
  to?: string | null;
  kg?: number | string | null;
  distance_km?: number | string | null;
  region?: string | null;
  cost_share_pct?: number | string | null;
};

/**
 * Rencana alokasi dari `GET /surplus/allocations` (dihitung server, lintas
 * lokasi). Baris tanpa `from`/`to` atau tanpa kg positif dibuang: yang tidak
 * terurai tidak boleh tampil sebagai pasangan.
 */
export function planFromServer(payload: unknown, limit = 6): AllocationPlan {
  const data = (payload ?? {}) as {
    available?: unknown;
    reason?: unknown;
    pairs?: unknown;
    surplus_locations?: unknown;
    shortage_locations?: unknown;
    min_surplus_kg?: unknown;
  };
  const pairs = Array.isArray(data.pairs) ? (data.pairs as AllocationPairWire[]) : [];
  const rows: Allocation[] = [];
  for (const pair of pairs) {
    const from = String(pair?.from ?? "").trim();
    const to = String(pair?.to ?? "").trim();
    const kg = number(pair?.kg);
    if (!from || !to || kg <= 0) continue;
    rows.push({
      from,
      to,
      kg,
      distanceKm:
        pair?.distance_km === null || pair?.distance_km === undefined
          ? null
          : number(pair.distance_km),
      region: pair?.region ? String(pair.region) : null,
      costSharePct:
        pair?.cost_share_pct === null || pair?.cost_share_pct === undefined
          ? null
          : number(pair.cost_share_pct),
    });
    if (rows.length >= limit) break;
  }
  return {
    rows,
    available: Boolean(data.available) && rows.length > 0,
    reason: typeof data.reason === "string" ? data.reason : null,
    surplusLocations:
      data.surplus_locations === null || data.surplus_locations === undefined
        ? null
        : number(data.surplus_locations),
    shortageLocations:
      data.shortage_locations === null || data.shortage_locations === undefined
        ? null
        : number(data.shortage_locations),
    minSurplusKg:
      data.min_surplus_kg === null || data.min_surplus_kg === undefined
        ? null
        : number(data.min_surplus_kg),
  };
}

/** Kalimat sebab saat rencana kosong — bukan "kosong" tanpa penjelasan. */
export function alasanTanpaRencana(reason?: string | null): string {
  switch (reason) {
    case "tidak_ada_sisi_terukur":
      return "Belum ada catatan pasokan dan permintaan yang bisa dipasangkan pada komoditas ini.";
    case "tidak_ada_surplus_terukur":
      return "Tidak ada lokasi bersurplus terukur pada komoditas ini — surplus hanya dihitung bila permintaannya tercatat.";
    case "tidak_ada_kekurangan_terukur":
      return "Tidak ada lokasi berkekurangan terukur pada komoditas ini — kekurangan hanya dihitung bila pasokannya tercatat.";
    case "surplus_di_bawah_ambang":
      return "Tidak ada lokasi dengan surplus 150 kg atau lebih. Surplus yang lebih kecil tidak direncanakan karena biaya tetap pengirimannya tidak sebanding.";
    case "alokasi_di_bawah_ambang":
      return "Pasangan yang terbentuk semuanya di bawah 150 kg per pengiriman, jadi belum layak direncanakan.";
    default:
      return "Tidak ada pasangan surplus→kekurangan yang bisa dialokasikan saat ini.";
  }
}

export type SurplusFact = { label: string; value: string; hint?: string | null };

/** Bentuk minimum respons `GET /waste/summary` yang dipakai panel. */
export type WastePayload = {
  recorded?: { available?: boolean; kg?: number | null; events?: number };
  diverted?: { available?: boolean; kg?: number | null; events?: number };
  unassigned?: { available?: boolean; kg?: number | null; events?: number };
  partners?: { name?: string; kg?: number; events?: number }[];
};

/** Apakah server benar-benar mengirim angka limbah (bukan "belum ada data")? */
export function angkaLimbahAda(payload?: unknown): boolean {
  const data = (payload ?? {}) as WastePayload;
  return Boolean(data.recorded?.available);
}

function wasteKg(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return `${Number(value).toLocaleString("id-ID", { maximumFractionDigits: 1 })} kg`;
}

/**
 * Bagian limbah/sisa pangan.
 *
 * `payload` = respons `/waste/summary` (kolom `partner_name`, migrasi 022).
 * Tanpa payload, ketiga baris tetap "—" dengan alasannya — keadaan "belum
 * dimuat" TIDAK boleh tampil sebagai 0 kg yang seolah terukur.
 */
export function wasteFacts(payload?: unknown): SurplusFact[] {
  const data = (payload ?? {}) as WastePayload;
  const tercatat = data.recorded;
  const dialihkan = data.diverted;
  const tanpaMitra = data.unassigned;
  const mitra = (data.partners ?? []).filter(
    (p): p is { name: string; kg: number; events?: number } =>
      Boolean(p && p.name) && Number.isFinite(Number(p.kg))
  );

  const adaTercatat = Boolean(tercatat?.available);
  const adaAlih = Boolean(dialihkan?.available);

  return [
    {
      label: "Sisa pangan dicatat",
      value: adaTercatat ? wasteKg(tercatat?.kg) : DASH,
      hint: adaTercatat
        ? `${tercatat?.events ?? 0} peristiwa · ${wasteKg(tanpaMitra?.kg)} tanpa mitra`
        : "pencatatan limbah/sisa pangan belum tersedia",
    },
    {
      label: "Limbah dialihkan",
      value: adaAlih ? wasteKg(dialihkan?.kg) : DASH,
      hint: adaAlih
        ? `${dialihkan?.events ?? 0} peristiwa ke mitra`
        : "pengalihan limbah belum tercatat",
    },
    {
      label: "Komposter / bank pangan",
      value: mitra.length
        ? mitra.map((p) => `${p.name} · ${wasteKg(p.kg)}`).join(" · ")
        : DASH,
      hint: mitra.length
        ? `${mitra.length} mitra pengolahan`
        : "belum ada data mitra pengolahan",
    },
  ];
}

function nodes(locations: unknown): BalanceNode[] {
  return Array.isArray(locations) ? (locations as BalanceNode[]) : [];
}

function number(value: unknown): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function name(node: BalanceNode): string {
  const raw = node?.location ? String(node.location).trim() : "";
  return raw || DASH;
}

function region(node: BalanceNode): string | null {
  const raw = node?.region ? String(node.region).trim() : "";
  return raw || null;
}

function sumOrNull(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((total, value) => total + value, 0);
}

/**
 * Tiga baris limbah untuk halaman Location Network (versi ringkas).
 *
 * Dipisah dari `wasteFacts` karena daftar mitra bukan angka yang dibaca operator
 * di halaman ini, dan label panjang membuat baris terlipat. Bila server belum
 * mengirim angka, hasilnya array KOSONG: pemanggil menulis "Belum dicatat."
 * alih-alih tiga baris "—" yang terbaca seperti pengukuran nol.
 */
export function wasteRingkas(
  payload?: unknown
): { label: string; value: string; hint: string | null }[] {
  const data = (payload ?? {}) as WastePayload;
  if (!data.recorded?.available) return [];

  const baris = (
    label: string,
    sumber: { available?: boolean; kg?: number | null; events?: number } | undefined
  ) => ({
    label,
    value: sumber?.available ? wasteKg(sumber?.kg) : DASH,
    hint:
      sumber?.available && Number.isFinite(Number(sumber?.events))
        ? `${sumber?.events} peristiwa`
        : null,
  });

  return [
    baris("Tercatat", data.recorded),
    baris("Dialihkan", data.diverted),
    baris("Tanpa mitra", data.unassigned),
  ];
}
