// @vitest-environment jsdom
//
// Penyambungan paginasi ke dua bagian halaman Pemasok (permintaan pemilik
// 19 Okt 2026): "Daftar pemasok" dan "Papan kiriman" menampilkan 10 baris per
// halaman, sisanya di halaman berikutnya. Tes ini memakai 25 pemasok / 23
// kiriman supaya benar-benar ada lebih dari satu halaman, lalu memeriksa baris
// yang berpindah — bukan sekadar keberadaan pager.

import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";

import ShipmentBoard from "../components/ShipmentBoard";
import SupplierBoard from "../components/SupplierBoard";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const pemasok = (n: number, i: number) => ({
  id: `s${i}`,
  name: `Pemasok Uji ${String(i).padStart(2, "0")}`,
  location: "Cianjur",
  commodity: "wortel",
  certification_status: "haccp",
  reliability_score: 0.9,
  latitude: -6.82 + i / 1000,
  longitude: 107.16,
  excluded_at_hub: false,
  excluded_scope_locations: [],
});

const kiriman = (n: number, i: number) => ({
  batch_id: `B-${String(i).padStart(2, "0")}`,
  supplier_id: `S${i}`,
  supplier_name: `Supplier ${String(i).padStart(2, "0")}`,
  origin: { latitude: -6.8, longitude: 107.1, name: `Supplier ${i}` },
  destination_id: "L1",
  destination_name: "Jakarta",
  destination: { latitude: -6.2, longitude: 106.8, name: "Jakarta" },
  commodity: "telur",
  quantity_kg: 100 + i,
  harvested_at: "2026-10-16T01:00:00+00:00",
  usable_until: "2026-11-07T11:00:00+00:00",
  safety_status: "pass",
  straight_km: 78.35,
  road: null,
  journey: null,
});

function pasang(node: React.ReactElement) {
  const wadah = document.createElement("div");
  document.body.appendChild(wadah);
  const root = createRoot(wadah);
  act(() => root.render(node));
  return { wadah, root };
}

const barisTabel = (wadah: HTMLElement) =>
  Array.from(wadah.querySelectorAll<HTMLTableRowElement>("table tbody tr"));

const tombolHalaman = (wadah: HTMLElement, label: string) =>
  wadah.querySelector<HTMLButtonElement>(`[aria-label="${label}"]`);

describe("paginasi Daftar pemasok", () => {
  it("menampilkan 10 dari 25 pemasok pada halaman pertama", () => {
    const { wadah, root } = pasang(
      <SupplierBoard
        suppliers={{ count: 25, total: 25, items: Array.from({ length: 25 }, (_, i) => pemasok(25, i + 1)) }}
        exclusions={{ items: [], count: 0 }}
        selectedDecisionId={null}
        supplierContext={null}
        role="bgn_monitor"
        token="t"
      />
    );
    expect(barisTabel(wadah)).toHaveLength(10);
    expect(wadah.textContent).toContain("Pemasok Uji 01");
    expect(wadah.textContent).not.toContain("Pemasok Uji 11");
    expect(wadah.querySelector("nav[aria-label='Halaman daftar pemasok']")).not.toBeNull();
    expect(wadah.querySelector(".pager-range")?.textContent).toBe("1–10 dari 25");
    act(() => root.unmount());
  });

  it("halaman 2 memuat baris 11–20, halaman 3 sisanya", () => {
    const { wadah, root } = pasang(
      <SupplierBoard
        suppliers={{ count: 25, total: 25, items: Array.from({ length: 25 }, (_, i) => pemasok(25, i + 1)) }}
        exclusions={{ items: [], count: 0 }}
        selectedDecisionId={null}
        supplierContext={null}
        role="bgn_monitor"
        token="t"
      />
    );
    act(() => tombolHalaman(wadah, "Halaman 2")!.click());
    expect(wadah.textContent).toContain("Pemasok Uji 11");
    expect(wadah.textContent).not.toContain("Pemasok Uji 01");
    expect(wadah.querySelector(".pager-range")?.textContent).toBe("11–20 dari 25");
    expect(tombolHalaman(wadah, "Halaman 2")?.getAttribute("aria-current")).toBe("page");
    act(() => tombolHalaman(wadah, "Halaman 3")!.click());
    expect(barisTabel(wadah)).toHaveLength(5);
    expect(wadah.querySelector(".pager-range")?.textContent).toBe("21–25 dari 25");
    expect(tombolHalaman(wadah, "Halaman berikutnya")?.disabled).toBe(true);
    act(() => root.unmount());
  });

  it("satu halaman saja tidak menampilkan deretan tombol", () => {
    const { wadah, root } = pasang(
      <SupplierBoard
        suppliers={{ count: 3, total: 3, items: [pemasok(3, 1), pemasok(3, 2), pemasok(3, 3)] }}
        exclusions={{ items: [], count: 0 }}
        selectedDecisionId={null}
        supplierContext={null}
        role="bgn_monitor"
        token="t"
      />
    );
    expect(barisTabel(wadah)).toHaveLength(3);
    expect(wadah.querySelector(".pager-range")?.textContent).toBe("1–3 dari 3");
    expect(wadah.querySelector(".pager-controls")).toBeNull();
    act(() => root.unmount());
  });
});

describe("paginasi Papan kiriman", () => {
  it("menampilkan 10 kiriman per halaman dari 23 kiriman", () => {
    const { wadah, root } = pasang(
      <ShipmentBoard routes={{ routes: Array.from({ length: 23 }, (_, i) => kiriman(23, i + 1)) }} />
    );
    expect(barisTabel(wadah)).toHaveLength(10);
    expect(wadah.querySelector("nav[aria-label='Halaman papan kiriman']")).not.toBeNull();
    expect(wadah.querySelector(".pager-range")?.textContent).toBe("1–10 dari 23");
    act(() => tombolHalaman(wadah, "Halaman 3")!.click());
    expect(barisTabel(wadah)).toHaveLength(3);
    expect(wadah.querySelector(".pager-range")?.textContent).toBe("21–23 dari 23");
    act(() => root.unmount());
  });

  it("mengganti urutan mengembalikan pembaca ke halaman 1", () => {
    const { wadah, root } = pasang(
      <ShipmentBoard routes={{ routes: Array.from({ length: 23 }, (_, i) => kiriman(23, i + 1)) }} />
    );
    act(() => tombolHalaman(wadah, "Halaman 3")!.click());
    expect(wadah.querySelector(".pager-range")?.textContent).toBe("21–23 dari 23");
    const pil = wadah.querySelector<HTMLButtonElement>(".board-sort-pill:not(.is-active)");
    act(() => pil!.click());
    expect(wadah.querySelector(".pager-range")?.textContent).toBe("1–10 dari 23");
    expect(tombolHalaman(wadah, "Halaman 1")?.getAttribute("aria-current")).toBe("page");
    act(() => root.unmount());
  });
});
