"use client";

/**
 * Angka pengadaan (GET /procurement/summary) untuk tile Overview.
 *
 * Kenapa dipoll: laporan pemilik 27 Okt 2026 — "setelah pengadaan dieksekusi,
 * Overview tidak berubah". Angka PO/eksekusi/truk harus terlihat berubah tanpa
 * memuat ulang halaman, sama seperti panel KPI (`KPI_POLL_MS`). Biayanya
 * terukur: tiga agregat SQL, tanpa LLM. Selain poll, setiap permintaan tulis
 * yang berhasil menyegarkan SELURUH cache lewat `lib/refresh.ts`, jadi eksekusi
 * dari tab Decision & Evidence langsung terlihat ketika pengguna kembali ke
 * Overview.
 *
 * Query hanya hidup di tab Overview (`enabled`): tab lain tidak menampilkannya,
 * jadi tidak perlu permintaan.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchProcurementSummary } from "../api";
import { KPI_POLL_MS, errorMessage, queryKeys } from "../query";

export function useProcurementSummary(
  token: string | null,
  scope: string,
  tab: string,
  windowKey: string = "today"
) {
  const aktif = Boolean(token) && tab === "overview";
  const query = useQuery({
    queryKey: queryKeys.procurementSummary(scope, windowKey),
    queryFn: () => fetchProcurementSummary(windowKey, token as string),
    enabled: aktif,
    // Selalu basi saat dibuka: angka ini bukti, bukan hiasan. `staleTime` 30
    // detik bawaan proyek akan membuat tile tetap menampilkan angka sebelum
    // eksekusi sampai satu putaran poll terlewat.
    staleTime: 0,
    refetchInterval: aktif ? KPI_POLL_MS : false,
    refetchIntervalInBackground: false,
  });
  return {
    data: query.data ?? null,
    loading: query.isFetching,
    error: errorMessage(query.error),
    refetch: query.refetch,
  };
}
