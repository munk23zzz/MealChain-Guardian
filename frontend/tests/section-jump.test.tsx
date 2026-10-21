// @vitest-environment jsdom
// Komponen bersama "lompat ke bagian halaman" — kontrak 20 Okt 2026.
//
// Latar: pola nav menempel yang dipakai halaman Decision & Evidence dipindahkan
// keluar dari komponen itu supaya bisa dipakai halaman lain TANPA menyalin
// logika. Yang diuji di sini adalah kontraknya, bukan tampilannya:
//
//   1. Markup: <nav> berlabel, daftar tujuan berupa TAUTAN (bukan tombol) —
//      supaya bisa dibuka di tab baru dan terbaca pembaca layar sebagai daftar
//      tujuan halaman.
//   2. Satu penanda posisi: tepat satu `aria-current="true"`, dan ia menunjuk
//      bagian yang sedang dibaca (diukur dari atas viewport, bukan rasio
//      irisan — bagian yang lebih tinggi dari layar tidak pernah "menang" bila
//      diukur dengan IntersectionObserver).
//   3. Tujuan yang tidak ada di DOM dilewati, bukan dianggap aktif: halaman
//      yang bagiannya bergantung pada data tidak boleh punya tautan mati.
//   4. Daftar bagian tiap halaman dibangun fungsi murni (lib/section-jump.ts)
//      dari kondisi render yang SAMA dengan bagiannya — bukan konstanta tetap.
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";

import SectionJump from "../components/SectionJump";
import {
  EVIDENCE_SECTION_IDS,
  OVERVIEW_SECTION_IDS,
  SAFETY_SECTION_IDS,
  evidenceSections,
  overviewSections,
  safetySections,
} from "../lib/section-jump";

const ITEMS = [
  { id: "satu", label: "Ringkasan" },
  { id: "dua", label: "Peta" },
  { id: "tiga", label: "Telemetri" },
];

let root: Root;
let host: HTMLDivElement;

/** Target tiruan: jsdom tidak punya layout, jadi atas tiap elemen ditentukan
 *  sendiri lewat getBoundingClientRect yang di-stub. */
function target(id: string, top: number) {
  const el = document.createElement("section");
  el.id = id;
  el.getBoundingClientRect = () =>
    ({ top, bottom: top + 400, height: 400, left: 0, right: 0, width: 0, x: 0, y: 0, toJSON: () => ({}) }) as DOMRect;
  document.body.append(el);
  return el;
}

function mount(items = ITEMS) {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  // rAF dijalankan langsung: pengukuran tetap melewati jalur yang sama
  // (rAF-throttled), hanya tidak menunggu frame.
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    cb(0);
    return 1;
  });
  vi.stubGlobal("cancelAnimationFrame", () => {});
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => {
    root.render(<SectionJump items={items} />);
  });
}

function aktif(): string | null {
  const ditandai = host.querySelectorAll('[aria-current="true"]');
  expect(ditandai).toHaveLength(1);
  return ditandai[0].getAttribute("href");
}

function gulir() {
  act(() => {
    window.dispatchEvent(new Event("scroll"));
  });
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  document.querySelectorAll("section[id]").forEach((el) => el.remove());
  vi.unstubAllGlobals();
});

describe("SectionJump — markup", () => {
  it("nav berlabel dengan daftar tujuan berupa tautan", () => {
    const html = renderToStaticMarkup(<SectionJump items={ITEMS} />);
    expect(html).toContain('class="section-jump"');
    expect(html).toContain('aria-label="Lompat ke bagian halaman"');
    expect(html).toContain('class="section-jump-label">Bagian<');
    expect(html).toContain('href="#tiga"');
    expect(html).not.toContain("<button");
  });

  it("bagian pertama ditandai sebagai posisi sekarang, dan hanya satu", () => {
    const html = renderToStaticMarkup(<SectionJump items={ITEMS} />);
    expect(html).toMatch(/aria-current="true"[^>]*>Ringkasan</);
    expect((html.match(/aria-current="true"/g) ?? []).length).toBe(1);
  });

  it("label dan aria-label bisa diganti per halaman", () => {
    const html = renderToStaticMarkup(
      <SectionJump items={ITEMS} label="Bagian halaman" ariaLabel="Bagian Keamanan Pangan" />
    );
    expect(html).toContain('aria-label="Bagian Keamanan Pangan"');
    expect(html).toContain("Bagian halaman");
  });
});

