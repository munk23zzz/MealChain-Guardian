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
 * Tidak lagi "potret sekali ambil": sejak 23 Okt 2026 kebijakan muatnya datang
 * dari `kpiQueryPolicy` — selalu basi saat dibuka (`staleTime: 0`) dan dipoll
 * tiap `KPI_POLL_MS` selama tab yang menampilkannya terbuka. Itulah yang
 * membuat kartu berubah sendiri beberapa detik setelah operator menjalankan
 * Event 1 → approve → execute, tanpa berpindah tab atau memuat ulang halaman.
 * Di tab yang tidak menampilkan KPI, query tetap MATI (tanpa permintaan
 * sia-sia).
 *
 * Sejak 2026-10-15 potret ini hanya diambil di tab yang memakainya
 * (`shouldLoadKpi` di lib/kpi.ts: tab Hari Ini + tab gabungan KPI & Kualitas
 * Agen). Sebelumnya ia diambil di SEMUA tab.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchKpis } from "../api";
import { kpiQueryPolicy, kpiWindowRange, type KpiWindowKey } from "../kpi";
import { errorMessage, queryKeys } from "../query";

export function useKpi(
  token: string | null,
  scope: string,
  tab: string,
  windowKey: KpiWindowKey = "24h"
) {
  const kebijakan = kpiQueryPolicy(tab);
  const query = useQuery({
    queryKey: queryKeys.kpiLive(scope, windowKey),
    queryFn: () => {
      const { start, end } = kpiWindowRange(windowKey);
      return fetchKpis(start, end, token as string);
    },
    enabled: Boolean(token) && kebijakan.enabled,
    staleTime: kebijakan.staleTime,
    refetchInterval: kebijakan.refetchInterval,
    // Ditulis eksplisit: jangan menembak backend saat tab browser tidak
    // terlihat. Default React Query memang begitu, tetapi panel demo ini
    // dipakai di laptop yang sering berpindah tab.
    refetchIntervalInBackground: false,
  });
  return {
    data: query.data ?? null,
    loading: query.isFetching,
    error: errorMessage(query.error),
    refetch: query.refetch,
  };
}
