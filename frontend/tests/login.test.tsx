// Test polish login (TDD): brand panel + rute dingin + akun demo +
// state loading/error. Render SSR sama seperti smoke.test.tsx.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import Page from "../app/page";
import { withProviders } from "./with-providers";

describe("login polish", () => {
  const html = renderToStaticMarkup(withProviders(<Page />));

  it("brand: judul MealChain Guardian + eyebrow SPPG/BGN", () => {
    expect(html).toContain("MealChain Guardian");
    expect(html).toContain("SPPG");
  });

  it("rute dingin & kotak angka DIHAPUS dari panel brand (arah Roy)", () => {
    expect(html).not.toContain("route-line");
    expect(html).not.toContain("brand-stats");
    expect(html).not.toContain("50 km");
  });

  it("akun demo kota lain tersedia: Bandung & Surabaya (label saja)", () => {
    // Keputusan produk 3A: approver per kota supaya alur approval bisa
    // didemokan di luar Jakarta.
    expect(html).toContain("Kepala Bandung");
    expect(html).toContain("Gizi Bandung");
    expect(html).toContain("Kepala Surabaya");
    expect(html).toContain("Gizi Surabaya");
    expect(html).toContain("Kota lain:");
    // Email demo tidak dipajang di login (visual lebih bersih).
    expect(html).not.toContain("demo.local");
  });

  it("tiga akun demo utama tetap ada untuk klik-isi cepat", () => {
    expect(html).toContain("SPPG Head");
    expect(html).toContain("Nutritionist");
    expect(html).toContain("BGN Monitor");
    expect(html).not.toContain("demo.local");
  });

  it("form punya label Email, Password, dan tombol Masuk", () => {
    expect(html).toContain("Email");
    expect(html).toContain("Password");
    expect(html).toContain("Masuk");
  });

  it("panel brand memuat konteks program (BGN)", () => {
    expect(html).toContain("Badan Gizi Nasional");
  });
});
