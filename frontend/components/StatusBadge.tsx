// StatusBadge — status TIDAK boleh ambigu (design.md §1.2).
//
// Label memakai `statusLabel` (lib/bahasa.ts): enum mentah berbahasa Inggris
// ("PENDING APPROVAL" 23x di feed Recommendation) dulu tampil apa adanya di UI
// berbahasa Indonesia. `data-status` tetap menyimpan nilai mentah — kontrak CSS.
import { statusLabel } from "../lib/bahasa";

const COLORS: Record<string, string> = {
  PASS: "status-safe",
  FAIL: "status-danger",
  NEEDS_VERIFICATION: "status-warning",
  PROPOSED: "status-neutral",
  VERIFIER_FLAGGED: "status-warning",
  PENDING_APPROVAL: "status-warning",
  APPROVED: "status-safe",
  REJECTED: "status-danger",
  EXECUTED: "status-safe",
  SURPLUS: "status-safe",
  SHORTAGE: "status-danger",
  TIGHT: "status-warning",
};

export default function StatusBadge({ status }: { status: string }) {
  const upper = (status ?? "").toUpperCase();
  const cls = COLORS[upper] ?? "status-neutral";
  const label = statusLabel(status) ?? "";
  return (
    <span className={`badge ${cls}`} data-status={upper}>
      {label}
    </span>
  );
}
