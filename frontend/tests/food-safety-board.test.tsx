// Kontrak markup halaman "Keamanan Pangan" (halaman sidebar acuan /compliance).
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

const NOW = new Date("2026-10-11T06:00:00Z");
const BATCHES = [
  { id: "b1", location: "Cianjur", commodity: "telur", quantity_kg: 400, safety_status: "pass", freshness_score: 0.69, usable_until: "2026-10-11T18:00:00Z" },
  { id: "b2", location: "Surabaya", commodity: "ayam", quantity_kg: 120, safety_status: "fail", freshness_score: null, usable_until: null },
];

function render(props: Partial<Parameters<typeof FoodSafetyBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <FoodSafetyBoard batches={BATCHES} now={NOW} commodity="telur" {...props} />
  );
}

describe("FoodSafetyBoard", () => {
  it("judul + ringkasan pengawasan tampil dengan angka dari batch", () => {
    const html = render();
    expect(html).toContain("Keamanan Pangan");
    expect(html).toContain("Ringkasan pengawasan");
    expect(html).toContain("Batch diperiksa");
    expect(html).toContain("Gagal uji");
    expect(html).toContain("120 kg");
  });

  it("batch gagal dinyatakan terang-terangan beserta lokasinya", () => {
    const html = render();
    expect(html).toContain("Batch gagal uji: Surabaya");
    expect(html).toContain("tidak boleh dialokasikan");
  });

  it("tabel per batch memuat status, kesegaran, dan sisa masa", () => {
    const html = render();
    expect(html).toContain("Status keamanan per batch");
    expect(html).toContain("Aman");
    expect(html).toContain("69%");
    expect(html).toContain("12 jam lagi");
    expect(html).toContain("—"); // batch tanpa skor/tanggal
  });

  it("nilai kosong tidak diganti angka nol", () => {
    const html = render({
      batches: [{ id: "x", location: "Bogor", commodity: "telur", quantity_kg: 10, safety_status: null }],
    });
    expect(html).toContain("0"); // hitungan aman 0 memang benar
    expect(html).not.toMatch(/>0 kg</);
    expect(html).toContain("—");
  });

  it("galat pemuatan dijelaskan, bukan halaman kosong", () => {
    const html = render({ batches: null, error: "batches 500" });
    expect(html).toContain("Tidak bisa memuat batch");
    expect(html).toContain("batches 500");
  });

  it("tidak ada catatan internal (path API / nama kolom) di layar", () => {
    const html = render();
    expect(html).not.toContain("Catatan sumber");
    expect(html).not.toContain("/batches");
    expect(html).not.toContain("usable_until");
  });
});
