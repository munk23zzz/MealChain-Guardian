import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "fs";
import { join } from "path";
import { renderToStaticMarkup } from "react-dom/server";

import OpsConsole from "../components/OpsConsole";
import { runEvent1 } from "../lib/api";

// Event 1 PENUH dari UI (2026-10-16).
//
// Kenapa ada: sebelum endpoint `/demo/event1`, `run_event1` hanya dipanggil
// berkas tes backend, sehingga langkah SUPERVISE (narasi supervisor) tidak
// pernah muncul di `agent_traces` pada aplikasi yang dilihat juri. Tes ini
// mengunci dua hal: (1) tombolnya hanya muncul untuk peran yang boleh menulis
// (backend menolak bgn_monitor dengan 403), (2) bentuk body yang dikirim —
// backend memakai nama field `commodity` / `target_location` / `ttl_minutes`.

const HASIL_EVENT1 = {
  decision_id: "11111111-1111-1111-1111-111111111111",
  detect: { commodity: "telur" },
  verifier: { verdict: "PASS" },
  forecast: { forecast_qty_kg: 360.5 },
  supervisor: {
    status: "narrated",
    summary: "Surplus Bogor 300 kg dialihkan ke SPPG Jakarta.",
    provider: "primary:sap_ai_core",
  },
  decision_snapshot: { status: "proposed", approved: false },
  trace_steps: ["DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE", "DECIDE", "SUPERVISE"],
};

describe("Ops Console — Event 1 penuh", () => {
  it("peran approver melihat tombol Jalankan Event 1 penuh", () => {
    const html = renderToStaticMarkup(
      <OpsConsole role="sppg_head" token="t" ownLocationName="Jakarta" />
    );
    expect(html).toContain("ops-event1");
    expect(html).toContain("Jalankan Event 1 penuh");
  });

  it("bgn_monitor (read-only) tidak melihat tombol itu", () => {
    const html = renderToStaticMarkup(<OpsConsole role="bgn_monitor" token="t" />);
    expect(html).not.toContain("Jalankan Event 1 penuh");
  });

  it("blok hasil menampilkan keputusan, rantai langkah, dan narasi supervisor", () => {
    const html = renderToStaticMarkup(
      <OpsConsole
        role="sppg_head"
        token="t"
        ownLocationName="Jakarta"
        event1Result={HASIL_EVENT1}
      />
    );
    expect(html).toContain("ops-event1-result");
    expect(html).toContain(HASIL_EVENT1.decision_id);
    expect(html).toContain("narrated");
    expect(html).toContain("primary:sap_ai_core");
    expect(html).toContain("DETECT");
    // Narasi supervisor = inti endpoint ini; harus tampil di layar.
    expect(html).toContain("Surplus Bogor 300 kg dialihkan ke SPPG Jakarta.");
  });
});

describe("POST /demo/event1 — kontrak payload", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("mengirim commodity, target_location, dan ttl_minutes", async () => {
    const panggilan: Array<{ url: string; init: RequestInit }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        panggilan.push({ url, init });
        return new Response(JSON.stringify(HASIL_EVENT1), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        });
      })
    );

    const hasil = await runEvent1("telur", "Jakarta", "token-1", 45);

    expect(panggilan).toHaveLength(1);
    expect(panggilan[0].url).toContain("/demo/event1");
    expect(panggilan[0].init.method).toBe("POST");
    const body = JSON.parse(String(panggilan[0].init.body));
    expect(Object.keys(body).sort()).toEqual([
      "commodity",
      "target_location",
      "ttl_minutes",
    ]);
    expect(body.commodity).toBe("telur");
    expect(body.target_location).toBe("Jakarta");
    expect(body.ttl_minutes).toBe(45);
    // Nilai balikan dipakai UI apa adanya (tanpa dihitung ulang di klien).
    expect(hasil.supervisor.status).toBe("narrated");
  });

  it("ttl default 30 menit bila pemanggil tidak menyebutkannya", async () => {
    let body: any = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init: RequestInit) => {
        body = JSON.parse(String(init.body));
        return new Response(JSON.stringify(HASIL_EVENT1), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        });
      })
    );

    await runEvent1("telur", "Jakarta", "token-1");
    expect(body.ttl_minutes).toBe(30);
  });
});

// Wiring (pola tests/summary-wiring.test.tsx): dua jebakan yang sulit terlihat
// di render statis — (1) page tidak meneruskan callback-nya, (2) handler
// Event 1 kembali memanggil `onSubmitted` yang MEMINDAH TAB sehingga blok hasil
// (beserta narasi supervisor) langsung hilang dari layar. Keduanya pernah
// terjadi saat mengerjakan fitur ini.
describe("Wiring Event 1 penuh di konsol", () => {
  const baca = (bagian: string[]) =>
    readFileSync(join(process.cwd(), ...bagian), "utf-8");

  it("page meneruskan onDecisionCreated ke OpsConsole", () => {
    const src = baca(["app", "page.tsx"]);
    expect(src).toContain("<OpsConsole");
    expect(src).toContain("onDecisionCreated=");
  });

  it("handler Event 1 memakai onDecisionCreated, bukan onSubmitted", () => {
    const src = baca(["components", "OpsConsole.tsx"]);
    const mulai = src.indexOf("async function jalankanEvent1Penuh");
    const akhir = src.indexOf("async function submit", mulai);
    expect(mulai).toBeGreaterThan(-1);
    expect(akhir).toBeGreaterThan(mulai);
    const isi = src.slice(mulai, akhir);
    expect(isi).toContain("onDecisionCreated?.()");
    expect(isi).not.toContain("onSubmitted?.()");
  });
});

