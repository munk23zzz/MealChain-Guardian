"use client";

// DecisionDetail — ISI satu keputusan, tanpa cangkang halaman.
//
// Kenapa dipisah (28 Okt 2026): detail yang sama harus bisa muncul di DUA tempat —
// (a) halaman tab "Decision & Evidence" (kerja panjang, tautan bersama), dan
// (b) POPUP yang dibuka dari kartu rekomendasi / daftar Hari Ini / PO ("detail &
// jejak agen" tanpa meninggalkan halaman yang sedang dibaca).
//
// Karena itu komponen ini TIDAK memuat PageHeader, pemilih keputusan, atau
// navigasi bagian halaman — ketiganya milik halaman, bukan milik keputusan.
// Markup, kalimat, dan angka di dalamnya SAMA PERSIS dengan yang dulu ditulis di
// `DecisionEvidence.tsx` (dipindah, bukan dirancang ulang), supaya 39 tes halaman
// itu tetap menguji perilaku yang sama.
//
// Aturan yang tetap berlaku: nilai tak diketahui ditulis "—" (tidak dikarang),
// gating approval tidak diubah, angka berasal dari API/lib murni, bukan dihitung
// ulang di komponen ini selain yang memang sudah ada.

import DecisionActions from "./DecisionActions";
import ApprovalOverview from "./ApprovalOverview";
import { caseLabelOf } from "./RecommendationCard";
import DecisionAudit from "./DecisionAudit";
import IntegrityPanel from "./IntegrityPanel";
import DecisionPurchaseOrder from "./DecisionPurchaseOrder";
import DecisionTraceList from "./DecisionTraceList";
import { SupplierExclusionView } from "./SupplierExclusionPanel";
import { CatatanTeknis } from "./CatatanTeknis";
import GoodsReceiptDrawer from "./GoodsReceiptDrawer";
import { statusWord } from "../lib/decision-picker";
import { shortId } from "../lib/agent-quality";
import type { SupplierContext } from "../lib/supplier-exclusions";
import {
  attentionFlags,
  auditTimeline,
  costFacts,
  decisionFacts,
  decisionHeadline,
  decisionMetrics,
  safetyBadge,
  safetyFacts,
  supplierFact,
  windowUsage,
} from "../lib/evidence";
import { downloadDossier } from "../lib/export";
import FactList from "./FactList";
import DecisionEconomics from "./DecisionEconomics";
import HumanReviewPanel from "./HumanReviewPanel";
import BatchEvaluationTable from "./BatchEvaluationTable";
import { fetchDecisionPacket } from "../lib/api";
import { dueLabel } from "../lib/today";
import { useEffect, useState } from "react";

// Nada lencana status memakai kelas `.status-*` yang sudah ada — jangan bikin
// palet kedua. Status tak dikenal → netral (jujur, bukan ditebak).
const STATUS_TONES: Record<string, string> = {
  proposed: "neutral",
  pending_approval: "warning",
  verifier_flagged: "warning",
  needs_verification: "warning",
  approved: "safe",
  executed: "safe",
  rejected: "danger",
  expired: "danger",
};


/**
 * @param dalamPopup true = dirender di dalam dialog. Dua hal yang berbeda di
 *   sana: (1) pengukur posisi zona keputusan memakai gulir JENDELA, sedangkan
 *   di popup gulirnya ada di `.popup-body` — jadi pengukur itu tidak dijalankan;
 *   (2) bilah pintasan bawah tidak ditampilkan, karena tombol tujuannya sudah
 *   terlihat tanpa menggulir sejauh halaman.
 */
