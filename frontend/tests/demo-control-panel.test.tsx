// Kontrak render Demo Control sederhana (keputusan Roy 2026-10-19).
//
// Yang dipaku di sini:
// - tab ini hanya tiga blok (siapkan data → jalankan agent → bukti), TANPA
//   skenario Event 1/2/3;
// - tombol agent hanya hidup untuk kepala SPPG yang punya token;
// - blok bukti menyebut langkah/provider yang benar-benar tercatat, dan TIDAK
//   membocorkan alamat runtime internal saat review 7-worker mati.

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DemoControlPanel, { DemoProof } from "../components/DemoControlPanel";
import type { AgentRun } from "../lib/demo-agent";

const RUN: AgentRun = {
  found: true,
  decision_id: "590ce354-dff4-4a86-af13-1d01ecb05c5c",
  status: "proposed",
  created_at: "2026-10-19T13:53:39+00:00",
  quantity_kg: "1257.14",
  commodity: "beras",
  source_location: "Cianjur",
  target_location: "Jakarta",
  verifier_note: "needs_verification",
  steps: [
    { step_name: "DETECT", tool_called: "supply.get+demand.get" },
    { step_name: "VERIFY", tool_called: "verifier.rest" },
    { step_name: "PREDICT", tool_called: "forecast.provider" },
    { step_name: "OPTIMIZE", tool_called: "balance.recommend" },
    { step_name: "DECIDE", tool_called: "POST /decisions" },
    { step_name: "SUPERVISE", tool_called: "supervisor.narration" },
  ],
  supervisor: {
    status: "narrated",
    provider: "fallback_1:sap_ai_core",
    fallback_used: true,
    summary: "Ringkasan keputusan distribusi.",
  },
  agent_review: {
    status: "unavailable",
    error:
      "AgentApiError: tidak dapat menghubungi API di https://solid-faster-reef-finally.trycloudflare.com",
    run_id: null,
  },
  agents_run_id: "ccf2b4bd",
  agents: [
    { key: "supply", label: "Pasokan", status: "ok", duration_ms: 1200, warnings: 0 },
    { key: "demand", label: "Permintaan", status: "ok", duration_ms: 900, warnings: 0 },
    { key: "freshness", label: "Kesegaran", status: "degraded", duration_ms: 400, warnings: 2 },
    { key: "safety", label: "Keamanan Pangan", status: "ok", duration_ms: 800, warnings: 0 },
    { key: "price", label: "Harga", status: "error", duration_ms: 300, warnings: 0 },
    { key: "logistics", label: "Logistik", status: "ok", duration_ms: 700, warnings: 0 },
    { key: "evidence", label: "Bukti", status: "missing" },
  ],
};

function render(props: Partial<React.ComponentProps<typeof DemoControlPanel>> = {}) {
  return renderToStaticMarkup(
    <DemoControlPanel token={"t"} role={"sppg_head"} locationName={"Jakarta"} {...props} />
  );
}

describe("DemoControlPanel — tiga blok, tanpa event", () => {
  it("menyusun blok dalam urutan siapkan data → jalankan agent → bukti", () => {
    const html = render();
    const i1 = html.indexOf("Siapkan data demo");
    const i2 = html.indexOf("Jalankan agent");
    const i3 = html.indexOf("Bukti agent");
    expect(i1).toBeGreaterThan(-1);
    expect(i2).toBeGreaterThan(i1);
    expect(i3).toBeGreaterThan(i2);
  });

  it("tidak lagi memuat skenario Event 1/2/3 atau chaos", () => {
    const html = render();
    expect(html).not.toContain("Event 1");
    expect(html).not.toContain("Event 2");
    expect(html).not.toContain("Event 3");
    expect(html).not.toContain("Chaos");
    expect(html).not.toContain("Picu");
  });

  it("menampilkan parameter yang benar-benar dipakai: beras + lokasi akun", () => {
    const html = render();
    expect(html).toContain("beras");
    expect(html).toContain("Jakarta");
  });

  it("lokasi kosong tidak dikarang menjadi nama kota", () => {
    const html = render({ locationName: null });
    expect(html).toContain("lokasi akun Anda");
  });

  it("tombol agent aktif untuk kepala SPPG bertoken, dan tidak aktif saat sibuk/kosong", () => {
    const aktif = render();
    expect(aktif).not.toMatch(/class="button button-primary dc-run"[^>]*disabled/);
    expect(render({ token: null })).toMatch(
      /class="button button-primary dc-run"[^>]*disabled/
    );
  });

  it("komoditas berupa dropdown yang pilihannya dari server (bukan teks mati)", () => {
    const html = render();
    expect(html).toContain('aria-label="Komoditas"');
    expect(html).toContain("<select");
    // Daftar belum termuat pada render statis → tidak ada nama komoditas
    // karangan; dropdown menyatakan dirinya kosong.
    expect(html).toContain("belum ada pilihan");
    expect(html).not.toContain('class="dc-param">beras<');
  });

  it("peran non-kepala melihat catatan mode baca dan tombolnya mati", () => {
    const html = render({ role: "bgn_monitor" });
    expect(html).toContain("Mode baca");
    expect(html).toMatch(/class="button button-primary dc-run"[^>]*disabled/);
  });
});

