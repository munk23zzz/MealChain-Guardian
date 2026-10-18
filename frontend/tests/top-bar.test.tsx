// Top bar — kontrak render (pola repo ini: renderToStaticMarkup, tanpa DOM).
//
// Kontrak BARU (refactor header 2026-10-11): header global hanya memuat
// peran + lokasi SPPG + jam + lonceng notifikasi. Brand "MealChain Guardian",
// tombol keluar, dan aksi lain PINDAH ke rail sidebar (dipin di blok wiring di
// bawah) supaya pemindahan itu tidak menghilangkan unsurnya tanpa jejak.
//
// Yang dijaga berkas ini: (1) setiap unsur yang tampil berasal dari data yang
// dioper, bukan dikarang; (2) aturan peran untuk cakupan lokasi tetap hidup di
// lib/topbar.ts (`scopeModel`) dan diuji di tests/topbar-lib.test.ts — lihat
// catatan di uji terakhir soal kontrol UInya yang belum dipasang kembali.
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
      onOpenNotifications={() => {}}
      onLogout={() => {}}
      {...overrides}
    />
  );
}

describe("TopBar (header global)", () => {
  it("menampilkan peran + lokasi SPPG apa adanya dari props", () => {
    const html = render();
    expect(html).toContain("top-bar");
    expect(html).toContain("top-bar-role");
    expect(html).toContain("SPPG Operations Lead");
    // Lokasi diwakili pemilih cakupan; <span class="top-bar-sppg"> dihapus
    // supaya tidak tampil dua kali.
    expect(html).not.toContain("top-bar-sppg");
    expect(html).not.toContain("SPPG Jakarta");
    expect(html).toContain(">Jakarta<");
  });

  it("tanpa lokasi: tidak ada teks karangan, pemilih cakupan menampilkan placeholder", () => {
    const html = render({ userSub: null, ownLocation: null, activeLocation: null });
    expect(html).not.toContain("top-bar-sppg");
    expect(html).toContain("Lokasi belum diketahui");
  });

  it("jam hanya dirender di klien (SSR tanpa jam supaya tidak hidrasi mismatch)", () => {
    // renderToStaticMarkup = sisi server: span jam TIDAK boleh ada di markup awal.
    expect(render()).not.toContain("top-bar-clock");
    // Sisi kliennya ada di sumber: useEffect + interval 1 detik (detik berjalan)
    // + label aksesibel dari formatJam (waktu Indonesia, bukan zona mesin).
    const src = readFileSync("components/TopBar.tsx", "utf8");
    expect(src).toContain("top-bar-clock");
    expect(src).toContain("formatJam");
    expect(src).toContain("setInterval(tick, 1000)");
    expect(src).not.toContain("setInterval(tick, 30000)");
  });

  it("lonceng notifikasi menghitung keputusan yang menunggu tindakan", () => {
    const html = render();
    expect(html).toContain('aria-label="Notifikasi: 1 keputusan menunggu tindakan"');
    expect(html).toContain("top-bar-bell-count");
    expect(html).toContain(">1<");
    // Tanpa keputusan menunggu: tanpa angka, klaim tetap jujur.
    const kosong = render({ decisions: [] });
    expect(kosong).toContain('aria-label="Notifikasi: 0 keputusan menunggu tindakan"');
    expect(kosong).not.toContain("top-bar-bell-count");
  });

  it("lonceng membuka POPUP, bukan langsung pindah tab", () => {
    // Saat tertutup: panel tidak dirender, tetapi tombol mengumumkan bahwa ia
    // membuka dialog (aria-haspopup/aria-expanded) supaya perilakunya terduga.
    const html = render();
    // Panelnya sendiri tidak dirender saat tertutup (id-nya muncul hanya di
    // aria-controls, jadi yang diperiksa elemen panelnya).
    expect(html).not.toContain('class="top-bar-notif-panel"');
    expect(html).not.toContain('role="dialog"');
    expect(html).toContain('aria-haspopup="dialog"');
    expect(html).toContain('aria-expanded="false"');
    // aria-controls hanya dipasang saat panel ADA di DOM. Menunjuk id yang belum
    // dirender membuat axe melaporkan "aria-valid-attr-value" (atribut menunjuk
    // elemen tak dikenal) — jadi saat tertutup atribut itu memang tidak ada.
    expect(html).not.toContain('aria-controls="top-bar-notif-panel"');
    // Isi popup diambil dari logika murni lib/topbar.ts, bukan dihitung ulang
    // di komponen, dan tombolnya TIDAK memanggil onOpenNotifications langsung.
    const src = readFileSync("components/TopBar.tsx", "utf8");
    expect(src).toContain('aria-controls={notifOpen ? "top-bar-notif-panel" : undefined}');
    expect(src).toContain("notifList");
    expect(src).toContain('role="dialog"');
    expect(src).toContain("Escape");
    expect(src).toContain("setNotifOpen");
    expect(src).not.toContain("onClick={onOpenNotifications}");
  });

  it("brand + tombol keluar tidak lagi di header (pindah ke rail sidebar)", () => {
    const html = render();
    expect(html).not.toContain("MealChain Guardian");
    expect(html).not.toContain("Keluar akun");
  });

  it("pemilih cakupan lokasi ADA di header (dipulihkan 11 Okt)", () => {
    const html = render();
    expect(html).toContain("top-bar-scope");
    expect(html).toContain("Cakupan lokasi yang ditampilkan");
    expect(html).toContain("top-bar-select");
    expect(html).toContain("<select");
  });

  it("dropdown cakupan terkunci untuk peran SPPG (cakupan tidak diperluas)", () => {
    const html = render();
    expect(html).toContain("disabled");
    expect(html).toContain("Peran SPPG hanya memantau SPPG-nya sendiri");
    expect(html).toContain(">Jakarta<");
    // Opsi lokasi lain tidak ditawarkan ke peran SPPG.
    expect(html).not.toContain(">Bandung<");
    // Satu opsi saja → tanpa panah dropdown (bukan pilihan).
    expect(html).toContain("top-bar-select-locked");
  });

  it("monitor nasional melihat semua lokasi + opsi per lokasi", () => {
    const html = render({ role: "bgn_monitor", ownLocation: null, activeLocation: null });
    expect(html).not.toContain("disabled");
    expect(html).not.toContain("top-bar-select-locked"); // ada pilihan → panah tetap
    expect(html).toContain("Semua lokasi SPPG (2 lokasi)");
    expect(html).toContain(">Bandung<");
    expect(html).toContain(">Jakarta<");
  });

  it("lokasi pemakai belum diketahui → placeholder, bukan daftar semua lokasi", () => {
    const html = render({ ownLocation: null, activeLocation: null });
    expect(html).toContain("Lokasi belum diketahui");
    expect(html).not.toContain(">Bandung<");
  });

  it("pemilih cakupan TIDAK disembunyikan CSS (jebakan 11 Okt)", () => {
    const css = readFileSync("app/globals.css", "utf8");
    expect(css).not.toContain(".top-bar-scope { display: none; }");
    expect(css).not.toContain(".top-bar-select { display: none; }");
    // Varian terkunci wajib mematikan panah dropdown.
    expect(css).toContain(".top-bar-select-locked");
    // Panah hilang = `appearance: none` di dalam blok aturan yang sama
    // (regex dibatasi ke satu blok `{...}` supaya tidak bergantung jarak).
    expect(css).toMatch(/\.top-bar-select-locked[^{]*\{[^}]*appearance: none;/);
  });
});

describe("wiring header & rail di app/page.tsx", () => {
  const pageSrc = readFileSync("app/page.tsx", "utf8");
  const apiSrc = readFileSync("lib/api.ts", "utf8");

  it("page memasang TopBar dan membungkus konten dengan .app-body", () => {
    expect(pageSrc).toMatch(/<TopBar/);
    expect(pageSrc).toContain("app-body");
  });

  it("lokasi pemakai datang dari server (GET /auth/me), bukan tebakan", () => {
    const meHook = readFileSync("lib/hooks/useMe.ts", "utf8");
    expect(pageSrc).toContain("useMe");
    expect(meHook).toContain("fetchMe");
    expect(apiSrc).toContain("/auth/me");
  });

  it("peta memuat data di semua tab (header butuh daftar lokasi)", () => {
    // Gerbang lama: fetch peta hanya saat tab overview.
    expect(pageSrc).not.toContain('tab !== "overview"');
  });

  it("lokasi aktif dioper ke peta untuk disorot", () => {
    expect(pageSrc).toMatch(/activeLocation=\{activeLocation\}/);
  });

  it("TopBar tetap menerima daftar lokasi & penangan pilih lokasi", () => {
    expect(pageSrc).toMatch(/onSelectLocation=\{/);
    expect(pageSrc).toMatch(/locations=\{[^}]*\}/);
  });

  it("brand + tombol keluar ada di rail sidebar (dipindah, bukan dihapus)", () => {
    // Rail memakai template literal di className, jadi patokannya unsur di dalamnya.
    const rail = pageSrc.slice(pageSrc.indexOf("side-brand"), pageSrc.indexOf("</aside>"));
    expect(rail).toContain("MealChain Guardian");
    expect(rail).toContain('aria-label="Keluar"');
    // Dulu di sini diperiksa literal "side-tab" karena nav-nya ditulis inline di
    // halaman ini. WS-D memindahkan nav ke components/SideNav.tsx (supaya bisa
    // diuji sebagai komponen) — jadi yang diperiksa sekarang: rail memang
    // merender SideNav. Isi tab & aria-current-nya diuji di tests/side-nav.test.tsx.
    expect(rail).toContain("<SideNav");
  });

  it("aturan cakupan lokasi masih dijaga logika murninya (lib/topbar.ts)", () => {
    const topbarSrc = readFileSync("lib/topbar.ts", "utf8");
    expect(topbarSrc).toContain("export function scopeModel");
    expect(topbarSrc).toContain("Semua lokasi SPPG");
    // Komponen TopBar memakai scopeModel (bukan logika tulis-sendiri).
    const topBarSrc = readFileSync("components/TopBar.tsx", "utf8");
    expect(topBarSrc).toContain("<select");
    expect(topBarSrc).toContain("scopeModel");
    // CATATAN (11 Okt): setelah refactor header, KONTROL pemilih cakupan belum
    // dipasang kembali di UI mana pun — scopeModel masih ada dan teruji, tetapi
    // belum dipakai komponen. Bila kontrolnya dipasang kembali (header atau
    // rail), tambahkan uji render-nya di sini.
  });
});
