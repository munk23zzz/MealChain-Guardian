// Papan status integrasi (W-3 · PLAN-012) — kontrak tampilan KEJUJURAN.
//
// Yang dipaku: kategori ditampilkan sebagai JENIS BUKTI (bukan "operasional"),
// hijau hanya untuk `probe_passed`, komponen tanpa bukti tidak pernah hijau, dan
// panel menyebut berapa probe yang benar-benar dijalankan — termasuk nol.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import IntegrationStatusPanel, { categoryTone, probesNote } from "../components/IntegrationStatusPanel";

const PAYLOAD = {
  checked_at: "2026-10-17T03:00:00+00:00",
  probes_run: 0,
  components: [
    {
      id: "sap_ai_core",
      name: "SAP AI Core (SAP-RPT-1.6)",
      category: "contract_tested",
      category_label: "kontrak diuji",
      evidence: "env SAP_AI_CORE_CLIENT_ID terisi",
      artifact: "docs/verification/fase-12.md",
      note: "Peramal deret resmi; kontrak pemanggil diuji di backend/tests.",
    },
    {
      id: "agentcore_runtime",
      name: "AgentCore Runtime (Strands supervisor)",
      category: "artifacts_ready",
      category_label: "artefak siap",
      evidence: "env AGENTCORE_RUNTIME_ARN kosong; artefak agent/ siap",
      artifact: "agent/README-deploy.md",
      note: "Deploy belum dijalankan.",
    },
    {
      id: "aws_for_sap_mcp",
      name: "AWS for SAP MCP",
      category: "not_started",
      category_label: "belum dimulai",
      evidence: "belum ada implementasi/tenant",
      artifact: "docs/Roadmap.md",
      note: "Tertahan akses tenant SAP S/4HANA.",
    },
  ],
};

function render(props: Record<string, unknown> = {}) {
  return renderToStaticMarkup(<IntegrationStatusPanel data={PAYLOAD} {...props} />);
}

describe("IntegrationStatusPanel", () => {
  it("menampilkan kategori sebagai jenis bukti beserta sumbernya", () => {
    const html = render();
    expect(html).toContain("kontrak diuji");
    expect(html).toContain("artefak siap");
    expect(html).toContain("belum dimulai");
    expect(html).toContain("Bukti: env SAP_AI_CORE_CLIENT_ID terisi");
    expect(html).toContain("Sumber: agent/README-deploy.md");
  });

  it("tanpa probe: tidak ada satu pun baris hijau", () => {
    const html = render();
    expect(html).toContain("Tidak ada probe jaringan dijalankan");
    expect(html).not.toContain("integration-badge-ok");
  });

  it("komponen yang belum ada berbunyi belum dimulai (merah), bukan hijau", () => {
    const html = render();
    // Kelas nada ada di elemen <li>, SEBELUM nama komponen — potong per baris.
    const baris = html.split("<li").find((b) => b.includes("AWS for SAP MCP")) ?? "";
    expect(baris).toContain("integration-tone-danger");
    expect(baris).not.toContain("integration-tone-ok");
  });

  it("hijau hanya untuk bukti probe nyata", () => {
    const denganProbe = render({
      data: {
        checked_at: PAYLOAD.checked_at,
        probes_run: 1,
        components: [
          {
            id: "mock_sap",
            name: "Mock SAP",
            category: "probe_passed",
            category_label: "probe lulus",
            evidence: "GET /health → 200",
            artifact: "backend/app/sap_integration/mock_service.py",
          },
        ],
      },
    });
    expect(denganProbe).toContain("integration-badge-ok");
    expect(denganProbe).toContain("1 probe nyata dijalankan");
  });

  it("galat ditampilkan apa adanya, bukan layar kosong yang tampak aman", () => {
    const html = render({ error: "HTTP 500: /integrations/status" });
    expect(html).toContain("Status integrasi tidak bisa dibaca");
    expect(html).toContain("HTTP 500");
    expect(html).not.toContain("integration-badge-ok");
  });

  it("probesNote jujur soal nol probe", () => {
    expect(probesNote(0)).toContain("Tidak ada probe jaringan dijalankan");
    expect(probesNote(null)).toContain("Tidak ada probe jaringan dijalankan");
    expect(probesNote(3)).toBe("3 probe nyata dijalankan untuk papan ini.");
  });

  it("pemetaan nada: hanya probe_passed yang hijau", () => {
    expect(categoryTone("probe_passed")).toBe("ok");
    expect(categoryTone("contract_tested")).toBe("plain");
    expect(categoryTone("configured")).toBe("plain");
    expect(categoryTone("provisioned")).toBe("plain");
    expect(categoryTone("artifacts_ready")).toBe("plain");
    expect(categoryTone("fail_closed")).toBe("warn");
    expect(categoryTone("unavailable")).toBe("danger");
    expect(categoryTone("not_started")).toBe("danger");
  });
});
