"use client";

// AgentExecutionSummary — ringkasan eksekusi tab Agent Log (UI-1, 29 Okt 2026).
//
// Yang dijaga:
// 1. Hanya keadaan yang BENAR-BENAR ada di skema yang dihitung. Tidak ada
//    "berjalan" atau "gagal" per eksekusi karena tabel tidak menyimpannya;
//    kalimat kaki menyebut batas itu, bukan menyembunyikannya.
// 2. Nol yang nyata ditulis "0" (keputusan memang tidak ada), sedangkan daftar
//    kosong tidak dicetak sebagai enam angka nol — ia satu kalimat kosong.
// 3. Angka tidak bergantung pada warna: setiap kotak punya label teks.

import type { ExecutionOverview } from "../lib/agent-execution";

type Tone = "neutral" | "ok" | "warn" | "danger";

function persen(bagian: number, total: number): string | null {
  if (total <= 0) return null;
  const nilai = (bagian / total) * 100;
  return `${nilai < 10 ? nilai.toFixed(1) : Math.round(nilai)}%`;
}

export default function AgentExecutionSummary({
  overview,
  periodLabel = null,
  loading = false,
}: {
  overview: ExecutionOverview;
  /** Nama periode terpilih (mis. "24 jam"); ditulis di kaki ringkasan. */
  periodLabel?: string | null;
  /** Daftar masih dimuat: jangan menyimpulkan "belum ada keputusan". */
  loading?: boolean;
}) {
  const { total, reviewed, waiting, rejected, flagged, overdue, attention } = overview;

  const tiles: {
    key: string;
    label: string;
    value: number;
    note: string;
    tone: Tone;
    title: string;
  }[] = [
    {
      key: "attention",
      label: "Perlu perhatian",
      value: attention,
      note:
        attention > 0
          ? [flagged > 0 ? `${flagged} ditandai verifikator` : null, overdue > 0 ? `${overdue} lewat tenggat` : null]
              .filter(Boolean)
              .join(" · ")
          : "tidak ada yang ditandai",
      tone: attention > 0 ? "warn" : "ok",
      title: "Keputusan yang ditandai verifikator atau tenggatnya sudah lewat",
    },
    {
      key: "total",
      label: "Keputusan",
      value: total,
      note: periodLabel ? `periode ${periodLabel}` : "pada periode terpilih",
      tone: "neutral",
      title: "Seluruh keputusan pada periode terpilih",
    },
    {
      key: "reviewed",
      label: "Punya jejak agen",
      value: reviewed,
      note: (() => {
        const bagian = persen(reviewed, total);
        return bagian ? `${bagian} dari ${total} keputusan` : "belum ada keputusan";
      })(),
      tone: "neutral",
      title: "Keputusan yang sudah punya jejak penilaian agent (bukan tanda sudah diverifikasi)",
    },
    {
      key: "waiting",
      label: "Menunggu verifikasi",
      value: waiting,
      note: "belum ada penilaian verifikator",
      tone: "neutral",
      title: "Keputusan yang belum diverifikasi",
    },
    {
      key: "rejected",
      label: "Ditolak verifikator",
      value: rejected,
      note: "butuh usulan ulang",
      tone: rejected > 0 ? "danger" : "neutral",
      title: "Keputusan yang ditolak; tidak dapat dieksekusi tanpa usulan baru",
    },
    {
      key: "overdue",
      label: "Lewat tenggat",
      value: overdue,
      note: "masih menunggu tindakan",
      tone: overdue > 0 ? "danger" : "neutral",
      title: "Keputusan yang masih menunggu tindakan padahal tenggatnya sudah lewat",
    },
  ];

  return (
    <section className="aa-exec" aria-labelledby="aa-exec-title" data-testid="agent-execution-summary">
      <div className="aa-exec-head">
        <h3 id="aa-exec-title" className="aa-section-title">
          Ringkasan eksekusi
        </h3>
        <p className="aa-exec-caption">Keadaan keputusan pada periode terpilih</p>
      </div>

      {total === 0 ? (
        <p className="aa-exec-empty" data-testid="agent-execution-empty">
          {loading
            ? "Memuat ringkasan eksekusi…"
            : "Belum ada keputusan pada periode ini, jadi tidak ada yang bisa diringkas."}
        </p>
      ) : (
        <dl className="aa-exec-grid">
          {tiles.map((tile) => (
            <div
              key={tile.key}
              className="aa-exec-tile"
              data-tone={tile.tone}
              data-metric={tile.key}
              title={tile.title}
            >
              <dt>{tile.label}</dt>
              <dd className="aa-exec-value">
                {tile.value.toLocaleString("id-ID")}
              </dd>
              <span className="aa-exec-note">{tile.note}</span>
            </div>
          ))}
        </dl>
      )}

      <p className="aa-exec-foot">
        Dihitung dari daftar keputusan, bukan dari catatan eksekusi. Status
        <em> berjalan</em> atau <em>gagal</em> per eksekusi tidak dicatat;
        kegagalan yang tercatat adalah keputusan yang ditolak verifikator.
      </p>
    </section>
  );
}
