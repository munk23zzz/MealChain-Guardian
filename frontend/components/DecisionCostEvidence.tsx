"use client";

// DecisionCostEvidence — blok BUKTI BIAYA halaman Decision & Evidence
// (TAHAP 3, 29 Okt 2026, gaya clean dashboard).
//
// Dua arti biaya yang tidak boleh tercampur, dipisah jadi dua tabel:
//   Biaya PO = bahan + transportasi + handling — yang ditagihkan ke pemasok.
//   SDC      = biaya PO + penalti risiko internal — untuk membandingkan pilihan.
//
// Semua angka dari `buildCostView` (lib/decision-economics), sumber yang sama
// dengan kartu biaya di halaman lain. Komponen ini TIDAK menghitung biaya:
// `null` berarti "tidak berlaku", dan itu ditulis — bukan Rp 0.
import type {
  CommercialCostPayload,
  CostBlock,
  MarketReference,
} from "../lib/decision-economics";
import { buildCostView } from "../lib/decision-economics";

function Tabel({ block }: { block: CostBlock }) {
  return (
    <article className="cost-block" data-block={block.key}>
      <h3 className="cost-block-title">{block.title}</h3>
      <p className="cost-block-nota">{block.caption}</p>
      <table className="cost-table">
        <caption className="cost-caption">{block.title}</caption>
        <tbody>
          {block.rows.map((row) => {
            const total = row.label.startsWith("Total ");
            return (
              <tr key={row.label} className={total ? "cost-row cost-row-total" : "cost-row"}>
                <th scope="row">
                  {row.label}
                  {/* Catatan pendek ("per kg") menempel pada label: kalau ia
                      jatuh ke baris sendiri, ia terbaca seperti baris baru dan
                      menambah tinggi baris tanpa menambah informasi. Catatan
                      penjelas yang panjang tetap di bawah label. */}
                  {/* Spasi nyata, bukan margin: pembaca layar menggabungkan
                      teks tanpa memperdulikan margin, jadi tanpa ini label
                      terbaca "Harga satuan POper kg". */}
                  {row.note ? " " : null}
                  {row.note ? (
                    <span
                      className={
                        row.note.length <= 18 ? "cost-note cost-note-inline" : "cost-note"
                      }
                    >
                      {row.note}
                    </span>
                  ) : null}
                </th>
                <td>{row.value}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </article>
  );
}

export default function DecisionCostEvidence({
  cost,
  market = null,
}: {
  cost: CommercialCostPayload | null;
  market?: MarketReference | null;
}) {
  const view = buildCostView(cost, market);

  if (view.status === "tidak_berlaku") {
    return (
      <section
        className="dash-cost"
        id="bukti" data-bagian="bukti"
        data-testid="decision-economics"
        data-status="tidak_berlaku"
        aria-labelledby="judul-bukti-biaya"
      >
        <h2 className="dash-cost-title" id="judul-bukti-biaya">
          Bukti biaya
        </h2>
        <p className="dash-cost-kosong" data-testid="cost-message">
          {view.message}
        </p>
      </section>
    );
  }

  return (
    <section
      className="dash-cost"
      id="bukti"
      data-testid="decision-economics"
      data-status={view.status}
      aria-labelledby="judul-bukti-biaya"
    >
      <header className="dash-cost-head">
        <h2 className="dash-cost-title" id="judul-bukti-biaya">
          Bukti biaya
        </h2>
        <p className="dash-cost-lead">
          Biaya yang ditagihkan ke pemasok dan biaya analitis untuk memilih
          dipisah, supaya keduanya tidak tertukar saat dibaca.
        </p>
      </header>

      <div className="cost-grid">
        {view.blocks.map((block) => (
          <Tabel key={block.key} block={block} />
        ))}
      </div>

      {view.message ? (
        <p className="dash-cost-catatan" data-testid="cost-message">
          {view.message}
        </p>
      ) : null}
    </section>
  );
}
