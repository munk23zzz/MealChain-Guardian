// @vitest-environment jsdom
//
// "Lihat keputusan" harus PINDAH keputusan di dalam aplikasi, bukan memuat ulang
// halaman. Temuan 19 Okt 2026: tautan lama memakai `href="?keputusan=…"` tanpa
// penangan klik, sehingga klik = navigasi penuh → halaman mulai dari atas dan
// (kalau posisi gulir dipulihkan) pengguna tetap melihat daftar PO yang sama,
// terasa "tombolnya tidak berfungsi".
//
// Kontrak yang dipaku di sini:
//   1. Klik kiri biasa → `onOpenDecision(id)` dipanggil, navigasi dibatalkan.
//   2. Ctrl/Cmd/Shift-klik tetap membuka tab baru (default tidak dicegah) —
//      tautan tetap tautan, bukan tombol yang menelan perilaku browser.
//   3. `href` tetap ada supaya tautan bisa disalin/dibuka di tab baru.
import { describe, expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";

import PurchaseOrderList from "../components/PurchaseOrderList";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const KEPUTUSAN = "11111111-1111-1111-1111-111111111111";

const PAYLOAD = {
  scope: "lokasi",
  source: "mock_sap_table",
  count: 1,
  limit: 50,
  items: [
    {
      po_number: "MC-AAAA",
      status: "submitted",
      created_at: "2026-10-19T02:00:00+00:00",
      decision_id: KEPUTUSAN,
      decision_status: "executed",
      location_name: "Jakarta",
      supplier_name: "CV Sumber Ayam",
      material_number: "MAT-AYAM",
      commodity_name: "ayam",
      ordered_quantity_kg: 600,
      price_per_kg: 41500,
      total_value: 24900000,
      source: "mock_sap_table",
      origin: "execution",
    },
  ],
};

function pasang(props: Record<string, unknown>) {
  const wadah = document.createElement("div");
  document.body.appendChild(wadah);
  const root = createRoot(wadah);
  // 20 Okt 2026: panel memegang keadaan unduhan PDF, jadi ia WAJIB dirender
  // sebagai elemen. Memanggilnya sebagai fungsi biasa menaruh hook di luar
  // renderer React ("Invalid hook call").
  act(() => {
    root.render(
      <PurchaseOrderList
        data={PAYLOAD}
        summary={{
          by_status: { draft: 0, submitted: 1, confirmed: 0 },
          count: 1,
          total_value: 24900000,
          source: "mock_sap_table",
          scope: "lokasi",
        }}
        {...(props as any)}
      />
    );
  });
  const tautan = wadah.querySelector(".po-link") as HTMLAnchorElement;
  return { wadah, root, tautan };
}

function klik(el: Element, init: MouseEventInit = {}) {
  const ev = new MouseEvent("click", {
    bubbles: true,
    cancelable: true,
    button: 0,
    ...init,
  });
  act(() => {
    el.dispatchEvent(ev);
  });
  return ev;
}

describe("tautan keputusan di panel purchase order", () => {
  it("klik kiri memilih keputusan di dalam aplikasi, bukan memuat ulang", () => {
    const buka = vi.fn();
    const { tautan, root } = pasang({ onOpenDecision: buka });
    expect(tautan.getAttribute("href")).toBe(`?keputusan=${KEPUTUSAN}`);
    const ev = klik(tautan);
    expect(buka).toHaveBeenCalledTimes(1);
    expect(buka).toHaveBeenCalledWith(KEPUTUSAN);
    expect(ev.defaultPrevented).toBe(true);
    act(() => root.unmount());
  });

  it("ctrl/cmd-klik tetap membuka tab baru (default tidak dicegah)", () => {
    const buka = vi.fn();
    const { tautan, root } = pasang({ onOpenDecision: buka });
    expect(tautan.getAttribute("href")).toBe(`?keputusan=${KEPUTUSAN}`);
    // href dilepas sebelum dispatch supaya jsdom tidak mencoba navigasi
    // sungguhan (bukan bagian yang diuji); perilaku default tetap terukur.
    tautan.removeAttribute("href");
    const ev = klik(tautan, { ctrlKey: true });
    expect(buka).not.toHaveBeenCalled();
    expect(ev.defaultPrevented).toBe(false);
    act(() => root.unmount());
  });

  it("tanpa penangan, tautan tetap membawa href yang bisa disalin", () => {
    const { tautan, root } = pasang({});
    // Tidak diklik di sini: klik tanpa penangan = navigasi penuh (perilaku
    // bawaan browser), yang bukan urusan komponen ini.
    expect(tautan.getAttribute("href")).toBe(`?keputusan=${KEPUTUSAN}`);
    expect(tautan.getAttribute("href")).toMatch(/^[^#]+$/);
    act(() => root.unmount());
  });
});
