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

const TONE_MARK: Record<string, string> = {
  ok: "✓",
  danger: "✕",
  warn: "!",
  plain: "•",
  muted: "•",
};

export default function DecisionAudit({ events }: { events: AuditEvent[] }) {
  if (!events || events.length === 0) {
    return <p className="evidence-note">Belum ada jejak yang bisa dibaca untuk keputusan ini.</p>;
  }
  return (
    <ol className="audit-list" aria-label="Jejak keputusan">
      {events.map((event) => (
        <li className={`audit-item audit-${event.tone}`} key={event.id}>
          <span className="audit-mark" aria-hidden="true">
            {TONE_MARK[event.tone] ?? "•"}
          </span>
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
