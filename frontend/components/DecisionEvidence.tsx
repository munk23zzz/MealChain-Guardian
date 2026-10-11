"use client";

// Langkah 4 (permintaan Roy 2026-10-11): halaman tersendiri
// "Decision & Evidence" — halaman ke-3 di sidebar acuan
// (mockupui/decision_detail_evidence_ledger). Sebelumnya detail keputusan
// hanya menempel di bawah feed Recommendations; kini punya halamannya sendiri
// supaya bukti satu keputusan bisa diperiksa utuh.
//
// Susunan (mengikuti urutan blok di mockup, disesuaikan ke data yang BENAR
// ada di backend — tidak ada gadget IoT/Arrhenius yang tidak punya sumber):
//   1. ringkasan keputusan (kartu + status)
//   2. identitas & tenggat
//   3. biaya (rincian + biaya aman terkirim)
//   4. keamanan pangan & pemasok
//   5. governance & persetujuan (DecisionActions = alur approval nyata)
//   6. riwayat iterasi (DecisionChain)
//   7. bukti tersimpan + ledger + tanda tangan (IntegrityPanel) & ekspor
//
// Semua nilai tak diketahui ditulis "—" (lib/evidence.ts), tidak dikarang.

import RecommendationCard from "./RecommendationCard";
import DecisionActions from "./DecisionActions";
import DecisionChain from "./DecisionChain";
import IntegrityPanel from "./IntegrityPanel";
import PageHeader from "./PageHeader";
import { SupplierExclusionView } from "./SupplierExclusionPanel";
import { pendingDecisions, type TodayDecision } from "../lib/today";
import type { SupplierContext } from "../lib/supplier-exclusions";
import {
  approvalFacts,
  costFacts,
  decisionFacts,
  safetyFacts,
  supplierFact,
  type FactRow,
} from "../lib/evidence";

/** Daftar fakta label→nilai (dipakai semua kartu di halaman ini). */
function FactList({ rows }: { rows: FactRow[] }) {
  return (
    <dl className="fact-list">
      {rows.map((row) => (
        <div className="fact-row" key={row.label}>
          <dt>{row.label}</dt>
          <dd className={`fact-value fact-${row.tone ?? "plain"}`}>
            {row.value}
            {row.hint && <span className="fact-hint">{row.hint}</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default function DecisionEvidence({
  decisions,
  selected,
  selectedId,
  onSelect,
  chain,
  summary,
  supplierContext,
  role,
  token,
  now,
  onSupplierCreated,
  onOpenRecommendations,
}: {
  decisions: TodayDecision[];
  selected: any | null;
  selectedId: string | null;
  onSelect: (decisionId: string) => void;
  chain: any[];
  summary: any;
  supplierContext: SupplierContext | null;
  role: string;
  token: string | null;
  now: Date | null;
  onSupplierCreated?: (decisionId: string) => void;
  onOpenRecommendations?: () => void;
}) {
  const clock = now ?? new Date(0);
  // Pilihan untuk empty state: yang paling perlu tindakan lebih dulu.
  const suggestions = pendingDecisions(decisions, clock).items.slice(0, 6);

  return (
    <section className="evidence-page">
      <PageHeader
        title="Decision & Evidence"
        description="Satu keputusan, seluruh buktinya: identitas & tenggat, biaya, hasil pemeriksaan keamanan, pemasok, governance persetujuan, riwayat iterasi, lalu bukti tersimpan dengan alamat konten dan tanda tangannya — semuanya dari API."
        meta={
          <select
            className="page-header-select"
            aria-label="Pilih keputusan"
            value={selectedId ?? ""}
            onChange={(event) => onSelect(event.target.value)}
          >
            <option value="">— pilih keputusan —</option>
            {decisions.map((decision) => (
              <option key={String(decision.decision_id)} value={String(decision.decision_id)}>
                {String(decision.decision_type ?? "keputusan")} · {String(decision.status)} ·{" "}
                {String(decision.decision_id ?? "").slice(0, 8)}
              </option>
            ))}
          </select>
        }
      />

      {!selected ? (
        <article className="card evidence-empty">
          <h2>Belum ada keputusan dipilih</h2>
          <p className="evidence-note">
            Pilih keputusan di kanan atas, atau buka salah satu yang menunggu tindakan di bawah
            ini. Halaman ini menampilkan bukti satu keputusan — bukan ringkasan seluruh feed.
          </p>
          {suggestions.length === 0 ? (
            <p className="evidence-note">
              Tidak ada keputusan yang menunggu tindakan saat ini
              {onOpenRecommendations ? "." : " — buka tab Recommendations untuk melihat semua."}
            </p>
          ) : (
            <ul className="evidence-suggest">
              {suggestions.map((decision) => (
                <li key={String(decision.decision_id)}>
                  <button
                    type="button"
                    className="button evidence-suggest-button"
                    onClick={() => onSelect(String(decision.decision_id))}
                  >
                    <span className="evidence-suggest-title">
                      {String(decision.decision_type ?? "keputusan").replace(/_/g, " ")}
                    </span>
                    <span className="evidence-suggest-meta">
                      {String(decision.status ?? "—")} · {String(decision.decision_id ?? "").slice(0, 8)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {onOpenRecommendations && (
            <button type="button" className="button button-secondary" onClick={onOpenRecommendations}>
              Buka Recommendation Feed
            </button>
          )}
        </article>
      ) : (
        <>
          <article className="card evidence-summary">
            <h2>Ringkasan keputusan</h2>
            <RecommendationCard decision={selected} mockSourced={false} />
            <FactList rows={decisionFacts({ ...selected, summary }, clock)} />
          </article>

          <div className="evidence-grid">
            <article className="card">
              <h2>Biaya</h2>
              <FactList rows={costFacts({ ...selected, summary })} />
            </article>

            <article className="card">
              <h2>Keamanan &amp; pemasok</h2>
              <FactList rows={[...safetyFacts(summary), supplierFact(summary)]} />
            </article>

            <article className="card">
              <h2>Governance &amp; persetujuan</h2>
              <FactList rows={approvalFacts(summary)} />
              <DecisionActions
                decisionId={selected.decision_id}
                role={role}
                status={selected.status}
                token={token}
                summary={summary}
              />
            </article>
          </div>

          <article className="card">
            <h2>Riwayat iterasi</h2>
            {chain && chain.length > 0 ? (
              <DecisionChain chain={chain} />
            ) : (
              <p className="evidence-note">Belum ada iterasi sebelumnya untuk keputusan ini.</p>
            )}
          </article>

          {supplierContext && (
            <SupplierExclusionView
              key={selected.decision_id}
              context={supplierContext}
              role={role}
              token={token ?? ""}
              onCreated={onSupplierCreated ?? (() => {})}
            />
          )}

          {/* Bukti tersimpan: daftar evidence + rantai Merkle + tanda tangan
              ECDSA + tombol ekspor JSON/CSV. */}
          <IntegrityPanel token={token ?? ""} decisionId={selected.decision_id} />
        </>
      )}
    </section>
  );
}
