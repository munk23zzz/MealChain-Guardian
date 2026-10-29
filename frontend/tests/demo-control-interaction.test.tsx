// @vitest-environment jsdom
//
// Bukti interaksi Demo Control (butir 1, 2, 3).
//
// Kenapa berkas ini ada padahal `realtime-demo-control.test.tsx` sudah menguji
// bentuk payload: berkas itu membaca SUMBER. Yang tidak bisa dibuktikan dengan
// membaca sumber adalah hal yang justru dijanjikan rencana —
//
//   - klik "Muat Demo" benar-benar mengirim payload yang benar (bukan mengganti
//     label saja), dan tidak ada lagi tombol mode terpisah di layar,
//   - SESI hasil balasan server BENAR-BENAR masuk state (dan dipakai analisis
//     berikutnya),
//   - refresh membaca sesi dari server (mode + jangkar yang sama), lalu sesi
//     BARU dibaca sebagai sesi baru — tidak ada id yang dikarang,
//   - status kesiapan kasus + alasan hold tampil, berasal dari
//     `/decisions/{id}/approval-summary` (server), bukan aturan kedua di klien.
//
// Lingkungan: jsdom + React 18 `createRoot`. `fetch` diganti rute palsu yang
// MEREKAM setiap permintaan, jadi asersi pertama adalah permintaan HTTP-nya,
// baru layarnya.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import DemoControlPanel from "../components/DemoControlPanel";

