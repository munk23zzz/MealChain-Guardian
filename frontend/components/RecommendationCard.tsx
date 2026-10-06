// RecommendationCard — item feed (design.md §3.2): judul, badge status,
// SDC, quantity, expiry, dan badge "Data Simulasi" bila bersumber mock.

import StatusBadge from "./StatusBadge";
import { formatIDR } from "../lib/auth";

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
  return (
    <div className="card recommendation-card">
      <div className="card-header">
        <h3>{typeLabel}</h3>
        <StatusBadge status={decision.status} />
      </div>
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
      {mockSourced && <span className="badge mock-badge">Data Simulasi</span>}
      <a href={`/decisions/${decision.decision_id}`}>Lihat Detail</a>
    </div>
  );
}
