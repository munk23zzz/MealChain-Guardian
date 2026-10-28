// Dua jalur demo (Fase 10 MG): tombol muat, panel sesi, dan analisis.
//
// Kenapa diuji begini: `request()` di lib/api.ts menembak jaringan sungguhan,
// jadi satu-satunya yang bisa dipaku tanpa server adalah BENTUK payload dan
// kontrak tampilan. Untuk panel, repo ini memakai `renderToStaticMarkup`
// (tanpa DOM/testing-library), jadi keadaan "sesi berjalan" diuji pada helper
// murni `ringkasSesi()` lalu dipastikan panel benar-benar memakainya.
//
// Yang dikunci:
// 1. SATU tombol "Muat Demo" (keputusan Roy 28 Okt 2026): pilihan replay/realtime
//    dihapus dari UI. Tombol mengirim mode=realtime + `replace: true`, karena
//    arti "muat dataset ini" adalah mengganti sesi bermode lain — termasuk sisa
//    sesi replay yang masih ada di DB.
// 2. Tidak ada lagi tombol "Muat Demo Utama"/"Muat Demo Real-time"/"Siapkan
//    data demo": konsep datanya kembali ke "dibangun saat dimuat" (jangkar =
//    waktu sekarang).
// 3. Panel menyebut mode, jangkar, dan bahwa suhu berasal dari simulasi.
// 4. Refresh membaca sesi dari server (`GET /demo/session`), bukan menebak
//    "sesi terbaru" dan bukan menyimpannya di localStorage.
// 5. OpsConsole meneruskan sesi yang dipilih ke analisis; jalur agent di panel
//    sudah membawa sesi yang sama.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DemoControlPanel from "../components/DemoControlPanel";
import {
  jangkarSesi,
  modeSesi,
  ringkasSesi,
  type StatusSesiDemo,
} from "../lib/demo-session";

const AKAR = join(__dirname, "..");

function baca(berkas: string): string {
  return readFileSync(join(AKAR, berkas), "utf8");
}

/** Badan satu fungsi `export async function <nama>` / `async function <nama>`. */
function badanFungsi(berkas: string, nama: string): string {
  const sumber = baca(berkas);
  const mulai = sumber.indexOf(`function ${nama}`);
  expect(mulai, `fungsi ${nama} tidak ditemukan di ${berkas}`).toBeGreaterThan(-1);
  // Badan berhenti di deklarasi berikutnya ATAU di komentar dokumentasi fungsi
  // berikutnya — kalau tidak, komentar fungsi tetangga ikut terbaca sebagai
  // isi fungsi ini (dan `replace: true` di komentar itu jadi positif palsu).
  const pembatas = ["\n  async function ", "\n  function ", "\n  /**"]
    .map((penanda) => sumber.indexOf(penanda, mulai + 10))
    .filter((n) => n > -1);
  const akhir = pembatas.length > 0 ? Math.min(...pembatas) : sumber.length;
  return sumber.slice(mulai, akhir);
}

function sesi(ubin: Partial<StatusSesiDemo> = {}): StatusSesiDemo {
  return {
    active: true,
    enforced: true,
    session_id: "11111111-1111-4111-8111-111111111111",
    status: "active",
    mode: "replay",
    evaluation_anchor: "2026-10-08T12:00:00+00:00",
    dataset_version: "kanon-2026-10-08T12:00:00Z",
    expires_at: "2026-10-27T10:00:00+00:00",
    anchor_now: "2026-10-27T08:00:00+00:00",
    server_now: "2026-10-27T08:00:00+00:00",
    remaining_seconds: 7200,
    ...ubin,
  };
}

function renderPanel(): string {
  return renderToStaticMarkup(
    <DemoControlPanel token={"t"} role={"sppg_head"} locationName={"Jakarta"} />
  );
}

// --- butir 1: satu tombol, satu payload -------------------------------------

