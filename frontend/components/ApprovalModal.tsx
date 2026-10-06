// ApprovalModal — approval adalah friksi yang disengaja (design.md §1.3):
// ringkasan WAJIB tampil sebelum tombol approve. Tidak ada approve-all.

import { formatIDR } from "../lib/auth";

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
  return (
    <div className="approval-modal" role="dialog" aria-label="Konfirmasi approval">
      <h3>Konfirmasi Approval</h3>
      <ul>
        <li>Jumlah: {summary.quantity_kg} kg</li>
        <li>Total biaya: {formatIDR(summary.safe_delivered_cost)}</li>
        <li>Verdict verifier: {summary.verdict}</li>
      </ul>
      <p>
        Setelah approve dan eksekusi, PO akan dibuat ke SAP (mock, berlabel
        Data Simulasi).
      </p>
      <div className="approval-modal-actions">
        <button type="button" className="button" onClick={onConfirm}>
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
