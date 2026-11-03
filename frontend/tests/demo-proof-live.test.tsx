// Blok ketiga Demo Control = LOG PROSES PENGAMBILAN DATA, bukan "Bukti agent"
// (29 Okt 2026, permintaan pemilik).
//
// Riwayat singkat: 29 Okt pagi bagian ini sempat hanya berubah menjadi log
// SELAMA putaran berjalan, lalu sembilan kartu kembali setelah putaran ditutup.
// Pemilik meminta kartu itu dihapus seluruhnya - apa pun keadaannya bagian ini
// adalah terminal log. Yang dijaga di sini: tidak ada satu pun kartu
// "Selesai - Durasi - Peringatan", dan log tetap punya isi walau halaman
// dimuat ulang (dibaca dari jejak `agent_traces`, bukan dari kanal yang hilang).

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DemoRunLog } from "../components/DemoControlPanel";
import type { LangkahAgent } from "../lib/agent-stream";
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
  ],
  supervisor: {
    status: "narrated",
    provider: "fallback_1:sap_ai_core",
    fallback_used: true,
    summary: "Ringkasan keputusan distribusi.",
  },
  agent_review: { status: "ok", error: null, run_id: "ccf2b4bd" },
  agents_run_id: "ccf2b4bd",
  agents: [
    { key: "supply", label: "Pasokan", status: "ok", duration_ms: 5300, warnings: 0 },
    { key: "demand", label: "Permintaan", status: "ok", duration_ms: 6100, warnings: 0 },
    { key: "freshness", label: "Kesegaran", status: "ok", duration_ms: 5200, warnings: 1 },
    { key: "safety", label: "Keamanan Pangan", status: "ok", duration_ms: 5800, warnings: 1 },
    { key: "price", label: "Harga", status: "ok", duration_ms: 5500, warnings: 0 },
    { key: "logistics", label: "Logistik", status: "ok", duration_ms: 7800, warnings: 0 },
    { key: "evidence", label: "Bukti", status: "ok", duration_ms: 6500, warnings: 1 },
    { key: "verifier", label: "Verifikasi", status: "ok", verdict: "flagged", duration_ms: 900 },
  ],
} as AgentRun;

const LANGKAH: LangkahAgent[] = [
  {
    step: "DETECT",
    tool: "supply.get+demand.get+supplier.get",
    ringkas: "supply_kg=780 \u00b7 demand_kg=1560 \u00b7 gap_kg=780",
    at: "2026-10-29T03:21:04Z",
  },
  {
    step: "VERIFY",
    tool: "verifier.rest",
    ringkas: "verdict=consistent \u00b7 provider=local",
    at: "2026-10-29T03:21:09Z",
  },
];

describe("DemoRunLog — terminal, apa pun keadaan putarannya", () => {
  it("putaran berjalan: log hidup dengan jam dan ringkasan per langkah", () => {
    const html = renderToStaticMarkup(
      <DemoRunLog run={RUN} running langkahHidup={LANGKAH} />,
    );

    expect(html).toContain('aria-label="Log proses pengambilan data"');
    expect(html).toContain("10.21.04");
    expect(html).toContain("gap_kg=780");
    expect(html).toContain("DETECT");
    expect(html).toContain("VERIFY");

    // Kartu hasil putaran sebelumnya TIDAK dicetak.
    expect(html).not.toContain('aria-label="Sembilan agen review"');
    expect(html).not.toContain('class="dc-agent"');
    expect(html).not.toContain("5,3 dtk");
    expect(html).not.toContain("Peringatan");
  });

  it("menyebut asal data yang sedang diambil per langkah", () => {
    const html = renderToStaticMarkup(
      <DemoRunLog run={RUN} running langkahHidup={LANGKAH} />,
    );
    expect(html).toContain('data-sumber="supply.get"');
    expect(html).toContain('data-sumber="demand.get"');
    expect(html).toContain('data-sumber="supplier.get"');
    expect(html).toContain('data-sumber="verifier.rest"');
  });

  it("putaran berjalan tanpa satu langkah pun tetap jujur: menunggu langkah pertama", () => {
    const html = renderToStaticMarkup(<DemoRunLog run={RUN} running langkahHidup={[]} />);
    expect(html).toContain("menunggu langkah pertama");
    expect(html).not.toContain('class="dc-agent"');
  });

  it("kanal yang gagal dicetak sebagai galat di dalam log yang sama", () => {
    const html = renderToStaticMarkup(
      <DemoRunLog run={RUN} running langkahHidup={LANGKAH} galatAliran="Kanal terputus" />,
    );
    expect(html).toContain("Kanal terputus");
  });

  it("setelah putaran ditutup: tetap terminal, isi dibaca dari jejak tersimpan", () => {
    const html = renderToStaticMarkup(<DemoRunLog run={RUN} langkahHidup={[]} />);

    // Tidak ada kartu, tidak ada lipatan "Langkah pipeline"/"Hasil supervisor".
    expect(html).not.toContain('class="dc-agent"');
    expect(html).not.toContain("dc-steps-fold");
    expect(html).not.toContain("dc-narration");

    // Log tetap terbaca: dua langkah tersimpan, sumbernya ikut.
    expect(html).toContain('aria-label="Log proses pengambilan data"');
    expect(html).toContain("DETECT");
    expect(html).toContain("VERIFY");
    expect(html).toContain("2 langkah");
    expect(html).toContain('data-sumber="verifier.rest"');
    expect(html).toContain("Dibaca dari jejak putaran tersimpan");
  });

  it("baris jejak tanpa jam: kolom jam dilipat, bukan diisi --.--.--", () => {
    const html = renderToStaticMarkup(<DemoRunLog run={RUN} />);
    expect(html).toContain("dc-term-baris--tanpa-jam");
    expect(html).not.toContain("dc-term-jam--kosong");
    expect(html).not.toContain("dc-term-jam");
  });

  it("baris hidup yang punya jam tidak memakai grid tanpa jam", () => {
    const html = renderToStaticMarkup(
      <DemoRunLog run={RUN} running langkahHidup={LANGKAH} />,
    );
    expect(html).not.toContain("dc-term-baris--tanpa-jam");
    expect(html).toContain("dc-term-jam");
  });

  it("log yang ditutup tidak menyembunyikan isi di balik <details>", () => {
    const html = renderToStaticMarkup(<DemoRunLog run={RUN} />);
    expect(html).not.toContain("<details");
    expect(html).toContain("DETECT");
  });
});
