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

export type MenuActions = {
  approve: boolean;
  execute: boolean;
  repropose: boolean;
  readOnly: boolean;
};

/** Handler mengembalikan pesan galat; `null` = aksi berhasil. */
type ActionResult = Promise<string | null>;

export default function ApprovalMenu({
  summary,
  actions,
  administrative,
  onApprove,
  onReject,
  onVerify,
  onExecute,
  onRepropose,
  onClose,
}: {
  summary: any;
  actions: MenuActions;
  administrative: boolean;
  onApprove: () => ActionResult;
  onReject: (reason: string) => ActionResult;
  onVerify: () => ActionResult;
  onExecute: () => ActionResult;
  onRepropose: () => ActionResult;
  onClose: () => void;
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

  const hasChoice = actions.approve || actions.execute || actions.repropose;

  return (
    <div className="approval-menu">
      <section className="approval-menu-block" aria-label="Ringkasan bukti keputusan">
        <ApprovalModal
          summary={summary}
          onConfirm={() => run("approve", onApprove)}
          onCancel={onClose}
          showActions={actions.approve}
          busy={busy === "approve"}
        />
      </section>

      {hasChoice && (
        <section className="approval-menu-block" aria-label="Pilihan tindakan lain">
          <h4 className="approval-menu-heading">Pilihan tindakan</h4>
          <ul className="action-menu">
            {actions.approve && (
              <li className="action-menu-item">
                <div className="action-menu-text">
                  <strong>Tolak keputusan</strong>
                  <span>
                    Status menjadi <code>rejected</code>. Alasan wajib diisi dan dipakai agent
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

            {actions.execute && (
              <li className="action-menu-item">
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

            {actions.execute && (
              <li className="action-menu-item">
                <div className="action-menu-text">
                  <strong>Eksekusi ke SAP (mock)</strong>
                  <span>
                    {administrative
                      ? "Mencatat status administratif supplier; safety batch tidak diubah."
                      : "Hanya sah setelah approval terpenuhi. Menulis purchase order berlabel data simulasi."}
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

            {actions.repropose && !administrative && (
              <li className="action-menu-item">
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
        <button type="button" className="button button-secondary" onClick={onClose} disabled={busy !== null}>
          Tutup
        </button>
      </div>
    </div>
  );
}
