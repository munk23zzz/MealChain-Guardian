"use client";

// ApprovalMenu — ISI popup "Governance & persetujuan" (permintaan Roy
// 2026-10-14). Dulu pilihan tindakan adalah deretan tombol di dalam kartu
// Governance (dan kotak alasan penolakan melebar di situ, mendorong isi kartu
// di grid 3 kolom). Sekarang pilihan menjadi MENU di dalam popup: tiap baris
// memuat nama tindakan, akibatnya dalam satu kalimat, lalu tombolnya.
// Yang sengaja dipertahankan:
// - design.md §1.3 — ringkasan read model kanonik tampil LEBIH DULU; tidak ada
//   approve satu klik dan tidak ada approve massal;
// - design.md §1.4 — aksi mutasi mengikuti `actions` (hasil visibleActions),
//   jadi bgn_monitor tidak pernah melihat menu mutasi sama sekali;
// - galat tampil DI DEKAT kontrolnya (peran/detail), bukan di kartu yang
//   tertutup popup — dan diumumkan lewat role="alert";
// - tombol dikunci + diberi status "Memproses…" selama aksi berjalan supaya
//   tidak ada klik ganda pada aksi berisiko tinggi.

import { useState } from "react";
import ApprovalModal from "./ApprovalModal";
import { batchGateView } from "../lib/safety-gate";

export type MenuActions = {
  approve: boolean;
  verify: boolean;
  execute: boolean;
  propose: boolean;
  repropose: boolean;
  readOnly: boolean;
};

/** Handler mengembalikan pesan galat; `null` = aksi berhasil. */
type ActionResult = Promise<string | null>;

