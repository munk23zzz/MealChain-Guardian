// DecisionAudit — SATU lini masa untuk "Jejak & riwayat" halaman Decision &
// Evidence (Langkah 2 desain baru, 17 Okt 2026).
//
// Kenapa menyatukan: sebelumnya halaman memisahkan "Riwayat iterasi" (chip
// v1/v2/v3) dari fakta governance, sehingga pertanyaan penyetuju — "siapa
// memegang, sudah disetujui siapa, apa alasannya" — harus dijahit sendiri dari
// beberapa kartu. Riset pola (approval worklog / activity log) menyarankan satu
// catatan yang bercerita: siapa · kapan · versi mana · alasannya.
//
// Isinya murni dari `auditTimeline()` (lib/evidence.ts, ada tesnya): iterasi
// keluarga dari `/decisions/{id}/chain`, pengajuan + verifikasi dari payload
// keputusan, dan tiap baris approval dari `/approval-summary`. Tidak ada
// kejadian yang dikarang, dan waktu yang tidak ada ditulis apa adanya.

import { formatDateTime } from "../lib/datetime";
import type { AuditEvent } from "../lib/evidence";

/** Penanda nada digambar SVG, bukan glyph.
 *
 *  Sebelumnya ✓ ✕ ! • dicetak sebagai teks di dalam bulatan 22 px. Glyph
 *  tidak punya metrik yang sama: ✓ dan ✕ lebih lebar, ! dan • lebih sempit,
 *  dan baseline-nya berbeda — hasilnya penanda terlihat "keluar jalur" dari
 *  satu baris ke baris lain (keluhan pemilik 30 Okt 2026). SVG 12×12 dengan
 *  stroke bulat selalu duduk di tengah bulatan dan sejajar satu sama lain.
 */
function MarkTone({ tone }: { tone: string }) {
  const isi =
    tone === "ok" ? (
      <path
        d="M2.6 6.4l2.4 2.4 4.6-5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ) : tone === "danger" ? (
      <path
        d="M3.1 3.1l5.8 5.8M8.9 3.1l-5.8 5.8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    ) : tone === "warn" ? (
      <>
        <path d="M6 2.8v4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="6" cy="9.2" r="1" fill="currentColor" />
      </>
    ) : (
      <circle cx="6" cy="6" r="2" fill="currentColor" />
    );
  return (
    <span className="audit-mark" aria-hidden="true">
      <svg width="12" height="12" viewBox="0 0 12 12" focusable="false">
        {isi}
      </svg>
    </span>
  );
}

export default function DecisionAudit({ events }: { events: AuditEvent[] }) {
  if (!events || events.length === 0) {
    return <p className="evidence-note">Belum ada jejak yang bisa dibaca untuk keputusan ini.</p>;
  }
  return (
    <ol className="audit-list" aria-label="Jejak keputusan">
      {events.map((event) => (
        <li className={`audit-item audit-${event.tone}`} key={event.id}>
          <MarkTone tone={event.tone} />
          <div className="audit-body">
            <p className="audit-head">
              <strong className="audit-title">{event.title}</strong>
              {event.actor ? <span className="audit-actor">{event.actor}</span> : null}
              <span className="audit-time">
                {/* Waktu yang tidak tercatat TIDAK dikarang — dikatakan. */}
                {event.at ? formatDateTime(event.at) : "waktu tidak tercatat"}
              </span>
            </p>
            {event.detail ? <p className="audit-detail">{event.detail}</p> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
