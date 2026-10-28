// Tes daftar jejak agen milik satu keputusan (rencana langkah 5).
// Jejak dirender DI DALAM dossier, bukan lewat lompatan ke tab Agent Log.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DecisionTraceList from "../components/DecisionTraceList";

const langkah = [
  {
    step_name: "Periksa kecukupan stok",
    agent_name: "balance-agent",
    tool_called: "balance_map",
    duration_ms: 42.4,
    step_at: "2026-10-28T09:15:00Z",
  },
  {
    step_name: "Susun alokasi",
    agent_name: "allocation-agent",
    tool_called: null,
    duration_ms: null,
    step_at: null,
  },
];

function render(props: Parameters<typeof DecisionTraceList>[0]): string {
  return renderToStaticMarkup(<DecisionTraceList {...props} />);
}

describe("DecisionTraceList", () => {
  it("mencetak setiap langkah dengan agen dan alatnya", () => {
    const html = render({ traces: { steps: langkah } });
    expect(html).toContain("Periksa kecukupan stok");
    expect(html).toContain("balance-agent");
    expect(html).toContain("balance_map");
    expect(html).toContain("42");
    expect(html).toContain("Susun alokasi");
    expect(html).toContain("allocation-agent");
  });

  it("menyebut sebab ketika belum ada langkah terekam", () => {
    expect(render({ traces: { steps: [] } })).toMatch(/belum ada langkah agen yang terekam/i);
    expect(render({ traces: null })).toMatch(/belum ada langkah agen yang terekam/i);
  });

  it("menulis keadaan memuat, bukan daftar kosong yang menyamar", () => {
    expect(render({ traces: null, loading: true })).toMatch(/memuat jejak agen/i);
  });

  it("meneruskan pesan galat apa adanya", () => {
    const html = render({ traces: null, error: "HTTP 403" });
    expect(html).toMatch(/gagal dimuat: HTTP 403/);
  });

  it("menerima array langsung maupun bentuk {steps}", () => {
    expect(render({ traces: langkah })).toContain("Periksa kecukupan stok");
  });
});
