"use client";

/**
 * Surplus per WILAYAH (GET /surplus/regions) — pasangan grafik kecukupan di
 * Overview (28 Okt 2026).
 *
 * Kenapa lewat server: peta akun SPPG dibatasi cakupan (Ruling 2026-10-14),
 * jadi "surplus daerah lain" tidak ada di data yang boleh dibaca klien. Server
 * yang mengagregasi per `Location.region`, termasuk membuang lokasi pengguna
 * (`exclude`) supaya angka panel berarti "daerah LAIN".
 *
 * Poll 60 detik, bukan 5 detik seperti peta: angka ini neraca harian, bukan
 * posisi truk. Cukup cepat untuk demo, tidak membanjiri backend dengan agregat
 * sepuluh lokasi × empat komoditas.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchSurplusRegions } from "../api";
import { errorMessage, queryKeys, QUERY_POLL_MS } from "../query";

export function useSurplusRegions(
  token: string | null,
  scope: string,
  commodities: readonly string[],
  exclude: string | null,
  enabled = true
) {
  const query = useQuery({
    queryKey: queryKeys.surplusRegions(scope, commodities, exclude),
    queryFn: () => fetchSurplusRegions(token as string, commodities, exclude),
    enabled: Boolean(token) && enabled && commodities.length > 0,
    refetchInterval: QUERY_POLL_MS,
  });
  return {
    data: query.data ?? null,
    // `isLoading` (bukan `isFetching`): poll 60 detik tidak boleh mengedipkan
    // skeleton setiap menit — panel hanya kosong saat percobaan PERTAMA.
    loading: query.isLoading,
    error: query.error
      ? errorMessage(query.error) ?? "Surplus wilayah tidak tersedia."
      : null,
    updatedAt: query.dataUpdatedAt || null,
    refetch: query.refetch,
  };
}
