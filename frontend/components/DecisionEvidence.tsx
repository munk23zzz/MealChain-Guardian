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
import { decisionGroups } from "../lib/decision-picker";
import { countActionable } from "../lib/topbar";
import type { SupplierContext } from "../lib/supplier-exclusions";
import {
  approvalFacts,
  costFacts,
  decisionFacts,
  nextStep,
  safetyFacts,
  supplierFact,
} from "../lib/evidence";
import FactList, { type FactRow } from "./FactList";

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
  onOpenTraces,
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
  /** Membuka tab Agent Log untuk keputusan yang sedang dibuka. */
  onOpenTraces?: () => void;
}) {
  const clock = now ?? new Date(0);
  // Kalimat "apa yang harus saya lakukan" untuk keputusan yang sedang dibuka.
  // Satu sumber logika (lib/evidence.ts), diuji di tests/evidence-summary.test.ts.
  const langkah = nextStep({ role, status: String(selected?.status ?? ""), summary });
  // Pilihan untuk empty state: yang paling perlu tindakan lebih dulu.
  const suggestions = pendingDecisions(decisions, clock).items.slice(0, 6);
  // Kelompok dropdown dari lib/decision-picker (satu sumber dengan tab Agent Log).
  const groups = decisionGroups(decisions, now);

  return (
    <section className="evidence-page">
      <PageHeader
        title="Decision & Evidence"
        description="Satu keputusan, seluruh buktinya: identitas & tenggat, biaya, hasil pemeriksaan keamanan, pemasok, governance persetujuan, riwayat iterasi, lalu bukti tersimpan dengan alamat konten dan tanda tangannya — semuanya dari API."
        meta={
          // Pemilih keputusan: dulu tanpa label (hanya opsi "— pilih keputusan —")
          // dan tanpa konteks jumlah, sehingga pengguna tidak tahu ada berapa
          // keputusan dan mana yang menunggu tindakan. Label terlihat + kalimat
          // jumlah di bawahnya menjawab itu, dan angkanya dari SATU sumber yang
          // sama dengan lonceng notifikasi (countActionable).
          <div className="evidence-picker">
            <label className="evidence-picker-label" htmlFor="pilih-keputusan">
              Keputusan yang diperiksa
            </label>
            <select
              id="pilih-keputusan"
              className="page-header-select"
              value={selectedId ?? ""}
              onChange={(event) => onSelect(event.target.value)}
            >
              <option value="">— pilih keputusan —</option>
              {groups.map((group) => (
                <optgroup key={group.id} label={group.label}>
                  {group.options.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <span className="evidence-picker-hint">
              {countActionable(decisions, now)} menunggu tindakan · {decisions.length} keputusan
              tersedia
            </span>
          </div>
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
            {/* Langkah berikutnya: SATU kalimat yang menjawab "apa yang harus
                saya lakukan" — halaman ini dulu hanya menumpahkan fakta sehingga
                pengguna harus menyimpulkan sendiri tindakannya. */}
            <div className={`evidence-next evidence-next-${langkah.tone}`} role="status">
              <span className="evidence-next-label">Langkah berikutnya</span>
              <p className="evidence-next-text">{langkah.text}</p>
            </div>
            {/* Bento ringkasan (Fase 3): kartu keputusan di kiri, fakta identitas
                & tenggat di kanan — bukan satu kolom panjang yang membuat tenggat
                tergulung jauh ke bawah layar. */}
            <div className="evidence-summary-body">
              <div className="evidence-summary-main">
                {/* hint={null}: di halaman ini kartu TIDAK dibungkus tombol (tidak
                    seperti di feed), jadi ajakan "klik untuk rincian" akan jadi janji
                    kosong. Jejak agennya sendiri ada di tab Agent Log — ditautkan di
                    bawah, dan tautan itu benar-benar bisa diklik. */}
                <RecommendationCard decision={selected} mockSourced={false} hint={null} />
                {onOpenTraces ? (
                  <p className="evidence-traces">
                    <button type="button" className="button button-secondary" onClick={onOpenTraces}>
                      Buka jejak agen
                      <span aria-hidden="true"> →</span>
                    </button>
                    <span className="evidence-note">
                      Jejak reasoning tiap langkah (model, alat, durasi) ada di tab Agent Log, untuk
                      keputusan yang sedang dibuka ini.
                    </span>
                  </p>
                ) : null}
              </div>
              <div className="evidence-summary-facts">
                <FactList rows={decisionFacts({ ...selected, summary }, clock)} collapseEmpty />
              </div>
            </div>
          </article>

          <div className="evidence-grid">
            <article className="card">
              <h2>Biaya</h2>
              <FactList rows={costFacts({ ...selected, summary })} collapseEmpty />
            </article>

            <article className="card">
              <h2>Keamanan &amp; pemasok</h2>
              <FactList rows={[...safetyFacts(summary), supplierFact(summary)]} collapseEmpty />
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

          {/* Form pengecualian pemasok (governance) tampil lebar penuh tepat
              setelah kartu governance — ia form, jadi butuh lebar; baris bento
              paling bawah menyandingkan riwayat iterasi dengan bukti kripto. */}
          {supplierContext && (
            <SupplierExclusionView
              key={selected.decision_id}
              context={supplierContext}
              role={role}
              token={token ?? ""}
              onCreated={onSupplierCreated ?? (() => {})}
            />
          )}

          <div className="evidence-bottom">
            <article className="card evidence-chain-card">
              <h2>Riwayat iterasi</h2>
              {chain && chain.length > 0 ? (
                <DecisionChain chain={chain} />
              ) : (
                <p className="evidence-note">Belum ada iterasi sebelumnya untuk keputusan ini.</p>
              )}
            </article>

            {/* Bukti tersimpan: daftar evidence + rantai Merkle + tanda tangan
                ECDSA + tombol ekspor JSON/CSV. */}
            <IntegrityPanel token={token ?? ""} decisionId={selected.decision_id} />
          </div>
        </>
      )}
    </section>
  );
}
