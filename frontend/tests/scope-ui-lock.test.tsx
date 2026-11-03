/**
 * Kontrak UI cakupan lokasi untuk peran SPPG (Ruling 2026-10-14).
 *
 * Sebelum ruling, dua panel ini membiarkan pemakai memilih 5 kota; setelah
 * cakupan ditegakkan di server, memilih kota lain hanya menghasilkan 403 di
 * tengah demo. Uji ini memastikan kontrolnya benar-benar terkunci untuk peran
 * SPPG dan tetap terbuka untuk bgn_monitor (cakupan nasional).
 */

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import Event2Panel from "../components/Event2Panel";
import OpsConsole from "../components/OpsConsole";
import { mapHeaderSubtitle } from "../lib/overview-copy";

const OTHER_CITY = "Cianjur"; // ada di daftar kota panel, bukan lokasi kepala demo

describe("pemilih lokasi panel", () => {
  it("kepala SPPG terkunci ke SPPG-nya (tanpa pilihan kota lain)", () => {
    const html = renderToStaticMarkup(
      <OpsConsole role="sppg_head" token="t" ownLocationName="Jakarta" />
    );
    expect(html).toContain('class="ops-location"');
    expect(html).toMatch(/class="ops-location"[^>]*disabled/);
    expect(html).toContain("Jakarta");
    expect(html).not.toContain(OTHER_CITY);
    expect(html).toContain("Terkunci ke SPPG Anda");
  });

  it("bgn_monitor bebas memilih lokasi (cakupan nasional)", () => {
    const html = renderToStaticMarkup(
      <OpsConsole role="bgn_monitor" token="t" ownLocationName={null} />
    );
    expect(html).toContain(OTHER_CITY);
    expect(html).not.toMatch(/class="ops-location"[^>]*disabled/);
    expect(html).toContain("Cakupan nasional");
  });

  it("panel Event 2 mengikuti aturan yang sama", () => {
    const head = renderToStaticMarkup(
      <Event2Panel role="sppg_head" token="t" ownLocationName="Jakarta" />
    );
    expect(head).toMatch(/class="event2-location"[^>]*disabled/);
    expect(head).not.toContain(OTHER_CITY);

    // bgn_monitor tidak "terkunci satu kota" — daftar kotanya utuh. Kontrolnya
    // memang disabled, tetapi karena peran itu read-only (tidak menjalankan
    // Event 2), bukan karena cakupan lokasi.
    const monitor = renderToStaticMarkup(
      <Event2Panel role="bgn_monitor" token="t" ownLocationName={null} />
    );
    expect(monitor).toContain(OTHER_CITY);
    expect(monitor).toContain("Cakupan nasional");
    expect(monitor).toContain("Mode baca");
  });
});

describe("kop peta Overview", () => {
  it("satu lokasi ditulis sebagai SPPG pemakai, bukan 'Peta 1 lokasi SPPG'", () => {
    const teks = mapHeaderSubtitle(1);
    expect(teks).toContain("Peta SPPG Anda");
    expect(teks).not.toContain("1 lokasi");
  });

  it("banyak lokasi tetap menyebut jumlahnya", () => {
    expect(mapHeaderSubtitle(10)).toContain("Peta 10 lokasi SPPG");
  });

  it("tidak ada lokasi tidak dikarang jadi nol titik", () => {
    expect(mapHeaderSubtitle(0)).toContain("Tidak ada lokasi");
  });
});
