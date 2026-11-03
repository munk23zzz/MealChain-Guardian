// Tile ringkasan sebagai tombol saring (redesign 29 Okt 2026, tahap 2).
//
// Dua hal yang dikunci di sini:
//   1. angka ringkasan bisa DIKLIK dan menyaring daftar (sebelumnya pajangan);
//   2. status tidak disampaikan warna saja: setiap tile membawa ikon SVG
//      (aria-hidden) dan label teks, dan angkanya diumumkan sebagai satu
//      kalimat utuh lewat role="status".
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import FoodSafetyBoard from "../components/FoodSafetyBoard";
import { filterSafetyRows, matchesSafetyFilter, type SafetyRow } from "../lib/food-safety";

const NOW = new Date("2026-10-11T06:00:00Z");
const BATCHES = [
  { id: "b1", location: "Cianjur", commodity: "telur", quantity_kg: 400, safety_status: "pass", freshness_score: 0.69, usable_until: "2026-10-11T18:00:00Z" },
  { id: "b2", location: "Surabaya", commodity: "ayam", quantity_kg: 120, safety_status: "fail", freshness_score: null, usable_until: null },
];

function render(props: Partial<Parameters<typeof FoodSafetyBoard>[0]> = {}) {
  return renderToStaticMarkup(<FoodSafetyBoard batches={BATCHES} now={NOW} {...props} />);
}

/** Potongan markup untuk satu tile, dari nama labelnya. */
function tile(html: string, label: string): string {
  const i = html.indexOf(`>${label}</span>`);
  expect(i, `tile ${label} tidak dirender`).toBeGreaterThan(-1);
  const mulai = html.lastIndexOf('<button type="button"', i);
  return html.slice(mulai, html.indexOf("</button>", i) + "</button>".length);
}

describe("tile ringkasan bisa menyaring", () => {
  it("setiap angka adalah tombol dengan nama aksesibel", () => {
    const html = render();
    const tombol = Array.from(html.matchAll(/aria-label="Saring daftar ke [^"]+"/g)).map((m) => m[0]);
    expect(tombol.length).toBeGreaterThanOrEqual(4);
    // Nama tombol menyebut label dan jumlahnya, bukan hanya angka.
    expect(tombol.some((t) => t.includes("Gagal uji"))).toBe(true);
  });

  it("tile bernilai nol tidak bisa diklik, tile yang berisi bisa", () => {
    const html = render();
    // "Gagal uji" = 1 pada data uji -> tombolnya aktif.
    expect(tile(html, "Gagal uji")).not.toContain("disabled");
    // "Ditahan" = 0 -> tombolnya mati (menyaring ke daftar kosong tidak berguna).
    expect(tile(html, "Ditahan")).toContain("disabled");
  });

  it("status tidak disampaikan warna saja: ada ikon SVG dan label teks", () => {
    const html = render();
    for (const label of ["Aman", "Gagal uji", "Ditahan"]) {
      const blok = tile(html, label);
      expect(blok, `${label} tanpa ikon`).toContain("<svg");
      expect(blok, `${label} ikon harus aria-hidden`).toContain('aria-hidden="true"');
      expect(blok).toContain(label);
    }
  });

  it("angka diumumkan sebagai satu kalimat utuh (role=status, aria-atomic)", () => {
    const html = render();
    const i = html.indexOf('role="status"');
    expect(i).toBeGreaterThan(-1);
    const pembuka = html.lastIndexOf("<p", i);
    expect(html.slice(pembuka, i + 40)).toContain('aria-atomic="true"');
    // Kalimatnya menyebut jumlah batch, bukan angka telanjang.
    expect(html.slice(pembuka, html.indexOf("</p>", i))).toContain("batch diperiksa");
  });
});

describe("saringan per kelompok status", () => {
  // Baris di bawah dibuat pendek: yang diuji hanya pemetaan status -> saringan,
  // bukan pembentukan baris (itu diuji di berkas lain).
  const baris = (ubin: Record<string, unknown>): SafetyRow =>
    ({ location: "Cianjur", commodity: "telur", ...ubin }) as unknown as SafetyRow;
  const aman = baris({ id: "a", tone: "ok", hoursLeft: 48, quarantine: null });
  const gagal = baris({ id: "g", tone: "danger", hoursLeft: 48, quarantine: null });
  const verifikasi = baris({ id: "v", tone: "warn", hoursLeft: 48, quarantine: null });
  const belum = baris({ id: "n", tone: "muted", hoursLeft: null, quarantine: null });
  const kedaluwarsa = baris({ id: "k", tone: "ok", hoursLeft: -5, quarantine: null });
  const ditahan = baris({ id: "d", tone: "ok", hoursLeft: 48, quarantine: "quarantined" });
  const semua = [aman, gagal, verifikasi, belum, kedaluwarsa, ditahan];

  it("setiap kelompok bisa disaring sendiri-sendiri (bukan dilebur ke 'tindakan')", () => {
    expect(semua.filter((r) => matchesSafetyFilter(r, "ditahan"))).toEqual([ditahan]);
    expect(semua.filter((r) => matchesSafetyFilter(r, "kedaluwarsa"))).toEqual([kedaluwarsa]);
    expect(semua.filter((r) => matchesSafetyFilter(r, "belum"))).toEqual([belum]);
  });

  it("saringan kelompok tidak mengubah arti 'tindakan'", () => {
    // "tindakan" tetap = gagal + kedaluwarsa + verifikasi + ditahan.
    expect(semua.filter((r) => matchesSafetyFilter(r, "tindakan"))).toHaveLength(4);
  });

  it("filterSafetyRows memakai saringan baru tanpa kehilangan pencarian", () => {
    expect(filterSafetyRows(semua, "ditahan", "")).toHaveLength(1);
    expect(filterSafetyRows(semua, "semua", "a")).toHaveLength(6);
  });
});
