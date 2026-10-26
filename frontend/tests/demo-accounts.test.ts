import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  AKUN_DEMO_CADANGAN,
  kelompokkanAkun,
} from "../lib/demo-accounts";

const akar = join(__dirname, "..");

// Kontrak 26 Okt 2026: `GET /auth/demo-accounts` menuntut Bearer token
// ber-peran admin (`bgn_monitor`; skema tidak punya peran `admin`). Halaman
// login bersifat publik, jadi ia TIDAK boleh memanggil endpoint itu — kalau
// dipanggil, jawabannya 401 dan pengunjung melihat pesan error sebelum masuk.
// Daftar akun cukup datang dari konstanta tanpa sandi.
const POLA_PANGGILAN = /request\(\s*["'`]\/auth\/demo-accounts/;

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

  it("halaman login publik tidak memanggil endpoint akun demo", () => {
    for (const berkas of ["lib/demo-accounts.ts", "app/page.tsx"]) {
      expect(baca(berkas), `${berkas} masih memanggil /auth/demo-accounts`).not.toMatch(
        POLA_PANGGILAN,
      );
    }
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
