"use client";

// SupervisorStatusLine — satu baris status supervisor (dokumen 06 §2.8).
//
// Sengaja TERPISAH dari banner trace: satu keputusan bisa punya trace lengkap
// sementara supervisor tidak dikonfigurasi, dan menyatukannya akan membuat
// pembaca menyimpulkan sebab-akibat yang tidak ada.
//
// Warna tidak pernah hijau tanpa bukti `live` (invarian 4).
//
// Penempatan (permintaan pemilik 29 Okt 2026: "bagian ini 'Agent supervisor'
// kurang pas penempatannya"): dulu blok ini kartu berjudul sendiri yang duduk di
// samping kelompok "Dua agent yang bekerja" — dua bentuk berbeda berdampingan.
// Sekarang ia BARIS STATUS TIPIS tanpa kotak dan tanpa judul, dipasang sejajar
// dengan judul kelompok "Langkah & model", karena yang diterangkannya adalah
// keadaan seluruh jejak, bukan satu agent.

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
    <p
      className={`aa-supervisor-line aa-tone-${view.tone}`}
      data-testid="supervisor-line"
    >
      <span className="aa-dot" aria-hidden="true" />
      {/* Label untuk pembaca layar: baris ini tidak lagi punya judul sendiri,
          jadi tanpa kata "Agent supervisor" ia terbaca sebagai kalimat lepas. */}
      <span className="aa-sr">Agent supervisor:</span>
      {/* Label terlihat, kecil — supaya kotak abu-abu ini tetap punya nama
          tanpa perlu judul di atasnya (permintaan pemilik 29 Okt 2026). */}
      <span className="aa-supervisor-label">Supervisor</span>
      <strong>{sedangMuat ? "Status supervisor belum dimuat" : view.label}</strong>
      <span className="aa-supervisor-detail">
        {sedangMuat
          ? "Belum ada jawaban; jangan dibaca sebagai sehat."
          : view.detail}
      </span>
    </p>
  );
}
