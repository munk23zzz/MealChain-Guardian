"use client";

// Halaman "Decision & Evidence" — bukti SATU keputusan.
//
// Desain ulang 17 Okt 2026 (keluhan user: "tampilannya sangat kurang"; riset pola
// + rujukan di `_qa/rencana-decision-evidence-v2.md`). Susunannya mengikuti cara
// manusia mengambil keputusan, bukan urutan tabel database:
//
//   A. KEPALA KEPUTUSAN (`evidence-hero`) — aturan "3 detik": aksi dalam bahasa
//      manusia + angka kunci + status/jendela + flag triase + langkah berikutnya
//      + akibat tiap pilihan. Judulnya dari `decisionHeadline()`.
//   B. JALUR PERSETUJUAN (`evidence-route`) — empat langkah tetap: siapa sudah,
//      siapa memegang sekarang, siapa berikutnya (riset: "routed request record").
//   C. ZONA KEPUTUSAN (`evidence-decide`, #zona-keputusan) — kontrol keputusan
//      NAIK ke atas (urutan Tab kanonik: ringkasan → rute → kontrol keputusan →
//      bukti → riwayat), tetap memakai `DecisionActions` yang sama.
//   D. BUKTI — biaya, keamanan & pemasok, identitas & tenggat; baris "—" masuk
//      ke blok rincian yang bisa dibuka (prop `collapseEmpty`).
//   E. JEJAK — riwayat iterasi + panel integritas (Merkle/ECDSA).
//
// 28 Okt 2026: SELURUH isi A–E dipindah ke `components/DecisionDetail.tsx`
// (dipindah, bukan dirancang ulang) supaya detail yang sama bisa juga tampil di
// POPUP yang dibuka dari kartu rekomendasi. Halaman ini tinggal cangkangnya:
// kepala halaman, pemilih keputusan, navigasi bagian, dan keadaan kosong.
//
// Aturan lama yang TETAP: nilai tak diketahui ditulis "—" (tidak dikarang), gating
// approval tidak diubah, kotak bukti `.integrity-trust` tetap satu tempat (kini
// bertema terang, 19 Okt 2026), kelas tes-sensitif
// (`.map-*`, `.side-tab*`, `.board-table-wrap`) tidak disentuh.

