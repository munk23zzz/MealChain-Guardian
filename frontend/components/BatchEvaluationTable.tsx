"use client";

// BatchEvaluationTable — evaluasi batch dari PAKET KEPUTUSAN server (Fase 6
// butir 4 & 7).
//
// Kenapa komponen ini ada: sebelumnya layar keputusan hanya menampilkan status
// keputusan, sehingga batch yang TERTAHAN (on_hold: bukti suhu kurang, menunggu
// verifikasi, dst.) tidak terlihat sebagai pekerjaan yang harus diselesaikan.
// Komponen ini TIDAK menilai apa pun: status, alasan, dan langkah berikutnya
// datang dari `GET /decisions/{id}/packet` yang memakai evaluator yang sama
// dengan gerbang dispatch. Menghitung ulang di klien akan membuat dua layar
// menyimpulkan hal berbeda dari data yang sama.

import { humanizeBlocker, safetyLabel } from "../lib/bahasa";

export type BatchEvaluationView = {
  batch_id: string;
  status: string; // usable | on_hold | rejected | quarantined (gerbang)
  safety_status?: string | null;
  blocking_reasons?: string[] | null;
  next_step?: string | null;
  evidence_state?: string | null;
  usable_until?: string | null;
};

const GATE_WORDS: Record<string, string> = {
  usable: "layak",
  on_hold: "ditahan — butuh bukti",
  rejected: "ditolak gerbang",
  quarantined: "dikarantina",
};

function tanggal(iso?: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("id-ID");
}

export default function BatchEvaluationTable({
  evaluations,
}: {
  evaluations?: BatchEvaluationView[] | null;
}) {
  const daftar = Array.isArray(evaluations) ? evaluations : [];
  if (daftar.length === 0) {
    return (
      <p className="evidence-note">
        Keputusan ini tidak mengikat batch, jadi tidak ada evaluasi batch.
      </p>
    );
  }

  const perluTindakan = daftar.filter((b) => b.status !== "usable");

  return (
    <div className="batch-eval">
      <table className="batch-eval-table">
        <caption>
          Evaluasi batch (gerbang yang sama dengan dispatch): {daftar.length}{" "}
          batch, {perluTindakan.length} perlu tindakan.
        </caption>
        <thead>
          <tr>
            <th scope="col">Batch</th>
            <th scope="col">Gerbang</th>
            <th scope="col">Keamanan</th>
            <th scope="col">Layak sampai</th>
            <th scope="col">Alasan / langkah berikutnya</th>
          </tr>
        </thead>
        <tbody>
          {daftar.map((b) => {
            const alasan = (b.blocking_reasons ?? [])
              .map((k) => humanizeBlocker(k) ?? k)
              .join("; ");
            return (
              <tr key={b.batch_id} className={`batch-eval-${b.status}`}>
                <td>
                  <code>{String(b.batch_id).slice(0, 8)}</code>
                </td>
                <td>{GATE_WORDS[b.status] ?? b.status}</td>
                <td>{safetyLabel(b.safety_status) ?? b.safety_status ?? "-"}</td>
                <td>{tanggal(b.usable_until)}</td>
                <td>
                  {alasan || "—"}
                  {b.next_step && (
                    <div className="batch-eval-next">Langkah: {b.next_step}</div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
