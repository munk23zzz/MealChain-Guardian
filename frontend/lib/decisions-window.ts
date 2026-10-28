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
export type FeedWindowKey = "24h" | "7d" | "30d";

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

/**
 * Petunjuk periode yang HANYA dicetak bila menambah arti di luar labelnya.
 *
 * Di layar, label dan petunjuk berdiri berdampingan ("Periode: [7 hari] 7 hari
 * terakhir") — untuk dua dari tiga jendela, petunjuk itu mengulang labelnya dan
 * terbaca seperti chip keempat tanpa fungsi. Yang menambah arti hanya "Hari
 * ini" (24 jam bergulir, bukan hari kalender) dan "1 bulan" (bulan berjalan
 * WIB, bukan 30 hari bergulir).
 */
export function feedWindowHintBilaBerbeda(key: FeedWindowKey): string | null {
  const hint = feedWindowHint(key);
  const label = feedWindowLabel(key);
  const sama = hint.toLowerCase().startsWith(label.toLowerCase());
  return sama ? null : hint;
}
