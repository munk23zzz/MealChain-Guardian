// Daftar fakta label/nilai yang dipakai bersama halaman-halaman konsol
// (markup dipindahkan dari DecisionEvidence agar halaman baru tidak menyalinnya).
// Tipe barisnya SATU sumber: lib/evidence.ts (FactRow/FactTone).
// 17 Okt 2026 — `collapseEmpty`: kartu fakta di halaman Decision & Evidence
// dulu menumpahkan semua baris, sehingga separuhnya hanya "—" dan kartunya
// terbaca seperti dump database. Dengan prop ini baris kosong dipindahkan ke
// balik SATU klik (`<details>` natif — bisa dioperasikan keyboard & pembaca
// layar tanpa JS tambahan). Isinya tidak dibuang: jumlahnya tetap disebut.
import type { FactRow } from "../lib/evidence";
import { hiddenFactsLabel, hiddenRowsLabel, splitFacts } from "../lib/evidence";

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
  foldAfter,
}: {
  rows: FactRow[];
  /** Sembunyikan baris "—" di balik rincian yang bisa dibuka (bawaan: tampil semua). */
  collapseEmpty?: boolean;
  /**
   * Setelah berapa baris TERISI kartu mulai melipat sisanya (bawaan: tidak pernah).
   * Dipakai untuk kartu yang isinya panjang tetapi sebagian hanya rincian
   * pendukung — bukan untuk menyembunyikan data kosong (itu tugas collapseEmpty).
   */
  foldAfter?: number;
}) {
  if (!collapseEmpty && foldAfter === undefined) return <Rows rows={rows} />;

  // Pisahkan baris kosong hanya kalau diminta; kalau tidak, jangan buang apa pun.
  const { filled, empty } = collapseEmpty ? splitFacts(rows) : { filled: rows, empty: [] as FactRow[] };
  const batas = foldAfter === undefined ? filled.length : Math.max(0, foldAfter);
  const tampak = filled.slice(0, batas);
  const dilipat = filled.slice(batas);

  return (
    <>
      <Rows rows={tampak} />
      {dilipat.length > 0 && (
        <details className="fact-more">
          <summary>{hiddenRowsLabel(dilipat.length)}</summary>
          <Rows rows={dilipat} />
        </details>
      )}
      {empty.length > 0 && (
        <details className="fact-more">
          <summary>{hiddenFactsLabel(empty.length)}</summary>
          <Rows rows={empty} empty />
        </details>
      )}
    </>
  );
}
