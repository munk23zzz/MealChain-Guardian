// AgentTraceViewer — activity log dari trace AKTUAL (design.md §3.4).
// Data ditarik dari GET /decisions/{id}/traces (AgentTrace DB), bukan
// log buatan. Timestamp ditampilkan UTC agar bisa dibandingkan lintas hop.
// Restyle Stitch: console terminal gelap (#0F172A) + accent #2DD4BF.

import { formatClockUtc } from "../lib/datetime";
import {
  isNewStep,
  isRunningStep,
  stepAgeLabel,
  stepDurationLabel,
} from "../lib/agent-trace";

// Icon status langkah — inline SVG, bukan emoji (DESIGN.md).
function StepIcon({ done }: { done?: boolean }) {
  return done ? (
    <svg className="agent-console-ico" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
      <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M4.5 8.5l2.2 2.2L11 6" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg className="agent-console-ico" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
      <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="8" cy="8" r="2" fill="currentColor" />
    </svg>
  );
}

export default function AgentTraceViewer({
  steps,
  decisionId = null,
  now = null,
}: {
  steps: any[];
  /** Keputusan yang sedang dipilih; null = belum ada yang dipilih. */
  decisionId?: string | null;
  /** Jam klien (pola yang sama dengan halaman lain): dipakai HANYA untuk umur
   *  langkah. null = jam belum siap → umur tidak diklaim, jejaknya tetap utuh. */
  now?: Date | null;
}) {
  if (!steps || steps.length === 0) {
    // Dua keadaan yang BERBEDA, dua pesan yang berbeda (WS-C, QA 16 Okt).
    // Dulu satu pesan untuk keduanya: sebelum pengguna memilih apa pun, layar
    // sudah mengklaim "belum ada langkah agent ... untuk keputusan ini" —
    // seolah ada keputusan yang dipilih dan jejaknya hilang.
    return (
      <p className="empty-state">
        {decisionId
          ? "Belum ada langkah agent yang tercatat untuk keputusan ini."
          : "Pilih keputusan dulu untuk melihat jejak langkah agent."}
      </p>
    );
  }
  const last = steps[steps.length - 1];
  const umur = stepAgeLabel(last?.step_at, now);
  const adaYangBaru = Boolean(umur) && Boolean(isNewStep(last?.step_at, now));
  return (
    <div className="agent-console">
      {/* Chrome ala jendela terminal Stitch (agent_activity_log_traces) */}
      <div className="agent-console-bar">
        <span className="agent-console-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span className="agent-console-title">agent-core@mealchain:~ — trace log</span>
        {/* Umur langkah terakhir — fakta waktu dari step_at, bukan klaim bahwa
            agen masih bekerja (itu hanya boleh datang dari data langkahnya). */}
        {umur ? (
          <span className="agent-console-age" data-live={adaYangBaru ? "true" : undefined}>
            <span className="agent-console-age-dot" aria-hidden="true" />
            {umur}
          </span>
        ) : null}
      </div>
      <ol className="trace-timeline">
        {steps.map((s: any, i: number) => {
          const berjalan = isRunningStep(s);
          const baru =
            !berjalan && i === steps.length - 1 && isNewStep(s.step_at, now);
          const durasi = stepDurationLabel(s);
          return (
            <li
              key={i}
              className={`trace-step step-${s.step_name}`}
              data-state={berjalan ? "berjalan" : baru ? "baru" : "selesai"}
            >
              <span className="trace-dot" aria-hidden="true" />
              <div className="trace-step-head">
                <StepIcon done={!berjalan} />
                <div className="trace-step-name">{s.step_name}</div>
                {berjalan ? (
                  <span className="trace-chip trace-chip-running">sedang berjalan</span>
                ) : baru ? (
                  <span className="trace-chip trace-chip-new">baru masuk</span>
                ) : null}
                {durasi ? <span className="trace-duration">{durasi}</span> : null}
                <time>{formatClockUtc(s.step_at)} UTC</time>
              </div>
              <div className="trace-tool">{s.tool_called ?? "-"}</div>
              {/* W-5: nomor PO yang diterbitkan langkah ACT. Sebelumnya hanya
                  nama tool yang tampil, sehingga PO yang terbit tidak bisa
                  ditunjukkan dari jejak agent. */}
              {s.step_name === "ACT" && s.output_summary?.po_number ? (
                <div className="trace-po">
                  PO {s.output_summary.po_number} diterbitkan (mock SAP)
                </div>
              ) : null}
              {s.step_name === "SUPERVISE" &&
                s.output_summary?.provider && (
                  <div className="trace-model">
                    Model: {s.output_summary.provider}
                  </div>
                )}
              <pre className="trace-output">
                {JSON.stringify(s.output_summary ?? {})}
              </pre>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
