// Blok biaya keputusan (Fase 9): dua arti biaya yang tidak boleh tercampur.
//
//   Biaya PO  = bahan + transportasi + handling — yang ditagihkan ke pemasok.
//   SDC       = biaya PO + penalti risiko internal — untuk membandingkan pilihan.
//
// Semua angka datang dari server (`commercial_cost` pada GET /decisions/{id});
// komponen ini TIDAK menghitung biaya. `cost === null` berarti keputusan
// administratif tanpa transfer: tampilkan "tidak berlaku", jangan Rp 0.
import type {
  CommercialCostPayload,
  MarketReference,
} from "../lib/decision-economics";
import { buildCostView } from "../lib/decision-economics";

const TONE_KELAS: Record<string, string> = {
  tersedia: "cost-block",
  tidak_tercatat: "cost-block cost-block-partial",
  tidak_berlaku: "cost-block cost-block-none",
};

export default function DecisionEconomics({
  cost,
  market = null,
}: {
  cost: CommercialCostPayload | null;
  market?: MarketReference | null;
}) {
  const view = buildCostView(cost, market);

  if (view.status === "tidak_berlaku") {
    return (
      <article
        className={`card ${TONE_KELAS.tidak_berlaku}`}
        data-testid="decision-economics"
        data-status="tidak_berlaku"
      >
        <div className="card-header">
          <h3>Biaya</h3>
        </div>
        <p className="section-sub" data-testid="cost-message">
          {view.message}
        </p>
      </article>
    );
  }

  return (
    <div className={TONE_KELAS[view.status]} data-testid="decision-economics" data-status={view.status}>
      {view.blocks.map((block) => (
        <article className="card" key={block.key} data-block={block.key}>
          <div className="card-header">
            <h3>{block.title}</h3>
          </div>
          <p className="section-sub">{block.caption}</p>
          <dl className="fact-list">
            {block.rows.map((row) => (
              <div className="fact-row" key={row.label}>
                <dt>{row.label}</dt>
                <dd className="fact-value">
                  {row.value}
                  {row.note && <span className="fact-hint">{row.note}</span>}
                </dd>
              </div>
            ))}
          </dl>
        </article>
      ))}

      <p className="section-sub" data-testid="risk-method">
        Dasar risiko: {view.riskMethod.label} · {view.riskMethod.source} · versi{" "}
        {view.riskMethod.version}
        {view.riskMethod.period ? ` · periode ${view.riskMethod.period}` : ""}
      </p>
      {view.message && (
        <p className="section-sub" data-testid="cost-message">
          {view.message}
        </p>
      )}
    </div>
  );
}
