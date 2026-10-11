// Daftar fakta label/nilai yang dipakai bersama halaman-halaman konsol
// (markup dipindahkan dari DecisionEvidence agar halaman baru tidak menyalinnya).
// Tipe barisnya SATU sumber: lib/evidence.ts (FactRow/FactTone).
import type { FactRow } from "../lib/evidence";

export type { FactRow };


export default function FactList({ rows }: { rows: FactRow[] }) {
  return (
    <dl className="fact-list">
      {rows.map((row) => (
        <div className="fact-row" key={row.label}>
          <dt>{row.label}</dt>
          <dd className={`fact-value fact-${row.tone ?? "plain"}`}>
            {row.value}
            {row.hint && <span className="fact-hint">{row.hint}</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}
