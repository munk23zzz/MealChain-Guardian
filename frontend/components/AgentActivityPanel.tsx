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
import AgentExecutionSummary from "./AgentExecutionSummary";
import DecisionAuditTable from "./DecisionAuditTable";
import { buildPipeline, pipelineCaveat, pipelineSummary } from "../lib/agent-activity";
import type { AuditDecision } from "../lib/decision-table";
import type { ExecutionOverview } from "../lib/agent-execution";
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
  overview = null,
  periodLabel = null,
  now = null,
  loading = false,
  onOpenEvidence = null,
  stageFilter = null,
  onStageFilter = null,
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
  /** Ringkasan eksekusi dari daftar keputusan; `null` = tidak ditampilkan. */
  overview?: ExecutionOverview | null;
  periodLabel?: string | null;
  /** Jam acuan untuk penanda "lewat tenggat" di tabel. */
  now?: Date | null;
  /** Daftar keputusan masih dimuat. */
  loading?: boolean;
  onOpenEvidence?: (() => void) | null;
  /** Tahap yang sedang disaring (Tahap 4 redesign); `null` = semua langkah. */
  stageFilter?: string | null;
  onStageFilter?: ((code: string | null) => void) | null;
}) {
  // Ringkasan "3 dari 10 tahap punya jejak" pindah ke KANAN header (Tahap 4):
  // angkanya menerangkan seluruh panel, jadi tempatnya di kepala panel, bukan
  // baris baru di atas strip yang mendorong semuanya turun.
  const tahap = buildPipeline({ steps, ledger });
  const ringkas = pipelineSummary(tahap);
  const caveat = pipelineCaveat(tahap);

  return (
    <section className="agent-activity" aria-label="Agent Activity">
      <header className="aa-head">
        <div className="aa-head-main">
          {/* Label modul, bukan judul kedua: halaman sudah punya h1 "Agent
              Activity Log" (20 px). Sebelumnya h2 18 px duduk 10 px di bawahnya
              sehingga dua judul besar bersaing di satu layar. */}
          <h2 className="aa-kicker">Agent Activity</h2>
          <p className="aa-sub" title={kalimatPeran(role)}>
            {kalimatPeran(role)}
          </p>
        </div>
        {steps !== null ? (
          <p className="aa-summary aa-head-sum" role="status" aria-atomic="true" title={caveat}>
            {ringkas}
          </p>
        ) : null}
      </header>

      {overview ? (
        <AgentExecutionSummary
          overview={overview}
          periodLabel={periodLabel}
          loading={loading}
        />
      ) : null}

      <DecisionAuditTable
        rows={decisions}
        total={total}
        page={page}
        onPage={onPage}
        selectedId={selectedId}
        onSelect={onSelect}
        summary={summary}
        now={now}
      />

      <AgentPipelinePanel
        decisionId={selectedId}
        steps={steps}
        ledger={ledger}
        onOpenEvidence={onOpenEvidence}
        stageFilter={stageFilter}
        onStageFilter={onStageFilter}
      />
    </section>
  );
}