export default function ApprovalMenu({
  summary,
  actions,
  administrative,
  canReviewPo = false,
  poNumber = null,
  onReviewPo,
  onApprove,
  onReject,
  onVerify,
  onPropose,
  onExecute,
  onRepropose,
  onClose,
  dalamPanel = false,
}: {
  summary: any;
  actions: MenuActions;
  administrative: boolean;
  /** PO draft menunggu review Kepala SPPG (gerbang kedua, §6 dokumen 02). */
  canReviewPo?: boolean;
  poNumber?: string | null;
  onReviewPo?: () => ActionResult;
  onApprove: () => ActionResult;
  onReject: (reason: string) => ActionResult;
  onVerify: () => ActionResult;
  onPropose: () => ActionResult;
  onExecute: () => ActionResult;
  onRepropose: () => ActionResult;
  onClose: () => void;
  /**
   * Panel ini dirender DI DALAM popup detail, bukan sebagai jendela sendiri.
   * Kalimat penutup wajib jujur: Escape menutup seluruh popup keputusan,
   * bukan cuma panel ini.
   */
  dalamPanel?: boolean;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");

  async function run(id: string, fn: () => ActionResult) {
    if (busy) return;
    setError(null);
    setBusy(id);
    try {
      const failure = await fn();
      if (failure) {
        setError(failure);
        return;
      }
      onClose();
    } finally {
      setBusy(null);
    }
  }

  function openReject() {
    setError(null);
    setRejecting(true);
  }

  const hasChoice =
    canReviewPo ||
    actions.approve ||
    actions.verify ||
    actions.propose ||
    actions.execute ||
    actions.repropose;

  // WS-B (QA 16 Okt): pagar aksi mutasi memakai KEPUTUSAN SERVER, bukan
  // hitungan ulang di sini. Read model yang sama sudah mengirim `can_execute`
  // (= bukan hanya status peran: kedaluwarsa, belum terverifikasi, sudah
  // dieksekusi, requirement approval belum terpenuhi, safety revalidation
  // gagal). Dulu tombol Eksekusi tetap ditawarkan dan klik-nya berakhir 409
  // "decision expired" (backend app/api/actions.py `/actions/execute`).
  // Fail-closed, sama seperti `can_approve` di ApprovalModal (§S4-04/§S4-05).
  //
  // MG/phase-04 poin 7: alasannya kini KODE STABIL dari evaluator batch
  // (`safety_pending`, `quarantined`, …). Kode itu tidak pernah tampil di
  // layar — `batchGateView` menerjemahkannya jadi kalimat + langkah berikutnya,
  // dan satu peta itu dipakai juga oleh ringkasan approval dan papan Keamanan
  // Pangan. Sebelumnya yang tampil `blocking_reasons[0]` mentah.
  const gate = batchGateView(summary);
  const sudahDieksekusi = summary?.status === "executed";
  const canExecute = gate.canExecute && !sudahDieksekusi;

  // Keputusan owner 2026-10-16 (3b): "Tolak" memakai endpoint yang SAMA dengan
  // "Setuju" (approve_action dengan approved=false), jadi kelayakannya juga
  // milik server. Dulu UI menebaknya dari peran+status karena read model tidak
  // punya field-nya. Sekarang server menyatakan lewat `can_reject`.
  const canReject = summary?.can_reject === true;
  // Fase 0 butir 2 (18 Okt 2026): Setuju baru sah setelah verifikasi tercatat.
  // Server menolak approve tanpa `verified_by` (409) karena status `approved`
  // tidak menerima verify lagi — alur akan buntu di eksekusi.
  const canApprove = summary?.can_approve === true;
  // /actions/propose menolak keputusan kedaluwarsa tanpa syarat
  // (actions.py:129). `valid` yang tidak ada JANGAN dianggap kedaluwarsa —
  // jangan mengarang penghalang.
  const belumKedaluwarsa = summary?.expiry?.valid !== false;

  return (
    <div className="approval-menu">
      <section className="approval-menu-block" aria-label="Ringkasan bukti keputusan">
        <ApprovalModal
          summary={summary}
          onConfirm={() => run("approve", onApprove)}
          onCancel={onClose}
          showActions={actions.approve && canApprove}
          busy={busy === "approve"}
        />
      </section>

      {hasChoice && (
        <section className="approval-menu-block" aria-label="Pilihan tindakan lain">
          <h4 className="approval-menu-heading">Pilihan tindakan</h4>
          <ul className="action-menu">
            {/* Gerbang kedua (dokumen 02-approval-action.md §6): PO draft sudah
                terbit tetapi BELUM dikirim ke SAP. Tanpa baris ini, keadaan
                "menunggu review PO" tidak punya jalan keluar dari panel. */}
            {canReviewPo && onReviewPo && (
              <li className="action-menu-item" data-action="review-po">
                <div className="action-menu-text">
                  <strong>Review PO {poNumber ?? ""}</strong>
                  <span>
                    PO draft dikirim ke SAP simulasi, keputusan menjadi{" "}
                    <code>dieksekusi</code>, dan batch terikat diberangkatkan. Sebelum
                    ini, tidak ada barang yang berangkat.
                  </span>
                </div>
                <button
                  type="button"
                  className="button action-menu-button"
                  data-action="review-po"
                  onClick={() => run("review-po", onReviewPo)}
                  disabled={busy !== null}
                >
                  {busy === "review-po" ? "Memproses…" : "Review & kirim"}
                </button>
              </li>
            )}
            {actions.approve && canReject && (
              <li className="action-menu-item" data-action="reject">
                <div className="action-menu-text">
                  <strong>Tolak keputusan</strong>
                  <span>
                    Status menjadi <code>ditolak</code>. Alasan wajib diisi dan dipakai agent
                    sebagai bahan iterasi berikutnya.
                  </span>
                </div>
                <button
                  type="button"
                  className="button button-secondary action-menu-button"
                  data-action="reject"
                  onClick={openReject}
                  disabled={busy !== null}
                  aria-expanded={rejecting}
                >
                  Tolak
                </button>
              </li>
            )}

            {actions.approve && !canReject && (
              <li className="action-menu-item action-menu-note">
                <div className="action-menu-text">
                  <strong>Penolakan belum tersedia</strong>
                  <span>
                    Server belum mengizinkan penolakan untuk keputusan ini — statusnya sudah
                    tidak dapat ditolak, atau keputusan administratif ini sudah lewat tenggat.
                  </span>
                </div>
              </li>
            )}

            {actions.approve && !canApprove && (
              <li className="action-menu-item action-menu-note">
                <div className="action-menu-text">
                  <strong>Setuju belum tersedia</strong>
                  <span>
                    Verifikasi belum menghasilkan verdict. Tanpa verdict, persetujuan mengunci
                    jalan keluar (status <code>disetujui</code> tidak menerima verifikasi lagi) —
                    catat hasil verifier dulu.
                  </span>
                </div>
              </li>
            )}

            {actions.verify && belumKedaluwarsa && (
              <li className="action-menu-item" data-action="verify">
                <div className="action-menu-text">
                  <strong>Catat hasil verifier</strong>
                  <span>
                    Verifier dijalankan server-side dari data kanonik; verdict ditampilkan apa
                    adanya, tidak bisa di-override dari sini.
                  </span>
                </div>
                <button
                  type="button"
                  className="button button-secondary action-menu-button"
                  data-action="verify"
                  onClick={() => run("verify", onVerify)}
                  disabled={busy !== null}
                >
                  {busy === "verify" ? "Memproses…" : "Verifikasi"}
                </button>
              </li>
            )}

            {actions.verify && !belumKedaluwarsa && (
              <li className="action-menu-item action-menu-note">
                <div className="action-menu-text">
                  <strong>Catat hasil verifier</strong>
                  <span>
                    Belum tersedia — keputusan sudah lewat tenggat, jadi verifikasi ditolak
                    server.
                  </span>
                </div>
              </li>
            )}

            {actions.propose && !administrative && belumKedaluwarsa && (
              <li className="action-menu-item" data-action="propose">
                <div className="action-menu-text">
                  <strong>Ajukan untuk persetujuan</strong>
                  <span>
                    Status berpindah ke <code>menunggu persetujuan</code> supaya Ahli Gizi dan Kepala
                    SPPG bisa menilai. Tanpa langkah ini keputusan berhenti di{" "}
                    <code>diusulkan</code>.
                  </span>
                </div>
                <button
                  type="button"
                  className="button action-menu-button"
                  data-action="propose"
                  onClick={() => run("propose", onPropose)}
                  disabled={busy !== null}
                >
                  {busy === "propose" ? "Memproses…" : "Ajukan"}
                </button>
              </li>
            )}

            {actions.propose && !administrative && !belumKedaluwarsa && (
              <li className="action-menu-item action-menu-note">
                <div className="action-menu-text">
                  <strong>Ajukan untuk persetujuan</strong>
                  <span>
                    Belum tersedia — keputusan sudah lewat tenggat, jadi pengajuan ditolak
                    server.
                  </span>
                </div>
              </li>
            )}

            {actions.execute && canExecute && (
              <li className="action-menu-item" data-action="execute">
                <div className="action-menu-text">
                  <strong>Terbitkan PO draft (data simulasi)</strong>
                  <span>
                    {administrative
                      ? "Mencatat status administratif supplier; safety batch tidak diubah."
                      : "Hanya sah setelah approval terpenuhi. PO terbit sebagai DRAFT — belum dikirim ke SAP; Kepala SPPG mereviewnya lebih dulu."}
                  </span>
                </div>
                <button
                  type="button"
                  className="button action-menu-button"
                  data-action="execute"
                  onClick={() => run("execute", onExecute)}
                  disabled={busy !== null}
                >
                  {busy === "execute" ? "Memproses…" : "Eksekusi"}
                </button>
              </li>
            )}

            {actions.execute && !canExecute && (
              <li className="action-menu-item action-menu-note" data-action="execute-blocked">
                <div className="action-menu-text">
                  <strong>Terbitkan PO draft (data simulasi)</strong>
                  <span>
                    Belum tersedia — server belum mengizinkan
                    {gate.reasons.length > 0 ? `: ${gate.reasons.join(" · ")}` : "."}
                  </span>
                  {sudahDieksekusi ? (
                    <span>Keputusan ini sudah dieksekusi; tidak ada eksekusi kedua.</span>
                  ) : null}
                  {gate.nextStep && !sudahDieksekusi ? (
                    <span className="action-menu-next">
                      <strong>Langkah berikutnya:</strong> {gate.nextStep}
                    </span>
                  ) : null}
                </div>
              </li>
            )}

            {actions.repropose && !administrative && belumKedaluwarsa && (
              <li className="action-menu-item" data-action="repropose">
                <div className="action-menu-text">
                  <strong>Minta re-propose</strong>
                  <span>
                    Agent menyusun iterasi baru dari alasan penolakan sebelumnya; keputusan ini
                    tetap tersimpan sebagai riwayat.
                  </span>
                </div>
                <button
                  type="button"
                  className="button action-menu-button"
                  data-action="repropose"
                  onClick={() => run("repropose", onRepropose)}
                  disabled={busy !== null}
                >
                  {busy === "repropose" ? "Memproses…" : "Minta re-propose"}
                </button>
              </li>
            )}

            {actions.repropose && !administrative && !belumKedaluwarsa && (
              <li className="action-menu-item action-menu-note">
                <div className="action-menu-text">
                  <strong>Minta re-propose</strong>
                  <span>
                    Belum tersedia — keputusan sudah lewat tenggat, jadi usulan ulang
                    ditolak server.
                  </span>
                </div>
              </li>
            )}

            {actions.repropose && administrative && (
              <li className="action-menu-item action-menu-note">
                <div className="action-menu-text">
                  <span>Ajukan ulang melalui panel supplier dengan bukti baru.</span>
                </div>
              </li>
            )}
          </ul>

          {rejecting && (
            <div className="reject-reason-box">
              <label className="field">
                <span>Alasan penolakan (wajib — jadi bahan learning agent)</span>
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  rows={3}
                  autoFocus
                  placeholder="cth: Kuota SPPG Jakarta penuh minggu ini"
                  disabled={busy !== null}
                />
              </label>
              <div className="reject-reason-actions">
                <button
                  type="button"
                  className="button"
                  onClick={() => run("reject", () => onReject(reason))}
                  disabled={busy !== null}
                >
                  {busy === "reject" ? "Memproses…" : "Kirim penolakan"}
                </button>
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => {
                    setRejecting(false);
                    setReason("");
                    setError(null);
                  }}
                  disabled={busy !== null}
                >
                  Batal menolak
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {error && (
        <p className="action-error" role="alert">
          {error}
        </p>
      )}

      <div className="approval-menu-foot">
        <p className="approval-menu-hint">
          {dalamPanel
            ? "Tutup panel ini untuk kembali membaca rincian."
            : "Tekan Esc untuk menutup jendela ini."}
        </p>
        <button type="button" className="button button-secondary" onClick={onClose} disabled={busy !== null}>
          Tutup
        </button>
      </div>
    </div>
  );
}