import DecisionDetail from "./DecisionDetail";
import SectionJump from "./SectionJump";
import { PAGE_TITLES } from "../lib/navigation";
import { evidenceSections } from "../lib/section-jump";
import { pendingDecisions, type TodayDecision } from "../lib/today";
import { decisionGroups, statusWord } from "../lib/decision-picker";
import DecisionPicker from "./DecisionPicker";
import { countActionable, countExpiredActionable } from "../lib/topbar";
import { shortId } from "../lib/agent-quality";
import type { SupplierContext } from "../lib/supplier-exclusions";
import { useState } from "react";

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
  purchaseOrders,
  loading = false,
  diganti = false,
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
  /** Data PO jaringan; hanya baris milik keputusan ini yang dipakai. */
  purchaseOrders?: unknown;
  /**
   * Daftar keputusan masih diambil dari API. Tanpa ini, tautan yang dibagikan
   * sempat dituduh "tidak ada di cakupan" padahal datanya belum tiba.
   */
  loading?: boolean;
  /** Baris yang dituju sudah tidak ada di DB (404), bukan di luar cakupan. */
  diganti?: boolean;
}) {
  const clock = now ?? new Date(0);
  // Pilihan untuk empty state: yang paling perlu tindakan lebih dulu.
  const suggestions = pendingDecisions(decisions, clock).items.slice(0, 6);
  // Keputusan owner 17 Okt: yang lewat tenggat TIDAK ditawarkan sebagai pilihan
  // baru (backend menolak tindakannya). Semua baris lama tetap bisa dibuka lewat
  // tautan bersama karena `keep` menyertakan yang sedang dipilih.
  const [showExpired, setShowExpired] = useState(false);
  const expiredCount = countExpiredActionable(decisions as any, now, role);
  // Kelompok dropdown dari lib/decision-picker (satu sumber dengan tab Agent Log).
  const groups = decisionGroups(decisions, now, {
    includeExpired: showExpired,
    keep: selectedId,
  });

  return (
    <section className="evidence-page" aria-labelledby="judul-bukti">
      {/* TAHAP 1 (29 Okt 2026) — kepala + navigasi bagian.
          Kepala kini berbentuk KARTU seperti halaman Overview: judul dan satu
          kalimat penjelas di kiri, penanda keadaan di kanan (data simulasi,
          status keputusan, nomor keputusan). Alasan: kepala `PageHeader` biasa
          menaruh kontrol pemilih di kanan atas sehingga judul, penjelas, dan
          kontrol berebut tempat; di pola Overview kontrol turun ke bilahnya
          sendiri dan kepala hanya menjawab "halaman apa ini, keadaan apa".

          Yang TIDAK diubah di tahap ini: isi halaman di bawah nav (ringkasan,
          keputusan, bukti, jejak) tetap seperti sekarang — perubahan isi
          dikerjakan di tahap 2–5. */}
      <header className="overview-header">
        <div className="overview-header-main">
          <h1 id="judul-bukti">{PAGE_TITLES.evidence}</h1>
          <p className="overview-header-sub">
            Keputusan terpilih beserta rantai buktinya: alasan agen, angka yang
            dipakai, jejak langkah, PO, dan siapa yang menyetujui. Angka yang
            tidak tercatat ditulis alasannya, bukan ditebak.
          </p>
        </div>
        <div className="overview-header-status">
          <span
            className="overview-demo-chip"
            title="Data contoh untuk demo, bukan data operasional produksi"
          >
            Data simulasi
          </span>
          {selected ? (
            <span
              className="evidence-header-status"
              data-status={String(selected.status ?? "")}
            >
              {statusWord(selected.status)}
            </span>
          ) : null}
          {selected ? (
            <span className="overview-updated">
              #{shortId(String(selected.decision_id))}
            </span>
          ) : null}
        </div>
      </header>

      {/* Bilah kendali: pemilih keputusan keluar dari kepala ke kartunya sendiri
          (pola yang sama dengan bilah filter Overview). */}
      <div className="evidence-controls">
        <div className="evidence-picker">
          <DecisionPicker
            id="pilih-keputusan"
            label="Keputusan yang diperiksa"
            groups={groups}
            value={selectedId}
            onChange={onSelect}
            hint={
              <>
                {countActionable(decisions, now, role)} menunggu tindakan
                {expiredCount > 0
                  ? showExpired
                    ? ` · ${expiredCount} lewat tenggat ditampilkan`
                    : ` · ${expiredCount} lewat tenggat disembunyikan`
                  : ""}{" "}
                · {decisions.length} keputusan tersedia
              </>
            }
          />
          {expiredCount > 0 && (
            <label className="evidence-picker-toggle">
              <input
                type="checkbox"
                checked={showExpired}
                onChange={(event) => setShowExpired(event.target.checked)}
              />
              Tampilkan yang lewat tenggat ({expiredCount})
            </label>
          )}
        </div>
      </div>

      {/* Nav bagian tetap 4 tujuan yang sudah ada (Ringkasan · Keputusan ·
          Bukti · Jejak & integritas) — tahap 1 hanya memindahkan siapa yang
          merendernya: halaman ini sendiri, karena ia tidak lagi memakai
          PageShell. Sasaran jangkar tidak berubah. */}
      {selected && !loading ? (
        <SectionJump
          items={evidenceSections()}
          ariaLabel="Bagian halaman Decision & Evidence"
        />
      ) : null}
      {!selected && loading ? (
        <article className="card evidence-empty" role="status">
          <h2>Memuat keputusan…</h2>
          <p className="evidence-note">
            Daftar keputusan sedang diambil dari API. Kalau halaman ini dibuka lewat tautan
            bersama, keputusan yang dituju ditampilkan begitu daftarnya tiba.
          </p>
        </article>
      ) : !selected ? (
        <article className="card evidence-empty">
          {/* Tautan yang dibagikan bisa menunjuk keputusan di luar cakupan peran
              penerima — katakan itu, jangan berpura-pura tidak ada yang dipilih. */}
          <h2>
            {diganti
              ? "Keputusan ini sudah diganti oleh Muat Demo"
              : selectedId
                ? "Keputusan itu tidak ada di cakupan akun ini"
                : "Belum ada keputusan dipilih"}
          </h2>
          <p className="evidence-note">
            {diganti
              ? "Baris keputusan yang dituju tautan sudah tidak ada — \"Muat Demo\" mengganti baris operasional (batch, keputusan, pesanan). Pilih keputusan terbaru di kanan atas; data yang tampil setelah ini berasal dari dataset baru."
              : selectedId
              ? `Tautan menunjuk keputusan #${shortId(String(selectedId))}, tetapi keputusan itu tidak ada di daftar yang boleh dilihat peran ini — peran & lokasi membatasi daftar. Pilih keputusan lain di kanan atas, atau minta tautan dari akun yang cakupannya memuat keputusan itu.`
              : "Pilih keputusan di kanan atas, atau buka salah satu yang menunggu tindakan di bawah ini. Halaman ini menampilkan bukti satu keputusan — bukan ringkasan seluruh feed."}
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
        <DecisionDetail
          selected={selected}
          chain={chain}
          summary={summary}
          supplierContext={supplierContext}
          role={role}
          token={token}
          now={now}
          onSupplierCreated={onSupplierCreated}
          purchaseOrders={purchaseOrders}
        />
      )}
    </section>
  );
}
