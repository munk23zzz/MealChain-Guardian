// RecommendationCard — item feed (design.md §3.2): judul, badge status,
// SDC, quantity, expiry, dan badge "Data Simulasi" bila bersumber mock.
// Label kasus demo (arah Roy 2026-10-07): feed harus self-explanatory
// saat demo — juri langsung tahu kartu itu milik skenario apa.
// Restyle Stitch: kartu dengan alert edge kiri (tingkat status),
// header ber-garis, dl meta padat ala konsol data-dense.

import StatusBadge from "./StatusBadge";
import { formatIDR } from "../lib/auth";

const CASE_LABELS: Record<string, string> = {
  "rejection-loop-kuota": "Kasus: Rejection Loop (Kuota)",
  "shortage-darurat": "Kasus: Shortage Darurat",
  "supplier-janggal": "Kasus: Supplier Janggal",
  "gangguan-logistik": "Kasus: Gangguan Logistik",
};

// Peta status → kelas tepi kartu (alert edge ala Stitch).
const EDGE: Record<string, string> = {
  PENDING_APPROVAL: "edge-warning",
  VERIFIER_FLAGGED: "edge-warning",
  NEEDS_VERIFICATION: "edge-warning",
  REJECTED: "edge-danger",
  FAIL: "edge-danger",
  SHORTAGE: "edge-danger",
};

export default function RecommendationCard({
  decision,
  mockSourced = false,
}: {
  decision: any;
  mockSourced?: boolean;
}) {
  const typeLabel =
    decision.decision_type === "regional_balance"
      ? "Alokasi regional direkomendasikan"
      : "Keputusan baru";
  const caseLabel = decision.demo_case
    ? (CASE_LABELS[decision.demo_case] ??
      `Kasus: ${decision.demo_case.replace(/-/g, " ")}`)
    : null;
  const edge =
    EDGE[(decision.status ?? "").toUpperCase()] ?? "edge-primary";
  return (
    <article className={`card recommendation-card rec-edge ${edge}`}>
      <div className="card-header">
        <h3>
          {typeLabel}
          {decision.iteration && decision.iteration > 1 && (
            <span className="badge version-badge">v{decision.iteration}</span>
          )}
        </h3>
        <StatusBadge status={decision.status} />
      </div>
      {caseLabel && <p className="case-label">{caseLabel}</p>}
      <dl>
        <div className="rec-meta">
          <dt>Jumlah</dt>
          <dd className="rec-value">{decision.quantity_kg} kg</dd>
        </div>
        <div className="rec-meta">
          <dt>Safe Delivered Cost</dt>
          <dd className="rec-value">{formatIDR(decision.safe_delivered_cost)}</dd>
        </div>
        <div className="rec-meta">
          <dt>Kedaluwarsa</dt>
          <dd className={decision.valid ? "rec-value" : "rec-value rec-expired"}>
            {decision.valid
              ? `valid sisa ${decision.seconds_remaining ?? 0} detik`
              : "EXPIRED"}
          </dd>
        </div>
      </dl>
      {decision.rejection_reason && (
        <p className="chain-reason">Ditolak: {decision.rejection_reason}</p>
      )}
      {mockSourced && <span className="badge mock-badge">Data Simulasi</span>}
    </article>
  );
}
