"use client";

// Halaman "Decision & Evidence" — bukti SATU keputusan.
//
// Desain ulang 17 Okt 2026 (keluhan user: "tampilannya sangat kurang"; riset pola
// + rujukan di `_qa/rencana-decision-evidence-v2.md`). Susunannya sekarang
// mengikuti cara manusia mengambil keputusan, bukan urutan tabel database:
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
// Aturan lama yang TETAP: nilai tak diketahui ditulis "—" (tidak dikarang), gating
// approval tidak diubah, kotak bukti `.integrity-trust` tetap satu tempat (kini
// bertema terang, 19 Okt 2026), kelas tes-sensitif
// (`.map-*`, `.side-tab*`, `.board-table-wrap`) tidak disentuh.

import DecisionActions from "./DecisionActions";
import { caseLabelOf } from "./RecommendationCard";
import DecisionAudit from "./DecisionAudit";
import IntegrityPanel from "./IntegrityPanel";
import PageHeader from "./PageHeader";
import SectionJump from "./SectionJump";
import { evidenceSections } from "../lib/section-jump";
import { SupplierExclusionView } from "./SupplierExclusionPanel";
// Fase 9 butir 2 & 4: status penerimaan barang satu keputusan — tombolnya
// mengikuti `receipt_gate` server (`can_receive`/`can_quarantine`).
import GoodsReceiptDrawer from "./GoodsReceiptDrawer";
import { dueLabel, pendingDecisions, type TodayDecision } from "../lib/today";
import { decisionGroups, statusWord } from "../lib/decision-picker";
import DecisionPicker from "./DecisionPicker";
import { countActionable, countExpiredActionable } from "../lib/topbar";
import { shortId } from "../lib/agent-quality";
import type { SupplierContext } from "../lib/supplier-exclusions";
import {
  approvalFacts,
  approvalRoute,
  attentionFlags,
  auditTimeline,
  butuhTindakan,
  consequences,
  costFacts,
  decisionFacts,
  decisionHeadline,
  decisionMetrics,
  nextStep,
  safetyFacts,
  supplierFact,
  windowUsage,
  zonaShortcut,
  type ZonaPosisi,
} from "../lib/evidence";
import { downloadDossier } from "../lib/export";
import FactList from "./FactList";
import DecisionEconomics from "./DecisionEconomics";
import GovernanceStatus from "./GovernanceStatus";
import HumanReviewPanel from "./HumanReviewPanel";
import BatchEvaluationTable from "./BatchEvaluationTable";
import { fetchDecisionPacket } from "../lib/api";
import { governanceView } from "../lib/governance";
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

// Penanda langkah rute. Bentuknya BUKAN satu-satunya pembawa arti: teks keadaan
// dibacakan lewat `.sr-only`, jadi warna/bentuk saja tidak pernah jadi kuncinya.
const ROUTE_MARKS: Record<string, string> = {
  done: "✓",
  current: "●",
  waiting: "○",
  blocked: "✕",
};
const ROUTE_STATE_WORDS: Record<string, string> = {
  done: "selesai",
  current: "sedang di sini",
  waiting: "menunggu",
  blocked: "terhalang",
};

