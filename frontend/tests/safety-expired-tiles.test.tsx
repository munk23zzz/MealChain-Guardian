// Kontrak baru (audit 29 Okt 2026): batch kedaluwarsa tampil sebagai keadaan
// sendiri — punya tile, punya lencana "Kedaluwarsa" di tabel, dan tetap
// dijumlahkan ke total.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

const NOW = new Date("2026-10-29T04:00:00Z");

const batch = (over: Record<string, unknown> = {}) => ({
  id: "b1",
  location: "Jakarta",
  commodity: "wortel",
  quantity_kg: 200,
  safety_status: "pass",
  freshness_score: 0.8,
  usable_until: "2026-11-02T04:00:00Z",
  ...over,
});

function render(batches: Record<string, unknown>[]) {
  return renderToStaticMarkup(
    <FoodSafetyBoard batches={batches as never} now={NOW} />
  );
}

function kartuRingkasan(html: string) {
  const mulai = html.indexOf('id="safety-ringkasan"');
  return html.slice(mulai, html.indexOf("</article>", mulai));
}

describe("tile kedaluwarsa", () => {
  it("muncul saat ada batch yang masa layaknya lewat, dan ikut dijumlahkan", () => {
    const html = render([batch({ id: "layak" }), batch({ id: "lewat", usable_until: "2026-10-29T02:00:00Z" })]);
    const kartu = kartuRingkasan(html);
    expect(kartu).toContain("Kedaluwarsa");
    const angka = Array.from(kartu.matchAll(/class="safety-count-value">(\d+)</g)).map((m) =>
      Number(m[1])
    );
    expect(kartu.match(/class="safety-count /g) ?? []).toHaveLength(6);
    expect(angka.reduce((a, b) => a + b, 0)).toBe(2);
    expect(kartu).toContain("dari 2 batch");
  });

  it("tidak dirender saat tidak ada yang kedaluwarsa (strip tetap lima angka)", () => {
    const kartu = kartuRingkasan(render([batch({ id: "layak" })]));
    expect(kartu).not.toContain("Kedaluwarsa");
    expect(kartu.match(/class="safety-count /g) ?? []).toHaveLength(5);
  });

  it("tabel menulis Kedaluwarsa, bukan Aman, untuk batch yang sudah lewat", () => {
    // Butuh status yang biasanya menghasilkan langkah "Selesaikan verifikasi
    // verifier" supaya asersi di bawah benar-benar menguji gerbangnya.
    const html = render([
      batch({
        id: "lewat",
        safety_status: "needs_verification",
        usable_until: "2026-10-29T02:00:00Z",
      }),
    ]);
    // Chip saringan memang memuat kata "Aman"; yang diperiksa adalah baris
    // tabel "Status keamanan per batch" (tabel pertama adalah "Batch perlu
    // perhatian", jadi potong mulai id kartunya).
    const mulai = html.indexOf('id="safety-batch"');
    const badan = html.slice(html.indexOf("<tbody>", mulai), html.indexOf("</tbody>", mulai));
    expect(badan).toContain(">Kedaluwarsa<");
    expect(badan).not.toContain(">Aman<");
    // Langkah berikutnya harus sesuai keadaan: batch kedaluwarsa tidak bisa
    // "diselesaikan verifikasinya menjadi boleh dipakai". Kalimat penjelasnya
    // ("Masa layak lewat: … ajukan pengganti") dibuang 29 Okt 2026 — kolom
    // status sudah menulis "Kedaluwarsa", jadi barisnya tidak diisi lagi.
    expect(badan).not.toContain("Masa layak lewat");
    expect(badan).not.toContain("Selesaikan verifikasi verifier");
  });
});

describe("label cakupan di kepala ringkasan", () => {
  it("menyebut cakupannya supaya angka jaringan tidak dibaca sebagai angka lokasi", () => {
    const kartu = kartuRingkasan(render([batch()]));
    expect(kartu).toContain("safety-scope");
    expect(kartu).toMatch(/Seluruh jaringan|Semua lokasi|Jakarta/);
  });
});
