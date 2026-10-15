"use client";

/**
 * Envelope KPI (GET /kpi) lewat React Query (Rules.md §3) — dulu `loadKpi` +
 * `useEffect` di halaman.
 *
 * Jendela waktu (24 jam terakhir) dihitung SAAT fetch, bukan disimpan di kunci
 * query: kalau jendelanya masuk kunci, setiap detik kuncinya berubah dan query
 * tak pernah tenang. Karena itu kuncinya `kpiLive(scope)`.
 *
 * Tidak dipoll: KPI adalah potret, dan backend menghitungnya atas permintaan.
 * Tombol "Coba lagi" memanggil `refetch()`.
 *
 * Sejak 2026-10-15 potret ini hanya diambil di tab yang memakainya
 * (`shouldLoadKpi` di lib/kpi.ts: tab Hari Ini + tab gabungan KPI & Kualitas
 * Agen). Sebelumnya ia diambil di SEMUA tab.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchKpis } from "../api";
import { shouldLoadKpi } from "../kpi";
import { errorMessage, queryKeys } from "../query";

export const KPI_WINDOW_MS = 24 * 60 * 60 * 1000;

export function useKpi(token: string | null, scope: string, tab: string) {
  const query = useQuery({
    queryKey: queryKeys.kpiLive(scope),
    queryFn: () => {
      const end = new Date();
      const start = new Date(end.getTime() - KPI_WINDOW_MS);
      return fetchKpis(start.toISOString(), end.toISOString(), token as string);
    },
    enabled: Boolean(token) && shouldLoadKpi(tab),
    refetchInterval: false,
  });
  return {
    data: query.data ?? null,
    loading: query.isFetching,
    error: errorMessage(query.error),
    refetch: query.refetch,
  };
}
