"use client";

/**
 * Envelope KPI (GET /kpi) lewat React Query (Rules.md §3) — dulu `loadKpi` +
 * `useEffect` di halaman.
 *
 * Jendela waktu (dulu DIPAKU 24 jam di sini) kini datang dari pemilih periode:
 * `KPI_WINDOWS` di lib/kpi.ts, dan yang dikirim ke API hanya KUNCI periode
 * ("today" / "7d" / "1bulan"). Rentangnya dihitung SERVER dalam hari kalender
 * Asia/Jakarta, jadi tidak ada aritmetika tanggal di klien yang bisa meleset
 * 7 jam. Yang masuk kunci query adalah kunci periode, sehingga berpindah
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
import { KPI_DEFAULT_WINDOW, kpiQueryPolicy, type KpiWindowKey } from "../kpi";
import type { KpiScope } from "../kpi-provenance";
import { errorMessage, queryKeys } from "../query";

export function useKpi(
  token: string | null,
  scope: string,
  tab: string,
  windowKey: KpiWindowKey = KPI_DEFAULT_WINDOW,
  kpiScope: KpiScope = "operational",
  demoSessionId: string | null = null
) {
  const kebijakan = kpiQueryPolicy(tab);
  // Simulasi hanya bisa diminta dengan sesi eksplisit: server menolak 422 bila
  // `include_demo=true` tanpa `demo_session_id`, dan tidak ada jalur "sesi
  // terbaru" yang boleh menebak. Tanpa sesi aktif, permintaan tidak ditembak.
  const simulasi = kpiScope === "demo";
  const adaSesi = Boolean(demoSessionId);
  const query = useQuery({
    queryKey: queryKeys.kpiLive(scope, windowKey, simulasi ? "demo" : "operational"),
    queryFn: () => {
      // Hanya KUNCI periode yang dikirim: backend yang menghitung rentangnya
      // dalam hari kalender Asia/Jakarta. Menghitung tanggal di klien membuat
      // "Hari ini" bergeser 7 jam dan berbeda antar tab.
      return fetchKpis(windowKey, token as string, undefined, {
        includeDemo: simulasi,
        demoSessionId: demoSessionId ?? undefined,
      });
    },
    enabled: Boolean(token) && kebijakan.enabled && (!simulasi || adaSesi),
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