export default function DecisionDetail({
  selected,
  chain,
  summary,
  supplierContext,
  role,
  token,
  now,
  onSupplierCreated,
  purchaseOrders,
  traces,
  dalamPopup = false,
}: {
  selected: any | null;
  chain: any[];
  summary: any;
  supplierContext: SupplierContext | null;
  role: string;
  token: string | null;
  now: Date | null;
  onSupplierCreated?: (decisionId: string) => void;
  /** Jejak agen keputusan ini (dari GET /decisions/{id}/traces). */
  traces?: unknown;
  /** Data PO jaringan; komponen hanya memakai baris milik keputusan ini. */
  purchaseOrders?: unknown;
  dalamPopup?: boolean;
}) {
  const clock = now ?? new Date(0);
  // Unduhan bukti dari kepala halaman: keadaan dipegang di sini supaya tombol
  // bisa jujur (menyiapkan → nama berkas / gagal), bukan diam-diam tidak jalan.
  const [unduh, setUnduh] = useState<{ state: "diam" | "jalan" | "sukses" | "gagal"; nama?: string }>(
    { state: "diam" }
  );
  async function eksporBukti() {
    if (!token || !selected?.decision_id) return;
    setUnduh({ state: "jalan" });
    try {
      const nama = await downloadDossier(String(selected.decision_id), token);
      setUnduh({ state: "sukses", nama });
    } catch {
      setUnduh({ state: "gagal" });
    }
  }
  // Semua kalimat & angka disusun di `lib/evidence.ts` (murni, ada tesnya) —
  // komponen ini hanya menaruh hasilnya.
  const judul = decisionHeadline(selected, summary);
  const metrik = decisionMetrics(selected, summary, now);
  // Ringkasan persetujuan datang dari API terpisah (ikut poll 5 detik). Saat
  // belum tiba, `attentionFlags` hanya bisa menyimpulkan "belum diverifikasi"
  // dan menampilkan "(1)" padahal data aslinya tiga temuan — angka karangan.
  // Jadi daftar temuan baru disusun setelah ringkasan benar-benar ada.
  const adaRingkasan =
    Boolean(summary) && typeof summary === "object" && Object.keys(summary as object).length > 0;
  const flags = adaRingkasan ? attentionFlags({ decision: selected, summary }) : [];
  const audit = auditTimeline({ decision: selected, summary, chain });
  // Putusan safety satu keputusan: lencana di kepala kartu "Keamanan & pemasok".
  // Angka "N batch diperiksa" pindah ke lencana, jadi baris fakta yang sama
  // tidak dicetak dua kali (`countInBadge`).
  const badgeSafety = safetyBadge(summary);
  const faktaSafety = safetyFacts(summary, { countInBadge: true });
  const umur = windowUsage({
    created_at: selected?.created_at,
    expires_at: selected?.expires_at,
    now: now ?? null,
  });
  const statusKey = String(selected?.status ?? "").toLowerCase();

  // Fase 6 butir 4: SATU paket keputusan untuk layar ini — evaluasi batch,
  // biaya, bukti, dan review dibaca dari bentuk server, bukan dirakit ulang di
  // klien. Gagal mengambil paket TIDAK dikarang: tabel cukup tidak tampil.
  const [paket, setPaket] = useState<any>(null);
  useEffect(() => {
    const id = selected?.decision_id;
    if (!id || !token) {
      setPaket(null);
      return;
    }
    let batal = false;
    (async () => {
      try {
        const data = await fetchDecisionPacket(id, token);
        if (!batal) setPaket(data);
      } catch {
        if (!batal) setPaket(null);
      }
    })();
    return () => {
      batal = true;
    };
  }, [selected?.decision_id, token]);

  if (!selected) return null;

  return (
    <>
      {/* ── A. KEPALA KEPUTUSAN ─────────────────────────────────────────── */}
      <article className="card evidence-hero jump-target" id="ringkasan" data-bagian="kepala" data-status={statusKey}>
        <div className="evidence-hero-bar">
          <span
            className={`badge evidence-hero-status status-${STATUS_TONES[statusKey] ?? "neutral"}`}
            data-status={statusKey.toUpperCase()}
          >
            {statusWord(selected.status)}
          </span>
          {/* Audit M6: temuan review-only tidak punya jendela tindakan. */}
          {statusKey !== "review_only" && (
            <span className="evidence-hero-window">
              Jendela berlaku: {dueLabel(selected.expires_at, clock)}
            </span>
          )}
          {/* Badge kasus demo: dulu datang dari kartu feed yang kini diganti
              hero ini — penandanya tidak boleh hilang (kelas .rec-case
              dipakai ulang, bukan bikin palet kedua). */}
          {caseLabelOf(selected) && (
            <span className="badge rec-case">{caseLabelOf(selected)}</span>
          )}
          {/* Audit M6: temuan review-only tidak punya jendela tindakan —
              menampilkan "29 menit lagi" membuatnya tampak menunggu sesuatu. */}
          {statusKey !== "review_only" && umur.state !== "tidak diketahui" && (
            <span className="evidence-usage" data-state={umur.state}>
              {umur.label}
            </span>
          )}
          <span className="evidence-hero-id">
            #{shortId(selected.decision_id)} · iterasi v{Number(selected.iteration ?? 1)}
            {selected.supersedes_id ? " · memperbaiki keputusan sebelumnya" : ""}
          </span>
          <span className="evidence-hero-actions">
            <button
              type="button"
              className="button button-secondary evidence-export"
              onClick={eksporBukti}
              disabled={!token || unduh.state === "jalan"}
            >
              {unduh.state === "jalan" ? "Menyiapkan bukti…" : "Unduh bukti (JSON)"}
            </button>
          </span>
        </div>
        {unduh.state === "sukses" && (
          <p className="evidence-note" role="status">
            Bukti terunduh sebagai {unduh.nama}.
          </p>
        )}
        {unduh.state === "gagal" && (
          <p className="evidence-note" role="status">
            Gagal mengunduh bukti — coba lagi; kalau tetap gagal, unduh dari bagian
            &ldquo;Bukti tersimpan&rdquo; di bawah.
          </p>
        )}

        {/* Label kecil di atas judul BUKAN heading — heading seksi ini adalah
            aksinya sendiri (aturan 3 detik), supaya pembaca layar mendengar
            "Alihkan 712 kg…", bukan kata "Ringkasan keputusan". Label &
            judul dibungkus satu blok grid supaya jaraknya tidak lagi ikut
            tinggi kotak "Langkah berikutnya" di sebelahnya. */}
        <div className="evidence-hero-head">
          <p className="evidence-hero-eyebrow">Ringkasan keputusan</p>
          <h2 className="evidence-hero-title">{judul}</h2>
        </div>

        {metrik.length > 0 && (
          <dl className="evidence-metrics">
            {metrik.map((item) => (
              <div className="evidence-metric" data-metrik={item.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")} key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
        )}

        {/* Triase: hanya yang benar-benar dinyatakan data yang muncul. */}
        {flags.length > 0 && (
          <div className="evidence-flags">
            <h3 className="evidence-flags-title">Perlu diperhatikan ({flags.length})</h3>
            <ul className="evidence-flags-list">
              {flags.map((flag) => (
                <li className={`evidence-flag evidence-flag-${flag.tone}`} key={flag.id}>
                  <strong className="evidence-flag-label">{flag.label}</strong>
                  <span className="evidence-flag-text">{flag.text}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Ringkasan keputusan: fakta yang dibaca sebagai angka, bukan paragraf.
            Kotak "Langkah berikutnya" dan lipatan "Akibat tiap pilihan" dilepas
            29 Okt 2026 — keduanya milik momen MEMUTUSKAN dan sudah ada di popup
            Recommendations; halaman ini menyimpan buktinya, bukan menawarkan
            tindakan. Status tetap terbaca di kepala keputusan. */}
      </article>

      {/* ── B + C. PERSETUJUAN: KEPUTUSAN LALU JALUR ─────────────────────
          Urutan mengikuti dokumen `02-approval-action.md` §7.1: yang dibaca
          lebih dulu adalah JAWABAN (apa menahan, siapa dibutuhkan, apa yang
          terjadi setelah ini), baru kronologinya. Sebelum 28 Okt 2026 kartu
          jalur berdiri di atas kartu keputusan, sehingga pembaca melihat
          riwayat sebelum tahu apa yang harus dilakukan. */}
      <section className="evidence-block">
        <article className="card evidence-decide jump-target" id="zona-keputusan" data-bagian="keputusan">
          {/* Kepala: judul + aksi berdampingan supaya aksi menempel pada
              statusnya, bukan menggantung di bawah daftar fakta. */}
          <div className="evidence-decide-head">
            <h2>Governance &amp; persetujuan</h2>
            {/* `key` per keputusan: pesan sukses ("Approval tercatat",
                "PO MC-… dibuat") adalah state komponen; tanpa key ia
                menempel ke keputusan BERIKUTNYA saat penyetuju berpindah. */}
            <DecisionActions
              key={selected.decision_id}
              decisionId={selected.decision_id}
              role={role}
              status={selected.status}
              token={token}
              summary={summary}
              izinPersetujuan={false}
            />
          </div>
          {/* Modul persetujuan (dokumen `02-approval-action.md` §7, 28 Okt 2026):
              satu kepala yang menjawab tiga hal (apa menahan · siapa dibutuhkan ·
              apa setelah ini), keadaan keputusan, daftar penyetuju BERJAM, lalu
              tiga langkah dengan alasan tertulis saat tertutup. Ringkasan yang
              belum tiba tidak dirender sebagai keadaan yang seolah diketahui. */}
          {adaRingkasan ? (
            <ApprovalOverview summary={summary} role={role} now={now} />
          ) : (
            <p className="evidence-note" role="status" data-testid="governance-pending">
              Ringkasan persetujuan sedang dimuat — status keputusan di atas tetap
              berasal dari data keputusan, bukan dari panel ini.
            </p>
          )}
        </article>
      </section>

      {/* ── D. BUKTI ────────────────────────────────────────────────────── */}
      <section className="evidence-block jump-target" id="bukti" data-bagian="bukti">
        <h2 className="evidence-block-title">Bukti</h2>
        {/* Dua arti biaya dipisah di satu tempat (Fase 5 butir 5): PO =
            bahan + transportasi + handling (ditagihkan), SDC = PO +
            penalti risiko internal (analitis). Referensi pasar hanya
            pembanding harga bahan, bukan komponen biaya PO. */}
        <DecisionEconomics
          cost={selected?.commercial_cost ?? null}
          market={selected?.market_reference ?? null}
        />
        <div className="evidence-grid">
          <article className="card">
            <h2>Rincian komponen biaya</h2>
            <FactList rows={costFacts({ ...selected, summary })} collapseEmpty />
          </article>

          <article className="card">
            {/* Lencana putusan safety (dokumen `07-safety-evidence.md` §4.2
                butir 2): status + jumlah batch yang diperiksa, keduanya dari
                `approval-summary`. Jumlahnya TIDAK diulang sebagai baris fakta
                (lihat `safetyFacts(..., { countInBadge: true })`) — kecuali
                server tidak mengirim angka yang bermakna, maka barisnya tetap
                tampil dengan "—". */}
            <div className="board-card-head">
              <h2>Keamanan &amp; pemasok</h2>
              {badgeSafety ? (
                <span
                  className={`board-badge board-badge-${badgeSafety.tone}`}
                  data-testid="safety-verdict-badge"
                >
                  {badgeSafety.text}
                </span>
              ) : null}
            </div>
            {/* Pemasok sengaja di urutan ke-4 supaya tetap terlihat saat kartu
                dilipat (foldAfter=4); yang masuk rincian hanya baris pendukung:
                verifikator, nomor material, target eksekusi. */}
            <FactList
              rows={[
                ...faktaSafety.slice(0, 3),
                supplierFact(summary),
                ...faktaSafety.slice(3),
              ]}
              collapseEmpty
              foldAfter={4}
            />
          </article>

          <article className="card">
            <h2>Identitas &amp; tenggat</h2>
            <FactList rows={decisionFacts({ ...selected, summary }, clock)} collapseEmpty />
          </article>
        </div>
        {/* Fase 6 butir 3 & 5: review manusia atas bukti batch. Panel ini
            membaca paket keputusan server (bukan merakit ulang evaluasi) dan
            hanya menambah BUKTI — status dihitung ulang server. */}
        <article className="card">
          <h2>Evaluasi batch</h2>
          <BatchEvaluationTable evaluations={paket?.batch_evaluations} />
        </article>
        <HumanReviewPanel
          decisionId={selected?.decision_id ?? null}
          token={token}
          role={role}
          packet={paket}
          tanpaCatatan
        />

        {/* Penerimaan barang + governance pemasok: keduanya BUKTI pelaksanaan,
            jadi tinggal di blok Bukti yang sama (29 Okt 2026). Sebelumnya dua
            kartu ini mengambang di antara #bukti dan #jejak tanpa wadah —
            jaraknya beda dari kartu lain dan tidak bisa ditautkan. */}
        {/* Fase 9 butir 2 & 4: penerimaan barang. Status & tombol dari server
            (`receipt_gate`), bukan hitungan klien. */}
        <GoodsReceiptDrawer summary={summary} token={token} role={role} />
        {supplierContext && (
          <SupplierExclusionView
            key={selected.decision_id}
            context={supplierContext}
            role={role}
            token={token ?? ""}
            onCreated={onSupplierCreated ?? (() => {})}
            tanpaCatatan
          />
        )}
      </section>


      {/* ── E. JEJAK & INTEGRITAS ───────────────────────────────────────── */}
      <section className="evidence-block evidence-bottom jump-target" id="jejak" data-bagian="jejak">
        {/* "Jejak & riwayat" = SATU lini masa: iterasi keluarga, pengajuan,
            verifikasi, dan tiap keputusan orang (siapa · kapan · versi mana).
            Sebelumnya riwayat iterasi terpisah dari fakta governance sehingga
            penyetuju harus menjahit ceritanya sendiri dari beberapa kartu. */}
        {/* PO milik keputusan ini SAJA. Daftar PO jaringan ada di halaman
            Pemasok; menampilkannya di sini membuat baris milik keputusan lain
            terbaca sebagai milik keputusan yang dibuka. */}
        <article className="card">
          <h2>PO keputusan ini</h2>
          <DecisionPurchaseOrder
            purchaseOrders={purchaseOrders}
            decisionId={selected?.decision_id}
            token={token ?? null}
            decisionStatus={selected?.status ?? null}
          />
        </article>

        <article className="card">
          <h2>Jejak agen keputusan ini</h2>
          {/* Jejak dirender DI SINI, bukan lewat lompatan ke tab Agent Log:
              dossier harus lengkap tanpa berpindah halaman. */}
          <DecisionTraceList traces={traces} />
        </article>

        <article className="card evidence-audit-card">
          <h2>Jejak &amp; riwayat</h2>
          <DecisionAudit events={audit} />
        </article>

        {/* Bukti tersimpan: daftar evidence + rantai Merkle + tanda tangan
            ECDSA + tombol ekspor JSON/CSV. */}
        <IntegrityPanel
          key={selected.decision_id}
          token={token ?? ""}
          decisionId={selected.decision_id}
        />

        <CatatanTeknis />
      </section>
    </>
  );
}
