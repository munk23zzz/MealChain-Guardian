"use client";

// AgentRoster — dua kartu "agent yang bekerja" (dokumen 06 §2.2).
//
// Sumber tiap kartu ditulis apa adanya (`AGENTS`). Dasar pemisahan yang dibuat
// eksplisit di UI: angka safety-critical tetap dihitung tool deterministik, dan
// verifier tidak melihat penalaran supervisor — agent yang memeriksa dirinya
// sendiri bukan pengawasan.

import { AGENTS } from "../lib/agent-activity";

export default function AgentRoster() {
  return (
    <section className="aa-agents" aria-labelledby="aa-agents-title">
      <h3 id="aa-agents-title" className="aa-section-title">
        Dua agent yang bekerja
      </h3>
      <ul className="aa-agent-list">
        {AGENTS.map((agent) => (
          <li key={agent.key} className="aa-agent-card">
            <p className="aa-agent-name">{agent.name}</p>
            <p className="aa-agent-role">{agent.role}</p>
            <p className="aa-agent-work">{agent.work}</p>
            <p className="aa-agent-source">Sumber: {agent.source}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