// Navigasi "Bagian" halaman ini datang dari lib/section-jump.ts (satu daftar
// untuk nav DAN untuk uji), bukan konstanta lokal yang bisa menyimpang.

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
  loading = false,
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
  /**
   * Daftar keputusan masih diambil dari API. Tanpa ini, tautan yang dibagikan
   * sempat dituduh "tidak ada di cakupan" padahal datanya belum tiba.
   */
  loading?: boolean;
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
  const langkah = nextStep({ role, status: String(selected?.status ?? ""), summary });
  const konsekuensi = consequences({ decision: selected, summary });
  const judul = decisionHeadline(selected, summary);
  const metrik = decisionMetrics(selected, summary, now);
  // Ringkasan persetujuan datang dari API terpisah (ikut poll 5 detik). Saat
  // belum tiba, `attentionFlags` hanya bisa menyimpulkan "belum diverifikasi"
  // dan menampilkan "(1)" padahal data aslinya tiga temuan — angka karangan.
  // Jadi daftar temuan baru disusun setelah ringkasan benar-benar ada.
  const adaRingkasan =
    Boolean(summary) && typeof summary === "object" && Object.keys(summary as object).length > 0;
  const flags = adaRingkasan ? attentionFlags({ decision: selected, summary }) : [];
  const rute = approvalRoute({ decision: selected, summary, now });
  const audit = auditTimeline({ decision: selected, summary, chain });
  const umur = windowUsage({
    created_at: selected?.created_at,
    expires_at: selected?.expires_at,
    now: now ?? null,
  });
  const statusKey = String(selected?.status ?? "").toLowerCase();
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

  // ── F3: bar aksi saat zona keputusan sudah tergulir keluar layar ───────────
  // Pengukuran sebelum redesign: tombol "Kelola persetujuan…" berada di y≈1155
  // pada viewport 900 — 255 px di bawah lipatan. Bar ini hanya MENGANTAR ke
  // kontrol yang sama (#zona-keputusan); ia tidak pernah menggandakan aksi,
  // supaya tidak ada dua jalur mutasi yang bisa berlomba.
  // ── Posisi zona keputusan (pintasan ↓ / ↑) ────────────────────────────────
  // Penanda "bagian mana yang sedang dibaca" untuk nav TIDAK lagi di sini: ia
  // pindah ke komponen bersama `SectionJump` (lihat lib/hooks/useActiveSection)
  // supaya halaman lain memakai pengukur yang sama. Yang tersisa di sini hanya
  // pertanyaan yang khas halaman ini — apakah zona keputusan ada di bawah
  // lipatan, sedang terbaca, atau sudah dilewati — jadi tidak ada dua pengamat
  // yang menjawab pertanyaan yang sama.
  const [zonaPosisi, setZonaPosisi] = useState<ZonaPosisi>("terlihat");

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

  useEffect(() => {
    if (!selected?.decision_id) return;
    let raf = 0;
    const ukur = () => {
      raf = 0;

      // Posisi zona keputusan: di bawah lipatan (pintasan ↓), sedang terbaca
      // (pintasan disembunyikan total), atau sudah dilewati (pintasan ↑).
      // "Terbaca" = setidaknya separuh panelnya berada di antara bar atas (96 px)
      // dan dasar layar. Ambang separuh dipilih supaya pintasan tetap muncul di
      // puncak halaman, saat panelnya cuma mengintip beberapa puluh piksel di
      // dasar layar — di situlah pintasan paling dibutuhkan.
      const zona = document.getElementById("zona-keputusan");
      if (zona) {
        const kotak = zona.getBoundingClientRect();
        const atasLayar = 96;
        const dasarLayar = window.innerHeight;
        const tampak = Math.min(kotak.bottom, dasarLayar) - Math.max(kotak.top, atasLayar);
        const ruang = Math.min(kotak.height || 1, dasarLayar - atasLayar) || 1;
        let posisi: ZonaPosisi;
        if (kotak.bottom <= atasLayar) posisi = "lewat";
        else if (kotak.top >= dasarLayar) posisi = "bawah";
        else if (tampak / ruang >= 0.5) posisi = "terlihat";
        else posisi = kotak.top > atasLayar ? "bawah" : "lewat";
        setZonaPosisi((sebelum) => (sebelum === posisi ? sebelum : posisi));
      }
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(ukur);
    };
    ukur();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [selected?.decision_id]);

  // Peran pengawas tidak punya aksi, dan keputusan yang sudah selesai tidak
  // menunggu siapa pun. Pintasan bawah hanya muncul kalau memang ada
  // persetujuan yang tertunda untuk peran ini (permintaan pemilik 20 Okt 2026).
  const perluTindakan = butuhTindakan({
    role,
    status: statusKey,
    summary,
  });
  const ringkasanGov = (summary ?? {}) as Record<string, unknown>;
  const jumlahSetuju = Array.isArray(ringkasanGov.approvals)
    ? (ringkasanGov.approvals as unknown[]).length
    : null;
  const ambangSetuju = Number((ringkasanGov.approval_requirement as Record<string, unknown> | undefined)?.min_approvals);
  const hitunganSetuju =
    jumlahSetuju !== null && Number.isFinite(ambangSetuju)
      ? `${jumlahSetuju} dari ${ambangSetuju} persetujuan`
      : null;

  return (
    <section className="evidence-page">
      <PageHeader
        title="Decision & Evidence"
        description="Satu keputusan, seluruh buktinya — biaya, keamanan, pemasok, persetujuan, riwayat, dan bukti tersimpan. Semua angka di halaman ini datang dari API."
        meta={
          // Pemilih keputusan: dulu tanpa label (hanya opsi "— pilih keputusan —")
          // dan tanpa konteks jumlah, sehingga pengguna tidak tahu ada berapa
          // keputusan dan mana yang menunggu tindakan. Label terlihat + kalimat
          // jumlah di bawahnya menjawab itu, dan angkanya dari SATU sumber yang
          // sama dengan lonceng notifikasi (countActionable).
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
        }
      />

      {/* F2: navigasi bagian — pengganti "gulir 3.000 px lalu menebak".
          Komponen bersama (juga dipakai Overview & Keamanan Pangan); tautannya
          <a>, bukan tombol, supaya bisa dibuka di tab baru dan terbaca pembaca
          layar sebagai daftar tujuan. */}
      {selected && !loading && <SectionJump items={evidenceSections()} />}

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
            {selectedId ? "Keputusan itu tidak ada di cakupan akun ini" : "Belum ada keputusan dipilih"}
          </h2>
          <p className="evidence-note">
            {selectedId
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
        <>
          {/* ── A. KEPALA KEPUTUSAN ─────────────────────────────────────────── */}
          <article className="card evidence-hero jump-target" id="ringkasan" data-status={statusKey}>
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
                <a className="evidence-hero-jump" href="#zona-keputusan">
                  Ke zona keputusan
                  <span aria-hidden="true"> ↓</span>
                </a>
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

            {/* Satu kalimat "apa yang harus saya lakukan" (lib/evidence.nextStep). */}
            <div className={`evidence-next evidence-next-${langkah.tone}`} role="status">
              <span className="evidence-next-label">Langkah berikutnya</span>
              <p className="evidence-next-text">{langkah.text}</p>
            </div>

            {/* Akibat tiap pilihan — dilipat (F1) supaya kepala keputusan tidak
                memanjang. Ringkasan menyebut kedua cabang, dan tidak ada angka
                yang hanya hidup di dalam lipatan: angkanya dari strip metrik. */}
            <details className="evidence-consequence">
              <summary className="evidence-consequence-summary">
                Akibat tiap pilihan
                <span className="evidence-consequence-hint">disetujui / ditolak</span>
              </summary>
              <dl className="evidence-consequence-list">
                <div className="evidence-consequence-row">
                  <dt>Kalau disetujui</dt>
                  <dd>{konsekuensi.approve}</dd>
                </div>
                <div className="evidence-consequence-row">
                  <dt>Kalau ditolak</dt>
                  <dd>{konsekuensi.reject}</dd>
                </div>
              </dl>
            </details>

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
          </article>

          {/* ── B + C. PERSETUJUAN: JALUR & KEPUTUSAN ────────────────────────
              Satu panel, bukan dua kartu: "menunggu siapa" (jalur) dan "apa
              yang bisa saya lakukan" (kontrol) adalah satu cerita. Bingkai
              kedua hanya menambah garis dan jarak tanpa menambah arti. */}
          <section className="evidence-block jump-target" id="rute">
          <article className="card evidence-route">
            <h2>Jalur persetujuan</h2>
            {rute.length === 0 ? (
              <p className="evidence-note">
                Belum ada langkah yang bisa dibaca untuk keputusan ini.
              </p>
            ) : (
              <ol className="evidence-route-steps">
                {rute.map((step) => (
                  <li className={`evidence-route-step evidence-route-${step.state}`} key={step.id}>
                    <span className="evidence-route-mark" aria-hidden="true">
                      {ROUTE_MARKS[step.state]}
                    </span>
                    <span className="evidence-route-body">
                      <span className="evidence-route-label">{step.label}</span>
                      <span className="evidence-route-detail">{step.detail}</span>
                    </span>
                    <span className="sr-only">Keadaan langkah: {ROUTE_STATE_WORDS[step.state]}</span>
                  </li>
                ))}
              </ol>
            )}
          </article>

          <article className="card evidence-decide jump-target" id="zona-keputusan">
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
              />
            </div>
            {/* Ringkasan belum tiba ≠ "Menunggu persetujuan". Dulu
                `governanceView(null)` menghasilkan chip Menunggu padahal lencana
                keputusan di atas sudah "disetujui" — layar menyatakan dua hal
                berbeda tentang satu keputusan. Sekarang keadaan memuat disebut
                apa adanya. */}
            {adaRingkasan ? (
              <GovernanceStatus view={governanceView(summary)} />
            ) : (
              <p className="evidence-note" role="status" data-testid="governance-pending">
                Ringkasan persetujuan sedang dimuat — status keputusan di atas tetap
                berasal dari data keputusan, bukan dari panel ini.
              </p>
            )}
            {/* "Alasan tertahan" & "Peran penyetuju" pindah ke GovernanceStatus
                (satu fakta satu tempat); sisanya tetap dari approvalFacts. */}
            <FactList
              rows={approvalFacts(summary).filter(
                (row) => row.label !== "Alasan tertahan" && row.label !== "Peran penyetuju"
              )}
            />
          </article>
          </section>

          {/* ── D. BUKTI ────────────────────────────────────────────────────── */}
          <section className="evidence-block jump-target" id="bukti">
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
              <h2>Keamanan &amp; pemasok</h2>
              {/* Pemasok sengaja di urutan ke-4 supaya tetap terlihat saat kartu
                  dilipat (foldAfter=4); yang masuk rincian hanya baris pendukung:
                  verifikator, nomor material, target eksekusi. */}
              <FactList
                rows={[
                  ...safetyFacts(summary).slice(0, 3),
                  supplierFact(summary),
                  ...safetyFacts(summary).slice(3),
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
            />
          </section>

          {/* Form pengecualian pemasok (governance) tampil lebar penuh setelah bukti. */}
          {/* Fase 9 butir 2 & 4: penerimaan barang. Status & tombol dari server
              (`receipt_gate`), bukan hitungan klien. */}
          {selected ? (
            <GoodsReceiptDrawer summary={summary} token={token} role={role} />
          ) : null}
          {supplierContext && (
            <SupplierExclusionView
              key={selected.decision_id}
              context={supplierContext}
              role={role}
              token={token ?? ""}
              onCreated={onSupplierCreated ?? (() => {})}
            />
          )}

          {/* ── E. JEJAK & INTEGRITAS ───────────────────────────────────────── */}
          <section className="evidence-block evidence-bottom jump-target" id="jejak">
            {/* "Jejak & riwayat" = SATU lini masa: iterasi keluarga, pengajuan,
                verifikasi, dan tiap keputusan orang (siapa · kapan · versi mana).
                Sebelumnya riwayat iterasi terpisah dari fakta governance sehingga
                penyetuju harus menjahit ceritanya sendiri dari beberapa kartu. */}
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
          </section>
        </>
      )}

      {/* F3: hanya pintasan, bukan aksi kedua — kontrol yang sama tetap di
          #zona-keputusan. Muncul HANYA kalau persetujuan memang tertunda untuk
          peran ini, dan disembunyikan saat zonanya sedang terlihat. Panahnya
          mengikuti posisi zona: ↓ saat masih di bawah, ↑ saat sudah dilewati. */}
      {selected && perluTindakan && zonaPosisi !== "terlihat" && (
        <div
          className="evidence-actionbar"
          role="region"
          aria-label={zonaShortcut(zonaPosisi).label}
          data-tone={STATUS_TONES[statusKey] ?? "neutral"}
        >
          {/* Titik nada + dua baris teks: keadaan dulu (yang menentukan apakah
              ada yang bisa dikerjakan), lalu hitungan approval sebagai detail.
              Sebelumnya satu baris abu-abu "status · hitungan" — dua informasi
              berbeda bobotnya disamakan. */}
          <span className="evidence-actionbar-state">
            <span className="evidence-actionbar-dot" aria-hidden="true" />
            <span className="evidence-actionbar-text">
              <strong>{statusWord(selected.status)}</strong>
              {hitunganSetuju ? <span>{hitunganSetuju}</span> : null}
            </span>
          </span>
          <a className="button button-primary evidence-actionbar-link" href="#zona-keputusan">
            {zonaShortcut(zonaPosisi).text}
            <span aria-hidden="true"> {zonaShortcut(zonaPosisi).arrow}</span>
          </a>
        </div>
      )}
    </section>
  );
}
