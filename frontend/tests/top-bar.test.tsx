// Top bar — kontrak render (pola repo ini: renderToStaticMarkup, tanpa DOM).
// Yang dipin: unsur header acuan benar-benar ada, angka/label datang dari
// data yang dioper (bukan dikarang), dan cakupan peran tidak bisa diperluas.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";

import TopBar from "../components/TopBar";

const LOCATIONS = [
  { location: "Bandung", region: "Jawa Barat", status: "surplus" },
  { location: "Jakarta", region: "DKI Jakarta", status: "shortage" },
];

function render(overrides: Partial<Parameters<typeof TopBar>[0]> = {}) {
  return renderToStaticMarkup(
    <TopBar
      role="sppg_head"
      roleLabel="SPPG Operations Lead"
      userName="SPPG Head Demo"
      userSub="SPPG Jakarta"
      locations={LOCATIONS}
      activeLocation="Jakarta"
      onSelectLocation={() => {}}
      ownLocation="Jakarta"
      decisions={[{ status: "pending_approval" }, { status: "executed" }]}
      updatedAtLabel="Diperbarui 10.15.30"
      onOpenNotifications={() => {}}
      onLogout={() => {}}
      {...overrides}
    />
  );
}

describe("TopBar (header global acuan mockup)", () => {
  it("menampilkan brand + subjudul seperti acuan", () => {
    const html = render();
    expect(html).toContain("top-bar");
    expect(html).toContain("MealChain Guardian");
    expect(html).toContain("Cold-Chain Integrity");
  });

  it("dropdown cakupan terkunci untuk peran SPPG (cakupan tidak diperluas)", () => {
    const html = render();
    expect(html).toContain("Cakupan lokasi yang ditampilkan");
    expect(html).toContain("<select");
    expect(html).toContain("disabled");
    expect(html).toContain("Peran SPPG hanya memantau SPPG-nya sendiri");
    expect(html).toContain(">Jakarta<");
    // Opsi lokasi lain tidak ikut ditawarkan ke peran SPPG.
    expect(html).not.toContain(">Bandung<");
  });

  it("monitor nasional melihat semua lokasi + opsi per lokasi", () => {
    const html = render({ role: "bgn_monitor", ownLocation: null, activeLocation: null });
    expect(html).not.toContain("disabled");
    expect(html).toContain("Semua lokasi SPPG (2 lokasi)");
    expect(html).toContain(">Bandung<");
    expect(html).toContain(">Jakarta<");
  });

  it("lokasi pemakai belum diketahui → placeholder, bukan daftar semua lokasi", () => {
    const html = render({ ownLocation: null, activeLocation: null });
    expect(html).toContain("Lokasi belum diketahui");
    expect(html).not.toContain(">Bandung<");
  });

  it("ringkasan jaringan memakai angka nyata dari data peta", () => {
    expect(render()).toContain("1 lokasi shortage (2 terpantau)");
    expect(
      render({ locations: [{ location: "Bogor", status: "surplus" }] })
    ).toContain("Jaringan normal (1 lokasi)");
  });

  it("chip peran + identitas pemakai + waktu pembaruan tampil", () => {
    const html = render();
    expect(html).toContain("Peran: SPPG Operations Lead");
    expect(html).toContain("SPPG Head Demo");
    expect(html).toContain("SPPG Jakarta");
    expect(html).toContain("top-bar-avatar");
    expect(html).toContain("Diperbarui 10.15.30");
  });

  it("lonceng notifikasi menghitung keputusan yang menunggu tindakan", () => {
    const html = render();
    expect(html).toContain('aria-label="Notifikasi: 1 keputusan menunggu tindakan"');
    expect(html).toContain(">1<");
    // Tanpa keputusan menunggu: tanpa angka, klaim tetap jujur.
    const kosong = render({ decisions: [] });
    expect(kosong).toContain('aria-label="Notifikasi: 0 keputusan menunggu tindakan"');
    expect(kosong).not.toContain("top-bar-bell-count");
  });

  it("tombol keluar punya nama aksesibel (bukan hanya ikon)", () => {
    expect(render()).toContain('aria-label="Keluar akun"');
  });
});

describe("wiring top bar di app/page.tsx", () => {
  const pageSrc = readFileSync("app/page.tsx", "utf8");
  const apiSrc = readFileSync("lib/api.ts", "utf8");

  it("page memasang TopBar dan membungkus konten dengan .app-body", () => {
    expect(pageSrc).toMatch(/<TopBar/);
    expect(pageSrc).toContain("app-body");
  });

  it("lokasi pemakai datang dari server (GET /auth/me), bukan tebakan", () => {
    expect(pageSrc).toContain("fetchMe");
    expect(apiSrc).toContain("/auth/me");
  });

  it("peta memuat data di semua tab (top bar butuh daftar lokasi)", () => {
    // Gerbang lama: fetch peta hanya saat tab overview.
    expect(pageSrc).not.toContain('tab !== "overview"');
  });

  it("lokasi aktif dioper ke peta untuk disorot", () => {
    expect(pageSrc).toMatch(/activeLocation=\{activeLocation\}/);
  });
});
