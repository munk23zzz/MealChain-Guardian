// ProviderPanel — status provider model di dashboard (permintaan Roy, TDD).
// Kontrak:
// - tampil JUJUR dari payload backend: label slot:kind (primary:bedrock,
//   fallback_1:inferhub), fallback_used, attempt count
// - UNAVAILABLE/unavailable/error → badge netral, BUKAN hijau
// - fallback statistik forecast ditampilkan sebagai fallback, bukan model
// - AgentTraceViewer: langkah SUPERVISE menampilkan identitas model

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import ProviderPanel from "../components/ProviderPanel";
import AgentTraceViewer from "../components/AgentTraceViewer";

describe("ProviderPanel (status provider jujur)", () => {
  it("provider live: badge + label slot:kind + model", () => {
    const html = renderToStaticMarkup(
      <ProviderPanel
        providers={{
          verifier: {
            status: "ok",
            provider: "primary:bedrock",
            fallback_used: false,
            attempts: 1,
          },
        }}
      />
    );
    expect(html).toContain("provider-live");
    expect(html).toContain("primary:bedrock");
    expect(html).toContain("Verifier");
  });

  it("UNAVAILABLE → badge netral, bukan hijau (jujur)", () => {
    const html = renderToStaticMarkup(
      <ProviderPanel
        providers={{
          verifier: { status: "unavailable", provider: null, attempts: 0 },
        }}
      />
    );
    expect(html).toContain("provider-unavailable");
    expect(html).toContain("UNAVAILABLE");
    expect(html).not.toContain("provider-live");
  });

  it("fallback statistik forecast ditampilkan sebagai fallback", () => {
    const html = renderToStaticMarkup(
      <ProviderPanel
        providers={{
          forecast: {
            status: "fallback",
            provider: "statistical_fallback",
            fallback_used: true,
            attempts: 2,
          },
        }}
      />
    );
    expect(html).toContain("provider-fallback");
    expect(html).toContain("Fallback statistik");
    expect(html).toContain("2");
  });

  it("fallback_used → indikator fallback tampil", () => {
    const html = renderToStaticMarkup(
      <ProviderPanel
        providers={{
          supervisor: {
            status: "ok",
            provider: "fallback_1:inferhub",
            fallback_used: true,
            attempts: 2,
          },
        }}
      />
    );
    expect(html).toContain("fallback_1:inferhub");
    expect(html).toContain("(fallback)");
  });

  it("ketiga agent tampil: Verifier, Forecast, Supervisor", () => {
    const html = renderToStaticMarkup(<ProviderPanel providers={{}} />);
    expect(html).toContain("Verifier");
    expect(html).toContain("Forecast");
    expect(html).toContain("Supervisor");
  });
});

describe("AgentTraceViewer identitas model", () => {
  it("langkah SUPERVISE menampilkan provider slot:kind", () => {
    const html = renderToStaticMarkup(
      <AgentTraceViewer
        steps={[
          {
            step_name: "SUPERVISE",
            tool_called: "supervisor.narration",
            step_at: "2026-10-06T00:00:00Z",
            output_summary: {
              status: "narrated",
              provider: "primary:bedrock",
              summary: "Layak dieksekusi.",
            },
          },
        ]}
      />
    );
    expect(html).toContain("SUPERVISE");
    expect(html).toContain("primary:bedrock");
  });
});
