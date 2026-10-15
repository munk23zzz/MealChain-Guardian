"use client";

/**
 * Sampel keputusan untuk halaman Kualitas Agen & Pemasok (Rules.md §3): jejak
 * agen + ringkasan persetujuan per keputusan sampel.
 *
 * Kunci query memakai ISI sampel (daftar id), bukan seluruh daftar keputusan:
 * dengan begitu polling feed tidak memicu penilaian ulang, sementara sampel yang
 * benar-benar berubah tetap diambil ulang. Itu perilaku penjaga lama
 * (`evaluatedKey.current`), sekarang ditangani cache React Query.
 *
 * `retry: false`: kegagalan ditampilkan apa adanya, tidak diulang diam-diam.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchApprovalSummary, fetchDecisionTraces } from "../api";
import { errorMessage, queryKeys } from "../query";

export type SampleRow = { decisionId: string; trace: any; summary: any };

export function useQualitySample(
  token: string | null,
  scope: string,
  tab: string,
  sampleIds: string[]
) {
  const sampleKey = sampleIds.join(",");
  // Tab gabungan "kpi-kualitas" (keputusan pemilik 2026-10-15) menggantikan
  // tab "quality" lama; tab Pemasok tetap memakainya untuk konteks eksklusi.
  const tabRelevan = tab === "kpi-kualitas" || tab === "suppliers";
  const query = useQuery({
    queryKey: queryKeys.qualitySample(scope, sampleKey),
    queryFn: async (): Promise<SampleRow[]> =>
      Promise.all(
        sampleIds.map(async (decisionId) => {
          const [trace, summary] = await Promise.all([
            fetchDecisionTraces(decisionId, token as string).catch(() => null),
            fetchApprovalSummary(decisionId, token as string).catch(() => null),
          ]);
          return { decisionId, trace, summary };
        })
      ),
    enabled: Boolean(token) && Boolean(sampleKey) && tabRelevan,
    refetchInterval: false,
    retry: false,
  });
  return {
    rows: query.data ?? null,
    loading: query.isFetching,
    error: errorMessage(query.error),
    // Tombol "Coba lagi" di dua papan (Kualitas Agen & Pemasok) memakai ini.
    refetch: query.refetch,
  };
}
