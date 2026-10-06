"use client";

// DecisionActions — role scope (design.md §1.4): bgn_monitor read-only;
// approve/reject hanya role approver; execute hanya setelah approval.
// §1.3: approve SELALU lewat ApprovalModal (friksi disengaja).

import { useState } from "react";
import { approveAction, executeAction } from "../lib/api";
import ApprovalModal from "./ApprovalModal";

const APPROVER_ROLES = new Set(["sppg_head", "sppg_nutritionist"]);

// Pure helper — satu sumber untuk UI & test (visibleActions).
export function visibleActions(
  role: string,
  status: string
): { approve: boolean; execute: boolean; readOnly: boolean } {
  if (!APPROVER_ROLES.has(role)) {
    return { approve: false, execute: false, readOnly: true };
  }
  const actionable =
    status === "pending_approval" || status === "verifier_flagged";
  return { approve: actionable, execute: actionable, readOnly: false };
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
    if (!token) {
      setMessage("Login diperlukan");
      return;
    }
    try {
      await approveAction(decisionId, false, token);
      setMessage("Keputusan ditolak");
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
            onClick={onRejected}
          >
            Reject
          </button>
        </>
      )}
      {actions.execute && (
        <button type="button" className="button" onClick={onExecute}>
          Execute
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
