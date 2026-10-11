// Kontrak markup halaman "Pemasok" (halaman sidebar acuan /suppliers).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplierBoard from "../components/SupplierBoard";
import type { SupplierContext } from "../lib/supplier-exclusions";

const PAIRS = [
  { decisionId: "d1", decisionType: "regional_balance", commodity: "telur", supplier: { id: "s1", name: "Supplier A Cianjur", reliability_score: 0.8 } },
  { decisionId: "d2", decisionType: "regional_balance", commodity: "ayam", supplier: { id: "s1", name: "Supplier A Cianjur", reliability_score: 0.8 } },
];

const CONTEXT = {
  suppliers: [
    {
      id: "s1",
      name: "Supplier A Cianjur",
      batch_ids: ["b1"],
      evidence_refs: [{ type: "batch", id: "b1" }],
      batches: [{ id: "b1", safety_status: "pass" }],
    },
  ],
  scope_location_id: "loc-1",
  can_propose: false,
  reason_unavailable: null,
  exclusions: [],
} as unknown as SupplierContext;

function render(props: Partial<Parameters<typeof SupplierBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <SupplierBoard
      pairs={PAIRS}
      exclusions={{ items: [], count: 0 }}
      selectedDecisionId={null}
      supplierContext={null}
      role="bgn_monitor"
      token="t"
      {...props}
    />
  );
}

describe("SupplierBoard", () => {
  it("judul + ringkasan pemasok dari keputusan", () => {
    const html = render();
    expect(html).toContain("Pemasok");
    expect(html).toContain("Pemasok terlibat");
    expect(html).toContain("Supplier A Cianjur");
    expect(html).toContain("80%");
  });

  it("tabel daftar pemasok memuat jumlah keputusan + komoditas", () => {
    const html = render();
    expect(html).toContain("Daftar pemasok");
    expect(html).toContain("ayam, telur");
  });

  it("register eksklusi kosong dijelaskan apa adanya", () => {
    const html = render();
    expect(html).toContain("Register eksklusi");
    expect(html).toContain("Tidak ada pemasok yang sedang dieksklusi");
  });

  it("register eksklusi terisi ditampilkan dengan alasan + kode keputusan", () => {
    const html = render({
      exclusions: {
        items: [
          { id: "e1", supplier_name: "Supplier C Jakarta", reason: "dua kiriman suhu menyimpang", excluded_at: "2026-10-11T02:00:00Z", decision_id: "d9d9d9d9-1111" },
        ],
      },
    });
    expect(html).toContain("Supplier C Jakarta");
    expect(html).toContain("dua kiriman suhu menyimpang");
    expect(html).toContain("d9d9d9d9");
  });

  it("tanpa keputusan terpilih: form eksklusi diganti penjelasan", () => {
    const html = render();
    expect(html).toContain("Usul eksklusi");
    expect(html).toContain("Pilih keputusan lebih dulu");
  });

  it("dengan konteks keputusan: panel eksklusi nyata dipasang", () => {
    const html = render({ selectedDecisionId: "d1", supplierContext: CONTEXT, role: "sppg_head" });
    expect(html).toContain("Supplier governance");
  });

  it("catatan sumber menyebut keterbatasan endpoint", () => {
    expect(render()).toContain("belum punya endpoint daftar pemasok");
  });
});
