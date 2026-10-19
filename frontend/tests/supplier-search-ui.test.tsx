// @vitest-environment jsdom
//
// Pencarian "Daftar pemasok" (permintaan pemilik 19 Okt 2026). Yang dipaku:
// menyaring sebelum paginasi, kembali ke halaman 1 saat kueri berubah, angka di
// kartu Ringkasan TIDAK ikut berubah, dan keadaan "tidak ada hasil" memberi
// jalan keluar (tombol hapus), bukan layar kosong.

import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";

import SupplierBoard from "../components/SupplierBoard";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const pemasok = (i: number) => ({
  id: `s${i}`,
  name: `Pemasok Uji ${String(i).padStart(2, "0")}`,
  location: i % 2 === 0 ? "Cianjur" : "Bandung",
  commodity: i % 3 === 0 ? "ayam" : "wortel",
  certification_status: "haccp",
  reliability_score: 0.9,
  latitude: -6.82 + i / 1000,
  longitude: 107.16,
  excluded_at_hub: false,
  excluded_scope_locations: [],
});

const PAYLOAD = {
  count: 25,
  total: 25,
  items: Array.from({ length: 25 }, (_, i) => pemasok(i + 1)),
};

function pasang(props: Record<string, unknown> = {}) {
  const wadah = document.createElement("div");
  document.body.appendChild(wadah);
  const root = createRoot(wadah);
  act(() =>
    root.render(
      <SupplierBoard
        suppliers={PAYLOAD}
        exclusions={{ items: [], count: 0 }}
        selectedDecisionId={null}
        supplierContext={null}
        role="bgn_monitor"
        token="t"
        {...props}
      />
    )
  );
  return { wadah, root };
}

function ketik(input: HTMLInputElement, teks: string) {
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value"
  )!.set!;
  act(() => {
    setter.call(input, teks);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

const cariInput = (wadah: HTMLElement) =>
  wadah.querySelector<HTMLInputElement>("#cari-pemasok");

const baris = (wadah: HTMLElement) =>
  Array.from(wadah.querySelectorAll<HTMLTableRowElement>("table.location-table tbody tr"));

const rentang = (wadah: HTMLElement) =>
  wadah.querySelector(".pager-range")?.textContent ?? null;

describe("pencarian daftar pemasok", () => {
  it("kolom cari punya label terlihat dan status hasil", () => {
    const { wadah, root } = pasang();
    expect(wadah.querySelector('label[for="cari-pemasok"]')?.textContent).toBe("Cari pemasok");
    expect(cariInput(wadah)?.getAttribute("type")).toBe("search");
    expect(wadah.querySelector("#cari-pemasok-status")?.textContent).toBe("25 pemasok");
    act(() => root.unmount());
  });

  it("menyaring baris dan memaginasi ulang hasilnya", () => {
    const { wadah, root } = pasang();
    ketik(cariInput(wadah)!, "uji 1");
    // "uji 1" cocok dengan 01, 10–19, dan 21 → 12 pemasok → dua halaman.
    expect(wadah.querySelector("#cari-pemasok-status")?.textContent).toBe(
      "12 dari 25 cocok"
    );
    expect(baris(wadah)).toHaveLength(10);
    expect(rentang(wadah)).toBe("1–10 dari 12");
    expect(wadah.textContent).toContain("Pemasok Uji 01");
    expect(wadah.textContent).not.toContain("Pemasok Uji 02");
    act(() => root.unmount());
  });

  it("mencari pada hub dan komoditas, bukan hanya nama", () => {
    const { wadah, root } = pasang();
    ketik(cariInput(wadah)!, "bandung");
    expect(wadah.querySelector("#cari-pemasok-status")?.textContent).toBe(
      "13 dari 25 cocok"
    );
    ketik(cariInput(wadah)!, "ayam");
    expect(wadah.querySelector("#cari-pemasok-status")?.textContent).toContain("8 dari 25");
    act(() => root.unmount());
  });

  it("mengubah kueri mengembalikan pembaca ke halaman 1", () => {
    const { wadah, root } = pasang();
    act(() => wadah.querySelector<HTMLButtonElement>('[aria-label="Halaman 3"]')!.click());
    expect(rentang(wadah)).toBe("21–25 dari 25");
    ketik(cariInput(wadah)!, "bandung");
    expect(rentang(wadah)).toBe("1–10 dari 13");
    act(() => root.unmount());
  });

  it("tanpa hasil: kalimat + tombol hapus, bukan tabel kosong", () => {
    const { wadah, root } = pasang();
    ketik(cariInput(wadah)!, "zzzz");
    expect(wadah.querySelector(".board-search-empty")?.textContent).toContain(
      "Tidak ada pemasok yang cocok dengan “zzzz”"
    );
    expect(wadah.querySelector("table.location-table")).toBeNull();
    const hapus = Array.from(wadah.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "Hapus pencarian"
    )!;
    act(() => hapus.click());
    expect(baris(wadah)).toHaveLength(10);
    expect(cariInput(wadah)?.value).toBe("");
    act(() => root.unmount());
  });

  it("tombol × berlabel menghapus kueri", () => {
    const { wadah, root } = pasang();
    ketik(cariInput(wadah)!, "bandung");
    const silang = wadah.querySelector<HTMLButtonElement>('[aria-label="Hapus pencarian"]')!;
    expect(silang.textContent).toBe("×");
    act(() => silang.click());
    expect(cariInput(wadah)?.value).toBe("");
    expect(baris(wadah)).toHaveLength(10);
    act(() => root.unmount());
  });

  it("kartu Ringkasan tetap dihitung dari daftar penuh saat mencari", () => {
    const { wadah, root } = pasang();
    ketik(cariInput(wadah)!, "zzzz");
    const ringkasan = wadah.querySelector(".supplier-summary")?.textContent ?? "";
    expect(ringkasan).toContain("Pemasok terdaftar");
    expect(ringkasan).toContain("25");
    act(() => root.unmount());
  });
});
