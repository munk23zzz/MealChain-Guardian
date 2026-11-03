"use client";

// DecisionSummary — blok RINGKASAN halaman Decision & Evidence (TAHAP 1,
// 29 Okt 2026, gaya clean dashboard).
//
// Bentuk: satu band jawaban + strip angka.
//   · band   : jendela berlaku, umur jendela, nomor keputusan & iterasi;
//   · judul  : kalimat keputusan itu sendiri ("Seimbangkan 600 kg beras …");
//   · angka  : KPI card rapat (Kuantitas · Biaya aman terkirim · Selisih ·
//              Tenggat) — label kecil kapital, angka besar tabular;
//   · triase : "Perlu diperhatikan" HANYA dirender bila memang ada temuan.
//
// Semua angka dan kalimat datang dari `lib/evidence` (decisionHeadline,
// decisionMetrics, attentionFlags, windowUsage) — sumber yang sama dengan feed
// dan halaman lain, jadi tidak ada hitungan kedua di komponen ini. Nilai yang
// tidak ada tetap "—" dari helper, bukan nol.

import { shortId } from "../lib/agent-quality";
import {
  attentionFlags,
  decisionHeadline,
  decisionMetrics,
  windowUsage,
} from "../lib/evidence";
import { dueLabel } from "../lib/today";

export default function DecisionSummary({
  selected,
  summary,
  now,
}: {
  selected: unknown;
  summary: unknown;
  now: Date | null;
}) {
  const decision = (selected ?? null) as Record<string, unknown> | null;
  if (!decision) return null;

  const judul = decisionHeadline(decision, summary);
  const metrik = decisionMetrics(decision, summary, now);
  const flags = attentionFlags({ decision, summary });
  const umur = windowUsage({
    created_at: decision.created_at,
    expires_at: decision.expires_at,
    now,
  });
  const statusKey = String(decision.status ?? "").toLowerCase();
  const adaJendela = statusKey !== "review_only";
  const jendela = adaJendela
    ? now
      ? dueLabel(decision.expires_at, now)
      : "—"
    : null;
  const iterasi = Number(decision.iteration ?? 1);

  return (
    <article className="dash-summary" id="ringkasan" data-bagian="ringkasan">
      <div className="dash-summary-bar">
        {jendela ? (
          <span className="dash-summary-item">
            Jendela berlaku: <strong>{jendela}</strong>
          </span>
        ) : null}
        {/* Umur jendela hanya disebut bila bisa dihitung; helper mengembalikan
            "tidak diketahui" untuk data tanpa jam, dan kalimat itulah yang
            tampil — bukan persen karangan. */}
        {adaJendela && umur.state !== "tidak diketahui" ? (
          <span className="dash-summary-item" data-state={umur.state}>
            {umur.label}
          </span>
        ) : null}
        <span className="dash-summary-item dash-summary-id">
          #{shortId(String(decision.decision_id ?? ""))} · iterasi v{iterasi}
          {decision.supersedes_id ? " · memperbaiki keputusan sebelumnya" : ""}
        </span>
      </div>

      <h2 className="dash-summary-title">{judul}</h2>

      {metrik.length > 0 ? (
        <dl className="dash-kpis">
          {metrik.map((item) => (
            <div className="dash-kpi" key={item.label}>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {flags.length > 0 ? (
        <div className="dash-flags">
          <h3 className="dash-flags-title">Perlu diperhatikan ({flags.length})</h3>
          <ul className="dash-flags-list">
            {flags.map((flag) => (
              <li className="dash-flag" data-tone={flag.tone} key={flag.id}>
                {/* Sebagian temuan datang tanpa label (mis. keamanan batch);
                    label kosong tidak dirender supaya tidak ada garis kosong
                    sebelum kalimatnya. */}
                {flag.label ? (
                  <strong className="dash-flag-label">{flag.label}</strong>
                ) : null}
                <span className="dash-flag-text">{flag.text}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </article>
  );
}
