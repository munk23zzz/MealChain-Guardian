// AgentTraceViewer — activity log dari trace AKTUAL (design.md §3.4).
// Data ditarik dari GET /decisions/{id}/traces (AgentTrace DB), bukan
// log buatan. Timestamp ditampilkan UTC agar bisa dibandingkan lintas hop.
// Restyle Stitch: console terminal gelap (#0F172A) + accent #2DD4BF.

import { formatClockUtc } from "../lib/datetime";

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

export default function AgentTraceViewer({ steps }: { steps: any[] }) {
  if (!steps || steps.length === 0) {
    return (
      <p className="empty-state">
        Belum ada langkah agent yang tercatat untuk keputusan ini.
      </p>
    );
  }
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
      </div>
      <ol className="trace-timeline">
        {steps.map((s: any, i: number) => (
          <li key={i} className={`trace-step step-${s.step_name}`}>
            <div className="trace-step-head">
              <StepIcon done={true} />
              <div className="trace-step-name">{s.step_name}</div>
              <time>{formatClockUtc(s.step_at)} UTC</time>
            </div>
            <div className="trace-tool">{s.tool_called ?? "-"}</div>
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
        ))}
      </ol>
    </div>
  );
}
