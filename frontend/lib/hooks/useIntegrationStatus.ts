"use client";

/**
 * Papan status integrasi (GET /integrations/status, W-3 2026-10-17).
 *
 * Isinya env + artefak, bukan angka yang berubah tiap detik — jadi TIDAK di-poll
 * (sama seperti daftar pemasok) dan tanpa retry otomatis: kalau endpoint gagal,
 * panel harus mengatakannya, bukan mencoba terus lalu menampilkan layar kosong
 * yang bisa disalahartikan sebagai "semua baik".
 */
import { useQuery } from "@tanstack/react-query";

import { fetchIntegrationStatus } from "../api";
import { QUERY_STALE_MS, errorMessage, queryKeys } from "../query";

export function useIntegrationStatus(token: string | null) {
  const query = useQuery({
    queryKey: queryKeys.integrationStatus(),
    queryFn: () => fetchIntegrationStatus(token as string),
    enabled: Boolean(token),
    staleTime: QUERY_STALE_MS,
    refetchInterval: false,
    retry: false,
  });
  return {
    data: query.data ?? null,
    error: query.error
      ? errorMessage(query.error) ?? "Status integrasi tidak tersedia."
      : null,
    isFetching: query.isFetching,
    refetch: query.refetch,
  };
}
