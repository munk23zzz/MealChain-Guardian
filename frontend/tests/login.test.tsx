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

  it("tanpa blok akun demo: form hanya email, sandi, dan tombol Masuk", () => {
    // Permintaan pemilik 29 Okt 2026: seluruh blok demo dihapus dari login
    // (label "Demo:", "Kota lain:", dan pemberitahuan sandi manual). Kredensial
    // dibagikan di luar layar, bukan dicetak di halaman publik.
    expect(html).not.toContain("demo-block");
    expect(html).not.toContain("demo-link");
    expect(html).not.toContain("Kota lain:");
    expect(html).not.toContain("SPPG Head");
    expect(html).not.toContain("Nutritionist");
    expect(html).not.toContain("Sandi demo tidak dikirim");
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
