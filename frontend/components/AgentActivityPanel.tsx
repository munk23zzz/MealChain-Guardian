"use client";

// AgentActivityPanel — modul Agent Activity (dokumen `06-agent-log.md`).
//
// Urutan isi mengikuti §4.3: kepala → tabel keputusan (pilih satu) → banner
// keadaan trace → strip sembilan tahap. Semua yang bergantung pada satu
// keputusan diletakkan SETELAH pemilihnya, supaya sepertiga layar tidak
// berbunyi "belum dimuat" sebelum pengguna memilih apa pun.
//
// Anak komponen: `DecisionAuditTable`, `AgentPipelinePanel`. Komponen konteks
// (kartu agent, status supervisor, status model, integritas) dirender halaman
// di bawah panel — lihat `app/page.tsx` tab `agent-log`.

import AgentPipelinePanel from "./AgentPipelinePanel";
import DecisionAuditTable from "./DecisionAuditTable";
import type { AuditDecision } from "../lib/decision-table";
import type { LedgerBlockView, TraceStep } from "../lib/agent-activity";

const KALIMAT_PERAN: Record<string, string> = {
  sppg_head:
    "Telusuri langkah yang dijalankan agent untuk satu keputusan, beserta asal datanya.",
  sppg_nutritionist:
    "Periksa langkah agent yang menyangkut keselamatan dan verifikasi keputusan.",
  bgn_monitor:
    "Jejak kerja agent lintas keputusan untuk keperluan audit (baca-saja).",
};

export function kalimatPeran(role: string | null | undefined): string {
  return (
    KALIMAT_PERAN[role ?? ""] ??
    "Jejak langkah agent untuk satu keputusan, apa adanya dari trace."
  );
}

export default function AgentActivityPanel({
  role = null,
  decisions,
  total,
  page,
  onPage,
  selectedId,
  onSelect,
  summary,
  steps,
  ledger,
  onOpenEvidence = null,
}: {
  role?: string | null;
  decisions: ReadonlyArray<AuditDecision>;
  total: number;
  page: number;
  onPage: (page: number) => void;
  selectedId: string | null;
  onSelect: (decisionId: string) => void;
  summary: string;
  /** `null` = trace belum dimuat. `[]` = backend menjawab kosong. */
  steps: TraceStep[] | null;
  /** `null` = blok ledger belum dimuat. */
  ledger: LedgerBlockView[] | null;
  onOpenEvidence?: (() => void) | null;
}) {
  return (
    <section className="agent-activity" aria-label="Agent Activity">
      <header className="aa-head">
        <div>
          <h2>Agent Activity</h2>
          <p className="aa-sub">{kalimatPeran(role)}</p>
        </div>
      </header>

      <DecisionAuditTable
        rows={decisions}
        total={total}
        page={page}
        onPage={onPage}
        selectedId={selectedId}
        onSelect={onSelect}
        summary={summary}
      />

      <AgentPipelinePanel
        decisionId={selectedId}
        steps={steps}
        ledger={ledger}
        onOpenEvidence={onOpenEvidence}
      />
    </section>
  );
}
