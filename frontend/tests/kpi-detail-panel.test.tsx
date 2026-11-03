// @vitest-environment jsdom
//
// Kartu KPI = satu bentuk yang bisa diklik; penjelasannya informatif, bukan
// teknis (revisi pemilik 29 Okt 2026).
//
// Perubahan yang diuji dibanding versi pertama:
//   - TIDAK ada segitiga buka-tutup (`details`/`summary`) di halaman KPI,
//   - SELURUH kartu yang bisa diklik, bukan hanya namanya,
//   - panel menjelaskan arti angka dalam bahasa manusia; istilah teknis
//     (versi metode, rumus, kode sumber, jumlah sampel) tidak dipamerkan.
//
// Ditulis MERAH lebih dulu.

import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import KPIDashboard from "../components/KPIDashboard";

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

const METRIK = [
  {
    name: "Meal Continuity Rate",
    value: "82.5",
    unit: "percent",
    state: "available",
    trend: "up",
    sample_count: 42,
    coverage: "1.00",
    provenance: {
      evidence_kind: "measured",
      source: "menu_plans",
      period: { basis: "hari kalender WIB" },
      method_version: "kpi-1.4.0",
      definition: "porsi tersaji dibagi porsi rencana",
      formula: "served / planned",
    },
  },
  {
    name: "Safe Delivered Cost",
    value: null,
    unit: "IDR",
    state: "no_data",
    trend: null,
    sample_count: 0,
    coverage: null,
    reason: "belum ada purchase order terbit pada periode ini",
    provenance: { evidence_kind: "measured", source: "purchase_orders" },
  },
  {
    // Payload asli mengirim DAFTAR KOLOM sebagai "source" untuk metrik ini —
    // bahan audit, bukan penjelasan.
    name: "Avoidable Food Loss",
    value: null,
    unit: "kg",
    state: "no_data",
    trend: null,
    sample_count: 0,
    coverage: null,
    reason: "belum ada pencatatan susut pada periode ini",
    provenance: {
      evidence_kind: "measured",
      source: "disposal_events.disposed_at, disposal_events.quantity_kg",
    },
  },
];

const AMPLOP = {
  data_mode: "demo",
  period: { start: "2026-10-29T00:00:00+07:00", end: "2026-10-29T23:59:59+07:00" },
  scope: { role: "sppg_head" },
  metrics: METRIK,
};

let wadah: HTMLDivElement | null = null;
let akar: Root | null = null;

afterEach(() => {
  if (akar) act(() => akar!.unmount());
  wadah?.remove();
  wadah = null;
  akar = null;
});

function pasang() {
  wadah = document.createElement("div");
  document.body.appendChild(wadah);
  akar = createRoot(wadah);
  act(() => {
    akar!.render(<KPIDashboard kpi={AMPLOP} windowKey="today" scope="operational" />);
  });
  return wadah;
}

function kartu(host: HTMLElement): HTMLElement[] {
  return Array.from(host.querySelectorAll<HTMLElement>("article.kpi-card"));
}

/**
 * Kartu dicari dari NAMA metriknya, bukan urutan (UI-2, 29 Okt 2026): kartu
 * kini dikelompokkan per domain, jadi urutan tampil bukan lagi urutan server.
 * Mengunci indeks akan menguji tata letak, bukan perilaku panel.
 */
function kartuNama(host: HTMLElement, nama: string): HTMLElement {
  const found = kartu(host).find(
    (el) => el.querySelector(".kpi-card-name")?.textContent?.trim() === nama
  );
  expect(found, `kartu ${nama} tidak ditemukan`).toBeTruthy();
  return found!;
}

