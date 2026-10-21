/**
 * Titik tunggal konfigurasi data-fetching (Rules.md §3: semua data-fetching
 * lewat React Query, jangan fetch manual di dalam component).
 *
 * Modul ini MURNI (tanpa React, tanpa DOM) supaya bisa diuji dengan vitest
 * `environment: node` dan supaya komponen/halaman tidak menyalin angka
 * staleTime/interval polling masing-masing.
 */
import { QueryClient } from "@tanstack/react-query";

/** Data dianggap segar selama ini — mencegah refetch beruntun saat tab berganti. */
export const QUERY_STALE_MS = 30_000;

/** Interval poll layar demo (dulu hardcode `setInterval(…, 60000)` di halaman). */
export const QUERY_POLL_MS = 60_000;

/**
 * Data pemasok nyaris statis (profil + koordinat) — cukup segar 5 menit dan
 * TIDAK di-poll: kalau di-poll, 44 baris × 15 field ikut terkirim tiap putaran
 * padahal isinya tidak berubah. Tombol "Coba lagi"/invalidasi tetap bisa
 * memaksa muat ulang.
 */
export const SUPPLIERS_STALE_MS = 5 * 60_000;

/**
 * Kunci query terpusat. Sengaja berupa fungsi (bukan literal yang tersebar) agar
 * invalidasi setelah mutasi menyasar kunci yang sama persis — salah satu penyebab
 * umum data basi di UI.
 */
export const queryKeys = {
  today: (scope: string) => ["today", scope] as const,
  decisions: (scope: string) => ["decisions", scope] as const,
  batches: () => ["batches"] as const,
  kpi: (start: string, end: string, scope: string) =>
    ["kpi", start, end, scope] as const,
  exclusions: (scope: string) => ["exclusions", scope] as const,
  suppliers: (scope: string, reachKm?: number | null, commodity?: string | null) =>
    ["suppliers", scope, reachKm ?? "all", commodity ?? "all"] as const,
  supplierRoutes: (scope: string, commodity?: string | null, location?: string | null) =>
    ["supplier-routes", scope, commodity ?? "all", location ?? "all"] as const,
  me: (scope: string) => ["me", scope] as const,
  balanceMap: (scope: string, commodity: string) =>
    ["balance-map", scope, commodity] as const,
  kpiLive: (scope: string, windowKey: string = "24h") =>
    ["kpi-live", scope, windowKey] as const,
  // Limbah + mitra pengolahan (18 Okt 2026): satu angka per panel Surplus &
  // Limbah. Kunci memuat scope karena SPPG hanya melihat lokasinya.
  wasteSummary: (scope: string) => ["waste-summary", scope] as const,
  // Rencana alokasi surplus lintas lokasi (20 Okt 2026). Kunci TIDAK memuat
  // scope: rencananya memang lintas lokasi (server yang menghitung), jadi
  // jangan dibuat berbeda per peran — hasilnya sama untuk komoditas yang sama.
  surplusPlan: (commodity: string) => ["surplus-plan", commodity] as const,
  // Kalender agenda (langkah 2, 2026-10-16): rentang grid bulan masuk kunci
  // query supaya berpindah bulan memakai cache yang benar dan bulan yang sama
  // tidak diambil dua kali.
  agenda: (scope: string, start: string, end: string) =>
    ["agenda", scope, start, end] as const,
  decisionDetail: (decisionId: string, scope: string) =>
    ["decision-detail", decisionId, scope] as const,
  // Papan status integrasi (W-3, 2026-10-17): isinya env + artefak, bukan angka
  // live — tanpa scope karena sama untuk semua peran yang sah.
  integrationStatus: () => ["integration-status"] as const,
  // Purchase order mock SAP (W-5, 2026-10-17). Kuncinya memuat `scope` karena
  // isinya BERBEDA per peran: kepala/ahli gizi hanya PO lokasinya, monitor
  // nasional. Tanpa scope di kunci, dua peran di satu browser akan saling
  // menimpa cache dan menampilkan PO yang bukan haknya.
  purchaseOrders: (scope: string, saring = "all") =>
    ["purchase-orders", scope, saring] as const,
  purchaseOrderSummary: (scope: string) => ["purchase-order-summary", scope] as const,
  qualitySample: (scope: string, sampleKey: string) =>
    ["quality-sample", scope, sampleKey] as const,
  supplierContext: (decisionId: string) => ["supplier-context", decisionId] as const,
  traces: (decisionId: string) => ["traces", decisionId] as const,
  approvalSummary: (decisionId: string) => ["approval-summary", decisionId] as const,
  approvalLog: (decisionId: string) => ["approval-log", decisionId] as const,
} as const;

/**
 * Pesan galat yang aman ditampilkan. `null` berarti tidak ada galat, sehingga
 * pemanggil bisa memakai `??` untuk menggabungkan beberapa sumber galat.
 */
export function errorMessage(e: unknown): string | null {
  if (e === null || e === undefined) return null;
  if (e instanceof Error) return e.message;
  return String(e);
}

/** QueryClient dengan default proyek. Dibuat per sesi browser, bukan per modul. */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: QUERY_STALE_MS,
        refetchInterval: QUERY_POLL_MS,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });
}
