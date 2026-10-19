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

import { useRef, useState } from "react";
import {
  approveAction,
  executeAction,
  proposeAction,
  reproposeAction,
  verifyAction,
} from "../lib/api";
import ApprovalMenu from "./ApprovalMenu";
import GovernanceStatus from "./GovernanceStatus";
import { governanceView } from "../lib/governance";
import { humanizeBlocker } from "../lib/bahasa";
import Popup from "./Popup";

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

export default function DecisionActions({
  decisionId,
  role,
  status,
  token,
  summary,
}: {
  decisionId: string;
  role: string;
  status: string;
  token: string | null;
  summary?: any;
}) {
  const [opened, setOpened] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  // Tombol pemicu: fokus dikembalikan ke sini saat popup ditutup.
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const actions = visibleActions(role, status);
  // Satu turunan status untuk label pemicu DAN chip di kepala popup — jangan
  // menghitung dua kali dengan dua aturan berbeda.
  const view = governanceView(summary);
  // Langkah 4 (19 Okt 2026): label mengikuti keadaan. "Kelola persetujuan"
  // pada keputusan final menjanjikan pekerjaan yang tidak ada, dan pada
  // keputusan yang baru disetujui sebagian yang ditunggu adalah REKAN.
  // Semua keadaan tetap bisa dibuka — popup tetap satu-satunya gerbang aksi.
  const triggerLabel =
    view.state === "selesai" || view.state === "ditolak"
      ? "Lihat hasil"
      : view.state === "sebagian"
        ? "Menunggu rekan"
        : "Kelola persetujuan";
  const administrative = [
    "supplier_exclusion",
    "supplier_exclusion_restoration",
  ].includes(summary?.decision_type);
  if (actions.readOnly) {
    return <p className="read-only-note">Peran {role} bersifat read-only.</p>;
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

  // Setiap handler: `null` = berhasil (menu menutup popup & pesan tampil di
  // kartu), string = galat yang ditampilkan DI DALAM popup.
  async function approve(): Promise<string | null> {
    if (!token) return "Login diperlukan";
    try {
      await approveAction(decisionId, true, token);
      setMessage("Approval tercatat");
      return null;
    } catch (err: any) {
      return String(err.message ?? err);
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
      return String(err.message ?? err);
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
      return String(err.message ?? err);
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
      return String(err.message ?? err);
    }
  }

  async function execute(): Promise<string | null> {
    if (!token) return "Login diperlukan";
    try {
      const result = await executeAction(decisionId, token);
      setMessage(
        administrative
          ? `Status administratif supplier tercatat: ${result.status ?? "executed"}. Safety batch tidak diubah.`
          : `PO ${result.po_number ?? ""} dibuat (mock)`
      );
      return null;
    } catch (err: any) {
      return String(err.message ?? err);
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
          `Verifier (${result.provider ?? "tanpa provider"}): ${result.verdict ?? "tidak tersedia"} — tidak ada verdict hasil audit, jadi belum dihitung sebagai verifikasi. Setuju tetap terkunci sampai verifier memberi hasil.`
        );
      } else {
        setMessage(
          `Verifier (${result.provider ?? "tanpa provider"}): ${result.verdict ?? "tidak tersedia"} — verdict tercatat, keputusan siap dieksekusi setelah approval terpenuhi.`
        );
      }
      return null;
    } catch (err: any) {
      return String(err.message ?? err);
    }
  }

  return (
    <div className="decision-actions">
      <button
        type="button"
        ref={triggerRef}
        className="button"
        onClick={() => setOpened(true)}
        aria-haspopup="dialog"
        aria-expanded={opened}
        aria-describedby="governance-action-hint"
      >
        {triggerLabel}
        <span aria-hidden="true">…</span>
      </button>
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
        <ApprovalMenu
          summary={summary}
          actions={actions}
          administrative={administrative}
          onApprove={approve}
          onReject={reject}
          onVerify={verify}
          onPropose={ajukan}
          onExecute={execute}
          onRepropose={repropose}
          onClose={() => setOpened(false)}
        />
      </Popup>
    </div>
  );
}
