export const BALANCE_STATUSES = ["shortage", "surplus", "balanced"] as const;
export type BalanceStatus = (typeof BALANCE_STATUSES)[number];

/**
 * Asal nilai per sisi (PLAN-023, 2026-10-17). Backend mengisi supply/demand yang
 * TIDAK ADA dengan `0` supaya peta tetap lengkap, jadi angka saja tidak cukup:
 * `tidak_ada_baris` berarti angka 0 itu hasil pengisian, bukan hasil pengukuran.
 */
export type DataState = "terukur" | "sebagian" | "tidak_ada_baris";

/** The exact read model returned by GET /balance/map. Values may be absent on partial/stale data. */
export type BalanceMapLocation = {
  location: string;
  status: BalanceStatus | string;
  supply_kg?: number | string | null;
  demand_kg?: number | string | null;
  shortage_kg?: number | string | null;
  surplus_kg?: number | string | null;
  latitude?: number | string | null;
  longitude?: number | string | null;
  region?: string | null;
  /** Asal nilai per sisi + ringkasannya (opsional: respons lama tidak punya). */
  supply_state?: DataState | string | null;
  demand_state?: DataState | string | null;
  data_state?: DataState | string | null;
  supply_recorded_at?: string | null;
  demand_recorded_at?: string | null;
};

/** Sisi tanpa baris = angka 0-nya hasil pengisian, bukan fakta terukur. */
export function tanpaCatatan(state?: string | null): boolean {
  return state === "tidak_ada_baris";
}

/**
 * Catatan asal nilai untuk RINCIAN/tooltip — `null` bila semua sisi terukur,
 * sehingga tidak ada label tambahan di keadaan normal. Angka `0` yang terukur
 * tetap ditampilkan `0 kg`; catatan ini hanya menerangkan yang tidak tercatat.
 */
export function dataSourceNote(
  location: Partial<BalanceMapLocation> | null | undefined
): string | null {
  const sisi: string[] = [];
  if (tanpaCatatan(location?.supply_state)) sisi.push("pasokan");
  if (tanpaCatatan(location?.demand_state)) sisi.push("permintaan");
  if (sisi.length === 0) return null;
  return `${sisi.join(" & ")} tanpa catatan`;
}

export function isBalanceStatus(status: string): status is BalanceStatus {
  return (BALANCE_STATUSES as readonly string[]).includes(status);
}

const TANGGAL_DATA = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Asia/Jakarta",
});

/** Tanggal TERBARU dari satu sisi, dihitung dari stempel waktu mentah. */
function tanggalTerbaru(
  locations: readonly BalanceMapLocation[],
  sisi: "supply_recorded_at" | "demand_recorded_at"
): string | null {
  let msTerbaru: number | null = null;
  for (const location of locations) {
    const ms = Date.parse(location[sisi] ?? "");
    if (!Number.isFinite(ms)) continue;
    if (msTerbaru === null || ms > msTerbaru) msTerbaru = ms;
  }
  return msTerbaru === null ? null : TANGGAL_DATA.format(new Date(msTerbaru));
}

/**
 * Label periode data peta ("Pasokan per 4 Nov 2026 · permintaan per 8 Okt 2026").
 *
 * `GET /balance/map` memakai baris TERBARU per lokasi, dan deret demo sudah
 * diperluas sampai 5 Nov — jadi pasokan dan permintaan bisa berasal dari
 * tanggal berbeda. Tanpa label, angka itu terbaca sebagai "kondisi hari ini".
 * Stempel waktunya dibaca dari payload (`*_recorded_at`), bukan dari jam sistem.
 */
export function snapshotNote(
  locations: readonly BalanceMapLocation[] | null | undefined
): string | null {
  if (!locations?.length) return null;
  const pasokan = tanggalTerbaru(locations, "supply_recorded_at");
  const permintaan = tanggalTerbaru(locations, "demand_recorded_at");
  if (pasokan && permintaan) {
    return pasokan === permintaan
      ? `Data per ${pasokan}`
      : `Pasokan per ${pasokan} · permintaan per ${permintaan}`;
  }
  if (pasokan) return `Pasokan per ${pasokan} · permintaan belum ada catatan`;
  if (permintaan) return `Permintaan per ${permintaan}`;
  return null;
}

const JAM_SINKRON = new Intl.DateTimeFormat("id-ID", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
  timeZone: "Asia/Jakarta",
});

/**
 * "Sinkron 20.20.22 WIB" — jam PENGAMBILAN data (polling), bukan jam data.
 *
 * Dulu pill peta menulis "Diperbarui 15.14 WIB" dari jam fetch, sehingga
 * terbaca sebagai waktu data. Sekarang dua hal itu dipisah tegas: tanggal data
 * memakai `snapshotNote()` (dibaca dari `*_recorded_at`), sedangkan jam sinkron
 * memakai helper ini dan menyebut dirinya "Sinkron".
 */
export function syncLabel(at: Date | number | string | null | undefined): string | null {
  if (at == null || at === "") return null;
  const ms =
    at instanceof Date
      ? at.getTime()
      : typeof at === "number"
        ? at
        : Date.parse(at as string);
  if (!Number.isFinite(ms)) return null;
  return `Sinkron ${JAM_SINKRON.format(new Date(ms))} WIB`;
}

export function formatKg(value: number | string | null | undefined): string {
  if (value == null || value === "") return "—";
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toLocaleString("id-ID")} kg` : "—";
}

export function formatBalanceGap(location: BalanceMapLocation): string {
  if (location.status === "shortage") return `kurang ${formatKg(location.shortage_kg)}`;
  if (location.status === "surplus") return `lebih ${formatKg(location.surplus_kg)}`;
  if (location.status === "balanced") return "seimbang";
  return "status belum tersedia";
}

export function formatBalanceStatus(status: string): string {
  if (status === "shortage") return "Shortage";
  if (status === "surplus") return "Surplus";
  if (status === "balanced") return "Seimbang";
  return "Status belum tersedia";
}

export function sumFiniteKg(locations: readonly Pick<BalanceMapLocation, "supply_kg">[]): number | null {
  if (!locations.length) return null;
  let total = 0;
  for (const { supply_kg } of locations) {
    if (supply_kg == null || (typeof supply_kg === "string" && !supply_kg.trim())) return null;
    const value = Number(supply_kg);
    if (!Number.isFinite(value)) return null;
    total += value;
  }
  return total;
}

export function summarizeBalanceStatus(locations: readonly BalanceMapLocation[]): string {
  const counts = locations.reduce(
    (summary, location) => {
      if (isBalanceStatus(location.status)) summary[location.status] += 1;
      return summary;
    },
    { surplus: 0, shortage: 0, balanced: 0 } as Record<BalanceStatus, number>,
  );
  return `${counts.surplus} surplus · ${counts.shortage} shortage · ${counts.balanced} seimbang`;
}
