// Panel "Monitor harga komoditas" — kontrak SSR (tanpa jsdom, tanpa jaringan).
//
// Halaman Overview adalah komponen klien raksasa dan panel ini memakai React
// Query, jadi yang bisa dipaku saat render server adalah HAL YANG TIDAK
// BERGANTUNG PADA JARINGAN: judul, label kontrol, keadaan "belum masuk", dan
// ketiadaan angka karangan. Angka harga setelah data tiba diuji di
// tests/price-monitor.test.ts (logika murni) — bukan di sini.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import PriceMonitor from "../components/PriceMonitor";
import { withProviders } from "./with-providers";

function render(
  token: string | null,
  lokasi: string | null = "Jakarta",
  lokasiSendiri: string | null = null
) {
  return renderToStaticMarkup(
    withProviders(
      <PriceMonitor token={token} activeLocation={lokasi} lokasiSendiri={lokasiSendiri} />
    )
  );
}

describe("PriceMonitor (SSR)", () => {
  it("menampilkan judul, sumber, dan kontrol komoditas", () => {
    const html = render(null);
    expect(html).toContain("Monitor harga komoditas");
    expect(html).toContain("PIHPS Bank Indonesia");
    expect(html).toContain("Beras");
    expect(html).toContain("Telur");
    expect(html).toContain("Ayam");
    expect(html).toContain("7 hari");
    expect(html).toContain("30 hari");
    expect(html).toContain("90 hari");
  });

  it("tanpa token: minta masuk, bukan menampilkan angka", () => {
    const html = render(null);
    expect(html).toContain("Masuk dulu untuk melihat harga pasar");
    expect(html).not.toContain("Rp25.700");
  });

  it("kontrol komoditas adalah tombol ber-aria-pressed (bukan div klik)", () => {
    const html = render(null);
    expect(html).toMatch(/<button[^>]*aria-pressed="true"/);
    // Tiga chip komoditas + tiga pil rentang, semuanya tombol.
    expect((html.match(/class="pm-chip[ "]/g) ?? []).length).toBe(3);
    // Tiga pil rentang + dua pil skala (Indeks/Rupiah).
    expect((html.match(/pm-range-pil/g) ?? []).length).toBe(5);
    expect(html).toContain("Indeks");
    expect(html).toContain("Rupiah");
    // Tidak ada div yang berperan sebagai chip (klik harus lewat <button>).
    expect(html).not.toMatch(/<div[^>]*class="pm-chip[ "]/);
  });

  it("tidak lagi memuat catatan wortel tanpa acuan PIHPS", () => {
    // Permintaan pemilik 29 Okt 2026: kalimat "Wortel tidak termasuk 21
    // komoditas PIHPS…" dihapus. Chip komoditas tetap tiga (Beras/Telur/Ayam),
    // jadi tidak ada garis wortel yang perlu dijelaskan.
    const html = render(null);
    expect(html).not.toContain("Wortel");
    expect(html).not.toContain("21 komoditas PIHPS");
  });

  it("akun SPPG tanpa pilihan di bar atas membaca wilayahnya sendiri", () => {
    // Tanpa ini panel menjawab "Cakupan nasional" untuk kepala SPPG — angka
    // yang tidak bisa dipakai membeli di pasar mana pun.
    const html = render(null, null, "Bandung");
    expect(html).toContain("Wilayah harga mengikuti SPPG ini (Bandung)");
    expect(html).not.toContain("Cakupan nasional");
  });

  it("pilihan di bar atas tetap menang atas lokasi akun", () => {
    const html = render(null, "Cianjur", "Bandung");
    expect(html).toContain("Jawa Barat");
    expect(html).not.toContain("Wilayah harga mengikuti SPPG ini");
  });

  it("tanpa lokasi terpilih, panel memakai cakupan nasional dan mengatakannya", () => {
    const html = render(null, null);
    expect(html).toContain("Cakupan nasional");
  });

  it("Cianjur: cadangan provinsi disebut di layar (bukan harga kota palsu)", () => {
    const html = render("token", "Cianjur");
    expect(html).toContain("Jawa Barat");
  });
});
