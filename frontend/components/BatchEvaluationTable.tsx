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
import { formatDate } from "../lib/datetime";

export type BatchEvaluationView = {
  batch_id: string;
  status: string; // usable | on_hold | rejected | quarantined (gerbang)
  safety_status?: string | null;
  blocking_reasons?: string[] | null;
  next_step?: string | null;
  evidence_state?: string | null;
  usable_until?: string | null;
};

/* Kata gerbang + nada lencananya (polish 30 Okt 2026).
   Dulu nilainya string huruf kecil ("layak") sehingga kolom ini terbaca
   sebagai kode, bukan label; dan tanggalnya "23/11/2026" sementara halaman
   ini menulis "29 Okt 2026". Sekarang kata dan warna satu sumber. */
const GATE_WORDS: Record<string, { label: string; tone: string }> = {
  usable: { label: "Layak", tone: "ok" },
  on_hold: { label: "Ditahan — butuh bukti", tone: "warn" },
  rejected: { label: "Ditolak gerbang", tone: "danger" },
  quarantined: { label: "Dikarantina", tone: "danger" },
};

function gateUntuk(status: string): { label: string; tone: string } {
  return GATE_WORDS[status] ?? { label: status || "—", tone: "muted" };
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
            const gate = gateUntuk(b.status);
            const alasan = (b.blocking_reasons ?? [])
              .map((k) => humanizeBlocker(k) ?? k)
              .join("; ");
            return (
              <tr key={b.batch_id} className={`batch-eval-${b.status}`}>
                <td>
                  <code className="batch-eval-id" title={b.batch_id}>
                    {String(b.batch_id).slice(0, 8)}
                  </code>
                </td>
                <td>
                  <span className={`board-badge board-badge-${gate.tone}`}>{gate.label}</span>
                </td>
                <td>{safetyLabel(b.safety_status) ?? b.safety_status ?? "—"}</td>
                <td className="batch-eval-date">{formatDate(b.usable_until)}</td>
                <td>
                  {alasan ? (
                    <span className="batch-eval-reason">{alasan}</span>
                  ) : (
                    <span className="batch-eval-none">—</span>
                  )}
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
