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
import KPIDashboard from "./KPIDashboard";
import type { QualityRun } from "../lib/agent-quality";

export default function KpiQualityBoard({
  kpi,
  kpiLoading = false,
  kpiError = null,
  onRetryKpi,
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
    <section className="kpi-quality-page" aria-label="KPI dan Kualitas Agen">
      <KPIDashboard
        kpi={kpi}
        loading={kpiLoading}
        error={kpiError}
        onRetry={onRetryKpi}
      />
      {/* Pembatas bergaris: dua bagian panjang dalam satu gulungan tanpa
          penanda mudah terbaca sebagai satu tabel raksasa. */}
      <hr className="kpi-quality-divider" />
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
  );
}
