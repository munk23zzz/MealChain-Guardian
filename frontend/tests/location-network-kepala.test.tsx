// L1 — kepala halaman "Location Network": satu pita, satu baris filter, nav tetap 4.
//
// Yang dijaga:
//   * Baris filter komoditas pindah KE DALAM blok kepala halaman (`.page-header`),
//     bukan pita kedua di bawahnya — satu kepala, satu baris kontrol.
//   * Jumlah filter tidak bertambah: tetap satu `role="group"` berlabel "Komoditas"
//     (gerbang rencana isi §10.1).
//   * Hijau/hitam bukan satu-satunya penanda: pil keadaan menulis "catatan belum
//     lengkap" sebagai TEKS ketika ada isu, dan tidak muncul ketika data lengkap.
//   * Angka jumlah lokasi tetap muncul sekali; pil keadaan tidak menambah angka
//     baru (fakta yang sama tidak dicetak dua kali).
//   * Nav bagian tetap empat tujuan dan hilang saat halaman gagal memuat.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import LocationNetworkBoard from "../components/LocationNetworkBoard";
import type { BalanceMapLocation } from "../lib/overview-format";

const JAM = 3_600_000;
const SEKARANG = Date.now();

function lokasi(over: Partial<BalanceMapLocation> & { location: string }): BalanceMapLocation {
  return {
    region: "DKI Jakarta",
    latitude: -6.2,
    longitude: 106.8,
    supply_kg: 2150,
    demand_kg: 2930,
    status: "shortage",
    shortage_kg: 780,
    surplus_kg: 0,
    supply_state: "terukur",
    demand_state: "terukur",
    supply_recorded_at: new Date(SEKARANG - JAM).toISOString(),
    demand_recorded_at: new Date(SEKARANG - JAM).toISOString(),
    ...over,
  } as BalanceMapLocation;
}

const JAKARTA = lokasi({ location: "Jakarta" });
const CIANJUR = lokasi({
  location: "Cianjur",
  region: "Jawa Barat",
  status: "surplus",
  supply_kg: 2292,
  demand_kg: 900,
  shortage_kg: 0,
  surplus_kg: 1392,
});
/** Satu lokasi tanpa catatan pasokan — pemicu isu kelengkapan. */
const BOGOR = lokasi({
  location: "Bogor",
  region: "Jawa Barat",
  supply_kg: null,
  supply_state: "tidak_ada_baris",
  supply_recorded_at: null,
});

const KOMODITAS = ["telur", "ayam", "beras"];

function renderBoard(over: Partial<Parameters<typeof LocationNetworkBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <LocationNetworkBoard
      locations={[JAKARTA, CIANJUR]}
      commodity="telur"
      commodities={KOMODITAS}
      onCommodityChange={() => {}}
      selected={null}
      onSelect={() => {}}
      detail={null}
      snapshot="Data per 29 Okt 2026"
      {...over}
    />
  );
}

/** Isi blok kepala halaman, apa adanya. */
function kepala(html: string): string {
  const cocok = html.match(/<header class="page-header">([\s\S]*?)<\/header>/);
  return cocok ? cocok[1] : "";
}

describe("L1 — kepala halaman: filter di dalam pita kepala", () => {
  it("baris filter komoditas berada di dalam blok kepala, bukan pita terpisah", () => {
    const html = renderBoard();
    expect(kepala(html)).toContain('aria-label="Komoditas"');
    expect(kepala(html)).toContain("Telur".toLowerCase());
    expect(kepala(html)).toContain("Data per 29 Okt 2026");
  });

  it("hanya satu baris filter, satu judul h1, satu kalimat penjelas", () => {
    const html = renderBoard();
    expect((html.match(/aria-label="Komoditas"/g) ?? []).length).toBe(1);
    expect((html.match(/<h1>/g) ?? []).length).toBe(1);
    expect(
      (html.match(/Siapa kekurangan, siapa kelebihan, apa yang dialihkan, dan apa yang terbuang\./g) ?? [])
        .length
    ).toBe(1);
  });

  it("jumlah lokasi tetap satu kali dan tidak ada angka kedua di pil keadaan", () => {
    const html = renderBoard({ locations: [JAKARTA, CIANJUR, BOGOR] });
    expect((html.match(/3 lokasi/g) ?? []).length).toBe(1);
    // Pil keadaan menyebut keadaan, bukan angka yang sudah ada di daftar isu.
    const pilKeadaan = html.match(/data-state="sebagian"[^>]*>([^<]*)</);
    expect(pilKeadaan?.[1] ?? "").toBe("catatan belum lengkap");
  });

  it("pil keadaan muncul saat ada isu dan hilang saat data lengkap", () => {
    const adaIsu = renderBoard({ locations: [JAKARTA, BOGOR] });
    expect(adaIsu).toContain("catatan belum lengkap");
    expect(adaIsu).toContain("1 tanpa catatan pasokan");

    const lengkap = renderBoard({ locations: [JAKARTA, CIANJUR] });
    expect(lengkap).not.toContain("catatan belum lengkap");
  });

  it("selama memuat, pil jumlah dan pil keadaan tidak dicetak", () => {
    const html = renderBoard({ locations: [], loading: true });
    expect(html).not.toMatch(/\d+ lokasi</);
    expect(html).not.toContain("catatan belum lengkap");
    // Filter tetap ada supaya pengguna bisa mengganti komoditas sambil menunggu.
    expect(kepala(html)).toContain('aria-label="Komoditas"');
  });

  it("nav bagian tetap empat tujuan", () => {
    const html = renderBoard({ plan: { available: true, min_surplus_kg: 150, pairs: [] } });
    const tujuan = Array.from(html.matchAll(/href="#network-[a-z]+"/g), (m) => m[0]);
    expect(tujuan).toEqual([
      'href="#network-keadaan"',
      'href="#network-lokasi"',
      'href="#network-alih"',
      'href="#network-limbah"',
    ]);
  });

  it("saat gagal memuat: tanpa nav bagian", () => {
    const html = renderBoard({ error: "Saldo lokasi tidak terbaca." });
    expect(html).not.toContain('href="#network-');
  });
});

describe("L1 — pita kepala di CSS", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

  it("baris filter di pita kepala turun baris penuh, tanpa margin sendiri", () => {
    expect(css).toMatch(/\.page-header-filters \{[^}]*flex-basis: 100%/);
    expect(css).toMatch(/\.page-header-filters \.commodity-filters \{\s*margin: 0/);
  });

  it("label komoditas disembunyikan secara visual di ≤560 px, bukan dihapus", () => {
    // Terukur di pratinjau 375 px: label "Komoditas:" memakan satu baris pil,
    // pita filter 72 px → 32 px setelah disembunyikan.
    expect(css).toMatch(
      /@media \(max-width: 560px\) \{\s*\.page-header-filters \.commodity-filters-label \{[^}]*clip-path: inset\(50%\)/
    );
  });
});
