// @vitest-environment jsdom
//
// Redesign dropdown keputusan (19 Okt 2026): <select> bawaan diganti pemilih
// yang bisa dicari dan dinavigasi keyboard. Kontrak yang dipaku:
//   1. Tombol pemicu menampilkan pilihan aktif (judul + meta), bukan hanya "#id".
//   2. Panel tertutup secara default; klik memicu membuka.
//   3. Mengetik di kotak cari menyaring opsi; tanpa hasil muncul kalimat,
//      bukan panel kosong.
//   4. ArrowDown/ArrowUp memindahkan sorotan, Enter memilih & menutup,
//      Escape menutup tanpa mengubah pilihan.
//   5. Nilai yang dikirim ke pemanggil adalah `value` asli (decision_id).
import { describe, expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";

import { createElement } from "react";
import DecisionPicker from "../components/DecisionPicker";
import type { PickerGroup } from "../lib/decision-picker";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const GRUP: PickerGroup[] = [
  {
    id: "action",
    label: "Menunggu tindakan (2)",
    options: [
      { value: "aaa", label: "Alihkan pasokan · sisa 6 jam · #aaa111" },
      { value: "bbb", label: "Tambah pasokan · sisa 2 jam · #bbb222" },
    ],
  },
  {
    id: "rest",
    label: "Tidak menunggu tindakan (1)",
    options: [{ value: "ccc", label: "Kurangi pasokan · dieksekusi · #ccc333" }],
  },
];

function pasang(props: Record<string, unknown> = {}) {
  const wadah = document.createElement("div");
  document.body.appendChild(wadah);
  const root = createRoot(wadah);
  const onChange = (props.onChange as any) ?? vi.fn();
  act(() => {
    // Lewat elemen (bukan memanggil fungsi komponen langsung): komponen ini
    // memakai hook, jadi harus dirender oleh React.
    root.render(
      createElement(DecisionPicker, {
        groups: GRUP,
        value: "aaa",
        onChange,
        label: "Keputusan yang diperiksa",
        ...props,
      } as any)
    );
  });
  return { wadah, root, onChange };
}

const pemicu = (w: HTMLElement) => w.querySelector(".dpick-trigger") as HTMLButtonElement;
const panel = (w: HTMLElement) => w.querySelector(".dpick-panel") as HTMLElement;
const tertutup = (w: HTMLElement) => panel(w).hasAttribute("hidden");
const cari = (w: HTMLElement) => w.querySelector(".dpick-search") as HTMLInputElement | null;
const opsi = (w: HTMLElement) => [...w.querySelectorAll(".dpick-option")] as HTMLElement[];

function buka(w: HTMLElement) {
  act(() => {
    pemicu(w).dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
}

function ketik(input: HTMLInputElement, teks: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  act(() => {
    setter.call(input, teks);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

function tombol(el: Element, key: string) {
  act(() => {
    el.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
  });
}

describe("DecisionPicker", () => {
  it("pemicu menampilkan pilihan aktif sebagai judul + meta", () => {
    const { wadah, root } = pasang();
    const teks = pemicu(wadah).textContent!.replace(/\s+/g, " ");
    expect(teks).toContain("Alihkan pasokan");
    expect(teks).toContain("#aaa111");
    expect(pemicu(wadah).getAttribute("aria-expanded")).toBe("false");
    act(() => root.unmount());
  });

  it("panel tertutup default; klik pemicu membuka daftar lengkap", () => {
    const { wadah, root } = pasang();
    expect(tertutup(wadah)).toBe(true);
    buka(wadah);
    expect(pemicu(wadah).getAttribute("aria-expanded")).toBe("true");
    expect(tertutup(wadah)).toBe(false);
    expect(opsi(wadah)).toHaveLength(3);
    expect(wadah.textContent).toContain("Menunggu tindakan (2)");
    act(() => root.unmount());
  });

  it("kotak cari menyaring opsi dan grup tanpa hasil dibuang", () => {
    const { wadah, root } = pasang();
    buka(wadah);
    const input = cari(wadah)!;
    expect(input).not.toBeNull();
    ketik(input, "tambah");
    expect(opsi(wadah)).toHaveLength(1);
    expect(wadah.textContent).not.toContain("Tidak menunggu tindakan");
    act(() => root.unmount());
  });

  it("pencarian tanpa hasil menulis kalimat, bukan panel kosong", () => {
    const { wadah, root } = pasang();
    buka(wadah);
    ketik(cari(wadah)!, "zzzz");
    expect(opsi(wadah)).toHaveLength(0);
    expect(wadah.querySelector(".dpick-empty")?.textContent).toContain("Tidak ada keputusan");
    act(() => root.unmount());
  });

  it("ArrowDown + Enter memilih opsi dan menutup panel", () => {
    const { wadah, root, onChange } = pasang();
    buka(wadah);
    const input = cari(wadah)!;
    // Sorotan awal = pilihan aktif ("aaa"); ArrowDown → "bbb".
    tombol(input, "ArrowDown");
    const aktif = wadah.querySelector('[aria-selected="true"]') as HTMLElement;
    expect(aktif.textContent).toContain("#bbb222");
    tombol(input, "Enter");
    expect(onChange).toHaveBeenCalledWith("bbb");
    expect(tertutup(wadah)).toBe(true);
    act(() => root.unmount());
  });

  it("Escape menutup panel tanpa mengubah pilihan", () => {
    const { wadah, root, onChange } = pasang();
    buka(wadah);
    tombol(cari(wadah)!, "Escape");
    expect(onChange).not.toHaveBeenCalled();
    expect(tertutup(wadah)).toBe(true);
    act(() => root.unmount());
  });

  it("klik opsi memanggil onChange dengan decision_id asli", () => {
    const { wadah, root, onChange } = pasang();
    buka(wadah);
    const target = opsi(wadah).find((o) => o.textContent!.includes("#ccc333"))!;
    act(() => {
      target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(onChange).toHaveBeenCalledWith("ccc");
    act(() => root.unmount());
  });
});