describe("DemoProof — bukti dari payload, bukan karangan", () => {
  it("selalu tujuh kartu agen, keadaan dari status tersimpan", () => {
    const html = renderToStaticMarkup(<DemoProof run={RUN} />);
    expect(html.match(/class="dc-agent"/g)).toHaveLength(7);
    expect(html).toContain('data-state="ok"');
    expect(html).toContain('data-state="limited"');
    expect(html).toContain('data-state="failed"');
    expect(html).toContain('data-state="idle"');
    expect(html).toContain("Tidak dijalankan");
    expect(html).toContain("2 peringatan");
  });

  it("putaran sedang berjalan → ketujuh kartu Berjalan, bukan hasil lama", () => {
    const html = renderToStaticMarkup(<DemoProof run={RUN} running />);
    expect(html.match(/class="dc-agent" data-state="running"/g)).toHaveLength(7);
    expect(html).toContain("Putaran baru sedang berjalan");
    expect(html).not.toContain("Selesai");
  });

  it("menyebut langkah yang tercatat beserta alatnya", () => {
    const html = renderToStaticMarkup(<DemoProof run={RUN} />);
    expect(html).toContain("DETECT");
    expect(html).toContain("supervisor.narration");
    // Enam langkah pada fixture, bukan tujuh yang "seharusnya" ada.
    expect((html.match(/class="dc-step"/g) ?? []).length).toBe(6);
  });

  it("menampilkan id keputusan (potongan), kuantitas, dan provider yang menjawab", () => {
    const html = renderToStaticMarkup(<DemoProof run={RUN} />);
    expect(html).toContain("590ce354");
    expect(html).toContain("1.257,14 kg");
    expect(html).toContain("fallback_1:sap_ai_core");
    expect(html).toContain("Cianjur → Jakarta");
  });

  it("review 7-worker yang mati dinyatakan tanpa membocorkan alamat runtime", () => {
    // Tanpa baris agen tersimpan, kalimat review runtime yang mati tampil.
    const html = renderToStaticMarkup(
      <DemoProof run={{ ...RUN, agents: [], agents_run_id: null }} />
    );
    expect(html).toContain("tidak terjangkau");
    expect(html).not.toContain("trycloudflare");
    expect(html).not.toContain("AgentApiError");
  });

  it("daftar langkah pipeline dilipat, isinya tetap ada di DOM", () => {
    const html = renderToStaticMarkup(<DemoProof run={RUN} />);
    expect(html).toContain('<details class="dc-steps-fold">');
    expect(html).not.toContain('<details class="dc-steps-fold" open');
    expect(html).toContain("Langkah pipeline");
    expect(html).toContain('class="dc-steps"');
    // Enam langkah di fixture tetap dirender walau lipatan tertutup.
    expect(html.match(/class="dc-step"/g)).toHaveLength(6);
  });

  it("narasi supervisor dilipat (details), bukan memenuhi kartu", () => {
    const html = renderToStaticMarkup(<DemoProof run={RUN} />);
    expect(html).toContain('<details class="dc-narration">');
    expect(html).not.toContain('<details class="dc-narration" open');
  });

  it("tanpa narasi, lipatan tidak dirender sama sekali", () => {
    const html = renderToStaticMarkup(
      <DemoProof run={{ ...RUN, supervisor: { status: "unavailable" } }} />
    );
    expect(html).not.toContain("dc-narration");
  });

  it("tombol buka keputusan memakai id dari payload", () => {
    const html = renderToStaticMarkup(<DemoProof run={RUN} onOpenDecision={() => {}} />);
    expect(html).toContain("Buka keputusan");
    expect(html).not.toMatch(/class="button button-secondary dc-open-decision"[^>]*disabled/);
  });
});