// Harness React 18: tanpa penanda ini, pembaruan state dari klik tombol
// dijadwalkan di luar `act` sehingga asersi berjalan sebelum handler.
(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

const SID_LAMA = "11111111-1111-4111-8111-111111111111";
const SID_BARU = "22222222-2222-4222-8222-222222222222";
const ANCHOR_REPLAY = "2026-10-08T12:00:00+00:00";
const ANCHOR_REALTIME = "2026-10-27T08:15:00+00:00";

type Panggilan = { metode: string; jalur: string; badan: any };

function jawab(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

function sesi(ubin: Record<string, unknown> = {}) {
  return {
    active: true,
    enforced: true,
    session_id: SID_LAMA,
    status: "active",
    mode: "replay",
    evaluation_anchor: ANCHOR_REPLAY,
    dataset_version: "kanon-2026-10-08T12:00:00Z",
    expires_at: "2026-10-27T10:00:00+00:00",
    anchor_now: "2026-10-27T08:00:00+00:00",
    server_now: "2026-10-27T08:00:00+00:00",
    remaining_seconds: 7200,
    ...ubin,
  };
}

const STATUS_DATA = {
  tables: {
    supply_records: { seed: 10, demo: 5, demo_from: "2026-10-01", demo_to: "2026-10-08" },
    price_signals: { seed: 4, demo: 2 },
    menu_plans: { seed: 2, demo: 2, demo_from: "2026-10-01", demo_to: "2026-10-08" },
  },
};

/** Rute palsu: jalur → (panggilan) => body. */
function pasangFetch(rute: Record<string, (p: Panggilan) => unknown>) {
  const panggilan: Panggilan[] = [];
  const palsu = vi.fn(async (url: string, init?: RequestInit) => {
    // `jalur` disimpan UTUH (termasuk query) supaya asersi bisa memeriksa
    // parameter; routing memakai pathname-nya.
    const jalur = String(url).replace(/^https?:\/\/[^/]+/, "");
    const pathname = jalur.split("?")[0];
    const metode = (init?.method ?? "GET").toUpperCase();
    const badan = init?.body ? JSON.parse(String(init.body)) : null;
    const rekam = { metode, jalur, badan };
    panggilan.push(rekam);
    const kunci = `${metode} ${pathname}`;
    const penangan = rute[kunci] ?? rute[pathname];
    if (!penangan) return jawab({ detail: `tidak ada rute ${kunci}` }, 404);
    return jawab(penangan(rekam));
  });
  vi.stubGlobal("fetch", palsu);
  return panggilan;
}

let root: Root | null = null;

async function pasangPanel() {
  const wadah = document.createElement("div");
  document.body.appendChild(wadah);
  root = createRoot(wadah);
  await act(async () => {
    root!.render(<DemoControlPanel token="token-uji" role="sppg_head" locationName="Jakarta" />);
  });
  // Beri kesempatan seluruh efek awal (4 fetch) selesai.
  await act(async () => {
    await Promise.resolve();
  });
  return wadah;
}

async function bongkar() {
  if (!root) return;
  await act(async () => {
    root!.unmount();
  });
  root = null;
  document.body.innerHTML = "";
}

function teks(wadah: HTMLElement): string {
  return wadah.textContent ?? "";
}

async function klik(wadah: HTMLElement, label: string) {
  const tombol = Array.from(wadah.querySelectorAll("button")).find((b) =>
    (b.textContent ?? "").includes(label)
  );
  expect(tombol, `tombol "${label}" tidak ada di layar`).toBeTruthy();
  await act(async () => {
    tombol!.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  await act(async () => {
    await Promise.resolve();
  });
}

afterEach(async () => {
  await bongkar();
  vi.unstubAllGlobals();
});

// --- butir 1: satu tombol, satu payload ------------------------------------

describe("klik tombol Muat Demo memuat dataset", () => {
  it("Muat Demo mengirim mode=realtime + replace, lalu sesi server masuk state", async () => {
    const panggilan = pasangFetch({
      "GET /demo/session": () => sesi(),
      "GET /demo/data-status": () => STATUS_DATA,
      "GET /demo/agent/last-run": () => ({ found: false }),
      "GET /demo/agent/commodities": () => ({ commodities: ["beras"] }),
      "POST /demo/session/start": () =>
        sesi({
          created: false,
          session_id: SID_BARU,
          mode: "realtime",
          evaluation_anchor: ANCHOR_REALTIME,
          dataset_version: "realtime-2026-10-27T08:15:00Z",
        }),
    });

    const wadah = await pasangPanel();
    expect(teks(wadah)).toContain("8 Okt 2026 12:00 UTC");
    // Tombol mode terpisah sudah dihapus: yang ada hanya "Muat Demo".
    expect(teks(wadah)).not.toContain("Muat Demo Utama");
    expect(teks(wadah)).not.toContain("Muat Demo Real-time");
    await klik(wadah, "Muat Demo");

    const mulai = panggilan.filter((p) => p.metode === "POST" && p.jalur === "/demo/session/start");
    expect(mulai).toHaveLength(1);
    expect(mulai[0].badan).toEqual({ mode: "realtime", replace: true });

    // Bukan hanya label: mode dan jangkar yang TERLIHAT berasal dari balasan
    // server (sid baru, jangkar 27 Okt), bukan dari teks tombol.
    const layar = teks(wadah);
    expect(layar).toMatch(/real-time/i);
    expect(layar).toContain("27 Okt 2026 08:15 UTC");
    expect(layar).toContain("realtime-2026-10-27T08:15:00Z");
    expect(layar).not.toContain("8 Okt 2026 12:00 UTC");

    // State memegang id sesi yang DIKEMBALIKAN server: analisis berikutnya
    // harus membawa id itu, bukan id sesi lama.
    await klik(wadah, "Jalankan agent");
    const jalan = panggilan.filter((p) => p.metode === "POST" && p.jalur === "/demo/agent/run");
    expect(jalan).toHaveLength(1);
    expect(jalan[0].badan.demo_session).toBe(SID_BARU);
    expect(jalan[0].badan.mode).toBe("realtime");
  });

  it("sesi replay yang masih tersisa diganti dataset realtime, bukan diteruskan", async () => {
    // Keadaan nyata setelah tombol replay dihapus: DB masih memegang sesi replay
    // dari geladi sebelumnya. Menekan "Muat Demo" harus MENGGANTI sesi itu
    // (replace), bukan menumpang jangkar 8 Okt yang sudah tidak bisa dipilih.
    const panggilan = pasangFetch({
      "GET /demo/session": () => sesi({ mode: "replay", evaluation_anchor: ANCHOR_REPLAY }),
      "GET /demo/data-status": () => STATUS_DATA,
      "GET /demo/agent/last-run": () => ({ found: false }),
      "GET /demo/agent/commodities": () => ({ commodities: ["beras"] }),
      "POST /demo/session/start": () =>
        sesi({
          created: false,
          session_id: SID_BARU,
          mode: "realtime",
          evaluation_anchor: ANCHOR_REALTIME,
          dataset_version: "realtime-2026-10-27T08:15:00Z",
        }),
    });

    const wadah = await pasangPanel();
    expect(teks(wadah)).toContain("8 Okt 2026 12:00 UTC");
    await klik(wadah, "Muat Demo");

    const mulai = panggilan.filter((p) => p.metode === "POST" && p.jalur === "/demo/session/start");
    expect(mulai).toHaveLength(1);
    expect(mulai[0].badan).toEqual({ mode: "realtime", replace: true });
    // Jangkar replay hilang dari layar: yang tampil jangkar sesi baru.
    expect(teks(wadah)).not.toContain("8 Okt 2026 12:00 UTC");
    expect(teks(wadah)).toContain("27 Okt 2026 08:15 UTC");
  });
});

// --- butir 2: refresh membaca sesi dari server ------------------------------

describe("refresh halaman", () => {
  it("membaca sesi yang sama dari server, tanpa menyimpannya di localStorage", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const rute = {
      "GET /demo/session": () => sesi({ mode: "realtime", evaluation_anchor: ANCHOR_REALTIME }),
      "GET /demo/data-status": () => STATUS_DATA,
      "GET /demo/agent/last-run": () => ({ found: false }),
      "GET /demo/agent/commodities": () => ({ commodities: ["beras"] }),
    };
    const pertama = pasangFetch(rute);
    const wadah1 = await pasangPanel();
    const sebelum = teks(wadah1);
    expect(sebelum).toContain("27 Okt 2026 08:15 UTC");
    await bongkar();

    // "Refresh" = komponen dipasang ulang dari nol: satu-satunya sumber sesi
    // adalah GET /demo/session.
    const kedua = pasangFetch(rute);
    const wadah2 = await pasangPanel();
    const sesudah = teks(wadah2);
    expect(sesudah).toContain("27 Okt 2026 08:15 UTC");
    expect(sesudah).toMatch(/real-time/i);
    expect(kedua.filter((p) => p.jalur === "/demo/session").length).toBeGreaterThan(0);
    expect(setItem).not.toHaveBeenCalled();
    setItem.mockRestore();
    // Tidak ada jalur "sesi terbaru" yang dikarang klien.
    expect(pertama.some((p) => p.jalur.includes("latest"))).toBe(false);
  });

  it("sesudah seed berikutnya panel memakai ID dan jangkar BARU", async () => {
    const api = readFileSync(join(__dirname, "..", "lib", "api.ts"), "utf8");
    // Kontrak HTTP-nya: satu jalur sesi, bukan dua ("latest").
    expect(api).toContain('request("/demo/session"');
    expect(api).not.toContain("/demo/session/latest");

    const panggilan = pasangFetch({
      "GET /demo/session": () =>
        sesi({
          session_id: SID_BARU,
          mode: "realtime",
          evaluation_anchor: ANCHOR_REALTIME,
          dataset_version: "realtime-2026-10-27T09:00:00Z",
        }),
      "GET /demo/data-status": () => STATUS_DATA,
      "GET /demo/agent/last-run": () => ({ found: false }),
      "GET /demo/agent/commodities": () => ({ commodities: ["beras"] }),
    });
    const wadah = await pasangPanel();
    expect(teks(wadah)).toContain("27 Okt 2026 08:15 UTC");

    await klik(wadah, "Jalankan agent");
    const jalan = panggilan.filter((p) => p.jalur === "/demo/agent/run");
    expect(jalan[0].badan.demo_session).toBe(SID_BARU);
    // ID sesi lama tidak boleh muncul lagi di layar.
    expect(teks(wadah)).not.toContain(SID_LAMA);
  });
});

// --- butir 3: status kesiapan + alasan hold --------------------------------

describe("kesiapan kasus pada panel sesi", () => {
  const DIBUAT = "590ce354-dff4-4a86-af13-1d01ecb05c5c";

  it("menampilkan 'Ditahan — menunggu verifikasi' beserta alasannya", async () => {
    const panggilan = pasangFetch({
      "GET /demo/session": () => sesi(),
      "GET /demo/data-status": () => STATUS_DATA,
      "GET /demo/agent/last-run": () => ({
        found: true,
        decision_id: DIBUAT,
        status: "pending_approval",
        commodity: "beras",
      }),
      "GET /demo/agent/commodities": () => ({ commodities: ["beras"] }),
      [`GET /decisions/${DIBUAT}/approval-summary`]: () => ({
        status: "pending_approval",
        can_execute: false,
        blocking_reasons: ["safety_pending"],
      }),
    });

    const wadah = await pasangPanel();
    const layar = teks(wadah);
    expect(panggilan.some((p) => p.jalur === `/decisions/${DIBUAT}/approval-summary`)).toBe(true);
    expect(layar).toContain("Kesiapan kasus");
    expect(layar).toContain("Ditahan — menunggu verifikasi");
    // Alasan dari peta kode yang sama dengan popup governance (lib/safety-gate).
    expect(layar).toContain("batch sumber belum diuji keamanan pangan");
    expect(layar).toContain("Uji keamanan pangan batch ini, lalu catat verifikasi");
  });

  it("menampilkan 'Siap dieksekusi' saat server mengizinkan", async () => {
    pasangFetch({
      "GET /demo/session": () => sesi(),
      "GET /demo/data-status": () => STATUS_DATA,
      "GET /demo/agent/last-run": () => ({ found: true, decision_id: DIBUAT, status: "approved" }),
      "GET /demo/agent/commodities": () => ({ commodities: ["beras"] }),
      [`GET /decisions/${DIBUAT}/approval-summary`]: () => ({
        status: "approved",
        can_execute: true,
        blocking_reasons: [],
      }),
    });
    const wadah = await pasangPanel();
    expect(teks(wadah)).toContain("Siap dieksekusi");
  });

  it("tidak mengarang kesiapan saat belum ada putaran agent", async () => {
    pasangFetch({
      "GET /demo/session": () => sesi(),
      "GET /demo/data-status": () => STATUS_DATA,
      "GET /demo/agent/last-run": () => ({ found: false }),
      "GET /demo/agent/commodities": () => ({ commodities: ["beras"] }),
    });
    const wadah = await pasangPanel();
    expect(teks(wadah)).not.toContain("Kesiapan kasus");
  });
});

describe("bukti putaran mengikuti komoditas yang dijalankan", () => {
  it("last-run diminta dengan ?commodity= setelah agent dijalankan", async () => {
    // 28 Okt 2026: satu putaran "semua" menulis beberapa keputusan dalam satu
    // transaksi, jadi "putaran terbaru" bisa milik komoditas lain. Panel harus
    // meminta bukti untuk komoditas yang barusan ditekan.
    const panggilan = pasangFetch({
      "GET /demo/session": () => sesi(),
      "GET /demo/data-status": () => STATUS_DATA,
      "GET /demo/agent/last-run": () => ({ found: false }),
      "GET /demo/agent/commodities": () => ({ commodities: ["beras", "wortel"] }),
      "POST /demo/agent/run": () => ({
        commodity: "beras",
        decision_id: "d-beras",
        created: [{ commodity: "beras", decision_id: "d-beras" }],
      }),
    });

    const wadah = await pasangPanel();
    await klik(wadah, "Jalankan agent");

    const bukti = panggilan.filter(
      (p) => p.metode === "GET" && p.jalur.startsWith("/demo/agent/last-run?")
    );
    expect(bukti.length).toBeGreaterThan(0);
    expect(bukti.at(-1)!.jalur).toContain("commodity=beras");
    // 28 Okt 2026: id keputusan dari respons run dipakai eksplisit, supaya
    // pembacaan bukti tidak kalah balapan dengan commit jejak di server.
    expect(bukti.at(-1)!.jalur).toContain("decision_id=d-beras");
  });
});

// --- butir 4: nama komoditas di dropdown, tanpa angka ----------------------

describe("dropdown komoditas hanya memuat nama", () => {
  it("opsi berisi nama saja; angka kasus tetap tampil di kalimat bawahnya", async () => {
    // Alasan: pada demo, "Beras — kekurangan 2.113 kg" membuat daftar pilihan
    // sulit dipindai dan angkanya bisa berubah tiap putaran. Angka kasus tetap
    // ada — di `catatanKasus` di bawah dropdown, dari respons server yang sama.
    pasangFetch({
      "GET /demo/session": () => sesi(),
      "GET /demo/data-status": () => STATUS_DATA,
      "GET /demo/agent/last-run": () => ({ found: false }),
      "GET /demo/agent/commodities": () => ({
        commodities: ["beras", "ayam"],
        kasus: [
          { commodity: "beras", status: "shortage", shortage_kg: 2113 },
          { commodity: "ayam", status: "surplus", surplus_kg: 40 },
        ],
      }),
    });

    const wadah = await pasangPanel();
    const opsi = Array.from(wadah.querySelectorAll("option")).map((o) => ({
      nilai: o.getAttribute("value"),
      teks: (o.textContent ?? "").trim(),
    }));

    // Teks opsi = nama komoditas itu sendiri, persis.
    expect(opsi).toEqual(
      expect.arrayContaining([
        { nilai: "beras", teks: "beras" },
        { nilai: "ayam", teks: "ayam" },
      ])
    );
    // Tidak ada satuan berat di dalam dropdown.
    const isiDropdown = Array.from(wadah.querySelectorAll("option"))
      .map((o) => o.textContent ?? "")
      .join(" ");
    expect(isiDropdown).not.toMatch(/kg|kekurangan|surplus/i);
    // Angka kasus TIDAK hilang — pindah ke catatan di bawah dropdown.
    expect(teks(wadah)).toContain("2.113 kg");
  });
});
