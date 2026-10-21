"use client";

/**
 * Empat panggilan GET /balance/map (satu per komoditas) untuk satu SPPG.
 *
 * Halaman Overview hanya butuh SATU komoditas untuk peta, tetapi grafik
 * kecukupan SPPG/gizi membandingkan keempat komoditas sekaligus. Memanggil
 * hook `useBalanceMap` empat kali di loop melanggar rules-of-hooks; `useQueries`
 * adalah bentuk yang benar dan tetap memakai query key yang sama sehingga cache
 * peta dan grafik tidak pernah berbeda sumber.
 */
import { useQueries } from "@tanstack/react-query";

import { fetchBalanceMap } from "../api";
import type { BalanceMapLocation } from "../overview-format";
import { errorMessage, queryKeys } from "../query";
import { MAP_POLL_MS } from "./useBalanceMap";

export function useCommodityBalance(
  token: string | null,
  scope: string,
  commodities: readonly string[],
  enabled = true
) {
  const queries = useQueries({
    queries: commodities.map((commodity) => ({
      queryKey: queryKeys.balanceMap(scope, commodity),
      queryFn: () => fetchBalanceMap(commodity, token as string),
      enabled: Boolean(token) && enabled,
      refetchInterval: MAP_POLL_MS,
    })),
  });

  const byCommodity: Record<string, BalanceMapLocation[]> = {};
  let isLoading = false;
  let error: string | null = null;
  let updatedAt = 0;

  queries.forEach((query, index) => {
    const commodity = commodities[index];
    const locations = (query.data?.locations ?? []) as BalanceMapLocation[];
    byCommodity[commodity] = locations;
    if (query.isLoading) isLoading = true;
    if (query.error && !error) {
      error = errorMessage(query.error) ?? "Data komoditas tidak tersedia.";
    }
    if (query.dataUpdatedAt > updatedAt) updatedAt = query.dataUpdatedAt;
  });

  return {
    byCommodity,
    isLoading,
    error,
    updatedAt: updatedAt || null,
    refetch: () => Promise.all(queries.map((query) => query.refetch())),
  };
}
