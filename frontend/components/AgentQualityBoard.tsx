"use client";

// Halaman "Kualitas Agen" — halaman sidebar acuan /quality (di acuan memakai
// MOCK_AGENT_RUNS), disesuaikan ke data nyata repo ini:
// jejak agen (/decisions/{id}/traces) + putusan verifikator (approval-summary).

import PageHeader from "./PageHeader";
import FactList from "./FactList";
import {
  AGENT_QUALITY_METHOD_NOTE,
  VERDICT_LABEL,
  averageLabel,
  percentLabel,
  qualityMetrics,
  type QualityRun,
} from "../lib/agent-quality";

export default function AgentQualityBoard({
  runs,
  evaluatedCount,
  totalDecisions,
  loading = false,
  error = null,
  onRetry,
  onOpenDecision,
}: {
  runs: QualityRun[];
  evaluatedCount: number;
  totalDecisions: number;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onOpenDecision?: (decisionId: string) => void;
}) {
  const metrics = qualityMetrics(runs);

  return (
    <section className="board-page">
      <PageHeader
        title="Kualitas Agen"
        description="Seberapa baik rantai agen bekerja pada keputusan terakhir cakupan Anda: langkah yang diambil, kesesuaian dengan verifikator, dan berapa yang akhirnya diubah manusia."
        meta={
          <span className="page-header-pills">
            <span className="commodity-pill">{metrics.runs} run dinilai</span>
            <span className="commodity-pill">
              dari {totalDecisions} keputusan dalam cakupan
            </span>
          </span>
        }
      />

      {error ? (
        <article className="card">
          <h2>Tidak bisa memuat jejak agen</h2>
          <p className="evidence-note">{error}</p>
          {onRetry ? (
            <button type="button" className="button button-secondary" onClick={onRetry}>
              Coba lagi
            </button>
          ) : null}
        </article>
      ) : null}

      <div className="board-grid board-grid-2">
        <article className="card">
          <h2>Skor agregat</h2>
          <FactList
            rows={[
              { label: "Run dinilai", value: loading && !runs.length ? "…" : String(metrics.runs) },
              { label: "Total langkah", value: metrics.totalSteps === null ? "—" : String(metrics.totalSteps) },
              { label: "Langkah per run", value: averageLabel(metrics.avgSteps) },
              {
                label: "Kesesuaian verifier",
                value: percentLabel(metrics.agreementRate),
                tone: metrics.agreementRate === null ? "plain" : metrics.agreementRate >= 80 ? "ok" : "warn",
                hint: metrics.judged ? `${metrics.agree} dari ${metrics.judged} yang dinilai` : "belum ada penilaian verifikator",
              },
              { label: "Setuju", value: String(metrics.agree), tone: "ok" },
              { label: "Tidak setuju", value: String(metrics.disagree), tone: metrics.disagree ? "danger" : "plain" },
              { label: "Tidak tersedia", value: String(metrics.unavailable), tone: metrics.unavailable ? "warn" : "plain" },
              {
                label: "Tingkat fallback",
                value: percentLabel(metrics.fallbackRate),
                hint: `${metrics.totalFallbacks} langkah`,
              },
              {
                label: "Diubah manusia",
                value: percentLabel(metrics.humanChangedRate),
                hint: `${metrics.humanChanged} keputusan sudah pernah ditolak`,
              },
              { label: "Rata-rata durasi", value: metrics.avgDurationLabel },
            ]}
          />
        </article>

        <article className="card">
          <h2>Cara kami menilai</h2>
          <p className="evidence-note">{AGENT_QUALITY_METHOD_NOTE}</p>
          <p className="evidence-note">
            Yang dinilai hanya {evaluatedCount} keputusan terakhir dalam cakupan Anda — bukan seluruh
            riwayat — supaya halaman tetap cepat dan angkanya bisa ditelusuri.
          </p>
        </article>
      </div>

      <article className="card">
        <h2>Rincian per run</h2>
        {runs.length === 0 ? (
          <p className="evidence-note">
            {loading ? "Memuat jejak agen…" : "Belum ada run agen yang tercatat untuk keputusan dalam cakupan ini."}
          </p>
        ) : (
          <>
              <div className="board-table-wrap">
              <table className="location-table">
            <thead>
              <tr>
                <th scope="col">Keputusan</th>
                <th scope="col">ID</th>
                <th scope="col">Status</th>
                <th scope="col" className="num">
                  Langkah
                </th>
                <th scope="col">Alat dipakai</th>
                <th scope="col">Verifikator</th>
                <th scope="col" className="num">
                  Durasi
                </th>
                <th scope="col">Iterasi</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id || run.shortId}>
                  <td>
                    {onOpenDecision && run.id ? (
                      <button
                        type="button"
                        className="board-link"
                        onClick={() => onOpenDecision(run.id)}
                      >
                        {run.type.replace(/_/g, " ")}
                      </button>
                    ) : (
                      run.type.replace(/_/g, " ")
                    )}
                  </td>
                  <td>
                    <code>{run.shortId}</code>
                  </td>
                  <td>{run.status.replace(/_/g, " ")}</td>
                  <td className="num">{run.steps === null ? "—" : run.steps}</td>
                  <td>{run.tools.length ? run.tools.join(", ") : "—"}</td>
                  <td
                    className={
                      run.verdict === "agree"
                        ? "fact-ok"
                        : run.verdict === "disagree"
                          ? "fact-danger"
                          : "fact-muted"
                    }
                  >
                    {VERDICT_LABEL[run.verdict]}
                  </td>
                  <td className="num">{run.durationLabel}</td>
                  <td className="num">{run.iteration === null ? "—" : run.iteration}</td>
                </tr>
              ))}
            </tbody>
          </table>
            </div>
            <p className="board-scroll-hint">Geser tabel ke samping untuk melihat kolom lain.</p>
              </>
        )}
      </article>
    </section>
  );
}