describe("SectionJump — penanda posisi", () => {
  it("bagian yang sudah lewat atas layar menjadi posisi sekarang", () => {
    target("satu", 0);
    target("dua", 900);
    target("tiga", 1800);
    mount();

    expect(aktif()).toBe("#satu");

    // Bagian kedua melewati ambang atas (offset 140 px).
    document.getElementById("dua")!.getBoundingClientRect = () =>
      ({ top: -10, bottom: 390, height: 400 }) as DOMRect;
    gulir();
    expect(aktif()).toBe("#dua");

    // Ketiga menyusul: bagian terakhir yang lewat ambang menang.
    document.getElementById("tiga")!.getBoundingClientRect = () =>
      ({ top: -200, bottom: 200, height: 400 }) as DOMRect;
    gulir();
    expect(aktif()).toBe("#tiga");
  });

  it("bagian yang belum sampai tidak pernah jadi posisi sekarang", () => {
    target("satu", 0);
    target("dua", 900);
    mount();
    gulir();
    expect(aktif()).toBe("#satu");
  });

  it("tujuan yang tidak ada di halaman dilewati, bukan ditandai", () => {
    target("satu", 0);
    // "dua" sengaja tidak dibuat: bagiannya memang tidak dirender (data kosong).
    target("tiga", 1600);
    mount();
    gulir();
    expect(aktif()).toBe("#satu");
  });

  // Ditemukan saat verifikasi di aplikasi hidup (Overview, 1× zoom): bagian
  // TERAKHIR halaman sering lebih pendek dari sisa layar, jadi tepinya tidak
  // pernah melewati ambang dan nav tetap menandai bagian sebelumnya walau
  // pembaca sudah di dasar halaman. Di dasar = bagian terakhir, titik.
  it("di dasar halaman, bagian terakhir yang ditandai", () => {
    target("satu", 0);
    target("dua", 900);
    target("tiga", 1600);
    mount();

    Object.defineProperty(document.documentElement, "scrollHeight", { configurable: true, value: 3200 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 800 });
    Object.defineProperty(window, "scrollY", { configurable: true, value: 2400 });
    // 2400 + 800 = 3200 → tepat di dasar.
    gulir();
    expect(aktif()).toBe("#tiga");
  });

  it("belum di dasar halaman, aturan ambang tetap dipakai", () => {
    target("satu", 0);
    target("dua", 900);
    target("tiga", 1600);
    mount();

    Object.defineProperty(document.documentElement, "scrollHeight", { configurable: true, value: 3200 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 800 });
    Object.defineProperty(window, "scrollY", { configurable: true, value: 1200 });
    gulir();
    expect(aktif()).toBe("#satu");
  });
});

describe("daftar bagian per halaman", () => {
  it("Decision & Evidence: lima tujuan, urutan sesuai urutan baca keputusan", () => {
    expect(evidenceSections().map((i) => i.id)).toEqual([
      EVIDENCE_SECTION_IDS.ringkasan,
      EVIDENCE_SECTION_IDS.rute,
      EVIDENCE_SECTION_IDS.keputusan,
      EVIDENCE_SECTION_IDS.bukti,
      EVIDENCE_SECTION_IDS.jejak,
    ]);
  });

  it("Overview: lima tujuan, id sama dengan yang dipasang di halaman", () => {
    const items = overviewSections({ isApprover: true, hasShipments: true });
    // Urutan ini mengikuti `app/page.tsx` (Kecukupan dirender sebelum Kiriman);
    // sebelumnya nav menaruh Kiriman lebih dulu sehingga lompatannya melewati
    // Kecukupan. Lihat tests/overview-section-order.test.ts.
    expect(items.map((i) => i.id)).toEqual([
      OVERVIEW_SECTION_IDS.ringkas,
      OVERVIEW_SECTION_IDS.peta,
      OVERVIEW_SECTION_IDS.kecukupan,
      OVERVIEW_SECTION_IDS.kiriman,
      OVERVIEW_SECTION_IDS.telemetri,
    ]);
  });

  it("Overview: tujuan kiriman tidak dipasang saat kartunya tidak dirender", () => {
    const items = overviewSections({ isApprover: true, hasShipments: false });
    expect(items.map((i) => i.id)).toEqual([
      OVERVIEW_SECTION_IDS.ringkas,
      OVERVIEW_SECTION_IDS.peta,
      OVERVIEW_SECTION_IDS.kecukupan,
      OVERVIEW_SECTION_IDS.telemetri,
    ]);
  });

  it("Overview: judul bagian kecukupan mengikuti peran (SPPG vs monitor)", () => {
    const sppg = overviewSections({ isApprover: true, hasShipments: true });
    const monitor = overviewSections({ isApprover: false, hasShipments: true });
    expect(sppg.find((i) => i.id === OVERVIEW_SECTION_IDS.kecukupan)?.label).toBe("Kecukupan");
    expect(monitor.find((i) => i.id === OVERVIEW_SECTION_IDS.kecukupan)?.label).toBe(
      "Pasokan per lokasi"
    );
  });

  it("Keamanan Pangan: tujuan mengikuti bagian yang benar-benar dirender", () => {
    // Tanpa lokasi sendiri dan tanpa daftar keputusan: hanya tiga bagian tetap.
    expect(safetySections({ ownLocation: false, hasDecisions: false }).map((i) => i.id)).toEqual([
      SAFETY_SECTION_IDS.ringkasan,
      SAFETY_SECTION_IDS.segera,
      SAFETY_SECTION_IDS.batch,
    ]);
    // Kepala SPPG: penerimaan barang ikut muncul…
    expect(safetySections({ ownLocation: true, hasDecisions: false }).map((i) => i.id)).toEqual([
      SAFETY_SECTION_IDS.ringkasan,
      SAFETY_SECTION_IDS.segera,
      SAFETY_SECTION_IDS.terima,
      SAFETY_SECTION_IDS.batch,
    ]);
    // …dan panel keputusan menyusul saat daftar keputusan tersedia.
    expect(safetySections({ ownLocation: true, hasDecisions: true }).map((i) => i.id)).toEqual([
      SAFETY_SECTION_IDS.ringkasan,
      SAFETY_SECTION_IDS.segera,
      SAFETY_SECTION_IDS.terima,
      SAFETY_SECTION_IDS.batch,
      SAFETY_SECTION_IDS.keputusan,
    ]);
  });
});
