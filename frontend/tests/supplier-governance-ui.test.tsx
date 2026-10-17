import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import ApprovalModal from "../components/ApprovalModal";
import DecisionActions, { visibleActions } from "../components/DecisionActions";
import ApprovalMenu from "../components/ApprovalMenu";

const summary = {
  decision_id: "decision-local",
  decision_type: "supplier_exclusion",
  can_approve: true,
  can_execute: false,
  target_location: "Jakarta",
  supplier: { id: "supplier-known", name: "Pemasok teridentifikasi" },
  supplier_governance: {
    action: "exclude", reason: "Insiden suhu tercatat",
    scope_location_id: "jakarta", evidence_refs: [{ type: "batch", id: "batch-1" }],
  },
  expiry: { valid: true, seconds_remaining: 1200 },
  execution_target: "supplier_exclusion",
};

describe("Approval administratif supplier", () => {
  it("mereset form supplier saat keputusan terpilih berganti", () => {
    // Langkah 4 (11 Okt): form supplier ikut pindah ke halaman tersendiri
    // "Decision & Evidence" — kontrak `key` tetap sama, lokasinya berubah.
    const page = readFileSync("components/DecisionEvidence.tsx", "utf8");
    expect(page).toMatch(/<SupplierExclusionView\s+key=\{selected\.decision_id\}/);
  });
  it("menampilkan supplier, alasan, scope dan bukti tanpa PO atau biaya palsu", () => {
    const html = renderToStaticMarkup(<ApprovalModal summary={summary} />);
    expect(html).toContain("Insiden suhu tercatat");
    expect(html).toContain("Pemasok teridentifikasi");
    expect(html).toContain("Jakarta");
    expect(html).toContain("batch-1");
    expect(html).toContain("approval baru");
    expect(html).not.toContain("PO mock");
    expect(html).not.toContain("Total biaya");
    expect(html).not.toContain("Jumlah:");
  });

  it("restoration mempertahankan peringatan keamanan gagal", () => {
    const html = renderToStaticMarkup(<ApprovalModal summary={{ ...summary,
      decision_type: "supplier_exclusion_restoration", supplier_governance: {
        ...summary.supplier_governance, action: "restore",
      },
    }} />);
    expect(html).toContain("Pemulihan supplier");
    // Peringatannya tetap ada, dalam bahasa manusia (dulu "Batch FAIL ...").
    expect(html).toContain("gagal pemeriksaan");
    expect(html).not.toContain("PO mock");
  });

  it("administratif rejected tidak menawarkan repropose transfer", () => {
    // 2026-10-14: menu approval kini di dalam popup → yang diperiksa adalah
    // isi popup-nya (ApprovalMenu), bukan kartu halaman.
    const noop = async () => null;
    const html = renderToStaticMarkup(
      <ApprovalMenu
        summary={summary}
        actions={visibleActions("sppg_head", "rejected")}
        administrative
        onApprove={noop}
        onReject={noop}
        onVerify={noop}
        onExecute={noop}
        onRepropose={noop}
        onClose={() => {}}
      />
    );
    expect(html).not.toContain("Minta re-propose");
    expect(html).toContain("bukti baru");
  });
});
