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
// approval tidak diubah, kartu gelap `.integrity-trust` tetap, kelas tes-sensitif
// (`.map-*`, `.side-tab*`, `.board-table-wrap`) tidak disentuh.

import DecisionActions from "./DecisionActions";
import { caseLabelOf } from "./RecommendationCard";
import DecisionAudit from "./DecisionAudit";
import IntegrityPanel from "./IntegrityPanel";
import PageHeader from "./PageHeader";
import { SupplierExclusionView } from "./SupplierExclusionPanel";
import { dueLabel, pendingDecisions, type TodayDecision } from "../lib/today";
import { decisionGroups, statusWord } from "../lib/decision-picker";
import { countActionable, countExpiredActionable } from "../lib/topbar";
import { shortId } from "../lib/agent-quality";
import type { SupplierContext } from "../lib/supplier-exclusions";
import {
  approvalFacts,
  approvalRoute,
  attentionFlags,
  auditTimeline,
  consequences,
  costFacts,
  decisionFacts,
  decisionHeadline,
  decisionMetrics,
  nextStep,
  safetyFacts,
  supplierFact,
  windowUsage,
} from "../lib/evidence";
import { downloadDossier } from "../lib/export";
import FactList from "./FactList";
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
  const flags = attentionFlags({ decision: selected, summary });
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
  const [zonaTerlihat, setZonaTerlihat] = useState(true);
  useEffect(() => {
    if (!selected?.decision_id) return;
    const el = document.getElementById("zona-keputusan");
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([entry]) => setZonaTerlihat(entry.isIntersecting), {
      rootMargin: "-96px 0px 0px 0px",
    });
    io.observe(el);
    return () => io.disconnect();
  }, [selected?.decision_id]);

  // Peran pengawas mendapat kalimat "bersifat pengawasan" (nextStep → tone muted);
  // untuk mereka bar aksi tidak muncul karena memang tidak ada aksi yang boleh.
  const bolehBertindak = langkah.tone !== "muted";
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
        description="Satu keputusan, seluruh buktinya — dari permintaan sampai tanda tangan: biaya, keamanan, pemasok, persetujuan, riwayat iterasi, dan bukti tersimpan. Semua angka di halaman ini datang dari API."
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
            <span className="evidence-picker-hint">
              {countActionable(decisions, now, role)} menunggu tindakan
              {expiredCount > 0
                ? showExpired
                  ? ` · ${expiredCount} lewat tenggat ditampilkan`
                  : ` · ${expiredCount} lewat tenggat disembunyikan`
                : ""}{" "}
              · {decisions.length} keputusan tersedia
            </span>
          </div>
        }
      />

      {/* F2: navigasi bagian — pengganti "gulir 3.000 px lalu menebak".
          Tautan biasa (bukan tombol) supaya bisa dibuka di tab baru dan
          terbaca pembaca layar sebagai daftar tujuan. */}
      {selected && !loading && (
        <nav className="evidence-jump" aria-label="Lompat ke bagian halaman">
          <span className="evidence-jump-label">Bagian</span>
          <ul className="evidence-jump-list">
            {[
              ["ringkasan", "Ringkasan"],
              ["rute", "Jalur persetujuan"],
              ["zona-keputusan", "Keputusan"],
              ["bukti", "Bukti"],
              ["jejak", "Jejak & integritas"],
            ].map(([id, label]) => (
              <li key={id}>
                <a className="badge evidence-jump-link" href={`#${id}`}>
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      )}

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
          <article className="card evidence-hero" id="ringkasan">
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
                  menampilkan "29 mnt lagi" membuatnya tampak menunggu sesuatu. */}
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

            <h2 className="evidence-hero-heading">Ringkasan keputusan</h2>
            {/* Judul = AKTIONYA, bukan label jenis keputusan (aturan 3 detik). */}
            <p className="evidence-hero-title">{judul}</p>

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

          {/* ── B. JALUR PERSETUJUAN ────────────────────────────────────────── */}
          <article className="card evidence-route" id="rute">
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

          {/* ── C. ZONA KEPUTUSAN ───────────────────────────────────────────── */}
          <article className="card evidence-decide" id="zona-keputusan">
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

          {/* ── D. BUKTI ────────────────────────────────────────────────────── */}
          <div className="evidence-grid" id="bukti">
            <article className="card">
              <h2>Biaya</h2>
              <FactList rows={costFacts({ ...selected, summary })} collapseEmpty />
            </article>

            <article className="card">
              <h2>Keamanan &amp; pemasok</h2>
              <FactList rows={[...safetyFacts(summary), supplierFact(summary)]} collapseEmpty />
            </article>

            <article className="card">
              <h2>Identitas &amp; tenggat</h2>
              <FactList rows={decisionFacts({ ...selected, summary }, clock)} collapseEmpty />
            </article>
          </div>

          {/* Form pengecualian pemasok (governance) tampil lebar penuh setelah bukti. */}
          {supplierContext && (
            <SupplierExclusionView
              key={selected.decision_id}
              context={supplierContext}
              role={role}
              token={token ?? ""}
              onCreated={onSupplierCreated ?? (() => {})}
            />
          )}

          {/* ── E. JEJAK ────────────────────────────────────────────────────── */}
          <div className="evidence-bottom">
            {/* "Jejak & riwayat" = SATU lini masa: iterasi keluarga, pengajuan,
                verifikasi, dan tiap keputusan orang (siapa · kapan · versi mana).
                Sebelumnya riwayat iterasi terpisah dari fakta governance sehingga
                penyetuju harus menjahit ceritanya sendiri dari beberapa kartu. */}
            <article className="card evidence-audit-card" id="jejak">
              <h2>Jejak &amp; riwayat</h2>
              <DecisionAudit events={audit} />
            </article>

            {/* Bukti tersimpan: daftar evidence + rantai Merkle + tanda tangan
                ECDSA + tombol ekspor JSON/CSV. */}
            <IntegrityPanel token={token ?? ""} decisionId={selected.decision_id} />
          </div>
        </>
      )}

      {/* F3: hanya pintasan, bukan aksi kedua — kontrol yang sama tetap di
          #zona-keputusan. Disembunyikan saat zona itu terlihat, dan untuk peran
          pengawas yang memang tidak punya aksi. */}
      {selected && bolehBertindak && !zonaTerlihat && (
        <div className="evidence-actionbar" role="region" aria-label="Pintasan ke zona keputusan">
          <span className="evidence-actionbar-text">
            {statusWord(selected.status)}
            {hitunganSetuju ? ` · ${hitunganSetuju}` : ""}
          </span>
          <a className="button button-primary evidence-actionbar-link" href="#zona-keputusan">
            Ke zona keputusan
          </a>
        </div>
      )}
    </section>
  );
}
