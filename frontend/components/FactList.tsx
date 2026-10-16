// Daftar fakta label/nilai yang dipakai bersama halaman-halaman konsol
// (markup dipindahkan dari DecisionEvidence agar halaman baru tidak menyalinnya).
// Tipe barisnya SATU sumber: lib/evidence.ts (FactRow/FactTone).
// 17 Okt 2026 — `collapseEmpty`: kartu fakta di halaman Decision & Evidence
// dulu menumpahkan semua baris, sehingga separuhnya hanya "—" dan kartunya
// terbaca seperti dump database. Dengan prop ini baris kosong dipindahkan ke
// balik SATU klik (`<details>` natif — bisa dioperasikan keyboard & pembaca
// layar tanpa JS tambahan). Isinya tidak dibuang: jumlahnya tetap disebut.
import type { FactRow } from "../lib/evidence";
import { hiddenFactsLabel, splitFacts } from "../lib/evidence";

export type { FactRow };

function Rows({ rows, empty = false }: { rows: FactRow[]; empty?: boolean }) {
  return (
    <dl className={empty ? "fact-list fact-list-empty" : "fact-list"}>
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

export default function FactList({
  rows,
  collapseEmpty = false,
}: {
  rows: FactRow[];
  /** Sembunyikan baris "—" di balik rincian yang bisa dibuka (bawaan: tampil semua). */
  collapseEmpty?: boolean;
}) {
  if (!collapseEmpty) return <Rows rows={rows} />;

  const { filled, empty } = splitFacts(rows);
  return (
    <>
      <Rows rows={filled} />
      {empty.length > 0 && (
        <details className="fact-more">
          <summary>{hiddenFactsLabel(empty.length)}</summary>
          <Rows rows={empty} empty />
        </details>
      )}
    </>
  );
}
