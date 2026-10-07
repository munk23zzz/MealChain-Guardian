"use client";

// DecisionActions — role scope (design.md §1.4): bgn_monitor read-only;
// approve/reject hanya role approver; execute hanya setelah approval.
// §1.3: approve SELALU lewat ApprovalModal (friksi disengaja).

import { useState } from "react";
import { approveAction, executeAction, reproposeAction, verifyAction } from "../lib/api";
import ApprovalModal from "./ApprovalModal";

const APPROVER_ROLES = new Set(["sppg_head", "sppg_nutritionist"]);

// Pure helper — satu sumber untuk UI & test (visibleActions).
export function visibleActions(
  role: string,
  status: string
): {
  approve: boolean;
  execute: boolean;
  repropose: boolean;
  readOnly: boolean;
} {
  if (!APPROVER_ROLES.has(role)) {
    return { approve: false, execute: false, repropose: false, readOnly: true };
  }
  const actionable =
    status === "pending_approval" || status === "verifier_flagged";
  return {
    approve: actionable,
    execute: actionable,
    // Rejection loop: keputusan ditolak → agent minta iterasi baru.
    repropose: status === "rejected",
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
  const [message, setMessage] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");

  const actions = visibleActions(role, status);
  if (actions.readOnly) {
    return <p className="read-only-note">Peran {role} bersifat read-only.</p>;
  }

  async function onApproved() {
    setConfirming(false);
    if (!token) {
      setMessage("Login diperlukan");
      return;
    }
    try {
      await approveAction(decisionId, true, token);
      setMessage("Approval tercatat");
    } catch (err: any) {
      setMessage(String(err.message ?? err));
    }
  }

  async function onRejected() {
    setConfirming(false);
    if (!reason.trim()) {
      setMessage("Alasan penolakan wajib diisi — ini bahan learning agent.");
      return;
    }
    if (!token) {
      setMessage("Login diperlukan");
      return;
    }
    try {
      await approveAction(decisionId, false, token, reason.trim());
      setMessage("Keputusan ditolak — agent bisa re-propose dengan iterasi baru.");
      setRejecting(false);
      setReason("");
    } catch (err: any) {
      setMessage(String(err.message ?? err));
    }
  }

  async function onRepropose() {
    if (!token) {
      setMessage("Login diperlukan");
      return;
    }
    try {
      const result = await reproposeAction(decisionId, token);
      setMessage(
        `Iterasi v${result.iteration ?? "?"} dibuat — menunggu verifikasi & approval.`
      );
    } catch (err: any) {
      setMessage(String(err.message ?? err));
    }
  }

  async function onExecute() {
    if (!token) {
      setMessage("Login diperlukan");
      return;
    }
    try {
      const result = await executeAction(decisionId, token);
      setMessage(`PO ${result.po_number ?? ""} dibuat (mock)`);
    } catch (err: any) {
      setMessage(String(err.message ?? err));
    }
  }

  async function onVerify() {
    if (!token) {
      setMessage("Login diperlukan");
      return;
    }
    try {
      const result = await verifyAction(decisionId, "consistent", token);
      setMessage(
        `Verifier: ${result.verdict ?? "CONSISTENT"} — keputusan siap dieksekusi setelah approval terpenuhi.`
      );
    } catch (err: any) {
      setMessage(String(err.message ?? err));
    }
  }

  return (
    <div className="decision-actions">
      {actions.approve && (
        <>
          <button
            type="button"
            className="button"
            onClick={() => setConfirming(true)}
          >
            Approve
          </button>
          <button
            type="button"
            className="button-secondary button"
            onClick={() => setRejecting((v) => !v)}
          >
            Reject
          </button>
        </>
      )}
      {actions.repropose && (
        <button type="button" className="button" onClick={onRepropose}>
          Minta re-propose (iterasi baru)
        </button>
      )}
      {rejecting && (
        <div className="reject-reason-box">
          <label className="field">
            <span>Alasan penolakan (wajib — jadi bahan learning agent)</span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              placeholder="cth: Kuota SPPG Jakarta penuh minggu ini"
            />
          </label>
          <button type="button" className="button" onClick={onRejected}>
            Kirim penolakan
          </button>
        </div>
      )}
      {actions.execute && (
        <button type="button" className="button" onClick={onExecute}>
          Execute
        </button>
      )}
      {actions.execute && (
        <button
          type="button"
          className="button-secondary button"
          onClick={onVerify}
          title="Catat hasil verifier (CONSISTENT) — syarat sebelum Execute"
        >
          Verifikasi
        </button>
      )}
      {confirming && (
        <ApprovalModal
          summary={summary}
          onConfirm={onApproved}
          onCancel={() => setConfirming(false)}
        />
      )}
      {message && <p className="action-message">{message}</p>}
    </div>
  );
}
