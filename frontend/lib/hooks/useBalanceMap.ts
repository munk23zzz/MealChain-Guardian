"use client";

/**
 * Peta saldo (GET /balance/map) lewat React Query (Rules.md §3) — dulu
 * `loadMap` + `setInterval(…, 5000)` di dalam page.tsx.
 *
 * `updatedAt` diambil dari `dataUpdatedAt` React Query, bukan stempel waktu
 * buatan sendiri: label "Diperbarui HH:MM" jadi merujuk pada data yang benar-
 * benar diterima, dan tidak ada lagi state ganda yang bisa menyimpang.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchBalanceMap } from "../api";
import { errorMessage, queryKeys } from "../query";

/** Peta dipakai top bar di semua tab; 5 detik cukup untuk demo tanpa membanjiri backend. */
export const MAP_POLL_MS = 5_000;

export function useBalanceMap(
  token: string | null,
  scope: string,
  commodity: string
) {
  const query = useQuery({
    queryKey: queryKeys.balanceMap(scope, commodity),
    queryFn: () => fetchBalanceMap(commodity, token as string),
    enabled: Boolean(token),
    refetchInterval: MAP_POLL_MS,
  });
  return {
    data: query.data ?? null,
    error: query.error ? errorMessage(query.error) ?? "Peta tidak tersedia." : null,
    updatedAt: query.dataUpdatedAt || null,
    isFetching: query.isFetching,
    refetch: query.refetch,
  };
}
