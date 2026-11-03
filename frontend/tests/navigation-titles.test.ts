// Kontrak nama halaman (29 Okt 2026, permintaan pengguna: "samakan nama di navbar
// dan judul halaman").
//
// Sebelumnya label navbar dan judul halaman ditulis terpisah di dua tempat, sehingga
// empat tab menyimpang tanpa ada tes yang gagal:
//
//   navbar "Food Safety"   · judul "Keamanan Pangan"
//   navbar "Suppliers"     · judul "Pemasok"
//   navbar "Agent Log"     · judul "Agent Activity Log"
//   navbar "Supply & Demand" · judul "Pasokan & Kebutuhan"
//
// Tes ini menjaga tiga hal:
//   1. Nama yang disepakati (Bahasa Inggris) dipaku di `lib/navigation.ts`.
//   2. Navbar membaca konstanta itu, bukan literal.
//   3. Tiap halaman membaca konstanta yang sama, bukan literal.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { PAGE_TITLES, locationNetworkHint, locationNetworkTitle } from "../lib/navigation";

const root = join(__dirname, "..");
const baca = (relatif: string) => readFileSync(join(root, relatif), "utf8");

describe("PAGE_TITLES — nama yang disepakati", () => {
  it("lima tab yang disamakan memakai nama Inggris ini", () => {
    expect(PAGE_TITLES.evidence).toBe("Decision & Evidence");
    expect(PAGE_TITLES.safety).toBe("Food Safety");
    expect(PAGE_TITLES.suppliers).toBe("Suppliers");
    expect(PAGE_TITLES.agentLog).toBe("Agent Activity Log");
    expect(locationNetworkTitle("sppg_head")).toBe("Location Network");
  });

  it("judul jaringan lokasi mengikuti peran, navbar dan halaman memakai fungsi yang sama", () => {
    expect(locationNetworkTitle("sppg_nutritionist")).toBe("Supply & Demand");
    expect(locationNetworkTitle(null)).toBe("Location Network");
    expect(locationNetworkHint("sppg_nutritionist")).not.toBe(
      locationNetworkHint("sppg_head")
    );
  });
});

describe("navbar membaca PAGE_TITLES, bukan literal", () => {
  const page = baca("app/page.tsx");

  it("empat tab memakai konstanta", () => {
    expect(page).toContain('{ id: "evidence", label: PAGE_TITLES.evidence }');
    expect(page).toContain('{ id: "safety", label: PAGE_TITLES.safety }');
    expect(page).toContain('{ id: "suppliers", label: PAGE_TITLES.suppliers }');
    expect(page).toContain('{ id: "agent-log", label: PAGE_TITLES.agentLog }');
  });

  it("tab jaringan lokasi memakai fungsi peran, bukan ternary teks", () => {
    expect(page).toContain("label: locationNetworkTitle(role)");
    expect(page).not.toContain('"Pasokan & Kebutuhan"');
  });
});

describe("judul halaman membaca PAGE_TITLES yang sama dengan navbar", () => {
  it("Food Safety", () => {
    const src = baca("components/FoodSafetyBoard.tsx");
    expect(src).toContain("title={PAGE_TITLES.safety}");
    expect(src).not.toContain('title="Keamanan Pangan"');
  });

  it("Suppliers", () => {
    const src = baca("components/SupplierBoard.tsx");
    expect(src).toContain("title={PAGE_TITLES.suppliers}");
    expect(src).not.toContain('title="Pemasok"');
  });

  it("Decision & Evidence", () => {
    const src = baca("components/DecisionEvidence.tsx");
    // Tahap 1 (29 Okt 2026): judul dirender sebagai isi <h1> kepala kartu,
    // bukan sebagai prop `title` milik PageShell.
    // Judul kini dioper sebagai prop `title` ke PageHeader bersama.
    expect(src).toContain("title={PAGE_TITLES.evidence}");
  });

  it("Agent Activity Log", () => {
    const page = baca("app/page.tsx");
    expect(page).toContain("title={PAGE_TITLES.agentLog}");
    expect(page).not.toContain('title="Agent Log"');
  });

  it("Location Network / Supply & Demand", () => {
    const page = baca("app/page.tsx");
    expect(page).toContain("heading={locationNetworkTitle(role)}");
  });
});
