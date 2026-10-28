"use client";

// DecisionActions — role scope (design.md §1.4): bgn_monitor read-only;
// approve/reject hanya role approver; execute hanya setelah approval.
// §1.3: approve SELALU lewat ringkasan (ApprovalModal).
//
// 2026-10-14 (permintaan Roy): pilihan tindakan TIDAK lagi deretan tombol di
// dalam kartu Governance — kartu itu jadi tinggi dan berdesakan di grid 3
// kolom, dan kotak alasan penolakan melebar di situ. Kini kartu hanya memuat
// SATU tombol pemicu; seluruh pilihan hidup di popup
// (components/Popup.tsx + components/ApprovalMenu.tsx).
//
// Pembagian tugas sengaja: komponen ini satu-satunya pemanggil API (menu hanya
// presentasional, jadi tetap bisa diuji tanpa DOM), dan tiap handler
// mengembalikan pesan galat — menu menampilkan galat itu DI DALAM popup,
// bukan di kartu yang sudah tertutup popup.

import { useEffect, useRef, useState } from "react";
import {
  approveAction,
  approvePurchaseOrder,
  executeAction,
  proposeAction,
  reproposeAction,
  verifyAction,
} from "../lib/api";
import ApprovalMenu from "./ApprovalMenu";
import GovernanceStatus from "./GovernanceStatus";
import { governanceView } from "../lib/governance";
import { langkahPersetujuan, peranSudahSetuju, poDari } from "../lib/approval-panel";
import { humanizeBlocker, statusLabel } from "../lib/bahasa";
import { roleLabel } from "../lib/settings";
import Popup from "./Popup";
import TombolTutup from "./TombolTutup";
// Satu aturan PDF untuk halaman ini dan panel: `bolehUnduhPdf` membaca status
// keputusan (approved/executed), sama seperti tombol di Decision & Evidence.
// Dulu aturan ini hanya hidup di sana, jadi panel yang dipakai saat
// mengeksekusi tidak pernah menawarkan dokumennya.
import { bolehUnduhPdf } from "./PurchaseOrderList";
import { downloadPoPdf } from "../lib/export";

const APPROVER_ROLES = new Set(["sppg_head", "sppg_nutritionist"]);

// Pure helper — satu sumber untuk UI & test (visibleActions).
export function visibleActions(
  role: string,
  status: string
): {
  approve: boolean;
  verify: boolean;
  execute: boolean;
  propose: boolean;
  repropose: boolean;
  readOnly: boolean;
} {
  if (!APPROVER_ROLES.has(role)) {
    return {
      approve: false,
      verify: false,
      execute: false,
      propose: false,
      repropose: false,
      readOnly: true,
    };
  }
  // PLAN.md §13.1/§13.3: approve milik Head DAN Nutritionist (dua approval
  // berbeda user), tetapi verifikasi, eksekusi & ajukan ulang hanya Head.
  const headOnly = role === "sppg_head";
  const dapatDisetujui =
    status === "pending_approval" || status === "verifier_flagged";
  // Eksekusi baru masuk akal setelah kuorum penuh (status `approved`, produk
  // 2A). Sebelumnya tombol ini digantung pada status pra-approval sehingga
  // `approved` tidak pernah punya tombol apa pun.
  const dapatDieksekusi = status === "approved";
  return {
    approve: dapatDisetujui,
    // Verifikasi punya gerbangnya sendiri: dulu menumpang `actions.execute`,
    // sehingga setelah eksekusi dipisah ke status `approved`, tombol
    // Verifikasi ikut hilang dari keputusan yang justru belum diverifikasi.
    verify:
      (status === "proposed" ||
        status === "pending_approval" ||
        status === "verifier_flagged") &&
      headOnly,
    execute: dapatDieksekusi && headOnly,
    // Keputusan yang lahir `proposed` (Event 1/2/3, POST /decisions) belum
    // bisa di-approve sebelum diajukan. Tanpa baris ini keputusan berhenti
    // permanen — audit 18 Okt BLOCKER A1.
    propose: status === "proposed" && headOnly,
    // Rejection loop: keputusan ditolak → agent minta iterasi baru.
    repropose: status === "rejected" && headOnly,
    readOnly: false,
  };
}

