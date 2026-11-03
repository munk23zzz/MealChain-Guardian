"use client";

// Halaman gabungan "KPI & Kualitas Agen" (keputusan pemilik 2026-10-15).
//
// Dua tab lama — "KPI" dan "Kualitas Agen" — menjawab dua sisi pertanyaan yang
// sama: KPI = HASIL (tujuh indikator kontinuitas pangan, dihitung backend),
// Kualitas Agen = CARA (mutu kerja agen pada sampel keputusan terakhir).
// Pemilik memutuskan keduanya disatukan dalam satu tab, urutan **KPI dulu lalu
// mutu agen**, dengan "Rincian per run" tetap tampil penuh (tanpa pelipatan).
//
// Komponen ini SENGAJA tipis: ia tidak menghitung apa pun. Isi kedua bagian tetap
// milik `KPIDashboard` dan `AgentQualityBoard` (tidak diubah), sehingga angka di
// layar tidak bisa berbeda dari sebelum penggabungan. Yang diatur di sini hanya
// urutan + jarak antar-bagian, plus satu pembatas berjudul supaya pembaca tahu
// bagian mana yang sedang dilihat.
//
// Kemandirian galat: tiap bagian menerima loading/error-nya SENDIRI. KPI gagal
// tidak mematikan tabel mutu agen, dan sebaliknya — itu diuji di
// tests/kpi-quality-board.test.tsx (bagian kedua tanpa data tetap merender).

import AgentQualityBoard from "./AgentQualityBoard";
import KPIDashboard, { DESKRIPSI_HALAMAN } from "./KPIDashboard";
import PageShell from "./PageShell";
import PerformanceAuditPanel from "./PerformanceAuditPanel";
import type { QualityRun } from "../lib/agent-quality";
import type { KpiWindowKey } from "../lib/kpi";
import type { KpiScope } from "../lib/kpi-provenance";
import { PERF_AUDIT_SECTION_IDS, perfAuditSections } from "../lib/section-jump";

export default function KpiQualityBoard({
  kpi,
  kpiLoading = false,
  kpiError = null,
  onRetryKpi,
  windowKey,
  onWindowChange,
  scope,
  onScopeChange,
  scopeDisabledReason,
  runs,
  evaluatedCount,
  totalDecisions,
  qualityLoading = false,
  qualityError = null,
  onRetryQuality,
  onOpenDecision,
}: {
  /** Payload `GET /kpi` (amplop dari backend) atau null bila belum dimuat. */
  kpi: any | null;
  kpiLoading?: boolean;
  kpiError?: string | null;
  onRetryKpi?: () => void;
  /** Jendela KPI yang sedang diminta halaman + pengubahnya (pemilih periode). */
  windowKey?: KpiWindowKey;
  onWindowChange?: (key: KpiWindowKey) => void;
  /** Cakupan data KPI (fakta kerja vs sesi demo) + pengubahnya. */
  scope?: KpiScope;
  onScopeChange?: (scope: KpiScope) => void;
  scopeDisabledReason?: string | null;
  /** Sampel keputusan untuk penilaian mutu agen (8 terakhir dalam cakupan). */
  runs: QualityRun[];
  evaluatedCount: number;
  totalDecisions: number;
  qualityLoading?: boolean;
  qualityError?: string | null;
  onRetryQuality?: () => void;
  onOpenDecision?: (decisionId: string) => void;
}) {
  return (
    <PageShell
      className="kpi-quality-page"
      title="Performance & Audit"
      description={DESKRIPSI_HALAMAN}
      sections={perfAuditSections()}
      jumpAriaLabel="Bagian halaman Performance & Audit"
      meta={
        <span className="page-header-pills">
          {/* Pil kepala = JUMLAH, bukan ulangan kontrol: periode & cakupan sudah
              punya bilah kendali sendiri di dalam halaman. */}
          <span className="commodity-pill">
            {Array.isArray(kpi?.metrics) ? `${kpi.metrics.length} metrik` : "metrik —"}
          </span>
          <span className="commodity-pill">
            {Array.isArray(runs) ? `${runs.length} run dinilai` : "run —"}
          </span>
        </span>
      }
    >
      <section
        className="pa-section"
        id={PERF_AUDIT_SECTION_IDS.hasil}
        aria-labelledby="pa-hasil-judul"
      >
        <h2 className="pa-section-title" id="pa-hasil-judul">
          Hasil KPI
        </h2>
        <KPIDashboard
          kpi={kpi}
          loading={kpiLoading}
          error={kpiError}
          onRetry={onRetryKpi}
          windowKey={windowKey}
          onWindowChange={onWindowChange}
          scope={scope}
          onScopeChange={onScopeChange}
          scopeDisabledReason={scopeDisabledReason}
          showHeader={false}
        />
      </section>

      <section
        className="pa-section"
        id={PERF_AUDIT_SECTION_IDS.audit}
        aria-labelledby="pa-audit-judul"
      >
        <h2 className="pa-section-title" id="pa-audit-judul">
          Audit perhitungan
        </h2>
        {/* Panel audit membaca amplop yang SAMA dengan kartu di atasnya, jadi
            angkanya tidak mungkin berbeda dari kartu. */}
        <PerformanceAuditPanel kpi={kpi} windowKey={windowKey} />
      </section>

      {/* Judul "Mutu agen" menggantikan <hr class="kpi-quality-divider"> yang
          dulu memisahkan dua gulungan panjang (dibuang di Tahap 1: pemisah
          bagian adalah hierarki judul, bukan garis ornamen). */}
      <section
        className="pa-section"
        id={PERF_AUDIT_SECTION_IDS.mutu}
        aria-labelledby="pa-mutu-judul"
      >
        <h2 className="pa-section-title" id="pa-mutu-judul">
          Mutu agen
        </h2>
        <AgentQualityBoard
          runs={runs}
          evaluatedCount={evaluatedCount}
          totalDecisions={totalDecisions}
          loading={qualityLoading}
          error={qualityError}
          onRetry={onRetryQuality}
          onOpenDecision={onOpenDecision}
        />
      </section>
    </PageShell>
  );
}
