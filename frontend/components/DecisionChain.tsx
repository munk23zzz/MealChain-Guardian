// DecisionChain — timeline iterasi rejection loop (v1 → v2 → v3).
// Alasan penolakan ditampilkan eksplisit: inilah bahan learning agent
// (permintaan Roy 2026-10-07). Tanpa karangan — data dari /decisions/{id}/chain.

import StatusBadge from "./StatusBadge";
import { formatIDR } from "../lib/auth";

export default function DecisionChain({ chain }: { chain: any[] }) {
  if (!chain || chain.length === 0) return null;
  return (
    <div className="decision-chain">
      <h4>Riwayat iterasi</h4>
      <ol className="chain-list">
        {chain.map((c) => (
          <li key={c.decision_id} className={`chain-item chain-${c.status}`}>
            <div className="chain-head">
              <span className="chain-version">
                v{c.iteration ?? 1}
              </span>
              <StatusBadge status={c.status} />
            </div>
            <div className="chain-body">
              <span>{c.quantity_kg ?? "-"} kg</span>
              <span>{formatIDR(c.safe_delivered_cost)}</span>
            </div>
            {c.rejection_reason && (
              <p className="chain-reason">
                Ditolak: {c.rejection_reason}
              </p>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