/**
 * Kalimat batch untuk gerbang review PO.
 *
 * Backend `POST /actions/purchase-orders/{po}/approve` mengembalikan `dikirim`
 * (batch yang benar-benar berangkat sekarang) dan `ditahan` (batch terikat yang
 * TIDAK berangkat: sudah berangkat, gagal gerbang keselamatan, karantina).
 * Komentar backend tegas: `ditahan` disertakan "supaya UI tidak mengaku semua
 * barang jalan". Dulu UI hanya membaca status PO/keputusan, sehingga keputusan
 * bisa `executed` tanpa satu truk pun bergerak — terukur 29 Okt 2026 pada
 * keputusan bef077a8 (batch b772248c "sudah berangkat").
 *
 * Fungsi murni supaya teks yang sama bisa diuji tanpa DOM.
 */
export function ringkasanBatchPo(result: {
  dikirim?: { batch_id?: string; dispatched_at?: string }[] | null;
  ditahan?: { batch_id?: string; alasan?: string }[] | null;
}): string {
  const dikirim = Array.isArray(result?.dikirim) ? result.dikirim : [];
  const ditahan = Array.isArray(result?.ditahan) ? result.ditahan : [];
  const bagian: string[] = [];
  if (dikirim.length > 0) {
    bagian.push(`${dikirim.length} batch diberangkatkan`);
  }
  if (ditahan.length > 0) {
    const alasan = ditahan
      .map((baris) => (baris?.alasan ?? "").trim())
      .filter(Boolean)
      .slice(0, 2)
      .join("; ");
    bagian.push(`${ditahan.length} batch ditahan${alasan ? `: ${alasan}` : ""}`);
  }
  if (bagian.length === 0) {
    // Tidak ada binding batch pada PO ini — jangan meninggalkan kesan barang
    // berangkat.
    return "Tidak ada batch terikat pada PO ini, jadi tidak ada barang yang diberangkatkan.";
  }
  return `${bagian.join(" · ")}.`;
}

