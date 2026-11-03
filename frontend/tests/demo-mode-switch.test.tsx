// Kontrak mode + jangkar sesi demo (Fase 2 MG) — diuji tanpa DOM.
//
// Yang dikunci:
// 1. `seedDemo` mengirim `mode` EKSPLISIT di body (bukan hanya mengubah teks
//    tombol). Tanpa mode, backend memakai mode sesi — jadi klien boleh
//    menghilangkannya, tapi tidak boleh mengarang nilai lain.
// 2. `modeSesi`/`jangkarSesi` membaca sifat SESI apa adanya; sesi pra-Fase 2
//    (tanpa mode) tidak boleh ditebak menjadi `replay`.
// 3. `labelModeSesi` memberi label yang membedakan dua dataset.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { labelModeSesi } from "../lib/api";
import { jangkarSesi, modeSesi, type StatusSesiDemo } from "../lib/demo-session";

function sesi(ubin: Partial<StatusSesiDemo> = {}): StatusSesiDemo {
  return {
    active: true,
    enforced: true,
    session_id: "11111111-1111-4111-8111-111111111111",
    status: "active",
    expires_at: "2026-10-27T10:00:00+00:00",
    anchor_now: "2026-10-27T08:00:00+00:00",
    server_now: "2026-10-27T08:00:00+00:00",
    remaining_seconds: 7200,
    ...ubin,
  };
}

describe("mode sesi", () => {
  it("membaca mode apa adanya untuk replay dan realtime", () => {
    expect(modeSesi(sesi({ mode: "replay" }))).toBe("replay");
    expect(modeSesi(sesi({ mode: "realtime" }))).toBe("realtime");
  });

  it("tidak menebak mode untuk sesi lama atau sesi kosong", () => {
    // Sesi pra-Fase 2 tidak punya kolom mode: menebaknya jadi `replay` akan
    // membuat panel menjanjikan dataset kanon untuk sesi yang bukan kanon.
    expect(modeSesi(sesi())).toBeNull();
    expect(modeSesi(sesi({ mode: null }))).toBeNull();
    expect(modeSesi(null)).toBeNull();
  });

  it("memberi label berbeda untuk dua mode", () => {
    expect(labelModeSesi("replay")).toMatch(/replay/i);
    expect(labelModeSesi("realtime")).toMatch(/realtime/i);
    expect(labelModeSesi("replay")).toMatch(/8 Okt 2026/);
    expect(labelModeSesi(null)).toMatch(/belum ditentukan/i);
  });
});

describe("jangkar evaluasi sesi", () => {
  it("menampilkan jangkar kanon replay apa adanya", () => {
    // Jangkar kanon 2026-10-08T12:00:00Z — angka ini TIDAK boleh bergeser.
    expect(
      jangkarSesi(sesi({ mode: "replay", evaluation_anchor: "2026-10-08T12:00:00+00:00" }))
    ).toBe("8 Okt 2026 12:00 UTC");
  });

  it("membedakan jangkar realtime dari jangkar kanon", () => {
    const realtime = jangkarSesi(
      sesi({ mode: "realtime", evaluation_anchor: "2026-10-27T08:15:00+00:00" })
    );
    expect(realtime).toBe("27 Okt 2026 08:15 UTC");
    expect(realtime).not.toBe("8 Okt 2026 12:00 UTC");
  });

  it("mengembalikan null saat jangkar tidak ada atau rusak", () => {
    expect(jangkarSesi(sesi())).toBeNull();
    expect(jangkarSesi(sesi({ evaluation_anchor: null }))).toBeNull();
    expect(jangkarSesi(sesi({ evaluation_anchor: "bukan-tanggal" }))).toBeNull();
    expect(jangkarSesi(null)).toBeNull();
  });
});

describe("runDemoAgent meneruskan sesi", () => {
  const sumber = readFileSync(join(__dirname, "..", "lib", "api.ts"), "utf8");

  function badanFungsi(nama: string): string {
    const awal = sumber.indexOf(`export async function ${nama}`);
    expect(awal).toBeGreaterThan(-1);
    return sumber.slice(awal, sumber.indexOf("export async function", awal + 10));
  }

  it("menyertakan demo_session di body", () => {
    // Tanpa ini backend menstempel keputusan dari "sesi aktif", dan analisis
    // yang dijalankan atas sesi tertentu bisa mendarat di sesi lain.
    const badan = badanFungsi("runDemoAgent");
    expect(badan).toContain("payload.demo_session = demoSession");
    expect(badan).toContain('request("/demo/agent/run"');
  });

  it("membiarkan sesi kosong tidak dikirim", () => {
    // Field kosong bukan nilai sah: `demo_session=undefined` akan diserialkan
    // hilang, tetapi `null` akan ditolak kontrak UUID di server.
    const badan = badanFungsi("runDemoAgent");
    expect(badan).not.toMatch(/payload\.demo_session\s*=\s*null/);
  });

  it("menyertakan mode di body", () => {
    // Fase 2 MG butir 8: analisis membawa modenya sendiri. Tanpa ini server
    // hanya tahu sesi, dan klien yang mengira realtime bisa menulis ke sesi
    // replay tanpa ada yang menolak.
    const badan = badanFungsi("runDemoAgent");
    expect(badan).toContain("payload.mode = mode");
    expect(badan).toMatch(/mode\?: DemoSessionMode/);
  });
});

describe("startDemoSession meneruskan mode", () => {
  const sumber = readFileSync(join(__dirname, "..", "lib", "api.ts"), "utf8");

  it("mengirim mode eksplisit pada POST /demo/session/start", () => {
    const awal = sumber.indexOf("export async function startDemoSession");
    expect(awal).toBeGreaterThan(-1);
    const badan = sumber.slice(awal, sumber.indexOf("export async function", awal + 10));
    expect(badan).toContain("payload.mode = opsi.mode");
    expect(badan).toMatch(/"replay"\s*\|\s*"realtime"/);
    expect(badan).toContain('request("/demo/session/start"');
  });
});

describe("seedDemo meneruskan mode", () => {
  // Sumber dibaca sebagai teks: `request()` menembak jaringan sungguhan, jadi
  // yang bisa diuji di unit test adalah BENTUK payload yang dikirim. Yang mahal
  // bila salah bukan kompilasinya, melainkan klien yang diam-diam berhenti
  // mengirim mode sehingga sesi kedua selalu jatuh ke mode sesi pertama.
  const sumber = readFileSync(join(__dirname, "..", "lib", "api.ts"), "utf8");

  it("menyertakan mode dan demo_session di body", () => {
    const awal = sumber.indexOf("export async function seedDemo");
    expect(awal).toBeGreaterThan(-1);
    const badan = sumber.slice(awal, sumber.indexOf("export async function", awal + 10));
    expect(badan).toContain("payload.mode = opsi.mode");
    expect(badan).toContain("payload.demo_session = opsi.demoSession");
    expect(badan).toContain('request("/demo/seed"');
    // Mode harus dikirim sebagai nilai, bukan disimpulkan dari `force`.
    expect(badan).not.toMatch(/payload\.mode\s*=\s*(true|false)/);
  });

  it("membatasi mode pada nilai kontrak", () => {
    const awal = sumber.indexOf("export async function seedDemo");
    const badan = sumber.slice(awal, sumber.indexOf("export async function", awal + 10));
    expect(badan).toMatch(/"replay"\s*\|\s*"realtime"/);
  });
});
