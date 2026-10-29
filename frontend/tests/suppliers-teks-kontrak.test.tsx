// S0 — kontrak teks halaman Suppliers (29 Okt 2026).
//
// Sebab: pekerjaan 29 Okt membersihkan kalimat backend yang bocor ke layar di
// halaman lain (Food Safety, KPI, Pemasok). Halaman Suppliers belum punya
// penjaga sendiri, jadi kebocoran bisa masuk lagi tanpa ada yang gagal.
//
// Aturannya sempit dan disengaja: yang dilarang HANYA kata yang menyebut mesin
// (backend/server/database/payload/schema/endpoint) dan kode basis data
// (historical_seed). Kata "pemasok", "kiriman", "register" bebas dipakai —
// tes ini mengunci istilah mesin, bukan kosakata halaman.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplierBoard from "../components/SupplierBoard";
import { SupplierExclusionView } from "../components/SupplierExclusionPanel";
import type { SupplierContext } from "../lib/supplier-exclusions";

const TERLARANG = [/backend/i, /\bserver\b/i, /database/i, /\bpayload\b/i, /\bschema\b/i, /endpoint/i, /historical_seed/i];

const SUPPLIERS = {
  count: 2,
  total: 2,
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
      reliability_score: 0.71,
      latitude: -6.811,
      longitude: 107.1636,
      excluded_at_hub: false,
      excluded_scope_locations: [],
    },
  ],
};

const KONTEKS = {
  suppliers: [{ id: "s1", name: "Wortel Lestari Cianjur", batch_ids: ["b1"], evidence_refs: [], batches: [] }],
  scope_location_id: "loc-1",
  can_propose: true,
  reason_unavailable: null,
  exclusions: [],
} as unknown as SupplierContext;

function papan(props: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <SupplierBoard
      suppliers={SUPPLIERS}
      exclusions={{ items: [], count: 0 }}
      selectedDecisionId={null}
      supplierContext={KONTEKS}
      role="sppg_head"
      token="t"
      {...props}
    />
  );
}

function periksa(html: string) {
  for (const pola of TERLARANG) {
    expect(html).not.toMatch(pola);
  }
}

describe("halaman Suppliers tidak menyebut mesin", () => {
  it("keadaan normal: daftar, ringkasan, register, riwayat", () => {
    const html = papan();
    expect(html).toContain("Daftar pemasok");
    periksa(html);
  });

  it("belum dimuat: kalimat 'belum dimuat' tanpa menyebut asal data", () => {
    const html = papan({ suppliers: null });
    expect(html).toContain("belum dimuat");
    periksa(html);
  });

  it("daftar kosong: klaim apa adanya, tanpa istilah mesin", () => {
    const html = papan({ suppliers: { items: [], count: 0 } });
    expect(html).toContain("Tidak ada pemasok yang terdaftar");
    periksa(html);
  });

  it("galat muat: pesan manusia + tombol coba lagi, tanpa 'backend'/'server'", () => {
    const html = papan({ error: "HTTP 500: /suppliers", onRetry: () => {} });
    expect(html).toContain("Tidak bisa memuat data pemasok");
    expect(html).toContain("Coba lagi");
    periksa(html);
  });

  it("register eksklusi terisi: alasan & waktu, tanpa istilah mesin", () => {
    const html = papan({
      exclusions: {
        items: [
          {
            id: "e1",
            supplier_name: "Supplier C Jakarta",
            reason: "dua kiriman suhu menyimpang",
            excluded_at: "2026-10-11T02:00:00Z",
            decision_id: "d9d9d9d9-1111",
          },
        ],
        count: 1,
      },
    });
    expect(html).toContain("dua kiriman suhu menyimpang");
    periksa(html);
  });

  it("form usul eksklusi: keterangan ID tidak menjelaskan mekanisme validasi", () => {
    const html = renderToStaticMarkup(
      <SupplierExclusionView context={KONTEKS} role="sppg_head" token="t" onCreated={() => {}} />
    );
    // Panelnya sendiri berlabel "Usulan exclusion"; judul kartu "Usul eksklusi"
    // dipasang SupplierBoard, bukan panel — jadi yang diperiksa di sini formulirnya.
    expect(html).toContain('aria-label="Usulan eksklusi"');
    periksa(html);
  });
});
