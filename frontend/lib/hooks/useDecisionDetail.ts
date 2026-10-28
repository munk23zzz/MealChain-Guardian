"use client";

/**
 * Detail satu keputusan (Rules.md §3): jejak agen, rantai audit, ringkasan
 * persetujuan kanonik, dan konteks pemasok — dulu satu `load()` + `setInterval`
 * 5 detik di dalam page.tsx.
 *
 * Kontrak yang dipertahankan: keempat panggilan bersifat OPSIONAL bagi feed.
 * Kegagalan salah satunya TIDAK menutup panel, tetapi juga TIDAK disembunyikan:
 * bagian yang gagal dicatat di `errors` dan ditampilkan di halaman. Tidak ada
 * nilai karangan pengganti.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchApprovalSummary, fetchDecision, fetchDecisionChain, fetchDecisionTraces } from "../api";
import { queryKeys } from "../query";
import { fetchSupplierContext, type SupplierContext } from "../supplier-exclusions";

export const DECISION_DETAIL_POLL_MS = 5_000;

export type DecisionDetail = {
  traces: any[];
  chain: any[];
  approvalSummary: any;
  supplierContext: SupplierContext | null;
  /**
   * `GET /decisions/{id}` — sumber `commercial_cost` + `market_reference`
   * (Fase 9 butir 3). Daftar `GET /decisions` tidak memuat keduanya, jadi
   * tanpa ini blok biaya di layar selalu "tidak berlaku".
   */
  decision: any | null;
  /**
   * Bagian yang GAGAL dibaca (label bahasa Indonesia).
   *
   * Audit data 26 Okt 2026: dulu keempat panggilan menelan galat
   * tanpa jejak apa pun, sehingga panel kosong tidak bisa dibedakan dari
   * "memang tidak ada data" — persis yang dilarang lampiran audit ("jangan
   * menutupi kegagalan"). Sekarang kegagalan dikumpulkan dan bisa ditampilkan.
   */
  errors: string[];
};

const KOSONG: DecisionDetail = {
  traces: [],
  chain: [],
  approvalSummary: null,
  supplierContext: null,
  decision: null,
  errors: [],
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
      // `allSettled` (bukan penelanan galat): panel tetap terbuka dengan
      // bagian yang berhasil, tetapi bagian yang gagal DICATAT dan dilaporkan.
      const [traces, chain, summary, supplier, keputusan] = await Promise.allSettled([
        fetchDecisionTraces(id, token as string),
        fetchDecisionChain(id, token as string),
        fetchApprovalSummary(id, token as string),
        fetchSupplierContext(id, token as string),
        fetchDecision(id, token as string),
      ]);
      const gagal: string[] = [];
      const nilai = <T,>(hasil: PromiseSettledResult<T>, label: string): T | null => {
        if (hasil.status === "fulfilled") return hasil.value;
        gagal.push(label);
        return null;
      };
      const jejak = nilai(traces, "jejak agen");
      const rantai = nilai(chain, "rantai audit");
      const ringkasan = nilai(summary, "ringkasan persetujuan");
      const konteks = nilai(supplier, "konteks pemasok");
      const detailKeputusan = nilai(keputusan, "detail keputusan");
      return {
        traces: jejak?.steps ?? [],
        chain: rantai?.chain ?? [],
        approvalSummary: ringkasan ?? null,
        supplierContext: konteks ?? null,
        decision: detailKeputusan ?? null,
        errors: gagal,
      };
    },
    enabled: Boolean(token) && Boolean(decisionId),
    // Poll ini yang menyegarkan approval_state saat pihak lain menyetujui.
    refetchInterval: DECISION_DETAIL_POLL_MS,
  });
  return query.data ?? KOSONG;
}
