// @vitest-environment jsdom
// Tahap 3 redesign Keamanan Pangan (29 Okt 2026): tabel tetap ringkas, detail
// satu batch dibuka di popup, dan ekspor pindah dari dua tombol di kepala kartu
// menjadi satu pemicu.
//
// Kenapa interaksi, bukan renderToStaticMarkup: popup hanya dirender saat
// terbuka (Popup mengembalikan null bila tertutup), jadi uji string akan lolos
// walau tombolnya tidak pernah membuka apa pun.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

const NOW = new Date("2026-10-11T06:00:00Z");

const BATCHES = [
  {
    id: "b-jkt-1",
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 180,
    safety_status: "pass",
    freshness_score: 0.9,
    usable_until: "2026-11-07T12:00:00Z",
  },
  {
    id: "b-jkt-2",
    location: "Jakarta",
    commodity: "ayam",
    quantity_kg: 120,
    safety_status: "fail",
    freshness_score: null,
    usable_until: null,
  },
];

let host: HTMLDivElement;
let root: Root;

async function pasang() {
  await act(async () => {
    root.render(<FoodSafetyBoard batches={BATCHES} now={NOW} ownLocation="Jakarta" />);
  });
  return host.ownerDocument;
}

function tombol(doc: Document, teks: string): HTMLButtonElement {
  const ketemu = Array.from(doc.querySelectorAll("button")).find((b) =>
    (b.textContent ?? "").trim().startsWith(teks)
  );
  expect(ketemu, `tombol "${teks}" tidak ditemukan`).toBeTruthy();
  return ketemu as HTMLButtonElement;
}

async function klik(el: HTMLElement) {
  await act(async () => {
    el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  await act(async () => {
    await Promise.resolve();
  });
}

beforeEach(() => {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  document.body.innerHTML = "";
});

describe("tabel batch tahap 3", () => {
  it("tetap tabel semantik dengan kepala berlingkup kolom, dibungkus wadah gulir", async () => {
    const doc = await pasang();
    const tabel = doc.querySelector("table.safety-table");
    expect(tabel).toBeTruthy();
    // Wadah bergulir mendatar: satu-satunya cara tabel lebar tidak memecah tata letak.
    expect(tabel!.closest(".board-table-wrap")).toBeTruthy();
    const kepala = Array.from(doc.querySelectorAll("table.safety-table thead th"));
    expect(kepala.length).toBeGreaterThanOrEqual(6);
    for (const th of kepala) expect(th.getAttribute("scope")).toBe("col");
  });

  it("setiap baris punya tombol Detail yang namanya menyebut batch", async () => {
    const doc = await pasang();
    const detail = Array.from(doc.querySelectorAll("button")).filter(
      (b) => (b.textContent ?? "").trim() === "Detail"
    );
    expect(detail).toHaveLength(BATCHES.length);
    const nama = detail.map((b) => b.getAttribute("aria-label") ?? "");
    expect(nama[0]).toContain("telur");
  });

  it("Detail membuka popup berisi fakta yang tidak muat di kolom tabel", async () => {
    const doc = await pasang();
    await klik(tombol(doc, "Detail"));

    const dialog = doc.querySelector('[role="dialog"]');
    expect(dialog).toBeTruthy();
    const teks = dialog!.textContent ?? "";
    // Judul menyebut batch yang dibuka, bukan batch pertama sembarang.
    expect(teks).toContain("telur");
    expect(teks).toContain("Jakarta");
    // Fakta lengkap, termasuk yang tidak ada kolomnya di tabel.
    for (const label of ["Status keamanan", "Karantina", "Layak sampai", "Sisa masa", "Penerimaan"]) {
      expect(teks, `fakta ${label} tidak ada`).toContain(label);
    }
    // Popup bisa ditutup dengan Escape (perilaku Popup bersama).
    await act(async () => {
      doc.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(doc.querySelector('[role="dialog"]')).toBeNull();
  });

  it("ekspor: satu pemicu di kepala kartu, dua format di dalam popup", async () => {
    const doc = await pasang();
    const kepala = doc.querySelector('article[id="safety-batch"] .safety-head-right');
    const pemicuKepala = Array.from(kepala!.querySelectorAll("button"));
    expect(pemicuKepala).toHaveLength(1);
    expect(pemicuKepala[0].getAttribute("aria-haspopup")).toBe("dialog");

    await klik(pemicuKepala[0]);
    const dialog = doc.querySelector('[role="dialog"]');
    expect(dialog).toBeTruthy();
    const teks = dialog!.textContent ?? "";
    expect(teks).toContain("Ekspor tabel batch");
    expect(teks).toContain("Unduh CSV");
    expect(teks).toContain("Unduh JSON");
  });
});
