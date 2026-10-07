// RecommendationCard — item feed (design.md §3.2): judul, badge status,
// SDC, quantity, expiry, dan badge "Data Simulasi" bila bersumber mock.
// Label kasus demo (arah Roy 2026-10-07): feed harus self-explanatory
// saat demo — juri langsung tahu kartu itu milik skenario apa.

import StatusBadge from "./StatusBadge";
import { formatIDR } from "../lib/auth";

const CASE_LABELS: Record<string, string> = {
  "rejection-loop-kuota": "Kasus: Rejection Loop (Kuota)",
  "shortage-darurat": "Kasus: Shortage Darurat",
  "supplier-janggal": "Kasus: Supplier Janggal",
  "gangguan-logistik": "Kasus: Gangguan Logistik",
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
  return (
    <div className="card recommendation-card">
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
        <dt>Jumlah</dt>
        <dd>{decision.quantity_kg} kg</dd>
        <dt>Safe Delivered Cost</dt>
        <dd>{formatIDR(decision.safe_delivered_cost)}</dd>
        <dt>Kedaluwarsa</dt>
        <dd>
          {decision.valid
            ? `valid sisa ${decision.seconds_remaining ?? 0} detik`
            : "EXPIRED"}
        </dd>
      </dl>
      {decision.rejection_reason && (
        <p className="chain-reason">Ditolak: {decision.rejection_reason}</p>
      )}
      {mockSourced && <span className="badge mock-badge">Data Simulasi</span>}
    </div>
  );
}
