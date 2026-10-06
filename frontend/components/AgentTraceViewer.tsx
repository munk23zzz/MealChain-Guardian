// AgentTraceViewer — activity log dari trace AKTUAL (design.md §3.4).
// Data ditarik dari GET /decisions/{id}/traces (AgentTrace DB), bukan
// log buatan. Timestamp ditampilkan UTC agar bisa dibandingkan lintas hop.

export default function AgentTraceViewer({ steps }: { steps: any[] }) {
  if (!steps || steps.length === 0) {
    return (
      <p className="empty-state">
        Belum ada langkah agent yang tercatat untuk keputusan ini.
      </p>
    );
  }
  return (
    <ol className="trace-timeline">
      {steps.map((s: any, i: number) => (
        <li key={i} className={`trace-step step-${s.step_name}`}>
          <div className="trace-step-name">{s.step_name}</div>
          <div className="trace-tool">{s.tool_called ?? "-"}</div>
          <time>{new Date(s.step_at).toISOString().slice(11, 19)} UTC</time>
          <pre className="trace-output">
            {JSON.stringify(s.output_summary ?? {})}
          </pre>
        </li>
      ))}
    </ol>
  );
}
