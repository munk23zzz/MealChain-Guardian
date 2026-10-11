"use client";

/**
 * Register eksklusi pemasok (GET /supplier-exclusions) lewat React Query
 * (Rules.md §3).
 *
 * Register punya siklus muat SENDIRI. Dulu ia diambil di dalam efek sampel yang
 * ber-penjaga "sampel sudah dinilai", sehingga membuka tab Pemasok setelah tab
 * Kualitas Agen tidak pernah memanggil endpointnya — kartu register sempat
 * mengklaim "tidak ada eksklusi" padahal datanya belum dimuat. Gerbang
 * `shouldLoadExclusions` dipertahankan apa adanya.
 */
import { useQuery } from "@tanstack/react-query";

import { errorMessage, queryKeys } from "../query";
import { fetchExclusions, shouldLoadExclusions } from "../supplier-exclusions";

export function useExclusions(token: string | null, scope: string, tab: string) {
  const query = useQuery({
    queryKey: queryKeys.exclusions(scope),
    // Kegagalan diserap menjadi `null` seperti perilaku lama (kartu menampilkan
    // keadaan kosong, bukan galat halaman penuh).
    queryFn: () => fetchExclusions(token as string).catch(() => null),
    enabled: Boolean(token) && shouldLoadExclusions(tab, token),
    refetchInterval: false,
  });
  return {
    data: query.data ?? null,
    isFetching: query.isFetching,
    error: errorMessage(query.error),
  };
}
