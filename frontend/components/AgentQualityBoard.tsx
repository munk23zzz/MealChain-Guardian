"use client";

// Halaman "Kualitas Agen" — halaman sidebar acuan /quality (di acuan memakai
// MOCK_AGENT_RUNS), disesuaikan ke data nyata repo ini:
// jejak agen (/decisions/{id}/traces) + putusan verifikator (approval-summary).
//
// Restyle UI/UX: skor agregat kini strip kartu metrik (label kecil + angka besar
// + meter bergaya kartu KPI), putusan verifikator jadi satu bar bertumpuk dengan
// legenda berlabel (bukan warna saja), dan tabel per run memakai lencana status/
// putusan + chip alat. Kontrak INFORMASI tidak berubah: angka tetap dari
// lib/agent-quality, "—" tetap "—" (bukan 0), dan cakupan sampel ditulis apa adanya.

import type { ReactNode } from "react";

import PageHeader from "./PageHeader";
import {
  VERDICT_LABEL,
  agentQuality,
  averageLabel,
  percentLabel,
  qualityMetrics,
  type AgentQualityRow,
  type QualityRun,
  type QualityVerdict,
} from "../lib/agent-quality";
import { LoadingState } from "./LoadingState";
import ScrollHint from "./ScrollHint";
import { toolLabel } from "../lib/bahasa";

const DASH = "—";

/** Kata status dari backend apa adanya → tone lencana. Kata statusnya tidak diubah. */
function statusTone(status: string): "ok" | "warn" | "hard" | "danger" | "muted" {
  const s = status.toLowerCase();
  // Empat tingkat (17 Okt): ditolak/gagal = kritis (merah), "flagged" = berat
  // (oranye) — sebelumnya keduanya merah sehingga berat tak terbedakan.
  if (s.includes("reject") || s.includes("fail")) return "danger";
  if (s.includes("flagged")) return "hard";
  if (s.includes("pending") || s.includes("proposed") || s.includes("await")) return "warn";
  if (
    s.includes("approv") ||
    s.includes("execut") ||
    s.includes("complet") ||
    s.includes("done")
  ) {
    return "ok";
  }
  return "muted";
}

const VERDICT_TONE: Record<QualityVerdict, "ok" | "danger" | "muted"> = {
  agree: "ok",
  disagree: "danger",
  unavailable: "muted",
};

/** Peran agen: worker (tujuh analitik), supervisor, verifier (audit). */
const ROLE_LABEL: Record<AgentQualityRow["role"], string> = {
  worker: "Worker",
  supervisor: "Supervisor",
  verifier: "Verifier",
};

const ROLE_TONE: Record<AgentQualityRow["role"], "muted" | "ok"> = {
  worker: "muted",
  // Supervisor & verifier diberi nada sama dengan agen lain yang berjalan —
  // keduanya kelas satu, bukan lampiran.
  supervisor: "ok",
  verifier: "ok",
};

/** Lebar batang hanya untuk angka 0–100; null → 0 (tanpa klaim). */
function shareOf(value: number | null): number {
  if (value === null || !Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, value));
}

/** Persen legenda: satu desimal HANYA bila perlu, supaya jumlah bagian tetap
 *  100% (tiga angka yang dibulatkan sendiri-sendiri bisa berjumlah 101%). */
function shareLabel(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return `${Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)}%`;
}

/** Ikon kartu metrik — inline SVG (pola sama seperti ikon KPI), tanpa dependensi. */
const GLYPHS: Record<string, ReactNode> = {
  runs: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 4v6" />
    </>
  ),
  steps: (
    <>
      <path d="M5 18h3M11 12h3M17 6h3" />
      <circle cx="6" cy="18" r="1.7" />
      <circle cx="12" cy="12" r="1.7" />
      <circle cx="18" cy="6" r="1.7" />
    </>
  ),
  verdict: (
    <>
      <path d="M12 3l7 3v5c0 4.4-3 8.2-7 10-4-1.8-7-5.6-7-10V6l7-3Z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
  fallback: (
    <>
      <path d="M20 11a8 8 0 0 0-13.7-5.3L4 8" />
      <path d="M4 4v4h4" />
      <path d="M4 13a8 8 0 0 0 13.7 5.3L20 16" />
      <path d="M20 20v-4h-4" />
    </>
  ),
  human: (
    <>
      <path d="M16 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 18.5V20" />
      <circle cx="10" cy="8" r="3" />
      <path d="M17 11.5l1.8 1.8L22 10" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4.5l3 2" />
    </>
  ),
};

