// Kontrak render Demo Control sederhana (keputusan Roy 2026-10-19).
//
// Yang dipaku di sini:
// - tab ini hanya tiga blok (siapkan data → jalankan agent → bukti), TANPA
//   skenario Event 1/2/3;
// - tombol agent hanya hidup untuk kepala SPPG yang punya token;
// - blok ketiga adalah LOG PROSES PENGAMBILAN DATA (bukan sembilan kartu):
//   barisnya langkah yang tercatat, tanpa membocorkan alamat runtime internal
//   saat review 7-worker mati (29 Okt 2026, permintaan pemilik).

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DemoControlPanel, { DemoRunLog } from "../components/DemoControlPanel";
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
    {
      key: "verifier",
      label: "Verifikasi",
      status: "ok",
      verdict: "consistent",
      duration_ms: 12264,
      warnings: 0,
      summary: "Audit sepakat: 8 cek lulus.",
    },
  ],
};

function render(props: Partial<React.ComponentProps<typeof DemoControlPanel>> = {}) {
  return renderToStaticMarkup(
    <DemoControlPanel token={"t"} role={"sppg_head"} locationName={"Jakarta"} {...props} />
  );
}

describe("DemoControlPanel — tiga blok, tanpa event", () => {
  it("menyusun blok dalam urutan muat demo → jalankan agent → log proses", () => {
    const html = render();
    const i1 = html.indexOf("Muat demo");
    const i2 = html.indexOf("Jalankan agent");
    const i3 = html.indexOf("Log proses pengambilan data");
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

  it("menampilkan parameter yang benar-benar dipakai: komoditas terpilih + lokasi akun", () => {
    // Kontrak 28 Okt 2026 (permintaan pemilik): pilihan "Semua komoditas"
    // dihapus — operator wajib menyebut satu komoditas. Sebelum daftar dari
    // server termuat, dropdown menyatakan belum ada pilihan (bukan mengarang
    // nama). Lokasi tetap lokasi akun sendiri.
    const html = render();
    expect(html).not.toContain("Semua komoditas");
    expect(html).toContain("Belum ada komoditas");
    expect(html).toContain("Jakarta");
  });

  it("lokasi kosong tidak dikarang menjadi nama kota", () => {
    const html = render({ locationName: null });
    expect(html).toContain("lokasi akun Anda");
  });

  it("tombol agent menunggu komoditas: mati tanpa token DAN saat daftar komoditas kosong", () => {
    // Sejak 28 Okt 2026 tidak ada lagi "Semua komoditas": tombol baru hidup
    // setelah satu komoditas nyata terpilih. Kasus hidupnya diuji di
    // demo-control-interaction.test.tsx (daftar dari server berisi "beras").
    expect(render()).toMatch(/dc-run"[^>]*disabled/);
    expect(render({ token: null })).toMatch(/dc-run"[^>]*disabled/);
  });

  it("komoditas berupa dropdown yang pilihannya dari server (bukan teks mati)", () => {
    const html = render();
    expect(html).toContain('aria-label="Komoditas"');
    expect(html).toContain("<select");
    // Daftar belum termuat pada render statis → tidak ada nama komoditas
    // karangan, dan tidak ada lagi opsi "Semua komoditas" (dihapus 28 Okt 2026).
    expect(html).not.toContain("Semua komoditas");
    expect(html).toContain("Belum ada komoditas");
    expect(html).not.toContain('<option value="beras"');
    expect(html).not.toContain('class="dc-param">beras<');
  });

  it("peran non-kepala melihat catatan mode baca dan tombolnya mati", () => {
    const html = render({ role: "bgn_monitor" });
    expect(html).toContain("Mode baca");
    expect(html).toMatch(/class="button button-primary dc-run"[^>]*disabled/);
  });
});

describe("DemoRunLog — log proses dari jejak, bukan kartu karangan", () => {
  // Perubahan kontrak 29 Okt 2026 (permintaan pemilik): blok "Bukti agent"
  // DIHAPUS. Sembilan kartu "Selesai · Durasi · Peringatan", kartu Supervisor
  // + narasinya, dan catatan audit Verifier tidak dicetak lagi; penggantinya
  // satu terminal "Log proses pengambilan data" yang barisnya dibaca dari
  // jejak putaran (langkah + sumber data).
  it("mencetak terminal log, bukan sembilan kartu agen", () => {
    const html = renderToStaticMarkup(<DemoRunLog run={RUN} />);
    expect(html).toContain('aria-label="Log proses pengambilan data"');
    expect(html).toContain('role="log"');
    // Kartu, grid, dan judul-judul lamanya hilang.
    expect(html).not.toContain('class="dc-agent"');
    expect(html).not.toContain('aria-label="Sembilan agen review"');
    expect(html).not.toContain(">Supervisor</h3>");
    expect(html).not.toContain(">Verifier</h3>");
    expect(html).not.toContain("Narasi selesai");
    expect(html).not.toContain("Durasi");
  });

  it("setiap langkah tersimpan menjadi satu baris log", () => {
    const html = renderToStaticMarkup(<DemoRunLog run={RUN} />);
    for (const nama of ["DETECT", "VERIFY", "PREDICT", "OPTIMIZE", "DECIDE", "SUPERVISE"]) {
      expect(html).toContain(nama);
    }
    expect(html).toContain("6 langkah");
    // Sumber data yang dipanggil server tetap disebut per bagian.
    expect(html).toContain('data-sumber="supply.get"');
    expect(html).toContain('data-sumber="verifier.rest"');
  });

  it("mengatakan bahwa baris dibaca dari jejak tersimpan (tanpa jam karangan)", () => {
    const html = renderToStaticMarkup(<DemoRunLog run={RUN} />);
    expect(html).toContain("Dibaca dari jejak putaran tersimpan");
    // `agent_traces` tidak menyimpan jam per langkah: tidak ada "--.--.--".
    expect(html).not.toContain("--.--.--");
  });

  it("putaran berjalan: baris hidup dipakai apa adanya (jam + ringkasan)", () => {
    const html = renderToStaticMarkup(
      <DemoRunLog
        run={RUN}
        running
        langkahHidup={[
          {
            step: "DETECT",
            tool: "supply.get+demand.get",
            ringkas: "supply_kg=780 · gap_kg=780",
            at: "2026-10-29T03:21:04Z",
          },
        ]}
      />,
    );
    expect(html).toContain("10.21.04");
    expect(html).toContain("gap_kg=780");
    expect(html).toContain(">live<");
    // Selama putaran, baris tersimpan belum dipakai (itu hasil putaran lama).
    expect(html).not.toContain("Dibaca dari jejak putaran tersimpan");
    expect(html).not.toContain('class="dc-agent"');
  });

  it("narasi supervisor dan audit verifier tidak lagi dicetak", () => {
    const html = renderToStaticMarkup(<DemoRunLog run={RUN} />);
    expect(html).not.toContain("Ringkasan keputusan distribusi.");
    expect(html).not.toContain("dc-narration");
    expect(html).not.toContain("Audit sepakat");
    expect(html).toContain("Buka Agent Log");
  });

  it("review 7-worker yang mati tidak membocorkan alamat runtime", () => {
    const html = renderToStaticMarkup(
      <DemoRunLog run={{ ...RUN, agents: [], agents_run_id: null }} />,
    );
    expect(html).not.toContain("trycloudflare");
    expect(html).not.toContain("AgentApiError");
  });

  it("tanpa langkah sama sekali: terminal jujur kosong, tanpa baris karangan", () => {
    const html = renderToStaticMarkup(
      <DemoRunLog run={{ ...RUN, steps: [] }} />,
    );
    expect(html).toContain("0 langkah");
    expect(html).toContain(">siap<");
    expect(html).not.toContain("Dibaca dari jejak putaran tersimpan");
  });
  it("tombol buka keputusan memakai id dari payload", () => {
    const html = renderToStaticMarkup(
      <DemoRunLog run={RUN} onOpenDecision={() => {}} onOpenAgentLog={() => {}} />,
    );
    // Id utuh ada di payload handler; tombolnya hidup saat handler tersedia.
    expect(html).toContain("Buka keputusan");
    expect(html).not.toMatch(/class="button button-secondary dc-open-decision"[^>]*disabled/);
  });

  it("tombol tanpa handler dimatikan, bukan menipu", () => {
    const html = renderToStaticMarkup(<DemoRunLog run={RUN} />);
    expect(html).toMatch(/class="button button-secondary dc-open-decision"[^>]*disabled/);
    expect(html).toMatch(/class="button button-secondary dc-open-log"[^>]*disabled/);
    expect(html).toMatch(/class="button button-secondary dc-refresh-proof"[^>]*disabled/);
  });
});
