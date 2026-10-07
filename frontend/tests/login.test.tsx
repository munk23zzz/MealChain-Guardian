// Test polish login (TDD): brand panel + rute dingin + akun demo +
// state loading/error. Render SSR sama seperti smoke.test.tsx.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import Page from "../app/page";

describe("login polish", () => {
  const html = renderToStaticMarkup(<Page />);

  it("brand: judul MealChain Guardian + eyebrow SPPG/BGN", () => {
    expect(html).toContain("MealChain Guardian");
    expect(html).toContain("SPPG");
  });

  it("rute dingin Bogor → Jakarta tampil di panel brand", () => {
    expect(html).toContain("Bogor");
    expect(html).toContain("Jakarta");
    expect(html).toMatch(/→|→/);
  });

  it("tiga akun demo tersedia untuk klik-isi cepat", () => {
    expect(html).toContain("sppg.head@demo.local");
    expect(html).toContain("sppg.nutritionist@demo.local");
    expect(html).toContain("bgn.monitor@demo.local");
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
