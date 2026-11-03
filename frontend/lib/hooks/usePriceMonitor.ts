"use client";

/**
 * Deret harga pasar (GET /price/monitor) lewat React Query.
 *
 * Data ini terbit SEHARI sekali (PIHPS, hari kerja), jadi tidak di-poll:
 * `staleTime` 5 menit dan tanpa `refetchInterval`. Tombol "Coba lagi" di panel
 * tetap bisa memaksa muat ulang saat operator baru menjalankan penarik data.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchPriceMonitor } from "../api";
import type { MonitorPayload } from "../price-monitor";
import { errorMessage, queryKeys } from "../query";

/** Harga acuan pasar berubah sekali sehari; 5 menit sudah jauh lebih rapat. */
export const PRICE_MONITOR_STALE_MS = 5 * 60_000;

export function usePriceMonitor(
  token: string | null,
  region: string | null,
  days: number,
  commodity: string | null
) {
  const query = useQuery({
    queryKey: queryKeys.priceMonitor(region, days, commodity),
    queryFn: () =>
      fetchPriceMonitor(token as string, { region, days, commodity }) as Promise<MonitorPayload>,
    // Tanpa wilayah yang sah, permintaan akan mengirim "semua wilayah" dan
    // panel menerima ribuan baris yang tidak akan dipakai.
    enabled: Boolean(token) && Boolean(region),
    staleTime: PRICE_MONITOR_STALE_MS,
    refetchInterval: false,
  });

  return {
    data: (query.data ?? null) as MonitorPayload | null,
    loading: query.isFetching,
    error: errorMessage(query.error),
    refetch: query.refetch,
  };
}
