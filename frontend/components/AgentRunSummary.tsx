"use client";

// AgentRunSummary — status model agent (dokumen 06 §2.9).
//
// Satu-satunya tempat status model muncul. Yang dijaga: membedakan
//   - "belum ada trace" (tidak ada yang bisa dinilai), dan
//   - "trace ada, tetapi tidak ada langkah model" (provider tidak dipanggil).
// Keduanya BUKAN "provider sehat". ProviderPanel sendiri hanya hijau bila
// payload backend bilang `status: "ok"`.

import ProviderPanel from "./ProviderPanel";

export default function AgentRunSummary({
  providers,
  traceCount,
  modelSteps,
  hasError = false,
}: {
  providers: Record<string, unknown>;
  /** Jumlah langkah trace keputusan terpilih. */
  traceCount: number;
  /** Jumlah langkah yang benar-benar berasal dari model (VERIFY/SUPERVISE). */
  modelSteps: number;
  hasError?: boolean;
}) {
  const catatan = hasError
    ? "Sebagian bukti model gagal dibaca; status di bawah hanya yang berhasil dimuat."
    : traceCount === 0
    ? "Belum ada trace untuk keputusan ini, jadi status model belum bisa dinilai dari jejak."
    : modelSteps === 0
    ? `Trace berisi ${traceCount} langkah, tetapi tidak satu pun langkah model — status di bawah tidak berasal dari jejak.`
    : `${modelSteps} langkah model tercatat pada trace ini.`;

  return (
    <section className="aa-run-summary" aria-label="Ringkasan status model agent">
      <p className="aa-run-note">{catatan}</p>
      {/* Tanpa satu pun langkah model, tidak ada yang bisa dibaca dari jejak.
          Menampilkan tiga baris "tidak tersedia" untuk setiap keputusan
          membuat pembaca menyimpulkan "model tidak pernah jalan" — kesimpulan
          yang lebih besar daripada buktinya (audit 29 Okt 2026). */}
      {modelSteps > 0 ? (
        <ProviderPanel providers={providers as Record<string, never>} />
      ) : (
        <p className="aa-run-empty" data-testid="aa-run-tanpa-model">
          Tidak ada baris status provider yang bisa ditampilkan dari jejak ini.
        </p>
      )}
    </section>
  );
}
