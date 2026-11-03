"use client";

/**
 * Data halaman "Hari Ini" (Rules.md §3) — batch (GET /batches) + rantai audit
 * Merkle (GET /ledger/verify). Dulu satu fungsi loader + setInterval 60 detik.
 *
 * Kontrak yang dipertahankan: kegagalan salah satu panggilan tidak menjatuhkan
 * yang lain, dan tidak pernah ada angka karangan — kartu menulis "—" atau pesan
 * galat. Karena itu kegagalan verifikasi ledger diserap di dalam queryFn,
 * sedangkan kegagalan batch dibiarkan naik menjadi error query.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchBatches, verifyLedger } from "../api";
import { queryKeys } from "../query";

export const TODAY_POLL_MS = 60_000;

/** Bentuk data yang dipakai kartu halaman "Hari Ini" (dulu `any` di page.tsx). */
export type TodayData = { batches: any[]; ledger: any };

export function useToday(token: string | null, scope: string) {
  return useQuery({
    queryKey: queryKeys.today(scope),
    queryFn: async (): Promise<TodayData> => {
      const rows = await fetchBatches(token as string);
      let ledger: any = null;
      try {
        ledger = await verifyLedger(token as string);
      } catch {
        ledger = null;
      }
      return { batches: Array.isArray(rows) ? rows : [], ledger };
    },
    enabled: Boolean(token),
    refetchInterval: TODAY_POLL_MS,
  });
}
