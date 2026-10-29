// @vitest-environment jsdom
// Regresi lingkaran permintaan (temuan audit 29 Okt 2026).
//
// Halaman mengirim loader sebagai fungsi inline, jadi identitasnya berubah
// setiap render. Dulu efek bergantung langsung pada prop itu → tiap render
// memicu muat ulang → setState → render → muat ulang lagi. Terukur di browser:
// 15 panggilan `/receipts/menunggu` + 15 `/receipts/checklist` dalam 10 detik.
//
// Kontrak yang dikunci di sini: loader dipanggil SEKALI walau komponen
// dirender berkali-kali dengan prop fungsi yang selalu baru.

import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";

import FoodSafetyBoard from "../components/FoodSafetyBoard";
import type { ReceiptChecklist } from "../lib/api";

const NOW = new Date("2026-10-29T03:00:00Z");

const BATCH = [
  {
    id: "b1",
    location: "Jakarta",
    commodity: "telur",
    quantity_kg: 90,
    safety_status: "pending",
    freshness_score: 0.9,
    usable_until: "2026-11-03T03:00:00Z",
  },
];

const CEKLIS: ReceiptChecklist = {
  version: "uji",
  komoditas: "telur",
  total_bobot: 100,
  ambang: {
    fail_max_score: 50,
    ambiguous_max_score: 75,
    accepted_ratio_min: 0.9,
    berat_lebih_maks_persen: 5,
  },
  butir: [],
  nama_putusan: {},
};

let root: Root | null = null;
let host: HTMLDivElement | null = null;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = null;
  host = null;
});

describe("kartu Keamanan Pangan tidak memuat ulang tanpa henti", () => {
  it("loader antrean & ceklis dipanggil sekali meski prop berganti tiap render", async () => {
    const antrean = vi.fn(async () => ({ items: [], total: 0 }));
    const ceklis = vi.fn(async (_komoditas: string) => CEKLIS);

    const gambar = () =>
      act(() => {
        root?.render(
          // Sengaja inline: persis seperti `app/page.tsx` sebelum diperbaiki.
          <FoodSafetyBoard
            batches={BATCH}
            now={NOW}
            ownLocation="Jakarta"
            loadPendingReceipts={() => antrean()}
            loadChecklist={(komoditas) => ceklis(komoditas)}
          />
        );
      });

    await act(async () => {
      gambar();
      await Promise.resolve();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });

    // Empat render tambahan dengan fungsi baru setiap kali.
    for (let i = 0; i < 4; i += 1) {
      await act(async () => {
        gambar();
        await Promise.resolve();
      });
    }
    await act(async () => {
      await new Promise((r) => setTimeout(r, 60));
    });

    expect(antrean).toHaveBeenCalledTimes(1);
    expect(ceklis).toHaveBeenCalledTimes(1);
  });

  it("memuat ulang hanya saat isi antrean benar-benar berubah", async () => {
    const isi: { items: { id: string; recorded_at: string; checked_count: number }[] } = { items: [] };
    const antrean = vi.fn(async () => ({
      items: [...isi.items] as never[],
      total: isi.items.length,
    }));
    const ceklis = vi.fn(async (_komoditas: string) => CEKLIS);

    await act(async () => {
      root?.render(
        <FoodSafetyBoard
          batches={BATCH}
          now={NOW}
          ownLocation="Jakarta"
          loadPendingReceipts={() => antrean()}
          loadChecklist={(komoditas) => ceklis(komoditas)}
        />
      );
      await Promise.resolve();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 40));
    });
    expect(antrean).toHaveBeenCalledTimes(1);
  });
});
