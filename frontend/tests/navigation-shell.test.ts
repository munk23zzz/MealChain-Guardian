// Kontrak cangkang halaman (29 Okt 2026).
//
// Lima tab panjang sebelumnya menyusun kepalanya sendiri, jadi navigasi bagian
// hanya ada di tiga halaman (Decision & Evidence, Overview, Food Safety) dan
// tidak di tiga lainnya (Suppliers, Agent Activity Log, Location Network) —
// padahal panjangnya sama. Tes ini menjaga dua hal yang gampang rusak lagi:
//
//   1. Semua halaman memakai `PageShell` (satu urutan: kepala → nav bagian → isi).
//   2. Setiap id di daftar bagian BENAR-BENAR dipasang di halamannya. Tautan
//      nav yang tidak punya sasaran lebih buruk daripada tidak ada nav
//      (docs/design.md §24), dan itu tidak akan ketahuan tanpa tes: nav tetap
//      tampil, kliknya hanya diam.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  AGENT_LOG_SECTION_IDS,
  NETWORK_SECTION_IDS,
  SUPPLIER_SECTION_IDS,
  agentLogSections,
  evidenceSections,
  networkSections,
  supplierSections,
} from "../lib/section-jump";

const root = join(__dirname, "..");
const baca = (relatif: string) => readFileSync(join(root, relatif), "utf8");

describe("PageShell dipakai kelima halaman", () => {
  // Decision & Evidence dikeluarkan dari daftar PageShell pada TAHAP 1
  // (29 Okt 2026): kepalanya kini memakai pola kartu Overview, jadi ia menulis
  // kepalanya sendiri dan merender SectionJump sendiri. Yang dijaga untuk
  // halaman ini ada di tes terpisah di bawah.
  const halaman: [string, string][] = [
    ["components/FoodSafetyBoard.tsx", "safety-page"],
    ["components/SupplierBoard.tsx", "board-page"],
    ["components/LocationNetworkBoard.tsx", "board-page"],
    ["app/page.tsx", "agent-log-section"],
  ];

  for (const [berkas, kelas] of halaman) {
    it(`${berkas} memakai PageShell dan tetap membawa kelas lamanya`, () => {
      const src = baca(berkas);
      expect(src).toContain("<PageShell");
      expect(src).toContain(kelas);
    });
  }

  it("Decision & Evidence: kepala kartu + nav bagian sendiri (tahap 1)", () => {
    const src = baca("components/DecisionEvidence.tsx");
    expect(src).toContain('className="evidence-page"');
    // 30 Okt 2026: kepala halaman diseragamkan — halaman ini memakai
    // `PageHeader` bersama, bukan penanda kepala kedua.
    expect(src).toContain("<PageHeader");
    expect(src).not.toContain("overview-header");
    expect(src).toContain('className="evidence-controls"');
    expect(src).toContain("<SectionJump");
    expect(src).toContain("evidenceSections()");
  });

  it("blok Agent Activity Log tidak lagi mencetak PageHeader sendiri", () => {
    // page.tsx memuat SEMUA tab: tab lain (Overview, Recommendations, Demo
    // Control) masih memakai PageHeader telanjang dan itu sah — yang dijaga di
    // sini hanya blok agent-log, karena di situlah dulu PageHeader dan isi
    // halaman disusun manual sehingga nav bagiannya tidak pernah ikut.
    const src = baca("app/page.tsx");
    const mulai = src.indexOf('{tab === "agent-log" && (');
    expect(mulai).toBeGreaterThan(-1);
    const blok = src.slice(mulai, src.indexOf("</PageShell>", mulai));
    expect(blok).toContain("<PageShell");
    expect(blok).not.toContain("<PageHeader");
  });
});

describe("setiap tujuan nav punya sasaran di halamannya", () => {
  it("Suppliers — lima jangkar terpasang", () => {
    const src = baca("components/SupplierBoard.tsx");
    // 29 Okt 2026: Ringkasan & Kiriman ikut jadi tujuan (dua blok di atas daftar).
    for (const kunci of ["ringkasan", "kiriman", "daftar", "register", "usul"] as const) {
      expect(src).toContain(`SUPPLIER_SECTION_IDS.${kunci}`);
    }
    expect(supplierSections()).toHaveLength(5);
  });

  it("Location Network — jangkar mengikuti bagian yang benar-benar dirender", () => {
    const src = baca("components/LocationNetworkBoard.tsx");
    for (const kunci of ["keadaan", "lokasi", "alih", "limbah"] as const) {
      expect(src).toContain(`NETWORK_SECTION_IDS.${kunci}`);
    }
    // Tanpa baris lokasi, tujuan "Lokasi" tidak dipasang (kartunya tidak ada).
    const tanpaBaris = networkSections({ hasRows: false, hasTransfer: true });
    expect(tanpaBaris.map((i) => i.id)).not.toContain(NETWORK_SECTION_IDS.lokasi);
    const denganBaris = networkSections({ hasRows: true, hasTransfer: true });
    expect(denganBaris.map((i) => i.id)).toContain(NETWORK_SECTION_IDS.lokasi);
  });

  it("Agent Activity Log — tiga jangkar terpasang di page.tsx", () => {
    const src = baca("app/page.tsx");
    for (const kunci of ["pilih", "langkah", "integritas"] as const) {
      expect(src).toContain(`AGENT_LOG_SECTION_IDS.${kunci}`);
    }
    expect(agentLogSections()).toHaveLength(3);
  });

  it("Decision & Evidence — setiap jangkar dipasang oleh komponen bagian", () => {
    // Tahap 7 (29 Okt 2026): isi halaman dirakit enam komponen bagian, jadi
    // jangkar dicari di seluruh berkas yang merendernya.
    // Tahap 8: `DecisionDetail.tsx` DIKELUARKAN dari daftar — berkas itu tidak
    // dirender lagi, dan memasukkannya membuat tes ini hijau karena markah yang
    // tidak pernah tampil.
    const sumber = [
      "components/DecisionSummary.tsx",
      "components/DecisionApproval.tsx",
      "components/DecisionCostEvidence.tsx",
      "components/DecisionSafetySupplier.tsx",
      "components/DecisionIdentityBatch.tsx",
      "components/DecisionTraceIntegrity.tsx",
    ]
      .map((f) => baca(f))
      .join("\n");
    for (const item of evidenceSections()) {
      expect(sumber, `id ${item.id} tidak dipasang`).toContain(`id="${item.id}"`);
    }
  });
});

describe("aturan docs/design.md §24: maksimum lima tujuan", () => {
  it("tidak ada daftar yang melebihi lima", () => {
    expect(evidenceSections().length).toBeLessThanOrEqual(5);
    expect(supplierSections().length).toBeLessThanOrEqual(5);
    expect(agentLogSections().length).toBeLessThanOrEqual(5);
    expect(networkSections({ hasRows: true, hasTransfer: true }).length).toBeLessThanOrEqual(5);
  });

  it("id jangkar unik di dalam satu halaman", () => {
    const semua = [
      ...supplierSections().map((i) => i.id),
      ...agentLogSections().map((i) => i.id),
      ...networkSections({ hasRows: true, hasTransfer: true }).map((i) => i.id),
    ];
    expect(new Set(semua).size).toBe(semua.length);
  });
});