export default function DecisionActions({
  decisionId,
  role,
  status,
  token,
  summary,
  tampil = "dialog",
  terbukaAwal = false,
  izinPersetujuan = true,
}: {
  decisionId: string;
  role: string;
  status: string;
  token: string | null;
  summary?: any;
  /**
   * `dialog` (bawaan): konfirmasi dibuka sebagai jendela sendiri — dipakai di
   * halaman dan panel approval. `panel`: konfirmasi dirender DI DALAM induknya,
   * dipakai saat komponen ini hidup di dalam popup detail keputusan (permintaan
   * pemilik: "tidak ada popup dalam popup"). Jalur mutasinya tetap satu.
   */
  tampil?: "dialog" | "panel";
  /** Panel konfirmasi langsung terbuka (dipakai tombol "Persetujuan" di kartu). */
  terbukaAwal?: boolean;
  /**
   * `false` = halaman ini TIDAK menjalankan persetujuan (29 Okt 2026: approval
   * pindah ke popup Recommendations, lihat `DecisionDrawer`). Tombol setuju /
   * tolak / verifikasi / ajukan ulang disembunyikan; eksekusi & review PO tetap
   * ada karena keduanya langkah pemenuhan, bukan persetujuan. Bila tidak ada
   * yang tersisa, komponen mencetak catatan hanya-baca yang menyebut di mana
   * persetujuan dicatat — bukan tombol yang pasti ditolak.
   */
  izinPersetujuan?: boolean;
}) {
  const [opened, setOpened] = useState(terbukaAwal);
  const [message, setMessage] = useState<string | null>(null);
  // Prop `terbukaAwal` bisa BERUBAH saat popup detail dibuka ulang dengan pilihan
  // lain ("Persetujuan" ↔ "Rincian"). `useState` hanya membaca nilai awal, jadi
  // tanpa sinkronisasi ini panel bisa tertutup padahal diminta, atau terbuka
  // padahal pengguna cuma ingin membaca.
  useEffect(() => {
    setOpened(terbukaAwal);
  }, [terbukaAwal, decisionId]);
  // Tombol pemicu: fokus dikembalikan ke sini saat popup ditutup.
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  // Panel konfirmasi inline (mode `panel`) bisa berada jauh di bawah popup
  // detail; tanpa ini pengguna menekan tombol lalu tidak melihat apa pun.
  const panelRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!opened || tampil !== "panel") return;
    const el = panelRef.current;
    // jsdom tidak menyediakan scrollIntoView; di peramban ia ada. Tanpa penjaga
    // ini membuka panel di tes melempar TypeError.
    if (!el || typeof el.scrollIntoView !== "function") return;
    // Hanya gulir bila panel benar-benar di luar layar. Di popup "Persetujuan"
    // panel sudah berada tepat di bawah pita angka, dan menggulirnya ke atas
    // justru menyembunyikan angka yang menjelaskan keputusan.
    const kotak = el.getBoundingClientRect();
    const tinggi = window.innerHeight || document.documentElement.clientHeight;
    // Patokannya KEPALA panel, bukan dasarnya: panel setinggi layar pasti
    // "melewati bawah", dan mengejar dasarnya justru menyembunyikan konteks.
    // Gulir hanya bila kepala panel di atas layar atau masih di bawahnya.
    if (kotak.top < 0 || kotak.top > tinggi - 120) {
      el.scrollIntoView({ block: "nearest" });
    }
  }, [opened, tampil]);

  // Panel ditutup → pemicunya muncul kembali; fokus harus ikut ke sana, bukan
  // jatuh ke <body>.
  const pernahBuka = useRef(false);
  useEffect(() => {
    if (tampil !== "panel") return;
    if (opened) {
      pernahBuka.current = true;
      return;
    }
    if (pernahBuka.current) triggerRef.current?.focus();
  }, [opened, tampil]);

  const actions = visibleActions(role, status);
  // Satu turunan status untuk label pemicu DAN chip di kepala popup — jangan
  // menghitung dua kali dengan dua aturan berbeda.
  const view = governanceView(summary);
  // Gerbang kedua (dokumen `02-approval-action.md` §6): PO draft menunggu review
  // Kepala SPPG. Kewenangannya tetap keputusan server-side; di sini hanya dibaca.
  const po = poDari(summary);
  const langkah = langkahPersetujuan({ summary, role });
  const reviewTersedia = langkah.reviewPo.tersedia;
  const poDraft = po !== null && po.status === "draft";
  // 29 Okt 2026: di Decision & Evidence persetujuan hanya DIBACA (approval
  // dijalankan dari popup Recommendations). Masking di satu tempat supaya
  // popup, label pemicu, dan gerbang "tidak ada yang bisa dikerjakan" membaca
  // izin yang sama — bukan tiga aturan yang bisa berselisih.
  const izin = izinPersetujuan
    ? actions
    : { ...actions, approve: false, verify: false, propose: false, repropose: false };
  // Dokumen PO hanya sah setelah kuorum penuh; server memakai aturan yang sama,
  // jadi tombol ini tidak pernah menawarkan unduhan yang pasti ditolak 409.
  const pdfTersedia = po !== null && bolehUnduhPdf(status);
  const adaAksiLain = izin.execute || reviewTersedia || pdfTersedia;
  // Langkah 4 (19 Okt 2026): label mengikuti keadaan. "Kelola persetujuan"
  // pada keputusan final menjanjikan pekerjaan yang tidak ada, dan pada
  // keputusan yang baru disetujui sebagian yang ditunggu adalah REKAN.
  // Semua keadaan tetap bisa dibuka — popup tetap satu-satunya gerbang aksi.
  const triggerLabel =
    reviewTersedia
      ? "Review PO"
      : view.state === "selesai" || view.state === "ditolak"
        ? "Lihat hasil"
        : !izinPersetujuan
          ? izin.execute
            ? "Eksekusi"
            : "Lihat hasil"
          : view.state === "sebagian"
            ? peranSudahSetuju(summary, role)
              ? "Menunggu rekan"
              : "Setujui sekarang"
            : poDraft
              ? "Menunggu review PO"
              : "Kelola persetujuan";
  const administrative = [
    "supplier_exclusion",
    "supplier_exclusion_restoration",
  ].includes(summary?.decision_type);
  if (actions.readOnly) {
    // §7.5 (dan temuan F9 audit FE 27 Okt): peran pengawas tidak melihat tombol,
    // tetapi harus tahu KENAPA. Dulu baris ini mencetak kode peran mentah
    // ("Peran bgn_monitor bersifat read-only") — istilah API, bukan bahasa orang.
    return (
      <p className="read-only-note">
        Peran Anda memantau, bukan menyetujui — tampilan hanya-baca
        {roleLabel(role) ? ` (${roleLabel(role)})` : ""}. Tidak ada tombol yang
        hilang di sini: aksi persetujuan memang bukan kewenangan peran Anda, dan
        keputusan tetap bisa dibaca lengkap beserta alasan tertahannya.
      </p>
    );
  }
  // Audit M6 (18 Okt 2026): temuan review-only tidak punya approval maupun
  // eksekusi. Menawarkan "Kelola persetujuan" hanya mengantar ke penolakan.
  if (status === "review_only") {
    return (
      <p className="read-only-note">
        Temuan tinjauan (review-only): tidak ada approval atau eksekusi untuk keputusan ini.
      </p>
    );
  }
  // 29 Okt 2026: halaman ini tidak menjalankan persetujuan, dan tidak ada
  // eksekusi/PO yang tersisa untuk dikerjakan. Jangan tampilkan pemicu yang
  // membuka popup kosong — sebutkan di mana persetujuan dicatat.
  if (!izinPersetujuan && !adaAksiLain) {
    return (
      <p className="read-only-note" data-testid="persetujuan-di-rekomendasi">
        Persetujuan dijalankan dari <strong>Recommendations</strong>; halaman ini
        menyimpan buktinya.
      </p>
    );
  }

  // Setiap handler: `null` = berhasil (menu menutup popup & pesan tampil di
  // kartu), string = galat yang ditampilkan DI DALAM popup.
  // Galat aksi WAJIB menyebut aksi mana yang gagal dan sudah diterjemahkan.
  // Dulu popup menampilkan kalimat server apa adanya ("binding batch/supplier
  // berubah") tanpa konteks: penyetuju tidak tahu itu penolakan eksekusi.
  function galatAksi(judul: string, err: unknown): string {
    const mentah = String((err as any)?.message ?? err ?? "").trim();
    if (!mentah) return judul;
    return `${judul}: ${humanizeBlocker(mentah) ?? mentah}`;
  }
  async function approve(): Promise<string | null> {
    if (!token) return "Login diperlukan";
    try {
      await approveAction(decisionId, true, token);
      setMessage("Approval tercatat");
      return null;
    } catch (err: any) {
      return galatAksi("Persetujuan tidak tercatat", err);
    }
  }

  async function reject(reason: string): Promise<string | null> {
    if (!reason.trim()) {
      return "Alasan penolakan wajib diisi — ini bahan learning agent.";
    }
    if (!token) return "Login diperlukan";
    try {
      await approveAction(decisionId, false, token, reason.trim());
      setMessage("Keputusan ditolak — agent bisa re-propose dengan iterasi baru.");
      return null;
    } catch (err: any) {
      return galatAksi("Penolakan tidak tercatat", err);
    }
  }

  async function ajukan(): Promise<string | null> {
    if (!token) return "Login diperlukan";
    try {
      await proposeAction(decisionId, null, token);
      setMessage(
        "Keputusan diajukan — menunggu persetujuan Ahli Gizi dan Kepala SPPG."
      );
      return null;
    } catch (err: any) {
      return galatAksi("Pengajuan gagal", err);
    }
  }

  async function repropose(): Promise<string | null> {
    if (!token) return "Login diperlukan";
    try {
      const result = await reproposeAction(decisionId, token);
      setMessage(
        `Iterasi v${result.iteration ?? "?"} dibuat — menunggu verifikasi & approval.`
      );
      return null;
    } catch (err: any) {
      return galatAksi("Re-propose gagal", err);
    }
  }

  async function execute(): Promise<string | null> {
    if (!token) return "Login diperlukan";
    try {
      const result = await executeAction(decisionId, token);
      if (administrative) {
        setMessage(
          `Status administratif pemasok tercatat: ${statusLabel(result.status) ?? "dieksekusi"}. Keamanan batch tidak diubah.`
        );
      } else if (result.po_status === "draft" || result.awaiting === "po_review") {
        // Dua gerbang (dokumen 02-approval-action.md §6): eksekusi berhenti di
        // dokumen draft. Pesan lama "PO dibuat (mock)" membuat penyetuju
        // mengira pembelian sudah terjadi.
        setMessage(
          `PO ${result.po_number ?? ""} terbit sebagai DRAFT — menunggu review Kepala SPPG sebelum dikirim ke SAP.`
        );
      } else {
        setMessage(`PO ${result.po_number ?? ""} dibuat (mock)`);
      }
      return null;
    } catch (err: any) {
      return galatAksi("Eksekusi tidak dijalankan", err);
    }
  }

  /** Gerbang 2 — Kepala SPPG mereview PO draft; PO lalu dikirim ke SAP mock. */
  async function reviewPo(): Promise<string | null> {
    if (!token) return "Login diperlukan";
    if (!po) return "Belum ada PO untuk direview";
    try {
      const result = await approvePurchaseOrder(po.po_number, token);
      setMessage(
        `PO ${result.po_number ?? po.po_number} terkirim ke SAP (status ${
          result.po_status ?? "submitted"
        }) — keputusan menjadi ${result.decision_status ?? "executed"}. ` +
          ringkasanBatchPo(result)
      );
      return null;
    } catch (err: any) {
      return galatAksi("Review PO tidak tercatat", err);
    }
  }

  /**
   * Unduh dokumen PO (PDF) dari panel — permintaan pemilik 29 Okt 2026: setelah
   * eksekusi, dokumennya harus bisa diambil di tempat orang mengeksekusi, bukan
   * hanya di kartu "PO keputusan ini" yang jauh di halaman lain.
   */
  async function unduhDokumenPo(): Promise<string | null> {
    if (!token) return "Login diperlukan";
    if (!po) return "Belum ada PO untuk diunduh";
    try {
      const nama = await downloadPoPdf(po.po_number, token);
      setMessage(`Dokumen PO tersimpan: ${nama}`);
      return null;
    } catch (err: any) {
      return galatAksi("Dokumen PO gagal diunduh", err);
    }
  }

  async function verify(): Promise<string | null> {
    if (!token) return "Login diperlukan";
    try {
      // O-SEC-3: server menurunkan verdict independen; UI hanya memicu
      // verifikasi dan menampilkan hasil server apa adanya.
      const result = await verifyAction(decisionId, token);
      // Audit M1 (18 Okt 2026): UNAVAILABLE bukan verifikasi. Server tidak
      // mencatatnya, jadi UI tidak boleh menjanjikan jalan ke eksekusi.
      if (result.recorded === false) {
        setMessage(
          `Verifier (${result.provider ?? "tanpa provider"}): ${verdictManusia(result.verdict)} — belum ada hasil audit, jadi belum dihitung sebagai verifikasi. Tombol Setuju tetap terkunci sampai verifier memberi hasil.`
        );
      } else {
        setMessage(
          `Verifier (${result.provider ?? "tanpa provider"}): ${verdictManusia(result.verdict)} — hasil audit tercatat; keputusan siap dieksekusi setelah persetujuan lengkap.`
        );
      }
      return null;
    } catch (err: any) {
      return galatAksi("Verifikasi gagal", err);
    }
  }

  const menu = (
    <ApprovalMenu
      summary={summary}
      actions={izin}
      administrative={administrative}
      canReviewPo={reviewTersedia}
      poNumber={po?.po_number ?? null}
      pdfNumber={pdfTersedia ? po?.po_number ?? null : null}
      onUnduhPdf={unduhDokumenPo}
      onReviewPo={reviewPo}
      onApprove={approve}
      onReject={reject}
      onVerify={verify}
      onPropose={ajukan}
      onExecute={execute}
      onRepropose={repropose}
      onClose={() => setOpened(false)}
      dalamPanel={tampil === "panel"}
    />
  );

  return (
    <div className="decision-actions">
      {/* Saat panel inline terbuka, tombol pemicu disembunyikan: panelnya sudah
          punya "Tutup panel", dan dua kontrol untuk hal yang sama membingungkan
          (terutama di popup "Persetujuan" yang membuka panel sejak awal). */}
      {tampil === "panel" && opened ? null : (
      <button
        type="button"
        ref={triggerRef}
        className="button"
        onClick={() => setOpened((v) => !v)}
        // Di dalam popup detail, konfirmasi tidak lagi membuka jendela baru.
        aria-haspopup={tampil === "panel" ? undefined : "dialog"}
        aria-expanded={opened}
        aria-controls={tampil === "panel" ? "aksi-panel" : undefined}
        aria-describedby="governance-action-hint"
      >
        {triggerLabel}
        <span aria-hidden="true">…</span>
      </button>
      )}
      {/* Dulu ini teks terlihat di bawah tombol dan mengulang isi deskripsi
          popup — satu baris noise di kartu yang sempit. Janji "tidak ada aksi
          satu klik" tetap diumumkan ke pembaca layar lewat aria-describedby. */}
      <span className="sr-only" id="governance-action-hint">
        Ringkasan bukti dan pilihan tindakan dibuka di jendela terpisah. Tidak ada aksi satu klik.
      </span>
      {message && (
        <p className="action-message" role="status">
          {humanizeBlocker(message) ?? message}
        </p>
      )}
      {tampil === "panel" ? (
        opened ? (
          <div className="aksi-panel" id="aksi-panel" ref={panelRef} role="group" aria-label="Governance & persetujuan">
            <div className="aksi-panel-head">
              <span className="detail-h">Governance &amp; persetujuan</span>
              {/* 29 Okt 2026 (permintaan pemilik): penutup panel jadi X bulat,
                  bukan tombol teks "Tutup panel". Teks di kepala panel memakan
                  lebar yang dibutuhkan judul, dan "tutup" bukan keputusan —
                  tidak perlu bobot tombol sekunder. Label tetap ada untuk
                  pembaca layar + tooltip. */}
              <TombolTutup
                className="aksi-panel-close"
                label="Tutup panel"
                size={14}
                onClick={() => setOpened(false)}
              />
            </div>
            {/* Chip status tidak diulang di sini: ringkasan bukti tepat di
                bawahnya sudah mencetak Status ("Menunggu persetujuan"), syarat
                ("2 persetujuan"), dan peran yang kurang. Tiga kali kalimat yang
                sama dalam satu layar justru terbaca sebagai berisik. */}
            {menu}
          </div>
        ) : null
      ) : (
        <Popup
          open={opened}
          onClose={() => setOpened(false)}
          className="popup-governance"
          title={"Governance & persetujuan"}
          description={`Keputusan ${String(decisionId).slice(0, 8)} · ${String(
            summary?.decision_type ?? "keputusan"
          ).replace(/_/g, " ")} — periksa ringkasan bukti sebelum menyetujui.`}
          labelledBy="approval-popup-title"
          returnFocusRef={triggerRef}
        >
          {/* Chip status di kepala popup: pengguna yang menggulir ringkasan
              panjang tetap tahu posisi persetujuan tanpa menutup popup. */}
          <GovernanceStatus view={view} variant="chip" />
          {menu}
        </Popup>
      )}
    </div>
  );
}

/** Verdict verifier → kata di layar (jangan cetak enum backend). */
function verdictManusia(verdict: unknown): string {
  switch (String(verdict ?? "")) {
    case "consistent":
      return "konsisten";
    case "flagged":
      return "ditandai perlu diperiksa";
    case "unavailable":
      return "belum tersedia";
    default:
      return verdict ? String(verdict) : "belum tersedia";
  }
}
