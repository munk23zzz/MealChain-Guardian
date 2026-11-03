import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it, vi } from "vitest";

import {
  AKUN_DEMO_CADANGAN,
  kelompokkanAkun,
  muatAkunDemo,
  passwordDemoUntuk,
  sandiDemoTersedia,
} from "../lib/demo-accounts";

const akar = join(__dirname, "..");

// Kontrak 27 Okt 2026: halaman login publik TIDAK boleh memanggil
// `GET /auth/demo-accounts` (endpoint itu menuntut Bearer token `bgn_monitor`
// dan akan menjawab 401 bagi pengunjung). Sandi diambil dari pintu khusus
// `GET /auth/demo-login`, yang hanya terbuka bila DEMO_MODE + DEMO_LOGIN_AUTOFILL
// aktif. Kata sandi tetap tidak boleh ditanam di bundel klien.
const POLA_ENDPOINT_ADMIN = /request\(\s*["'`]\/auth\/demo-accounts/;
const POLA_ENDPOINT_LOGIN = /request\(\s*["'`]\/auth\/demo-login/;

function baca(relatif: string): string {
  return readFileSync(join(akar, relatif), "utf8");
}

describe("akun demo di layar login", () => {
  it("tidak pernah memuat sandi di bundel klien", () => {
    expect(AKUN_DEMO_CADANGAN).toHaveLength(7); // 3 peran utama + 4 approver kota
    for (const akun of AKUN_DEMO_CADANGAN) {
      expect(akun).not.toHaveProperty("password");
      expect(akun.email.endsWith("@demo.local")).toBe(true);
      expect(akun.label.length).toBeGreaterThan(0);
      expect(["sppg_head", "sppg_nutritionist", "bgn_monitor"]).toContain(akun.role);
    }
  });

  it("halaman login publik tidak memanggil endpoint admin, tetapi memakai pintu demo-login", () => {
    for (const berkas of ["lib/demo-accounts.ts", "app/page.tsx"]) {
      expect(baca(berkas), `${berkas} masih memanggil /auth/demo-accounts`).not.toMatch(
        POLA_ENDPOINT_ADMIN,
      );
    }
    expect(baca("lib/demo-accounts.ts")).toMatch(POLA_ENDPOINT_LOGIN);
  });

  it("mengisi sandi hanya bila server mengizinkannya (enabled:true)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(
        JSON.stringify({
          enabled: true,
          accounts: [
            { label: "SPPG Head", email: "sppg.head@demo.local", role: "sppg_head", grup: "utama", password: "sandi-demo" },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      )),
    );

    const akun = await muatAkunDemo();

    expect(akun).toHaveLength(1);
    expect(akun[0].password).toBe("sandi-demo");
    vi.unstubAllGlobals();
  });

  it("tidak mengarang sandi saat server mematikan autofill atau gagal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ enabled: false, accounts: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })),
    );

    const akun = await muatAkunDemo();

    expect(akun).toEqual(AKUN_DEMO_CADANGAN);
    expect(akun.every((a) => a.password === undefined)).toBe(true);

    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("jaringan mati");
    }));
    const akunGagal = await muatAkunDemo();
    expect(akunGagal.every((a) => a.password === undefined)).toBe(true);
    vi.unstubAllGlobals();
  });

  it("menyediakan akun untuk tiap peran yang dipakai demo", () => {
    const email = AKUN_DEMO_CADANGAN.map((a) => a.email);
    expect(email).toContain("sppg.head@demo.local");
    expect(email).toContain("sppg.nutritionist@demo.local");
    expect(email).toContain("bgn.monitor@demo.local");
    expect(email).toContain("sppg.head.bandung@demo.local");
    expect(email).toContain("sppg.nutritionist.surabaya@demo.local");
  });

  it("memisahkan tombol utama dan approver kota", () => {
    const { utama, kota } = kelompokkanAkun([
      { label: "A", email: "a@demo.local", role: "sppg_head", grup: "utama" },
      { label: "B", email: "b@demo.local", role: "sppg_head", grup: "kota" },
      { label: "C", email: "c@demo.local", role: "bgn_monitor" },
    ]);

    expect(utama.map((a) => a.label)).toEqual(["A", "C"]);
    expect(kota.map((a) => a.label)).toEqual(["B"]);
  });
});

// 29 Okt 2026 — dua kali login demo gagal karena tombol demo ditekan SEBELUM
// `GET /auth/demo-login` menjawab: kolom sandi kosong, "Masuk" 401/500, dan
// pembaca menyimpulkan aplikasinya rusak. Dua helper ini yang membuat layar
// login bisa (a) mengisi sandi susulan dan (b) berterus terang bila server
// memang tidak mengirim sandi.
describe("sandi demo: susulan dan kejujuran", () => {
  it("mengisi sandi begitu daftar bersandi tiba", () => {
    const berSandi = AKUN_DEMO_CADANGAN.map((akun) =>
      akun.email === "sppg.head@demo.local" ? { ...akun, password: "rahasia-demo" } : akun,
    );

    expect(passwordDemoUntuk(AKUN_DEMO_CADANGAN, "sppg.head@demo.local")).toBeNull();
    expect(passwordDemoUntuk(berSandi, "sppg.head@demo.local")).toBe("rahasia-demo");
    // Email yang tidak ada di daftar tidak menghasilkan sandi karangan.
    expect(passwordDemoUntuk(berSandi, "orang@luar.local")).toBeNull();
  });

  it("tahu kapan server tidak mengirim sandi sama sekali", () => {
    expect(sandiDemoTersedia(AKUN_DEMO_CADANGAN)).toBe(false);
    expect(sandiDemoTersedia([])).toBe(false);
    expect(
      sandiDemoTersedia([
        { label: "A", email: "a@demo.local", role: "sppg_head", password: "x" },
      ]),
    ).toBe(true);
  });
});
