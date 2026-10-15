// Halaman "Keamanan Pangan" — meniru halaman /compliance di aplikasi acuan
// (E:\hackathon\HackathonBil\MealchainGuardian), DISESUAIKAN ke data yang
// benar-benar ada di backend repo ini: GET /batches
// (safety_status, freshness_score, usable_until, quantity_kg, location, commodity).
//
// Tidak dipakai: papan CCP per-alat, bank sampel, jejak lot EPCIS, sensor suhu —
// backend ini tidak punya sumbernya, jadi halamannya TIDAK mengarang angka.
// Aturan tampilan: nilai tak diketahui ditulis "—".

const DASH = "—";

export type SafetyBatch = {
  id?: string | null;
  location?: string | null;
  commodity?: string | null;
  quantity_kg?: number | string | null;
  safety_status?: string | null;
  freshness_score?: number | string | null;
  usable_until?: string | null;
};

export type SafetyTone = "ok" | "warn" | "danger" | "muted";

/** Status keamanan batch → label manusia. */
export const SAFETY_LABEL: Record<string, string> = {
  pass: "Aman",
  fail: "Gagal uji",
  needs_verification: "Perlu verifikasi",
  pending: "Belum diuji",
};

export function safetyLabel(status: unknown): string {
  const key = text(status)?.toLowerCase() ?? "";
  if (!key) return DASH;
  return SAFETY_LABEL[key] ?? key.replace(/_/g, " ");
}

export function safetyTone(status: unknown): SafetyTone {
  switch (text(status)?.toLowerCase()) {
    case "pass":
      return "ok";
    case "fail":
      return "danger";
    case "needs_verification":
      return "warn";
    case "pending":
      return "muted";
    default:
      return "muted";
  }
}

/** Sisa jam sampai `usable_until`. null kalau tanggalnya tidak ada/tak terbaca. */
export function hoursLeft(usableUntil: unknown, now: Date): number | null {
  const parsed = Date.parse(String(usableUntil ?? ""));
  if (!Number.isFinite(parsed)) return null;
  const hours = (parsed - now.getTime()) / 3_600_000;
  return Number.isFinite(hours) ? hours : null;
}

export function hoursLabel(hours: number | null): string {
  if (hours === null) return DASH;
  const abs = Math.abs(hours);
  const text =
    abs >= 24
      ? `${Math.floor(abs / 24)} hari ${Math.round(abs % 24)} jam`
      : `${Math.round(abs)} jam`;
  return hours >= 0 ? `${text} lagi` : `lewat ${text}`;
}

export type SafetyRow = {
  id: string | null;
  location: string;
  commodity: string;
  kg: number | null;
  statusLabel: string;
  tone: SafetyTone;
  freshness: string;
  usableUntil: string;
  hoursLeft: number | null;
  hoursLabel: string;
};

/** Skor kesegaran 0..1 → persen (dipakai bersama halaman lain). */
export function freshnessPercent(score: unknown): string {
  if (score === null || score === undefined || score === "") return DASH;
  const numeric = Number(score);
  if (!Number.isFinite(numeric)) return DASH;
  return `${Math.round(numeric * 100)}%`;
}

/** Tanggal layak pakai ringkas (YYYY-MM-DD HH:MM WIB). */
export function usableLabel(usableUntil: unknown): string {
  const parsed = Date.parse(String(usableUntil ?? ""));
  if (!Number.isFinite(parsed)) return DASH;
  return new Date(parsed).toLocaleString("id-ID", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Jakarta",
  });
}

export function safetyRows(batches: unknown, now: Date): SafetyRow[] {
  const list = Array.isArray(batches) ? (batches as SafetyBatch[]) : [];
  return list.map((batch) => {
    const kg = Number(batch?.quantity_kg);
    const hours = hoursLeft(batch?.usable_until, now);
    return {
      id: text(batch?.id),
      location: text(batch?.location) ?? DASH,
      commodity: text(batch?.commodity) ?? DASH,
      kg: Number.isFinite(kg) ? kg : null,
      statusLabel: safetyLabel(batch?.safety_status),
      tone: safetyTone(batch?.safety_status),
      freshness: freshnessPercent(batch?.freshness_score),
      usableUntil: usableLabel(batch?.usable_until),
      hoursLeft: hours,
      hoursLabel: hoursLabel(hours),
    };
  });
}

export type SafetySummary = {
  total: number;
  safe: number;
  failed: number;
  needsVerification: number;
  unchecked: number;
  failedKg: number | null;
  failedLocations: string[];
  hasFail: boolean;
};

export function safetySummary(batches: unknown): SafetySummary {
  const rows = safetyRows(batches, new Date(0));
  const failed = rows.filter((row) => row.tone === "danger");
  const failedKg = failed.reduce<number | null>(
    (total, row) => (row.kg === null ? total : (total ?? 0) + row.kg),
    null
  );
  return {
    total: rows.length,
    safe: rows.filter((row) => row.tone === "ok").length,
    failed: failed.length,
    needsVerification: rows.filter((row) => row.tone === "warn").length,
    unchecked: rows.filter((row) => row.tone === "muted").length,
    failedKg,
    failedLocations: failed.map((row) => row.location),
    hasFail: failed.length > 0,
  };
}

function text(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const raw = String(value).trim();
  return raw ? raw : null;
}
