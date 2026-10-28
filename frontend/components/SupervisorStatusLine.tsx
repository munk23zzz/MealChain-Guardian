"use client";

// SupervisorStatusLine — satu baris status supervisor (dokumen 06 §2.8).
//
// Sengaja TERPISAH dari banner trace: satu keputusan bisa punya trace lengkap
// sementara supervisor tidak dikonfigurasi, dan menyatukannya akan membuat
// pembaca menyimpulkan sebab-akibat yang tidak ada.
//
// Warna tidak pernah hijau tanpa bukti `live` (invarian 4).

import { supervisorView, type SupervisorHealth } from "../lib/agent-activity";

export default function SupervisorStatusLine({
  health,
  loading = false,
}: {
  health: SupervisorHealth | null;
  loading?: boolean;
}) {
  const view = supervisorView(loading ? null : health);
  const sedangMuat = loading && !health;

  return (
    <section className="aa-supervisor" aria-labelledby="aa-supervisor-title">
      <h3 id="aa-supervisor-title" className="aa-section-title">
        Agent supervisor
      </h3>
      <p className={`aa-supervisor-line aa-tone-${view.tone}`}>
        <span className="aa-dot" aria-hidden="true" />
        <strong>{sedangMuat ? "Status supervisor belum dimuat" : view.label}</strong>
        <span className="aa-supervisor-detail">
          {sedangMuat
            ? "Belum ada jawaban dari backend; jangan dibaca sebagai sehat."
            : view.detail}
        </span>
      </p>
    </section>
  );
}
