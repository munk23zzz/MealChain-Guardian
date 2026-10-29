"use client";

// DecisionIdentityBatch — blok IDENTITAS & EVALUASI BATCH (TAHAP 5, 29 Okt 2026).
//
// Dua hal yang dijawab di sini:
//   1. Keputusan mana ini? — rute, komoditas, iterasi, penggantinya, pengusulnya.
//   2. Batch mana yang terikat, dan gerbang mana yang menahannya? — dari
//      `GET /decisions/{id}/packet` (`batch_evaluations`), evaluator yang sama
//      dengan gerbang dispatch.
//
// Aturan yang dipegang:
//   · Komponen ini TIDAK menilai batch dan tidak menghitung ulang status —
//     tabel memakai `BatchEvaluationTable` apa adanya.
//   · Paket gagal diambil → dikatakan gagal. Tabel kosong tidak ditampilkan,
//     dan tidak ada batch yang dikarang.
//   · Tanpa token/id keputusan tidak ada permintaan jaringan sama sekali.
import { useEffect, useState } from "react";

import { fetchDecisionPacket } from "../lib/api";
import { decisionFacts } from "../lib/evidence";
import BatchEvaluationTable, {
  type BatchEvaluationView,
} from "./BatchEvaluationTable";

type State =
  | { fase: "tanpa-token" }
  | { fase: "memuat" }
  | { fase: "gagal" }
  | { fase: "siap"; evaluations: BatchEvaluationView[] };

export default function DecisionIdentityBatch({
  selected,
  summary,
  token,
  now,
}: {
  selected: Record<string, unknown> & { decision_id?: string };
  summary: unknown;
  token: string | null;
  now: Date | null;
}) {
  const decisionId = selected?.decision_id ?? null;
  // Keadaan awal mengikuti kenyataan: bila id + token ada, yang benar adalah
  // "sedang dimuat" — bukan "butuh sesi", yang akan berbohong satu bingkai.
  const [state, setState] = useState<State>(
    decisionId && token ? { fase: "memuat" } : { fase: "tanpa-token" }
  );

  useEffect(() => {
    if (!decisionId || !token) {
      setState({ fase: "tanpa-token" });
      return;
    }
    let batal = false;
    setState({ fase: "memuat" });
    (async () => {
      try {
        const paket = (await fetchDecisionPacket(decisionId, token)) as {
          batch_evaluations?: BatchEvaluationView[] | null;
        } | null;
        if (batal) return;
        setState({
          fase: "siap",
          evaluations: Array.isArray(paket?.batch_evaluations)
            ? (paket?.batch_evaluations as BatchEvaluationView[])
            : [],
        });
      } catch {
        // Gagal mengambil paket TIDAK dikarang: tabelnya cukup tidak tampil.
        if (!batal) setState({ fase: "gagal" });
      }
    })();
    return () => {
      batal = true;
    };
  }, [decisionId, token]);

  const fakta = decisionFacts({ ...selected, summary }, now);

  return (
    <section
      className="dash-ident"
      id="identitas" data-bagian="identitas"
      aria-labelledby="judul-identitas"
      data-testid="identitas-batch"
    >
      <header className="dash-ident-head">
        <h2 className="dash-ident-title" id="judul-identitas">
          Identitas &amp; batch
        </h2>
        <p className="dash-ident-lead">
          Ciri keputusan ini dan batch yang terikat padanya — termasuk batch yang
          ditahan gerbang sebelum boleh dikirim.
        </p>
      </header>

      <article className="ident-block" data-block="identitas">
        <h3 className="ident-block-title">Identitas keputusan</h3>
        <table className="ident-table">
          <caption className="ident-caption">Identitas keputusan</caption>
          <tbody>
            {fakta.map((row) => (
              <tr className="ident-row" key={row.label}>
                <th scope="row">{row.label}</th>
                <td>
                  {row.value}
                  {row.hint ? <span className="ident-note">{row.hint}</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>

      <article className="ident-block" data-block="evaluasi" data-fase={state.fase}>
        <h3 className="ident-block-title">Evaluasi batch</h3>
        {state.fase === "tanpa-token" ? (
          <p className="ident-kosong" data-testid="evaluasi-tanpa-token">
            Evaluasi batch butuh sesi yang sudah masuk; halaman ini tidak
            menampilkan batch apa pun tanpa itu.
          </p>
        ) : state.fase === "memuat" ? (
          <p className="ident-kosong" data-testid="evaluasi-memuat">
            Memuat evaluasi batch…
          </p>
        ) : state.fase === "gagal" ? (
          <p className="ident-kosong" data-testid="evaluasi-gagal">
            Evaluasi batch belum bisa dimuat. Halaman ini sengaja tidak
            menampilkan angka apa pun yang belum terbaca dari server.
          </p>
        ) : state.evaluations.length === 0 ? (
          <BatchEvaluationTable evaluations={state.evaluations} />
        ) : (
          <>
            {/* Satu baris ringkas sebagai label yang TERBACA; caption tabel
                disembunyikan secara visual (tetap ada untuk pembaca layar).
                Alasan: di panel sempit caption 560 px terpotong di tengah
                kalimat — terbaca seperti halaman rusak. */}
            <p className="ident-eval-ringkas" data-testid="evaluasi-ringkas">
              {state.evaluations.length} batch ·{" "}
              {state.evaluations.filter((b) => b.status !== "usable").length} perlu
              tindakan
            </p>
            <BatchEvaluationTable evaluations={state.evaluations} />
          </>
        )}
      </article>
    </section>
  );
}
