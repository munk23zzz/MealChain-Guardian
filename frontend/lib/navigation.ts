/**
 * navigation.ts — SATU sumber nama tab.
 *
 * Masalah yang diselesaikan (29 Okt 2026): label navbar dan judul halaman ditulis
 * terpisah, jadi bisa menyimpang tanpa ada yang gagal. Keadaan sebelumnya:
 *
 *   navbar "Food Safety"          · judul halaman "Keamanan Pangan"
 *   navbar "Suppliers"            · judul halaman "Pemasok"
 *   navbar "Agent Log"            · judul halaman "Agent Activity Log"
 *   navbar "Supply & Demand"      · judul halaman "Pasokan & Kebutuhan"
 *
 * Sekarang keduanya membaca konstanta yang sama: mengganti nama halaman berarti
 * mengganti satu baris di sini, dan navbar otomatis ikut. Tes
 * `tests/navigation-titles.test.ts` membaca sumber komponen untuk memastikan tidak
 * ada yang kembali menulis judul sebagai literal.
 *
 * Bahasa: Inggris (pilihan pengguna 29 Okt 2026). Isi halaman tetap Bahasa
 * Indonesia — yang disamakan hanya NAMA halaman.
 */

/** Judul halaman untuk tab yang namanya tetap (tidak bergantung peran). */
export const PAGE_TITLES = {
  today: "Today",
  overview: "Overview",
  recommendations: "Recommendations",
  /** Keputusan + rantai buktinya. */
  evidence: "Decision & Evidence",
  /** Status keamanan batch, kesegaran, penerimaan barang. */
  safety: "Food Safety",
  /** Daftar pemasok, register eksklusi, usul eksklusi. */
  suppliers: "Suppliers",
  /** Jejak langkah agent per keputusan. */
  agentLog: "Agent Activity Log",
  kpiKualitas: "Performance & Audit",
  settings: "Settings",
  demoControl: "Demo Control",
} as const;

/**
 * Judul tab jaringan lokasi bergantung peran: nutritionist membuka halaman ini
 * untuk kecukupan gizi satu lokasi (bukan pandangan jaringan), jadi namanya
 * menyebut pekerjaannya sendiri. Navbar dan judul halaman memakai fungsi yang
 * SAMA supaya tidak pernah berbeda.
 */
export function locationNetworkTitle(role: string | null | undefined): string {
  return role === "sppg_nutritionist" ? "Supply & Demand" : "Location Network";
}

/** Kalimat bantuan (tooltip) tab jaringan lokasi — ikut peran, seperti judulnya. */
export function locationNetworkHint(role: string | null | undefined): string {
  return role === "sppg_nutritionist"
    ? "Supply, demand, and batches for one location"
    : "Who is short, who has surplus, what is reallocated, what is wasted";
}
