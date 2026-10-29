// Ringkasan eksekusi di tab Agent Log (UI-1, 29 Okt 2026).
//
// Yang dijaga tes ini:
//   1. Enam keadaan yang benar-benar ada di daftar keputusan tampil dengan
//      label teks — bukan warna saja.
//   2. Daftar kosong TIDAK dicetak sebagai enam angka nol; ia satu kalimat.
//   3. Batas skema dinyatakan: tidak ada angka "berjalan"/"gagal" per eksekusi.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import AgentExecutionSummary from "../components/AgentExecutionSummary";
import type { ExecutionOverview } from "../lib/agent-execution";

const ISI: ExecutionOverview = {
  total: 17,
  reviewed: 8,
  waiting: 14,
  rejected: 1,
  flagged: 1,
  overdue: 2,
  attention: 3,
};

describe("AgentExecutionSummary", () => {
  it("menampilkan enam keadaan dengan label yang bisa dibaca", () => {
    const html = renderToStaticMarkup(
      <AgentExecutionSummary overview={ISI} periodLabel="24 jam terakhir" />
    );
    for (const label of [
      "Perlu perhatian",
      "Keputusan",
      "Punya jejak agen",
      "Menunggu verifikasi",
      "Ditolak verifikator",
      "Lewat tenggat",
    ]) {
      expect(html).toContain(label);
    }
    expect(html).toContain("24 jam terakhir");
    expect(html).toContain("17");
  });

  it("kotak 'Perlu perhatian' menyebut sebabnya, bukan hanya angka", () => {
    const html = renderToStaticMarkup(<AgentExecutionSummary overview={ISI} />);
    expect(html).toContain("1 ditandai verifikator");
    expect(html).toContain("2 lewat tenggat");
    expect(html).toContain('data-tone="warn"');
  });

  it("tanpa keputusan: satu kalimat kosong, bukan deretan nol", () => {
    const html = renderToStaticMarkup(
      <AgentExecutionSummary
        overview={{
          total: 0,
          reviewed: 0,
          waiting: 0,
          rejected: 0,
          flagged: 0,
          overdue: 0,
          attention: 0,
        }}
      />
    );
    expect(html).toContain("Belum ada keputusan pada periode ini");
    expect(html).not.toContain("aa-exec-value");
  });

  it("saat daftar masih dimuat tidak menyimpulkan kosong", () => {
    const html = renderToStaticMarkup(
      <AgentExecutionSummary
        loading
        overview={{
          total: 0,
          reviewed: 0,
          waiting: 0,
          rejected: 0,
          flagged: 0,
          overdue: 0,
          attention: 0,
        }}
      />
    );
    expect(html).toContain("Memuat ringkasan eksekusi");
    expect(html).not.toContain("Belum ada keputusan pada periode ini");
  });

  it("menyatakan batas skema: status berjalan/gagal tidak dicatat", () => {
    const html = renderToStaticMarkup(<AgentExecutionSummary overview={ISI} />);
    expect(html).toContain("tidak menyimpan");
    expect(html).toContain("berjalan");
    expect(html).toContain("ditolak verifikator");
  });

  it("tidak mengarang angka yang tidak ada di data", () => {
    const html = renderToStaticMarkup(<AgentExecutionSummary overview={ISI} />);
    // Tidak ada istilah "berjalan" sebagai NILAI, dan tidak ada persen karangan
    // ketika totalnya nol.
    expect(html).not.toContain("aa-exec-value\">—");
  });
});
