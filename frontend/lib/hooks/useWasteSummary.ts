"use client";

/**
 * Limbah + mitra pengolahan (GET /waste/summary).
 *
 * Kenapa ada: panel Surplus & Limbah dulu menulis "—" untuk tiga baris limbah
 * karena tidak ada sumber datanya. Sekarang angkanya datang dari server
 * (`disposal_events.partner_name`, migrasi 022) — bukan dari klien.
 *
 * Diambil hanya di tab yang memakainya, sama seperti KPI: panel lain tidak
 * perlu memanggil endpoint ini.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchWasteSummary } from "../api";
import { errorMessage, queryKeys } from "../query";

export function useWasteSummary(
  token: string | null,
  scope: string,
  tab: string,
  days = 30
) {
  const query = useQuery({
    queryKey: queryKeys.wasteSummary(scope),
    queryFn: () => fetchWasteSummary(token as string, days),
    enabled: Boolean(token) && tab === "surplus",
    refetchInterval: false,
  });
  return {
    data: query.data ?? null,
    loading: query.isFetching,
    error: errorMessage(query.error),
    refetch: query.refetch,
  };
}
