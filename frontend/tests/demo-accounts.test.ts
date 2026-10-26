import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AKUN_DEMO_CADANGAN,
  kelompokkanAkun,
  muatAkunDemo,
} from "../lib/demo-accounts";

function balas(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("akun demo di layar login", () => {
  it("mengisi email DAN sandi saat DEMO_MODE aktif", async () => {
    balas({
      enabled: true,
      accounts: [
        { label: "SPPG Head", email: "sppg.head@demo.local", role: "sppg_head", grup: "utama", password: "rahasia-demo" },
      ],
    });

    const akun = await muatAkunDemo();

    expect(akun).toHaveLength(1);
    expect(akun[0].password).toBe("rahasia-demo");
    expect(akun[0].email).toBe("sppg.head@demo.local");
  });

  it("tidak menebak sandi saat endpoint mematikan mode demo", async () => {
    balas({ enabled: false, accounts: [] });

    const akun = await muatAkunDemo();

    expect(akun).toEqual(AKUN_DEMO_CADANGAN);
    expect(akun.every((a) => a.password === undefined)).toBe(true);
  });

  it("tetap memberi daftar saat backend gagal (jaringan/500)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("network down");
    }));

    const akun = await muatAkunDemo();

    expect(akun.length).toBeGreaterThan(0);
    expect(akun.every((a) => a.password === undefined)).toBe(true);
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
