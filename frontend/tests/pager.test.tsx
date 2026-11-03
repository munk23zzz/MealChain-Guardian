// @vitest-environment jsdom
//
// Kontrak komponen pager (19 Okt 2026): 10 baris per halaman di Daftar pemasok
// dan Papan kiriman. Yang dipaku di sini: label navigasi, aria-current, tombol
// ujung yang dinonaktifkan (bukan hilang), dan rentang "1–10 dari 60" yang
// diumumkan.

import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import Pager from "../components/Pager";
import { paginate } from "../lib/pagination";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const baris = (n: number) => Array.from({ length: n }, (_, i) => ({ id: i + 1 }));

function pasang(total: number, halaman: number, ukuran = 10) {
  const wadah = document.createElement("div");
  document.body.appendChild(wadah);
  const root = createRoot(wadah);
  const onChange = vi.fn();
  act(() => {
    root.render(
      <Pager page={paginate(baris(total), halaman, ukuran)} onChange={onChange} label="daftar pemasok" />
    );
  });
  return { wadah, root, onChange };
}

const tombolHalaman = (wadah: HTMLElement) =>
  Array.from(wadah.querySelectorAll<HTMLButtonElement>(".pager-list .pager-btn"));

const tombol = (wadah: HTMLElement, label: string) =>
  wadah.querySelector<HTMLButtonElement>(`[aria-label="${label}"]`);

describe("Pager", () => {
  it("menulis rentang dan menandai halaman aktif", () => {
    const { wadah, root } = pasang(60, 1);
    const nav = wadah.querySelector("nav");
    expect(nav?.getAttribute("aria-label")).toBe("Halaman daftar pemasok");
    expect(wadah.querySelector(".pager-range")?.textContent).toBe("1–10 dari 60");
    expect(tombolHalaman(wadah)).toHaveLength(6);
    expect(tombol(wadah, "Halaman 1")?.getAttribute("aria-current")).toBe("page");
    expect(tombol(wadah, "Halaman 2")?.getAttribute("aria-current")).toBeNull();
    act(() => root.unmount());
  });

  it("menonaktifkan Sebelumnya di halaman pertama dan Berikutnya di halaman akhir", () => {
    const awal = pasang(60, 1);
    expect(tombol(awal.wadah, "Halaman sebelumnya")?.disabled).toBe(true);
    expect(tombol(awal.wadah, "Halaman berikutnya")?.disabled).toBe(false);
    act(() => awal.root.unmount());

    const akhir = pasang(60, 6);
    expect(tombol(akhir.wadah, "Halaman berikutnya")?.disabled).toBe(true);
    expect(tombol(akhir.wadah, "Halaman sebelumnya")?.disabled).toBe(false);
    act(() => akhir.root.unmount());
  });

  it("mengirim nomor halaman saat tombol diklik", () => {
    const { wadah, root, onChange } = pasang(60, 1);
    act(() => tombol(wadah, "Halaman 3")!.click());
    expect(onChange).toHaveBeenCalledWith(3);
    act(() => tombol(wadah, "Halaman berikutnya")!.click());
    expect(onChange).toHaveBeenLastCalledWith(2);
    act(() => root.unmount());
  });

  it("halaman terakhir terisi sebagian dan tombolnya tetap menjepit", () => {
    const { wadah, root, onChange } = pasang(23, 3);
    expect(wadah.querySelector(".pager-range")?.textContent).toBe("21–23 dari 23");
    act(() => tombol(wadah, "Halaman sebelumnya")!.click());
    expect(onChange).toHaveBeenCalledWith(2);
    act(() => root.unmount());
  });

  it("banyak halaman memakai elipsis dan halaman aktif tetap ada", () => {
    const { wadah, root } = pasang(200, 10);
    expect(wadah.querySelectorAll(".pager-gap").length).toBeGreaterThan(0);
    expect(tombol(wadah, "Halaman 10")?.getAttribute("aria-current")).toBe("page");
    expect(tombol(wadah, "Halaman 1")).not.toBeNull();
    expect(tombol(wadah, "Halaman 20")).not.toBeNull();
    act(() => root.unmount());
  });

  it("satu halaman saja: hanya baris rentang, tanpa navigasi", () => {
    const html = renderToStaticMarkup(
      <Pager page={paginate(baris(7), 1, 10)} onChange={() => {}} label="papan kiriman" />
    );
    expect(html).toContain("1–7 dari 7");
    expect(html).not.toContain("pager-controls");
  });

  it("jumlah ribuan ditulis dengan pemisah Indonesia", () => {
    const html = renderToStaticMarkup(
      <Pager page={paginate(baris(1234), 1, 10)} onChange={() => {}} label="daftar pemasok" />
    );
    expect(html).toContain("1–10 dari 1.234");
  });
});
