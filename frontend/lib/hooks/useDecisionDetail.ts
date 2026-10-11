"use client";

/**
 * Detail satu keputusan (Rules.md §3): jejak agen, rantai audit, ringkasan
 * persetujuan kanonik, dan konteks pemasok — dulu satu `load()` + `setInterval`
 * 5 detik di dalam page.tsx.
 *
 * Kontrak yang dipertahankan: keempat panggilan bersifat OPSIONAL bagi feed.
 * Kegagalan salah satunya diserap (`catch(() => null)`) supaya panel tetap
 * terbuka dengan yang berhasil; tidak ada nilai karangan pengganti.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchApprovalSummary, fetchDecisionChain, fetchDecisionTraces } from "../api";
import { queryKeys } from "../query";
import { fetchSupplierContext, type SupplierContext } from "../supplier-exclusions";

export const DECISION_DETAIL_POLL_MS = 5_000;

export type DecisionDetail = {
  traces: any[];
  chain: any[];
  approvalSummary: any;
  supplierContext: SupplierContext | null;
};

const KOSONG: DecisionDetail = {
  traces: [],
  chain: [],
  approvalSummary: null,
  supplierContext: null,
};

export function useDecisionDetail(
  token: string | null,
  decisionId: string | null,
  scope: string
): DecisionDetail {
  const query = useQuery({
    queryKey: queryKeys.decisionDetail(decisionId ?? "none", scope),
    queryFn: async (): Promise<DecisionDetail> => {
      const id = decisionId as string;
      const [traces, chain, summary, supplier] = await Promise.all([
        fetchDecisionTraces(id, token as string).catch(() => null),
        fetchDecisionChain(id, token as string).catch(() => null),
        fetchApprovalSummary(id, token as string).catch(() => null),
        fetchSupplierContext(id, token as string).catch(() => null),
      ]);
      return {
        traces: traces?.steps ?? [],
        chain: chain?.chain ?? [],
        approvalSummary: summary ?? null,
        supplierContext: supplier ?? null,
      };
    },
    enabled: Boolean(token) && Boolean(decisionId),
    // Poll ini yang menyegarkan approval_state saat pihak lain menyetujui.
    refetchInterval: DECISION_DETAIL_POLL_MS,
  });
  return query.data ?? KOSONG;
}