describe("satu tombol muat demo", () => {
  it("hanya menampilkan Muat Demo, tanpa tombol mode terpisah", () => {
    const html = renderPanel();
    expect(html).toContain("Muat Demo");
    // Tombol replay & realtime yang terpisah sudah dihapus dari UI.
    expect(html).not.toContain("Muat Demo Utama");
    expect(html).not.toContain("Muat Demo Real-time");
    expect(html).not.toContain("Siapkan data demo");
  });

  it("mengirim mode=realtime + replace dari satu handler", () => {
    const sumber = baca("components/DemoControlPanel.tsx");
    // Helper dua-mode lama tidak boleh kembali diam-diam.
    expect(sumber).not.toMatch(/muatMode\(/);
    const badan = badanFungsi("components/DemoControlPanel.tsx", "onMuatDemo");
    expect(badan).toContain("startDemoSession(");
    expect(badan).toMatch(/mode:\s*"realtime"/);
    // Sesi bermode lain (sisa replay) harus diganti, bukan diteruskan.
    expect(badan).toMatch(/replace:\s*true/);
  });

  it("tanpa jendela sesi, memakai POST /demo/refresh untuk hari ini", () => {
    const badan = badanFungsi("components/DemoControlPanel.tsx", "onMuatDemo");
    expect(badan).toContain("refreshDemoToToday(");
    expect(badan).toMatch(/!\s*sesi\?\.enforced/);
  });
});

// --- butir 2 & 3: panel sesi + refresh -------------------------------------

describe("panel sesi aktif", () => {
  it("meringkas mode, jangkar, dan label simulasi dari sesi", () => {
    const replay = ringkasSesi(sesi());
    expect(replay.mode).toBe("replay");
    expect(replay.anchor).toBe("8 Okt 2026 12:00 UTC");
    expect(replay.simulasi).toBe(true);

    const realtime = ringkasSesi(
      sesi({ mode: "realtime", evaluation_anchor: "2026-10-27T08:15:00+00:00" })
    );
    expect(realtime.mode).toBe("realtime");
    expect(realtime.anchor).not.toBe(replay.anchor);
  });

  it("menampilkan jumlah kasus sesi dari server, tanpa mengarang saat kosong", () => {
    const denganKasus = ringkasSesi(sesi({ cases: 7 }));
    expect(denganKasus.kasus).toBe(7);
    expect(denganKasus.baris).toContain("7 kasus");
    expect(denganKasus.baris).toContain("suhu simulasi");

    // Sesi pra-Fase 7 / belum dihitung: "0 kasus" adalah kebohongan.
    const tanpa = ringkasSesi(sesi());
    expect(tanpa.kasus).toBeNull();
    expect(tanpa.baris).not.toContain("kasus");

    // Panel merender baris ringkasan apa adanya (satu sumber format).
    const sumber = baca("components/DemoControlPanel.tsx");
    expect(sumber).toContain("ringkasan.baris");
  });

  it("tidak mengarang sesi saat tidak ada sesi aktif", () => {
    const kosong = ringkasSesi(null);
    expect(kosong.mode).toBeNull();
    expect(kosong.anchor).toBeNull();
    expect(kosong.simulasi).toBe(false);
    expect(kosong.baris).toBeNull();
  });

  it("panel memakai helper yang sama, bukan format sendiri", () => {
    const sumber = baca("components/DemoControlPanel.tsx");
    expect(sumber).toContain("ringkasSesi(");
    // Label "suhu simulasi" dimiliki helper (`ringkasSesi`), bukan panel:
    // panel merender `ringkasan.baris` apa adanya. Dulu panel juga menulis
    // labelnya sendiri, dan hasilnya muncul dua kali di layar.
    expect(sumber).toContain("ringkasan.baris");
    expect(sumber).not.toContain("suhu simulasi");
    expect(baca("lib/demo-session.ts")).toContain("suhu simulasi");
  });

  it("membaca sesi dari server, tanpa sesi terbaru yang dikarang", () => {
    const api = baca("lib/api.ts");
    expect(api).toContain('request("/demo/session"');
    expect(api).not.toContain("fetchLatestDemoSession");

    const hook = baca("lib/hooks/useDemoSessionId.ts");
    expect(hook).toContain("session_id");
    // Komentar hook menyebut localStorage sebagai hal yang sengaja TIDAK
    // dipakai; yang dilarang adalah PEMAKAIANNYA.
    expect(hook).not.toMatch(/localStorage\.(get|set)Item/);
  });
});

// --- butir 3: analisis membawa sesi yang dipilih ---------------------------

describe("analisis membawa sesi", () => {
  it("OpsConsole meneruskan demoSession ke /balance/analyze", () => {
    const sumber = baca("components/OpsConsole.tsx");
    expect(sumber).toContain("demoSessionId");
    const badan = badanFungsi("components/OpsConsole.tsx", "runAgent");
    expect(badan).toMatch(/runAnalysis\(token,\s*commodity,\s*demoSessionId\)/);
  });

  it("tombol agent di panel membawa sesi aktif", () => {
    const badan = badanFungsi("components/DemoControlPanel.tsx", "onJalankan");
    expect(badan).toContain("runDemoAgent(");
    // Id sesi yang dikirim adalah `sesiId` hasil adopsi/penbukaan, bukan lagi
    // ekspresi langsung `sesi?.session_id` (28 Okt 2026).
    expect(badan).toMatch(/demoSession:\s*sesiId/);
  });

  it("menekan Jalankan agent tidak membangun ulang data bila server punya sesi", () => {
    // Gejala demo 28 Okt 2026: jam demo "restart" sesudah Jalankan agent.
    // Sebabnya panel membuka sesi baru (yang MEMBANGUN template + jangkar=now)
    // padahal server masih punya sesi aktif. Kontraknya: baca /demo/session
    // lebih dulu dan pakai id-nya.
    const badan = badanFungsi("components/DemoControlPanel.tsx", "onJalankan");
    const adopsi = badan.indexOf("fetchDemoSession(");
    const buka = badan.indexOf("startDemoSession(");
    expect(adopsi).toBeGreaterThan(-1);
    expect(buka).toBeGreaterThan(-1);
    expect(adopsi).toBeLessThan(buka);
    expect(badan).toContain("sesiId = aktif.session_id");
  });

  it("mode dan jangkar tidak ditebak dari data terbaru", () => {
    // `modeSesi` mengembalikan null untuk sesi pra-Fase 2 — panel tidak boleh
    // menganggapnya replay.
    expect(modeSesi(sesi({ mode: null }))).toBeNull();
    expect(jangkarSesi(sesi({ evaluation_anchor: null }))).toBeNull();
  });
});

// --- butir 2: KPI memakai sesi yang dipakai panel ---------------------------

describe("KPI membawa sesi eksplisit", () => {
  it("fetchKpis mengirim include_demo dan demo_session_id sesi yang dipilih", async () => {
    const { fetchKpis } = await import("../lib/api");
    const jejak: string[] = [];
    vi.stubGlobal("fetch", async (url: string) => {
      jejak.push(String(url));
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ metrics: [] }),
      } as unknown as Response;
    });
    try {
      await fetchKpis("today", "token-uji", undefined, {
        includeDemo: true,
        demoSessionId: "sesi-baru",
      });
    } finally {
      vi.unstubAllGlobals();
    }
    // `request()` memakai path relatif (base URL dari env), jadi URL di sini
    // juga relatif: beri basis fiktif supaya `searchParams` bisa dibaca.
    const url = new URL(jejak[0], "http://localhost");
    expect(url.searchParams.get("include_demo")).toBe("true");
    // ID diambil dari argumen pada SETIAP panggilan: sesi baru = ID baru,
    // bukan ID yang tertinggal dari klik sebelumnya.
    expect(url.searchParams.get("demo_session_id")).toBe("sesi-baru");
  });

  it("hook KPI memasukkan id sesi ke kunci query dan ke permintaan", () => {
    const hook = baca("lib/hooks/useKpi.ts");
    expect(hook).toContain('simulasi ? demoSessionId ?? "" : ""');
    expect(hook).toContain("demoSessionId: demoSessionId ?? undefined");
    const halaman = baca("app/page.tsx");
    expect(halaman).toContain("demoSession.sessionId");
    // Sesi baru dari server (polling hook sesi) mengubah kunci → permintaan
    // berikutnya memakai ID baru, bukan menyajikan angka sesi lama.
    const hookSesi = baca("lib/hooks/useDemoSessionId.ts");
    expect(hookSesi).toContain("refetchInterval");
  });
});
