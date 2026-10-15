// Kontrak markup halaman "Pemasok" (halaman sidebar acuan /suppliers).
//
// Fase 3 (2026-10-14): prop `pairs` (sampel keputusan) diganti `suppliers`
// (payload GET /suppliers). Yang diuji di sini adalah KEHORMATAN tampilan:
// angka tidak dikarang, keadaan "belum dimuat" tidak disamarkan sebagai
// "tidak ada data", dan enum internal tidak bocor ke layar.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplierBoard from "../components/SupplierBoard";
import type { SupplierContext } from "../lib/supplier-exclusions";

const SUPPLIERS = {
  count: 3,
  total: 3,
  items: [
    {
      id: "s1",
      name: "Wortel Lestari Cianjur",
      location: "Cianjur",
      commodity: "wortel",
      certification_status: "haccp",
      reliability_score: 0.93,
      latitude: -6.824,
      longitude: 107.1636,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
    {
      id: "s2",
      name: "Telur Berkah Cianjur",
      location: "Cianjur",
      commodity: "telur",
      certification_status: "none",
      reliability_score: 0.38,
      latitude: -6.811,
      longitude: 107.1636,
      excluded_at_hub: true,
      excluded_scope_locations: ["Cianjur", "Jakarta"],
    },
    {
      id: "s3",
      name: "Supplier A Cianjur",
      location: "Cianjur",
      commodity: null,
      certification_status: null,
      reliability_score: 0.8,
      latitude: -6.854,
      longitude: 107.1306,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
  ],
};

const CONTEXT = {
  suppliers: [
    {
      id: "s1",
      name: "Wortel Lestari Cianjur",
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

function render(props: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <SupplierBoard
      suppliers={SUPPLIERS}
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
  it("judul + ringkasan pemasok dari daftar (bukan sampel keputusan)", () => {
    const html = render();
    expect(html).toContain("Pemasok");
    expect(html).toContain("Pemasok terdaftar");
    expect(html).toContain("Rata-rata keandalan");
    expect(html).toContain("70%"); // (0,93 + 0,38 + 0,80) / 3
    expect(html).toContain("Keandalan rendah (&lt; 60%)");
    expect(html).toContain("Punya titik peta");
    expect(html).toContain("3 dari 3");
    // Tidak ada lagi kolom turunan sampel keputusan.
    expect(html).not.toContain("Keputusan terpindai");
  });

  it("tabel memuat hub, komoditas, sertifikat, koordinat, dan status eksklusi", () => {
    const html = render();
    expect(html).toContain("Daftar pemasok");
    expect(html).toContain("Wortel Lestari Cianjur");
    expect(html).toContain("Cianjur");
    expect(html).toContain("HACCP");
    expect(html).toContain("-6,8240 / 107,1636");
    expect(html).toContain("Aktif");
    expect(html).toContain("Dikecualikan di Cianjur, Jakarta");
    expect(html).toContain("Tidak bersertifikat");
  });

  it("nilai yang tidak ada ditulis '—', bukan 0", () => {
    const html = render();
    expect(html).toContain(">—<");
    // Pemasok kanonik tanpa fokus komoditas.
    expect(html).toContain("Supplier A Cianjur");
    expect(html).not.toContain(">0%<");
  });

  it("daftar belum dimuat: tidak mengklaim 'tidak ada pemasok'", () => {
    const html = render({ suppliers: null });
    expect(html).not.toContain("Tidak ada pemasok yang terdaftar");
    expect(html).toContain("belum dimuat");
  });

  it("daftar dimuat dan kosong: klaim 'tidak ada pemasok' sah", () => {
    const html = render({ suppliers: { items: [], count: 0 } });
    expect(html).toContain("Tidak ada pemasok yang terdaftar");
  });

  it("galat muat: pesan manusia + tombol coba lagi, tanpa bocor path API", () => {
    const html = render({ error: "HTTP 500: /suppliers", onRetry: () => {} });
    expect(html).toContain("Tidak bisa memuat data pemasok");
    expect(html).toContain("Coba lagi");
    expect(html).not.toContain("HTTP 500");
    expect(html).not.toContain("/suppliers");
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

  it("register belum dimuat (exclusions null): TIDAK mengklaim tidak ada eksklusi", () => {
    const html = render({ exclusions: null });
    expect(html).not.toContain("Tidak ada pemasok yang sedang dieksklusi");
    expect(html).toContain("belum dimuat");
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

  it("tidak ada catatan internal (path API) di layar", () => {
    const html = render();
    expect(html).not.toContain("endpoint");
    expect(html).not.toContain("/supplier-exclusions");
    expect(html).not.toContain("/suppliers");
    expect(html).not.toContain("Dari mana angka ini");
  });
});
