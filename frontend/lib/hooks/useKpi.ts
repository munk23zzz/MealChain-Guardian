"use client";

/**
 * Envelope KPI (GET /kpi) lewat React Query (Rules.md §3) — dulu `loadKpi` +
 * `useEffect` di halaman.
 *
 * Jendela waktu (dulu DIPAKU 24 jam di sini) kini datang dari pemilih periode:
 * `KPI_WINDOWS` + `kpiWindowRange` di lib/kpi.ts. Rentangnya dihitung SAAT
 * fetch, bukan disimpan di kunci query sebagai tanggal — kalau tanggalnya masuk
 * kunci, setiap detik kuncinya berubah dan query tak pernah tenang. Yang masuk
 * kunci adalah KUNCI JENDELA-nya ("24h" / "7d" / "30d"), sehingga berpindah
 * jendela memakai cache yang benar dan pilihannya bukan sekadar hiasan.
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
import { kpiWindowRange, shouldLoadKpi, type KpiWindowKey } from "../kpi";
import { errorMessage, queryKeys } from "../query";

export function useKpi(
  token: string | null,
  scope: string,
  tab: string,
  windowKey: KpiWindowKey = "24h"
) {
  const query = useQuery({
    queryKey: queryKeys.kpiLive(scope, windowKey),
    queryFn: () => {
      const { start, end } = kpiWindowRange(windowKey);
      return fetchKpis(start, end, token as string);
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
