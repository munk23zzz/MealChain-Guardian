// S1 — kepala halaman Suppliers & navigasi bagian (29 Okt 2026).
//
// Tiga hal yang dikunci di sini:
//   1. Deskripsi kepala = SATU kalimat konteks, bukan daftar ulang isi halaman
//      (daftar itu pekerjaan lima tautan bagian di bawahnya).
//   2. Pil angka = tiga: pemasok · kiriman · eksklusi. Pil kiriman TIDAK
//      dirender saat jalur belum dimuat — "0 kiriman" akan jadi klaim palsu.
//   3. Lima tautan bagian, dan SETIAP id-nya benar-benar terpasang di markup.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import SupplierBoard from "../components/SupplierBoard";
import { SUPPLIER_SECTION_IDS, supplierSections } from "../lib/section-jump";

const SUPPLIERS = {
  count: 1,
  total: 1,
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
  ],
};

const RUTE = {
  routes: [
    {
      batch_id: "B-1",
      supplier_id: "s1",
      supplier_name: "Wortel Lestari Cianjur",
      origin: { latitude: -6.824, longitude: 107.1636, name: "Cianjur" },
      destination_id: "L1",
      destination_name: "Jakarta",
      destination: { latitude: -6.2, longitude: 106.8, name: "Jakarta" },
      commodity: "wortel",
      quantity_kg: 400,
      usable_until: "2026-11-07T11:00:00+00:00",
      safety_status: "pass",
      straight_km: 78.35,
      road: null,
      journey: null,
    },
    {
      batch_id: "B-2",
      supplier_id: "s1",
      supplier_name: "Wortel Lestari Cianjur",
      origin: { latitude: -6.824, longitude: 107.1636, name: "Cianjur" },
      destination_id: "L2",
      destination_name: "Bogor",
      destination: { latitude: -6.6, longitude: 106.8, name: "Bogor" },
      commodity: "wortel",
      quantity_kg: 120,
      usable_until: null,
      safety_status: null,
      straight_km: null,
      road: null,
      journey: null,
    },
  ],
};

function papan(props: Record<string, unknown> = {}) {
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

describe("kepala halaman Suppliers", () => {
  it("deskripsi = satu kalimat konteks, bukan daftar ulang bagian", () => {
    const html = papan({ reachKm: 120 });
    expect(html).toContain(
      "Pemasok jaringan SPPG Anda — ringkasan, kiriman aktif, daftar dalam jangkauan 120 km, dan register eksklusi."
    );
    // Kalimat lama yang mendaftar semua isi halaman sudah tidak ada.
    expect(html).not.toContain("Daftar pemasok di jaringan, kepercayaan");
  });

  it("tanpa jarak jangkauan: kalimat konteks versi pendek", () => {
    const html = papan();
    expect(html).toContain(
      "Pemasok jaringan SPPG Anda — ringkasan, kiriman aktif, daftar, dan register eksklusi."
    );
  });

  it("tiga pil angka: pemasok · kiriman · eksklusi", () => {
    const html = papan({ supplierRoutes: RUTE });
    expect(html).toContain('<span class="commodity-pill">1 pemasok</span>');
    expect(html).toContain('<span class="commodity-pill">2 kiriman</span>');
    expect(html).toContain('<span class="commodity-pill">0 eksklusi</span>');
  });

  it("jalur belum dimuat: pil kiriman tidak dirender, bukan '0 kiriman'", () => {
    const html = papan({ supplierRoutes: null });
    expect(html).not.toContain("0 kiriman");
    expect(html).toContain('<span class="commodity-pill">1 pemasok</span>');
  });
});

describe("navigasi bagian Suppliers", () => {
  it("lima tujuan, urut dari atas halaman ke bawah", () => {
    expect(supplierSections().map((item) => item.label)).toEqual([
      "Ringkasan",
      "Kiriman",
      "Daftar pemasok",
      "Register eksklusi",
      "Usul eksklusi",
    ]);
  });

  it("setiap tujuan punya sasaran di markup", () => {
    const html = papan({ supplierRoutes: RUTE });
    for (const item of supplierSections()) {
      expect(html, `id ${item.id} tidak terpasang`).toContain(`id="${item.id}"`);
    }
  });

  it("jangkar baru (ringkasan & kiriman) benar-benar dipasang", () => {
    const html = papan({ supplierRoutes: RUTE });
    expect(html).toContain(`id="${SUPPLIER_SECTION_IDS.ringkasan}"`);
    expect(html).toContain(`id="${SUPPLIER_SECTION_IDS.kiriman}"`);
  });
});
