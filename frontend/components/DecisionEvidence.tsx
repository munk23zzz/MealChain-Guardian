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

import DecisionApproval from "./DecisionApproval";
import PageHeader from "./PageHeader";
import DecisionCostEvidence from "./DecisionCostEvidence";
import DecisionIdentityBatch from "./DecisionIdentityBatch";
import DecisionTraceIntegrity from "./DecisionTraceIntegrity";
import EvidenceEmptyState from "./EvidenceEmptyState";
import DecisionSafetySupplier from "./DecisionSafetySupplier";
// Penerimaan barang: kartu "Penerimaan barang" + tombol "Tandai diterima".
// Komponennya SELALU ada di repo, tetapi sejak Tahap 8 (29 Okt 2026) isi
// halaman pindah ke berkas ini sementara kartunya hanya dipasang di
// `DecisionDetail` — berkas yang tidak lagi dirender di mana pun. Akibatnya
// tombol penerimaan hilang dari layar keputusan; yang tersisa cuma antrean di
// tab Keamanan Pangan. Dipasang kembali di sini (30 Okt 2026).
import GoodsReceiptDrawer from "./GoodsReceiptDrawer";
import DecisionSummary from "./DecisionSummary";
import SectionJump from "./SectionJump";

// ─────────────────────────────────────────────────────────────────────────────
// ISI HALAMAN DIKOSONGKAN — 29 Okt 2026
//
// Permintaan pemilik: "hapus seluruh isi halaman Decision & Evidence, sisakan
// kerangka kosong (pemilih keputusan + kepala), lalu bangun ulang dari nol",
// ditambah "balikin design yang tadi" — jadi kerangka ini memakai kepala dan
// bilah kendali yang sudah ada, bukan bentuk baru.
//
// Kode isi lama TIDAK dihapus dari berkas ini: ia duduk di balik saklar di
// bawah, sehingga memulihkannya cukup mengubah satu nilai. Salinan utuh
// (DecisionEvidence, DecisionDetail, evidence-dossier.css) juga disimpan di
// docs/arsip/decision-evidence-20261029/.
//
// Tahap 8 (29 Okt 2026): saklar "isi sedang dibangun ulang" sudah dicabut —
// halaman hanya punya satu jalur render. Nav bagian kini selalu hidup karena
// semua jangkarnya ada (lihat lib/section-jump.ts).
// ─────────────────────────────────────────────────────────────────────────────
import { PAGE_TITLES } from "../lib/navigation";
import { evidenceSections } from "../lib/section-jump";
import { pendingDecisions, type TodayDecision } from "../lib/today";
import { decisionGroups, statusWord } from "../lib/decision-picker";
import DecisionPicker from "./DecisionPicker";
import { countActionable, countExpiredActionable } from "../lib/topbar";
import { shortId } from "../lib/agent-quality";
import type { SupplierContext } from "../lib/supplier-exclusions";
import type {
  CommercialCostPayload,
  MarketReference,
} from "../lib/decision-economics";
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
      <PageHeader
        titleId="judul-bukti"
        title={PAGE_TITLES.evidence}
        description="Halaman bukti satu keputusan: ringkasan, persetujuan, bukti biaya, keamanan & pemasok, identitas dan batch, sampai jejak dan integritas buktinya."
        meta={
          <>
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
          </>
        }
      />

      {/* Nav bagian: lima tujuan, label sama dengan judul bagian yang tercetak.
          Tahap 7 mencabut gerbang `!ISI_DIBANGUN_ULANG` — dulu nav disembunyikan
          supaya tidak ada tautan mati ke jangkar yang belum dirender; sekarang
          keenam bagian ada, jadi syaratnya kembali ke kenyataan: ada keputusan
          terpilih, daftar tidak sedang dimuat. */}
      {selected && !loading ? (
        <SectionJump
          items={evidenceSections()}
          ariaLabel="Bagian halaman Decision & Evidence"
        />
      ) : null}

      {/* BILAH KENDALI — pemilih "Keputusan yang diperiksa" (permintaan pemilik,
          30 Okt 2026): DIPISAH dari kartu kepala dan diletakkan di BAWAH nav
          bagian, jadi urutan baca halaman: kepala → bagian halaman → pilih
          keputusan → isi. Dulu pemilih menempel di dalam kepala sebagai baris
          bergaris, sehingga nav bagian (yang menempel saat menggulir) menutupi
          baris pemilih dan judul halaman + pemilih terbaca sebagai satu hal.
          Pemilih tetap dirender walau belum ada keputusan terpilih — tanpa itu
          tidak ada jalan memilih keputusan pertama. */}
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

      {/* TAHAP 8 (29 Okt 2026) — isi halaman jadi SATU jalur.
          Gerbang `ISI_DIBANGUN_ULANG` dicabut: dulu ia memilih antara isi baru
          (tahap 1–7) dan isi lama (`DecisionDetail`). Dua jalur berarti dua
          kebenaran — tiap perbaikan harus dikerjakan dua kali, dan tes lama
          dipaku pada markup yang tidak lagi dirender. Isi lama tetap utuh di
          `docs/arsip/decision-evidence-20261029/`.

          Keadaan kosong TIDAK hilang: ketiga sebabnya (memuat · baris diganti
          "Muat Demo" · tautan di luar cakupan peran) pindah ke
          `EvidenceEmptyState`, lengkap dengan daftar saran yang menunggu
          tindakan. */}
      {!selected ? (
        <EvidenceEmptyState
          loading={loading}
          selectedId={selectedId}
          diganti={diganti}
          suggestions={suggestions}
          onSelect={onSelect}
          onOpenRecommendations={onOpenRecommendations}
        />
      ) : (
        <>
          {/* TAHAP 1: ringkasan keputusan — pita jawaban + strip angka.
              Urutan mengikuti cara orang membaca: apa keputusannya, baru apa
              yang menahannya. */}
          <DecisionSummary selected={selected} summary={summary} now={now} />
          {/* TAHAP 2: persetujuan — satu-satunya bagian yang menuntut tindakan. */}
          <DecisionApproval
            decisionId={String(selected.decision_id)}
            role={role}
            status={selected.status ?? null}
            token={token}
            summary={summary}
            now={now}
          />
          {/* TAHAP 3: bukti biaya — dua tabel yang tidak boleh tercampur. */}
          <DecisionCostEvidence
            cost={(selected.commercial_cost ?? null) as CommercialCostPayload | null}
            market={(selected.market_reference ?? null) as MarketReference | null}
          />
          {/* TAHAP 4: keamanan & pemasok — "aman dan dari siapa". */}
          <DecisionSafetySupplier summary={summary} context={supplierContext} />
          {/* TAHAP 5: identitas keputusan + evaluasi batch. */}
          <DecisionIdentityBatch
            selected={selected as Record<string, unknown> & { decision_id?: string }}
            summary={summary}
            token={token ? String(token) : null}
            now={now}
          />
          {/* TAHAP 5b: penerimaan barang — BUKTI pelaksanaan, bukan angka baru.
              Status dan tombolnya dari `receipt_gate` server (can_receive),
              hanya untuk peran yang memang boleh memutuskan. */}
          <GoodsReceiptDrawer
            summary={summary}
            token={token ? String(token) : null}
            role={role}
          />
          {/* TAHAP 6: jejak, PO milik keputusan ini, dan integritas bukti. */}
          <DecisionTraceIntegrity
            selected={selected as Record<string, unknown> & { decision_id?: string }}
            summary={summary}
            chain={chain}
            token={token ? String(token) : null}
            purchaseOrders={purchaseOrders}
          />
        </>
      )}
    </section>
  );
}
