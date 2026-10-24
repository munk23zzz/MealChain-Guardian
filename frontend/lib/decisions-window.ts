/**
 * Jendela periode feed rekomendasi (permintaan pemilik 24 Okt 2026).
 *
 * Tiga pilihan: Hari ini (24 jam bergulir), 7 hari, 1 bulan (bulan berjalan
 * WIB). Kunci jendela SAMA dengan pemilih KPI (`KpiWindowKey`) supaya dua
 * kontrol di aplikasi ini tidak pernah punya arti berbeda untuk "7 hari".
 *
 * Label pertama sengaja "Hari ini" (bukan "24 jam") karena itu pertanyaan yang
 * dipakai di layar rekomendasi; teks bantuan menyebut 24 jam supaya tidak
 * ambigu dengan "hari kalender".
 */
import type { KpiWindowKey } from "./kpi";

export type FeedWindowKey = KpiWindowKey;

export const FEED_WINDOW_DEFAULT: FeedWindowKey = "24h";

export const FEED_WINDOWS: readonly {
  key: FeedWindowKey;
  label: string;
  hint: string;
}[] = [
  { key: "24h", label: "Hari ini", hint: "24 jam terakhir" },
  { key: "7d", label: "7 hari", hint: "7 hari terakhir" },
  { key: "30d", label: "1 bulan", hint: "bulan berjalan (WIB)" },
];

/** Label periode untuk dipakai di kalimat status/empty state. */
export function feedWindowLabel(key: FeedWindowKey): string {
  return FEED_WINDOWS.find((w) => w.key === key)?.label ?? "Hari ini";
}

export function feedWindowHint(key: FeedWindowKey): string {
  return FEED_WINDOWS.find((w) => w.key === key)?.hint ?? "24 jam terakhir";
}
