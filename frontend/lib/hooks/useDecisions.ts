"use client";

/**
 * Feed keputusan (Rules.md §3) — dulu polling 5 detik ditulis manual dengan
 * useState + setInterval di app/page.tsx. Sekarang React Query yang mengelola
 * siklus hidupnya; komponen tetap menerima daftar yang sama.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchDecisions } from "../api";
import { queryKeys } from "../query";

/** design.md §5: MVP memakai polling, belum WebSocket. */
export const DECISIONS_POLL_MS = 5_000;

/**
 * Bentuk baris feed yang dipakai UI. Dulu tipe ini hidup di dalam page.tsx
 * sebagai `type Decision`; sekarang tinggal di sini supaya hook dan halaman
 * memakai kontrak yang sama (dan tidak ada `unknown` yang bocor ke render).
 */
export type DecisionRow = {
  decision_id: string;
  decision_type: string;
  status: string;
  quantity_kg: number | null;
  safe_delivered_cost: number | null;
  expires_at: string;
  valid: boolean;
  /** P4: true bila keputusan ini punya jejak 7 worker (dihitung backend). */
  has_agent_review?: boolean;
  /** 24 Okt 2026: siapa yang mengirim + tujuannya (dari backend, bukan tebakan). */
  supplier_name?: string | null;
  pengirim?: "pemasok" | "antar_sppg" | null;
  target_location_name?: string | null;
};

export function useDecisions(
  token: string | null,
  scope: string,
  // Sejak 24 Okt 2026: feed rekomendasi bisa dipersempit ke hari ini / 7 hari /
  // 1 bulan. `null` = seluruh riwayat (perilaku lama, dipakai hitungan global).
  window: string | null = null,
  enabled = true
) {
  return useQuery({
    queryKey: queryKeys.decisions(scope, window ?? "all"),
    queryFn: async () =>
      (await fetchDecisions(token as string, window)) as { items?: DecisionRow[] },
    enabled: Boolean(token) && enabled,
    refetchInterval: DECISIONS_POLL_MS,
  });
}