function StatIcon({ name }: { name: keyof typeof GLYPHS }) {
  return (
    <span className="quality-stat-icon" aria-hidden="true">
      <svg
        viewBox="0 0 24 24"
        width="17"
        height="17"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {GLYPHS[name]}
      </svg>
    </span>
  );
}

function StatCard({
  label,
  value,
  hint,
  meter,
  tone = "plain",
  icon,
  hero = false,
}: {
  label: string;
  value: string;
  hint?: ReactNode;
  /** Angka 0–100 yang menggambar meter; undefined = kartu tanpa meter. */
  meter?: number | null;
  tone?: "plain" | "ok" | "warn" | "danger";
  icon: keyof typeof GLYPHS;
  hero?: boolean;
}) {
  return (
    <article
      className={`quality-stat${hero ? " quality-stat-hero" : ""}`}
      data-tone={tone}
      data-meter={meter === undefined ? undefined : Math.round(shareOf(meter))}
    >
      <div className="quality-stat-head">
        <span className="quality-stat-label">{label}</span>
        <StatIcon name={icon} />
      </div>
      <p className="quality-stat-value">{value}</p>
      {meter === undefined ? null : (
        <div className="quality-meter" aria-hidden="true">
          <span
            className={`quality-meter-fill quality-meter-${tone}`}
            style={{ width: `${shareOf(meter)}%` }}
          />
        </div>
      )}
      {hint ? <p className="quality-stat-hint">{hint}</p> : null}
    </article>
  );
}

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
  const perAgent = agentQuality(runs);
  const waiting = loading && !runs.length;
  const value = (text: string) => (waiting ? "…" : text);
  const maxSteps = runs.reduce((max, run) => Math.max(max, run.steps ?? 0), 0);
  const total = metrics.runs;

  // Komposisi dihitung dari SEMUA run (bukan hanya yang dinilai) supaya bagian
  // "tidak tersedia" terlihat sebagai bagian komposisi, bukan disembunyikan.
  const segments: Array<{ key: QualityVerdict; count: number; tone: string }> = [
    { key: "agree", count: metrics.agree, tone: "ok" },
    { key: "disagree", count: metrics.disagree, tone: "danger" },
    { key: "unavailable", count: metrics.unavailable, tone: "muted" },
  ];
  const agreementTone =
    metrics.agreementRate === null ? "plain" : metrics.agreementRate >= 80 ? "ok" : "warn";

  return (
    <section className="board-page" aria-busy={loading || undefined}>
      <PageHeader
        level={2}
        title="Kualitas Agen"
        description="Mutu kerja agen pada keputusan terakhir cakupan Anda: langkah, kesesuaian verifikator, dan yang diubah manusia."
        meta={
          <span className="page-header-pills">
            <span className="commodity-pill">{metrics.runs} run dinilai</span>
            <span className="commodity-pill">dari {totalDecisions} keputusan dalam cakupan</span>
          </span>
        }
      />

      {error ? (
        <article className="card quality-error">
          <h3>Tidak bisa memuat jejak agen</h3>
          <p className="evidence-note">{error}</p>
          {onRetry ? (
            <button type="button" className="button button-secondary" onClick={onRetry}>
              Coba lagi
            </button>
          ) : null}
        </article>
      ) : null}

      <section className="quality-section" aria-labelledby="quality-score-title">
        <div className="quality-section-head">
          <h3 id="quality-score-title">Skor agregat</h3>
          <p className="quality-section-sub">
            {metrics.runs} run ·{" "}
            {metrics.totalSteps === null ? DASH : metrics.totalSteps} langkah tercatat
          </p>
        </div>

        <div className="quality-stats">
          <StatCard
            label="Run dinilai"
            value={value(String(metrics.runs))}
            icon="runs"
            hint={`dari ${totalDecisions} keputusan dalam cakupan`}
          />
          <StatCard
            label="Langkah per run"
            value={value(averageLabel(metrics.avgSteps))}
            icon="steps"
            hint={
              metrics.totalSteps === null
                ? "belum ada langkah tercatat"
                : `total ${metrics.totalSteps} langkah`
            }
          />
          <StatCard
            label="Kesesuaian verifier"
            value={value(percentLabel(metrics.agreementRate))}
            meter={metrics.agreementRate}
            tone={agreementTone}
            icon="verdict"
            hero
            hint={
              metrics.judged
                ? `${metrics.agree} dari ${metrics.judged} yang dinilai`
                : "belum ada penilaian verifikator"
            }
          />
          <StatCard
            label="Tingkat fallback"
            value={value(percentLabel(metrics.fallbackRate))}
            meter={metrics.fallbackRate}
            tone={metrics.totalFallbacks ? "warn" : "plain"}
            icon="fallback"
            hint={`${metrics.totalFallbacks} langkah memakai jalur cadangan`}
          />
          <StatCard
            label="Diubah manusia"
            value={value(percentLabel(metrics.humanChangedRate))}
            meter={metrics.humanChangedRate}
            tone={metrics.humanChanged ? "warn" : "plain"}
            icon="human"
            hint={`${metrics.humanChanged} keputusan sudah pernah ditolak`}
          />
          <StatCard
            label="Rata-rata durasi"
            value={value(metrics.avgDurationLabel)}
            icon="clock"
            hint="dari langkah pertama ke langkah terakhir"
          />
        </div>

        <p className="quality-coverage">
          <svg
            viewBox="0 0 24 24"
            width="15"
            height="15"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="9" />
            <path d="M12 11v5M12 8h.01" />
          </svg>
          <span>
            Yang dinilai hanya {evaluatedCount} keputusan terakhir dalam cakupan Anda — bukan
            seluruh riwayat.
          </span>
        </p>
      </section>

      <article className="card quality-verdict">
        <div className="card-header">
          <h3>Putusan verifikator</h3>
          <span className={`board-badge board-badge-${metrics.judged ? "ok" : "muted"}`}>
            {metrics.judged} dari {metrics.runs} run dinilai
          </span>
        </div>
        {/* Penjelasan "apa yang dihitung" dulu selalu terbentang di atas grafik.
            Judul kartu + angka + legenda sudah menyatakan hal yang sama, jadi
            kalimatnya dipindahkan ke lipatan satu klik. */}
        <details className="card-note-more">
          <summary>Cara membaca kartu ini</summary>
          <p className="evidence-note">
            Berapa run yang disetujui verifikator, ditandai berbeda, atau belum pernah dinilai sama
            sekali.
          </p>
        </details>
        <div
          className="quality-verdict-bar"
          data-empty={total === 0 ? "true" : undefined}
          role="img"
          aria-label={`Komposisi putusan verifikator: ${metrics.agree} setuju, ${metrics.disagree} tidak setuju, ${metrics.unavailable} tidak tersedia dari ${total} run.`}
        >
          {segments
            .filter((segment) => segment.count > 0)
            .map((segment) => (
              <span
                key={segment.key}
                className={`quality-verdict-seg quality-verdict-seg-${segment.tone}`}
                style={{ width: `${(segment.count / (total || 1)) * 100}%` }}
              />
            ))}
        </div>
        <ul className="quality-legend">
          {segments.map((segment) => (
            <li key={segment.key} className="quality-legend-item" data-verdict={segment.key}>
              <span
                className={`quality-legend-dot quality-legend-dot-${segment.tone}`}
                aria-hidden="true"
              />
              <span>{VERDICT_LABEL[segment.key]}</span>
              <span className="quality-legend-value">
                {segment.count} · {total ? shareLabel((segment.count / total) * 100) : DASH}
              </span>
            </li>
          ))}
        </ul>
      </article>

      {/* Kualitas per agen: supervisor & verifier ikut dihitung dari jejak nyata.
          Angka di sini adalah HITUNGAN run, bukan skor turunan. */}
      <article className="card quality-agents">
        <div className="card-header">
          <h3>Kualitas per agen</h3>
          {perAgent.length ? (
            <span className="board-badge board-badge-muted">{perAgent.length} agen</span>
          ) : null}
        </div>
        <details className="card-note-more">
          <summary>Cara membaca kartu ini</summary>
          <p className="evidence-note">
            Berapa run yang benar-benar memuat baris tiap agen — tujuh worker, supervisor, lalu
            verifier — dari {metrics.runs || evaluatedCount} keputusan yang dinilai. Putusan verifier
            dihitung dari ringkasan approval tiap run, jadi bisa mencakup run yang baris auditnya
            tidak tersimpan.
          </p>
        </details>
        {waiting ? (
          <LoadingState label="Memuat jejak agen…" />
        ) : perAgent.length === 0 ? (
          <p className="evidence-note">
            Belum ada run agen yang tercatat untuk keputusan dalam cakupan ini.
          </p>
        ) : (
          <>
            <div className="board-table-wrap">
              <table className="location-table quality-table">
                <thead>
                  <tr>
                    <th scope="col">Agen</th>
                    <th scope="col">Peran</th>
                    <th scope="col" className="num">
                      Tercatat
                    </th>
                    <th scope="col" className="num">
                      Ada keluaran
                    </th>
                    <th scope="col" className="num">
                      Tidak tercatat
                    </th>
                    <th scope="col">Putusan verifier</th>
                  </tr>
                </thead>
                <tbody>
                  {perAgent.map((row) => (
                    <tr key={row.key} data-agent={row.key} data-role={row.role}>
                      <td>{row.label}</td>
                      <td>
                        <span
                          className={`board-badge board-badge-${ROLE_TONE[row.role]}`}
                          data-role={row.role}
                        >
                          {ROLE_LABEL[row.role]}
                        </span>
                      </td>
                      <td className="num">
                        {row.recorded}/{row.runs}
                      </td>
                      <td className="num">{row.delivered}</td>
                      <td className="num">{row.missing}</td>
                      <td>{row.verdicts ? row.verdictNote : DASH}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ScrollHint />
          </>
        )}
      </article>

      <article className="card">
        <div className="card-header">
          <h3>Rincian per run</h3>
          {runs.length ? (
            <span className="board-badge board-badge-muted">{runs.length} baris</span>
          ) : null}
        </div>
        {runs.length === 0 ? (
          <p className="evidence-note">
            {loading ? (
              <LoadingState label="Memuat jejak agen…" />
            ) : (
              "Belum ada run agen yang tercatat untuk keputusan dalam cakupan ini."
            )}
          </p>
        ) : (
          <>
            <div className="board-table-wrap">
              <table className="location-table quality-table">
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
                    <th scope="col" className="num">
                      Iterasi
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id || run.shortId} data-verdict={run.verdict}>
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
                      <td>
                        <span
                          className={`board-badge board-badge-${statusTone(run.status)}`}
                          data-status-tone={statusTone(run.status)}
                        >
                          {run.status.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="num">
                        <span className="quality-steps">
                          <span>{run.steps === null ? DASH : run.steps}</span>
                          {run.steps !== null && maxSteps > 0 ? (
                            <span className="quality-steps-track" aria-hidden="true">
                              <span
                                className="quality-steps-bar"
                                style={{ width: `${(run.steps / maxSteps) * 100}%` }}
                              />
                            </span>
                          ) : null}
                        </span>
                      </td>
                      <td>
                        {run.tools.length ? (
                          <ul className="quality-tools">
                            {run.tools.map((tool) => (
                              <li key={tool} className="quality-chip" title={tool}>
                                {toolLabel(tool) ?? tool}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          DASH
                        )}
                        {run.fallbackSteps > 0 ? (
                          <span className="quality-chip quality-chip-warn">
                            langkah cadangan ×{run.fallbackSteps}
                          </span>
                        ) : null}
                      </td>
                      <td>
                        <span className={`board-badge board-badge-${VERDICT_TONE[run.verdict]}`}>
                          {VERDICT_LABEL[run.verdict]}
                        </span>
                      </td>
                      <td className="num">{run.durationLabel}</td>
                      <td className="num" data-changed={run.humanChanged ? "true" : undefined}>
                        {run.humanChanged ? (
                          <span className="board-badge board-badge-warn">
                            diubah {run.iteration}×
                          </span>
                        ) : run.iteration === null ? (
                          DASH
                        ) : (
                          run.iteration
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ScrollHint />
          </>
        )}
      </article>
    </section>
  );
}
