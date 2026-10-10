// ApprovalModal — approval adalah friksi yang disengaja (design.md §1.3):
// ringkasan WAJIB tampil sebelum tombol approve. Tidak ada approve-all.
// S4-04: isi modal = read model kanonik dari GET /decisions/{id}/
// approval-summary — UI TIDAK menghitung requirement/verdict sendiri;
// can_execute & blocking_reasons murni keputusan server; field yang
// hilang tampil "unavailable", bukan default palsu (plan §S4-04).

import { formatIDR } from "../lib/auth";

function Show({ value }: { value: any }) {
  // Semua nilai dari server ditampilkan apa adanya; null → unavailable.
  return <>{value === null || value === undefined ? "unavailable" : String(value)}</>;
}

// Angka ditampilkan gaya Indonesia (koma desimal) untuk konsistensi UI.
function fmtNum(value: any): string {
  if (value === null || value === undefined) return "unavailable";
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("id-ID") : String(value);
}

export default function ApprovalModal({
  summary,
  onConfirm,
  onCancel,
}: {
  summary: any;
  onConfirm?: () => void;
  onCancel?: () => void;
}) {
  if (!summary) {
    return (
      <p className="empty-state">
        Tidak ada ringkasan keputusan — approval massal tidak tersedia.
      </p>
    );
  }
  const req = summary.approval_requirement ?? {};
  const state = summary.approval_state ?? {};
  const safety = summary.safety ?? {};
  const verdict = summary.verifier?.verdict ?? null;
  const missingRoles = (state.missing ?? [])
    .flat()
    .filter((r: string, i: number, a: string[]) => a.indexOf(r) === i)
    .join(" + ");
  const blocking = summary.blocking_reasons ?? [];
  // S4-05 regression (rehearsal 2026-10-08): tombol Setuju di-gate
  // can_approve (approve masih sah), BUKAN can_execute — can_execute
  // selalu false sebelum approval terpenuhi → deadlock approval.
  const canApprove = summary.can_approve === true;
  const canExecute = summary.can_execute === true;
  const administrative = ["supplier_exclusion", "supplier_exclusion_restoration"].includes(summary.decision_type);
  const governance = summary.supplier_governance;
  return (
    <div className="approval-modal" role="dialog" aria-label="Konfirmasi approval">
      <h3>Konfirmasi Approval</h3>
      <ul>
        <li>
          Keputusan #{summary.decision_id} (v{summary.iteration ?? 1}) — status{" "}
          <Show value={summary.status} />
        </li>
        {administrative ? <>
          <li>{summary.decision_type === "supplier_exclusion_restoration" ? "Pemulihan supplier" : "Exclusion supplier"}</li>
          <li>Supplier: <Show value={summary.supplier?.name} /></li>
          <li>Scope SPPG: <Show value={summary.target_location} /></li>
          <li>Alasan: <Show value={governance?.reason} /></li>
          <li>Bukti: {(governance?.evidence_refs ?? []).map((ref: { type: string; id: string }) => `${ref.type}: ${ref.id}`).join(", ") || "unavailable"}</li>
          <li>Aktif sampai pemulihan berbukti dengan approval baru. Batch FAIL tetap diblokir.</li>
        </> : <>
        <li>
          Alokasi: <Show value={summary.source_location} /> →{" "}
          <Show value={summary.target_location} /> ({summary.decision_type})
        </li>
        <li>
          Komoditas: <Show value={summary.commodity} /> — Jumlah:{" "}
          {fmtNum(summary.quantity_kg)} kg
        </li>
        <li>
          Supplier: <Show value={summary.supplier?.name ?? null} /> — Material:{" "}
          <Show value={summary.material_number} />
        </li>
        <li>Total biaya: {formatIDR(summary.safe_delivered_cost)}</li>
        </>}
        <li>
          Safety batch sumber:{" "}
          <Show value={safety.worst_status ?? null} />
          {safety.blocked ? " — EXCLUDED (FAIL)" : ""}
        </li>
        <li>
          Verdict verifier: <Show value={verdict} /> (server-side)
        </li>
        <li>
          Approval requirement: {req.min_approvals ?? "unavailable"} approval —{" "}
          {missingRoles || (req.required_roles ?? []).flat().join(" + ") || "unavailable"}
        </li>
        <li>
          Kedaluwarsa:{" "}
          {summary.expiry?.valid
            ? `valid (${summary.expiry.seconds_remaining}s)`
            : "expired"}
        </li>
        <li>
          Target eksekusi: <Show value={summary.execution_target} />
          {administrative ? " (administrasi lokal, tanpa PO)" : " (PO mock, berlabel Data Simulasi)"}
        </li>
      </ul>
      {blocking.length > 0 && (
        <ul className="approval-modal-blockers">
          {blocking.map((reason: string) => (
            <li key={reason}>⛔ {reason}</li>
          ))}
        </ul>
      )}
      <div className="approval-modal-actions">
        <button
          type="button"
          className="button"
          onClick={onConfirm}
          disabled={!canApprove || (administrative && !governance)}
          title={
            canApprove
              ? undefined
              : "Approve tidak tersedia untuk keputusan ini (expired/rejected)"
          }
        >
          Setuju
        </button>
        <button
          type="button"
          className="button-secondary button"
          onClick={onCancel}
        >
          Batal
        </button>
      </div>
    </div>
  );
}
