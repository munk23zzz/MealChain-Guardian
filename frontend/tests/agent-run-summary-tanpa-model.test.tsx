// Panel "Status Model Agent" tidak boleh menampilkan tiga baris "tidak
// tersedia" untuk SETIAP keputusan (audit 29 Okt 2026).
//
// Di seluruh database ada 0 langkah SUPERVISE, jadi `providersFromTraces`
// selalu kosong; tiga baris merah "tidak tersedia" membuat juri membaca
// "model tidak pernah jalan", padahal yang benar adalah "jejak ini tidak
// memuat langkah model". Bedanya besar, dan hanya kalimat yang bisa
// menyampaikannya.

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import AgentRunSummary from "../components/AgentRunSummary";

describe("AgentRunSummary tanpa langkah model", () => {
  it("menjelaskan, bukan menampilkan baris provider kosong", () => {
    const html = renderToStaticMarkup(
      <AgentRunSummary providers={{}} traceCount={2} modelSteps={0} />,
    );
    expect(html).toContain("tidak satu pun langkah model");
    expect(html).not.toContain("provider-row");
    expect(html).not.toContain("tidak tersedia");
  });

  it("tetap menampilkan provider bila ada langkah model", () => {
    const html = renderToStaticMarkup(
      <AgentRunSummary
        providers={{ supervisor: { status: "ok" } }}
        traceCount={3}
        modelSteps={1}
      />,
    );
    expect(html).toContain("provider-row");
    expect(html).toContain("1 langkah model tercatat");
  });

  it("tanpa trace sama sekali, kalimatnya berbeda", () => {
    const html = renderToStaticMarkup(
      <AgentRunSummary providers={{}} traceCount={0} modelSteps={0} />,
    );
    expect(html).toContain("Belum ada trace untuk keputusan ini");
  });
});
