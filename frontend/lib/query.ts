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
  me: (scope: string) => ["me", scope] as const,
  balanceMap: (scope: string, commodity: string) =>
    ["balance-map", scope, commodity] as const,
  kpiLive: (scope: string) => ["kpi-live", scope] as const,
  decisionDetail: (decisionId: string, scope: string) =>
    ["decision-detail", decisionId, scope] as const,
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
