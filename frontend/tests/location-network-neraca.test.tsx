// L2 — "Keadaan jaringan" sebagai kartu utama halaman.
//
// Yang dijaga:
//   * Kalimat neraca lebih besar dari isi lain (`.headline` naik ke --fs-5) dan
//     tidak mengecil ke ukuran catatan di layar sempit (tetap --fs-4).
//   * Nada jaringan ditulis sebagai TEKS ("ada kekurangan" / "kebutuhan tertutup"
//     / "tidak ada selisih" / "belum terbaca"), bukan warna saja.
//   * Penanda nada tidak membawa angka: angka jaringan tetap satu tempat, di
//     kalimat neraca.
//   * Isu kelengkapan menjadi SATU baris, bukan daftar dua butir, dan jejak
//     auditnya tetap ada sebagai atribut `data-kind`.
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
const SEIMBANG = lokasi({
  location: "Medan",
  region: "Sumatera Utara",
  status: "balanced",
  supply_kg: 300,
  demand_kg: 300,
  shortage_kg: 0,
  surplus_kg: 0,
});
const BOGOR = lokasi({
  location: "Bogor",
  region: "Jawa Barat",
  supply_kg: null as unknown as number,
  supply_state: "tidak_ada_baris",
  supply_recorded_at: null,
});

function renderBoard(over: Partial<Parameters<typeof LocationNetworkBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <LocationNetworkBoard
      locations={[JAKARTA, CIANJUR]}
      commodity="telur"
      selected={null}
      onSelect={() => {}}
      detail={null}
      {...over}
    />
  );
}

/** Penanda nada: teksnya saja, tanpa tag. */
function nada(html: string): string | null {
  const cocok = html.match(/data-testid="network-lead-state"[^>]*>([^<]*)</);
  return cocok ? cocok[1].trim() : null;
}

describe("L2 — neraca jaringan sebagai kartu utama", () => {
  it("kartu keadaan memakai kelas lead dan membawa nada", () => {
    const html = renderBoard();
    expect(html).toMatch(
      /<article class="card jump-target network-lead" id="network-keadaan" data-tone="(danger|safe|neutral|unknown)"/
    );
  });

  it("nada ditulis sebagai teks, bukan warna saja", () => {
    // Jakarta sendirian: kekurangan tanpa penutup → danger.
    expect(nada(renderBoard({ locations: [JAKARTA] }))).toBe("ada kekurangan");
    // Cianjur menutup Jakarta → surplus cukup → safe.
    expect(nada(renderBoard())).toBe("kebutuhan tertutup");
    expect(nada(renderBoard({ locations: [SEIMBANG] }))).toBe("tidak ada selisih");
    expect(nada(renderBoard({ locations: [] }))).toBe("belum terbaca");
  });

  it("penanda nada tidak memuat angka — angka tetap satu tempat di kalimat neraca", () => {
    for (const html of [
      renderBoard(),
      renderBoard({ locations: [CIANJUR] }),
      renderBoard({ locations: [SEIMBANG] }),
      renderBoard({ locations: [JAKARTA, CIANJUR] }),
    ]) {
      expect(nada(html) ?? "").not.toMatch(/[0-9]/);
    }
    // Kalimat neraca tetap membawa angkanya.
    expect(renderBoard()).toMatch(/kekurangan [0-9]/);
  });

  it("saat memuat tidak ada kesimpulan nada", () => {
    const html = renderBoard({ locations: [], loading: true });
    expect(nada(html)).toBeNull();
    expect(html).toContain("Memuat saldo lokasi…");
  });

  it("isu kelengkapan jadi satu baris, jejak data-kind tetap ada", () => {
    const html = renderBoard({ locations: [JAKARTA, BOGOR] });
    const baris = html.match(
      /<p class="[^"]*" data-testid="location-network-completeness">([\s\S]*?)<\/p>/
    );
    expect(baris, "isu kelengkapan harus berupa satu paragraf").not.toBeNull();
    const isi = baris?.[1] ?? "";
    expect(isi).toContain('data-kind="missing"');
    expect(isi).toContain("1 tanpa catatan pasokan");
    expect(html).not.toContain('data-testid="location-network-completeness"><li');
  });

  it("isu kelengkapan tidak dirender saat data lengkap", () => {
    const html = renderBoard({ locations: [JAKARTA, CIANJUR] });
    expect(html).not.toContain("location-network-completeness");
  });
});

describe("L2 — ukuran huruf kalimat neraca", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

  it("kalimat neraca memakai --fs-5, bukan ukuran catatan", () => {
    expect(css).toMatch(/\.network-lead-text \{[^}]*font-size: var\(--fs-5\)/);
  });

  it("di layar sempit turun satu langkah, bukan ke ukuran catatan", () => {
    const sempit = css.slice(css.indexOf("@media (max-width: 640px)"));
    expect(sempit).toMatch(/\.network-lead-text \{\s*font-size: var\(--fs-4\)/);
    expect(sempit.slice(0, 400)).not.toMatch(/--fs-[12]\)/);
  });

  it("penanda nada punya gaya untuk tiap nada", () => {
    expect(css).toMatch(/\.network-lead-state \{/);
    expect(css).toMatch(/\.network-lead-state\[data-tone="danger"\]/);
    expect(css).toMatch(/\.network-lead-state\[data-tone="safe"\]/);
  });

  it("kartu lead memakai garis tepi, bukan latar berwarna", () => {
    expect(css).toMatch(/\.network-lead \{[^}]*border-left: 3px solid var\(--line-strong\)/);
    expect(css).toMatch(/\.network-lead\[data-tone="danger"\] \{[^}]*border-left-color: var\(--danger\)/);
  });

  it("kelas modul untuk teks lead tidak lagi ada (satu tempat dengan kartunya)", () => {
    const modul = readFileSync(
      new URL("../components/LocationNetworkBoard.module.css", import.meta.url),
      "utf8"
    );
    expect(modul).not.toMatch(/^\.headline \{/m);
    expect(modul).not.toMatch(/^\.issues \{/m);
  });
});
