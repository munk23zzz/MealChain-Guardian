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

import {
  fetchApprovalSummary,
  fetchDecision,
  fetchDecisionChain,
  fetchDecisionLedger,
  fetchDecisionTraces,
} from "../api";
import { queryKeys } from "../query";
import { fetchSupplierContext, type SupplierContext } from "../supplier-exclusions";

export const DECISION_DETAIL_POLL_MS = 5_000;

export type DecisionDetail = {
  traces: any[];
  /**
   * Blok ledger keputusan ini (`GET /decisions/{id}/ledger`).
   *
   * `null` = belum dimuat atau gagal dibaca; `[]` = backend menjawab "tidak
   * ada blok". Dua hal itu berbeda: dokumen 06 melarang menampilkan ACT
   * sebagai "belum tercatat" bila bloknya ada, dan melarang menebak saat
   * datanya belum datang.
   */
  ledger: { height: number; action: string; created_at: string }[] | null;
  /** Trace belum dimuat (bukan "tidak ada trace") — dipakai banner 3 keadaan. */
  loading: boolean;
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
  /**
   * `true` bila `GET /decisions/{id}` menjawab 404 — barisnya tidak ada lagi
   * (biasanya karena "Muat Demo" mengganti baris operasional). 403 TIDAK
   * dihitung: itu masalah cakupan peran, bukan baris yang hilang.
   */
  gone: boolean;
};

const KOSONG: DecisionDetail = {
  traces: [],
  ledger: null,
  loading: true,
  chain: [],
  approvalSummary: null,
  supplierContext: null,
  decision: null,
  errors: [],
  gone: false,
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
      const [traces, chain, summary, supplier, keputusan, blok] =
        await Promise.allSettled([
          fetchDecisionTraces(id, token as string),
          fetchDecisionChain(id, token as string),
          fetchApprovalSummary(id, token as string),
          fetchSupplierContext(id, token as string),
          fetchDecision(id, token as string),
          fetchDecisionLedger(id, token as string),
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
      const ledger = nilai(blok, "blok ledger ACT");
      // Bedakan "baris sudah tidak ada" (404) dari "di luar cakupan" (403).
      // Sebelumnya semua galat disimpan sebagai label teks, sehingga 404
      // tampil sebagai "Sebagian bukti gagal dibaca" dan URL terus menunjuk
      // id mati sambil memanggil 5 endpoint tiap 5 detik (terukur 88 × 404
      // pada log backend, satu id dipanggil berjam-jam).
      const kode =
        keputusan.status === "rejected"
          ? (keputusan.reason as { status?: number } | null)?.status
          : undefined;
      const gone = kode === 404;
      return {
        traces: jejak?.steps ?? [],
        // `null` saat gagal: panel harus bisa menulis "belum dimuat", bukan
        // "tidak ada blok" (invarian 2 dokumen 06).
        ledger: Array.isArray(ledger?.blocks)
          ? (ledger!.blocks as { height: number; action: string; created_at: string }[])
          : null,
        loading: false,
        chain: rantai?.chain ?? [],
        approvalSummary: ringkasan ?? null,
        supplierContext: konteks ?? null,
        decision: detailKeputusan ?? null,
        errors: gagal,
        gone,
      };
    },
    enabled: Boolean(token) && Boolean(decisionId),
    // Poll ini yang menyegarkan approval_state saat pihak lain menyetujui.
    // Id yang sudah mati tidak boleh dipoll selamanya.
    refetchInterval: (query) =>
      query.state.data?.gone ? false : DECISION_DETAIL_POLL_MS,
  });
  if (query.data) return query.data;
  // Sebelum jawaban pertama tiba, `loading` harus jujur `true` supaya banner
  // menulis "Trace belum dimuat" — dulu `[]` membuatnya tampak "tidak ada".
  return { ...KOSONG, loading: true };
}
