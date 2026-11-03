// @vitest-environment jsdom
//
// Klik baris tabel = aksi yang sama dengan tombolnya (permintaan pemilik,
// 29 Okt 2026: "tabel yang ada tombol tidak perlu menekan tombol, menekan baris
// tabelnya juga bisa ke-trigger").
//
// Ditulis MERAH lebih dulu. Yang dijaga:
//   - klik di sel biasa menjalankan aksi baris,
//   - klik pada kontrol DI DALAM baris (tombol/tautan) TIDAK menggandakan aksi,
//   - teks yang sedang disorot tidak dianggap klik (menyalin isi tabel tidak
//     boleh membuka panel),
//   - tombol tetap ada: ia yang memegang akses papan ketik.

import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import DecisionAuditTable from "../components/DecisionAuditTable";
import { bolehKlikBaris } from "../lib/baris-klik";

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

let wadah: HTMLDivElement | null = null;
let akar: Root | null = null;

afterEach(() => {
  if (akar) act(() => akar!.unmount());
  wadah?.remove();
  wadah = null;
  akar = null;
  vi.restoreAllMocks();
});

function pasang(el: React.ReactElement) {
  wadah = document.createElement("div");
  document.body.appendChild(wadah);
  akar = createRoot(wadah);
  act(() => {
    akar!.render(el);
  });
  return wadah;
}

function klik(el: Element | null | undefined) {
  expect(el).toBeTruthy();
  act(() => {
    el!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

describe("bolehKlikBaris", () => {
  it("sel biasa boleh", () => {
    const td = document.createElement("td");
    td.textContent = "30 kg";
    expect(bolehKlikBaris(td)).toBe(true);
  });

  it("kontrol di dalam baris tidak boleh menggandakan aksi", () => {
    const td = document.createElement("td");
    const b = document.createElement("button");
    td.appendChild(b);
    expect(bolehKlikBaris(b)).toBe(false);
    const a = document.createElement("a");
    td.appendChild(a);
    expect(bolehKlikBaris(a)).toBe(false);
  });

  it("teks yang sedang disorot tidak dianggap klik", () => {
    const td = document.createElement("td");
    expect(bolehKlikBaris(td, "30 kg")).toBe(false);
  });

  it("target bukan elemen (mis. document) dianggap klik sah", () => {
    expect(bolehKlikBaris(null)).toBe(true);
  });
});

describe("tabel keputusan", () => {
  const ROW = {
    decision_id: "dec-1",
    decision_type: "procurement",
    commodity: "beras",
    status: "pending_approval",
    quantity_kg: 300,
    cost_idr: 4965000,
    created_at: "2026-10-29T03:21:04Z",
    expires_at: "2026-10-29T06:21:04Z",
    verification_state: "menunggu",
  } as never;

  function tabel(onSelect: (id: string) => void) {
    return pasang(
      <DecisionAuditTable
        rows={[ROW]}
        total={1}
        page={1}
        onPage={() => {}}
        selectedId={null}
        onSelect={onSelect}
        summary="1 keputusan"
      />,
    );
  }

  it("klik di sel biasa memilih baris", () => {
    const onSelect = vi.fn();
    const host = tabel(onSelect);
    const sel = host.querySelectorAll("tbody tr td")[1];
    klik(sel);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith("dec-1");
  });

  it("klik tombol baris tetap satu kali, bukan dua", () => {
    const onSelect = vi.fn();
    const host = tabel(onSelect);
    klik(host.querySelector("tbody tr button"));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });
});
