"use client";

// Status supervisor untuk tab Agent Log (dokumen 06-agent-log §2.8).
//
// Dipisah dari query trace: satu keputusan bisa punya trace lengkap sementara
// supervisor tidak dikonfigurasi. Menyatukannya akan membuat dua fakta berbeda
// terbaca sebagai satu sebab-akibat.

import { useQuery } from "@tanstack/react-query";

import { fetchSupervisorHealth } from "../api";
import { queryKeys } from "../query";

/** Status konfigurasi jarang berubah; 60 detik cukup. */
export const SUPERVISOR_HEALTH_POLL_MS = 60_000;

export function useSupervisorHealth(token: string | null, enabled = true) {
  return useQuery({
    queryKey: queryKeys.supervisorHealth(),
    queryFn: async () => await fetchSupervisorHealth(token as string),
    enabled: Boolean(token) && enabled,
    refetchInterval: SUPERVISOR_HEALTH_POLL_MS,
    staleTime: 30_000,
  });
}