function klik(el: Element | null | undefined) {
  expect(el).toBeTruthy();
  act(() => {
    el!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

function tekan(el: HTMLElement, key: string) {
  act(() => {
    el.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
  });
}

describe("bentuk kartu KPI", () => {
  it("tidak ada lagi segitiga buka-tutup di halaman KPI", () => {
    const host = pasang();
    expect(host.querySelectorAll("details")).toHaveLength(0);
    expect(host.querySelectorAll("summary")).toHaveLength(0);
  });

  it("seluruh kartu adalah tombol, bukan hanya namanya", () => {
    const host = pasang();
    const semua = kartu(host);
    expect(semua).toHaveLength(3);
    for (const k of semua) {
      expect(k.getAttribute("role")).toBe("button");
      expect(k.getAttribute("tabindex")).toBe("0");
      expect(k.getAttribute("aria-controls")).toBe("kpi-detail");
      expect(k.getAttribute("aria-expanded")).toBe("false");
    }
    expect(host.querySelectorAll("button.kpi-card-open")).toHaveLength(0);
  });

  it("klik di angka (bukan di nama) membuka panel", () => {
    const host = pasang();
    klik(kartu(host)[0].querySelector(".kpi-value"));
    expect(host.querySelector('[data-testid="kpi-detail"]')).not.toBeNull();
    expect(kartu(host)[0].getAttribute("aria-expanded")).toBe("true");
  });

  it("Enter dan Spasi membuka panel dari papan ketik", () => {
    const host = pasang();
    const k = kartu(host)[0];
    tekan(k, "Enter");
    expect(host.querySelector('[data-testid="kpi-detail"]')).not.toBeNull();
    tekan(k, "Enter");
    expect(host.querySelector('[data-testid="kpi-detail"]')).toBeNull();
    tekan(k, " ");
    expect(host.querySelector('[data-testid="kpi-detail"]')).not.toBeNull();
  });
});

describe("isi panel penjelasan", () => {
  it("menjelaskan arti angka dengan bahasa manusia", () => {
    const host = pasang();
    klik(kartu(host)[0]);
    const teks = host.querySelector('[data-testid="kpi-detail"]')!.textContent ?? "";
    expect(teks).toContain("Keberlanjutan menu");
    // 29 Okt 2026: judul "Cara membaca" dilebur ke blok "Apa artinya" sebagai
    // satu baris kecil — dua kepala blok untuk satu penjelasan terlalu berat.
    expect(teks).toContain("Apa artinya");
    expect(teks).not.toContain("Cara membaca");
    expect(teks).toContain("makin tinggi makin baik");
    expect(teks).toContain("82,50");
  });

  it("tidak memamerkan istilah teknis", () => {
    const host = pasang();
    klik(kartu(host)[0]);
    const teks = host.querySelector('[data-testid="kpi-detail"]')!.textContent ?? "";
    for (const teknis of [
      "kpi-1.4.0",
      "menu_plans",
      "measured",
      "served / planned",
      "sampel",
      "Rumus",
      "Metode",
    ]) {
      expect(teks).not.toContain(teknis);
    }
  });

  it("sumber berupa daftar kolom tidak dicetak sebagai 'sumber data'", () => {
    const host = pasang();
    klik(kartu(host)[2]);
    const teks = host.querySelector('[data-testid="kpi-detail"]')!.textContent ?? "";
    // Payload asli kadang berisi "disposal_events.disposed_at, …" — bahan audit,
    // bukan penjelasan. Ia tidak boleh muncul di panel informatif.
    expect(teks).not.toMatch(/disposal_events\.|supply_records\./);
  });

  it("sumber data ditulis sebagai nama yang bisa dibaca", () => {
    const host = pasang();
    klik(kartu(host)[0]);
    const teks = host.querySelector('[data-testid="kpi-detail"]')!.textContent ?? "";
    expect(teks).toContain("Rencana menu");
  });

  it("metrik tanpa angka menyebut sebabnya, bukan angka pengganti", () => {
    const host = pasang();
    klik(kartuNama(host, "Safe Delivered Cost"));
    const teks = host.querySelector('[data-testid="kpi-detail"]')!.textContent ?? "";
    expect(teks).toContain("belum ada purchase order terbit pada periode ini");
    expect(teks).toContain("—");
  });

  it("hanya satu panel: kartu lain memindahkan isi", () => {
    const host = pasang();
    klik(kartuNama(host, "Meal Continuity Rate"));
    klik(kartuNama(host, "Safe Delivered Cost"));
    expect(host.querySelectorAll('[data-testid="kpi-detail"]')).toHaveLength(1);
    const teks = host.querySelector('[data-testid="kpi-detail"]')!.textContent ?? "";
    expect(teks).toContain("Biaya kirim aman");
    expect(teks).not.toContain("Keberlanjutan menu");
    expect(
      kartuNama(host, "Meal Continuity Rate").getAttribute("aria-expanded")
    ).toBe("false");
  });

  it("klik kedua pada kartu yang sama menutup panel", () => {
    const host = pasang();
    const k = kartu(host)[0];
    klik(k);
    klik(k);
    expect(host.querySelector('[data-testid="kpi-detail"]')).toBeNull();
  });

  it("membuka panel menggulirnya ke layar dan memindahkan fokus ke judulnya", () => {
    // Kenapa diuji (tahap 3 redesign, 29 Okt 2026): panel hidup DI BAWAH grid,
    // dan pada viewport 900 px kartu baris pertama berada di 367–606 px
    // sementara panel muncul di 873 px — praktis di luar layar. Tanpa
    // menggulir + memindahkan fokus, klik kartu terasa tidak melakukan apa-apa
    // (terukur dengan CDP sebelum perbaikan: scrollY tetap 0, fokus tetap BODY).
    const gulir: Array<Record<string, unknown>> = [];
    (HTMLElement.prototype as unknown as { scrollIntoView: (o: unknown) => void }).scrollIntoView = (
      o: unknown
    ) => {
      gulir.push(o as Record<string, unknown>);
    };
    const host = pasang();
    klik(kartu(host)[0]);
    const panel = host.querySelector('[data-testid="kpi-detail"]')!;

    // Satu wilayah bernama: pembaca layar tahu ini wilayah rincian, bukan div
    // anonim, dan namanya datang dari judul di dalamnya.
    expect(panel.getAttribute("role")).toBe("region");
    expect(panel.getAttribute("aria-labelledby")).toBe("kpi-detail-judul");

    expect(gulir).toHaveLength(1);
    expect(gulir[0]).toMatchObject({ block: "start" });

    // Fokus pindah ke judul panel (bukan tertinggal di kartu), sehingga Tab
    // berikutnya menelusuri isi rincian dan Escape/tutup mengembalikannya.
    const judul = panel.querySelector(".kpi-detail-title") as HTMLElement;
    expect(judul.getAttribute("tabindex")).toBe("-1");
    expect(document.activeElement).toBe(judul);
  });

  it("tombol tutup mengembalikan fokus ke kartu", () => {
    const host = pasang();
    const k = kartu(host)[0];
    klik(k);
    klik(host.querySelector('[data-testid="kpi-detail"] button.kpi-detail-close'));
    expect(host.querySelector('[data-testid="kpi-detail"]')).toBeNull();
    expect(document.activeElement).toBe(k);
  });
});
