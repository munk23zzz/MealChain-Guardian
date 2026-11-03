"use client";

/**
 * Rencana alokasi surplus lintas lokasi (GET /surplus/allocations).
 *
 * Kenapa ada: panel "Rencana alokasi surplus" dulu merakit pasangan surplus ->
 * kekurangan dari `GET /balance/map`, yang untuk peran SPPG hanya berisi
 * lokasinya sendiri (Ruling 2026-10-14). Satu lokasi tidak pernah punya
 * pasangan, jadi panel selalu menulis "Tidak ada pasangan..." (terukur:
 * Kepala Bandung melihat 0 lokasi surplus). Halaman Surplus & Limbah justru
 * hanya bisa dibuka peran SPPG — dua aturan itu saling mengunci.
 *
 * Server yang menghitung: yang dikirim hanya pasangan (dari, ke, kg, jarak).
 *
 * Diambil hanya di tab yang memakainya (tab "surplus"), sama seperti limbah.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchSurplusAllocations } from "../api";
import { errorMessage, queryKeys } from "../query";

export function useSurplusPlan(
  token: string | null,
  commodity: string,
  tab: string,
  limit = 6
) {
  const query = useQuery({
    queryKey: queryKeys.surplusPlan(commodity),
    queryFn: () => fetchSurplusAllocations(token as string, commodity, limit),
    enabled:
      Boolean(token) && (tab === "surplus" || tab === "location-network") && Boolean(commodity),
    refetchInterval: false,
  });
  return {
    data: query.data ?? null,
    loading: query.isFetching,
    error: errorMessage(query.error),
    refetch: query.refetch,
  };
}
