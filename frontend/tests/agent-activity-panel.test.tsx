// Kontrak render modul Agent Activity (dokumen 06-agent-log §2–§4).
//
// Diuji per komponen, sesuai pembagian dokumen:
// - `AgentPipelinePanel`: banner tiga keadaan, strip 10 chip, baris ACT/ledger,
//   provenance, tautan Safety & Evidence.
// - `DecisionAuditTable`: keterangan pemilih, kolom, "—" untuk nilai kosong,
//   tombol baris, paginasi.
// - `SupervisorStatusLine`, `AgentRoster`, `AgentRunSummary`, `ModuleSearch`.
import { readFileSync } from "node:fs";
import path from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import AgentPipelinePanel from "../components/AgentPipelinePanel";
import { PIPELINE_STAGES } from "../lib/pipeline-stages";
import DecisionAuditTable from "../components/DecisionAuditTable";
import AgentRoster from "../components/AgentRoster";
import AgentRunSummary from "../components/AgentRunSummary";
import ModuleSearch from "../components/ModuleSearch";
import SupervisorStatusLine from "../components/SupervisorStatusLine";

const NOW = Date.UTC(2026, 9, 28, 3, 0, 0);

function step(step_name: string, menit: number, extra: Record<string, unknown> = {}) {
  return {
    step_name,
    step_at: new Date(NOW + menit * 60_000).toISOString(),
    tool_called: "balance.map",
    duration_ms: 800,
    agent_name: null,
    ...extra,
  } as never;
}

const LEDGER = [
  { height: 21, action: "execute", created_at: new Date(NOW + 9 * 60_000).toISOString() },
];

const CSS = readFileSync(path.join(__dirname, "..", "app", "agent-activity.css"), "utf8");

/** Render pipeline dengan default wajar; tiap tes menimpa satu hal. */
function pipe(props: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <AgentPipelinePanel
      decisionId="d-1234"
      steps={[step("DETECT", 0), step("VERIFY", 1)]}
      ledger={LEDGER}
      {...props}
    />
  );
}

/* ------------------------------------------------------------------ *
 *  Pipeline: banner + strip
 * ------------------------------------------------------------------ */

describe("AgentPipelinePanel — banner tiga keadaan", () => {
  it("belum ada keputusan: menyuruh memilih, strip tidak dirender", () => {
    const html = pipe({ decisionId: null, steps: null, ledger: null });
    expect(html).toContain("Belum ada keputusan dipilih");
    expect(html).not.toContain("aa-strip");
  });

  it("null ≠ []: belum dimuat punya kalimat sendiri", () => {
    const html = pipe({ steps: null, ledger: null });
    expect(html).toContain("Trace belum dimuat");
    expect(html).toContain("jangan dibaca sebagai hasil");
    expect(html).toContain("belum dimuat");
  });

  it("kosong menyangkal kata berhasil", () => {
    const html = pipe({ steps: [], ledger: [] });
    expect(html).toContain("Belum ada trace tersimpan");
    expect(html).toContain("BUKAN tanda keputusan berhasil");
  });

  it("ada langkah: menyebut jumlah + memisahkan provenance dari penilaian", () => {
    const html = pipe();
    expect(html).toContain("2 langkah tercatat");
    expect(html).toContain("bukan bahwa hasilnya benar");
  });
});

describe("AgentPipelinePanel — strip sembilan tahap", () => {
  it("sepuluh chip urut pipeline, ringkasan menghitung ACT sebagai jejak", () => {
    const html = pipe();
    expect(html.match(/class="aa-stage /g)).toHaveLength(PIPELINE_STAGES.length);
    const urutan = ["DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE", "DECIDE", "SUPERVISE", "ACT", "LEARN"];
    const posisi = urutan.map((kode) => html.indexOf(`>${kode}<`));
    expect(posisi.every((p) => p > -1)).toBe(true);
    expect([...posisi].sort((a, b) => a - b)).toEqual(posisi);
    // Ringkasan "N dari M tahap punya jejak" PINDAH ke kepala panel (Tahap 4
    // redesign 29 Okt 2026) — diuji di `agent-log-redesign-kontrak.test.tsx`.
    // Di strip ia tidak boleh tercetak dua kali.
    expect(html).not.toContain("tahap punya jejak tercatat");
  });

  it("ACT hanya punya blok ledger → 'tercatat di Ledger' + dasar ledger_blocks", () => {
    const html = pipe();
    expect(html).toContain("tercatat di Ledger");
    expect(html).toContain("ACT tercatat di Ledger (blok #21)");
    expect(html).toContain("ledger_blocks (action = execute)");
  });

  it("chip membuka rincian lewat aria-expanded + aria-controls", () => {
    const html = pipe();
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('role="region"');
  });

  it("penanda waktu/lambat berupa ikon; keterangan hanya sekali", () => {
    const html = pipe({
      steps: [step("DETECT", 0), step("DECIDE", 40, { duration_ms: 90_000 })],
    });
    expect(html).toContain("aa-mark-time");
    expect(html).toContain("aa-mark-slow");
    expect(html).toContain("1 tahap lebih lambat dari biasanya");
  });

  it("provenance memuat jumlah langkah + waktu pertama/terakhir", () => {
    const html = pipe();
    expect(html).toContain("2 langkah · pertama");
    expect(html).toContain("terakhir");
  });

  it("tautan Safety & Evidence hanya saat ada langkah dan handler", () => {
    expect(pipe({ onOpenEvidence: () => {} })).toContain("Safety &amp; Evidence");
    expect(pipe()).not.toContain("aa-link");
    expect(pipe({ steps: [], ledger: [], onOpenEvidence: () => {} })).not.toContain("aa-link");
  });
});

/* ------------------------------------------------------------------ *
 *  Tabel keputusan
 * ------------------------------------------------------------------ */

const ROWS = [
  {
    decision_id: "aaaa1111-2222-3333-4444-555566667777",
    decision_type: "supplier_procurement",
    status: "pending_approval",
    quantity_kg: 640,
    safe_delivered_cost: 1440000,
    expires_at: new Date(NOW + 3600_000).toISOString(),
    commodity_name: "beras",
    target_location_name: "Bandung",
  },
  {
    decision_id: "bbbb1111-2222-3333-4444-555566667777",
    decision_type: "regional_balance",
    status: "executed",
    quantity_kg: null,
    safe_delivered_cost: null,
    expires_at: null,
    commodity_name: null,
    target_location_name: "Bandung",
  },
];

function table(props: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <DecisionAuditTable
      rows={ROWS}
      total={ROWS.length}
      page={1}
      onPage={() => {}}
      selectedId={null}
      onSelect={() => {}}
      summary="2 dari 2 keputusan"
      {...props}
    />
  );
}

describe("DecisionAuditTable", () => {
  it("menulis keterangan pemilih, bukan terbaca sebagai laporan", () => {
    expect(table()).toContain(
      "Pilih satu keputusan, langkah yang dijalankan agent tampil di bawah"
    );
  });

  it("kolom mengikuti urutan triage: Status → Tenggat → bukti → identitas", () => {
    const html = table();
    const kolom = ["Status", "Tenggat", "Verifikasi", "Keputusan", "Komoditas", "Kuantitas", "Biaya aman"];
    for (const nama of kolom) expect(html).toContain(`>${nama}<`);
    // Urutannya dijaga, bukan hanya keberadaannya (Tahap 3 redesign 29 Okt 2026).
    const posisi = kolom.map((nama) => html.indexOf(`>${nama}<`));
    expect(posisi).toEqual([...posisi].sort((a, b) => a - b));
    expect(html).toContain("Pengadaan dari pemasok");
    expect(html).toContain("Penyeimbangan pasokan regional");
  });

  it("nilai kosong ditulis — (bukan 0 atau tebakan)", () => {
    const html = table();
    expect(html).toContain("—");
    // Bukan nol yang dikarang: sel kosong tidak ditulis "0 kg" / "Rp 0".
    expect(html).not.toMatch(/>\s*0(\.0+)?\s*kg</);
    expect(html).not.toMatch(/>Rp\s*0</);
  });

  it("baris terpilih ditandai aria-current + tombolnya 'Dipilih'", () => {
    const html = table({ selectedId: ROWS[0].decision_id });
    expect(html).toContain('aria-current="true"');
    expect(html).toContain("Dipilih");
    expect(html).toContain("Lihat jejak");
  });

  it("tanpa hasil: menyebut total periode, bukan '0 keputusan'", () => {
    const html = table({ rows: [], total: 7 });
    expect(html).toContain("Tidak ada keputusan yang cocok");
    expect(html).toContain("7");
  });
});

/* ------------------------------------------------------------------ *
 *  Pencarian, status supervisor, agent, run summary
 * ------------------------------------------------------------------ */

describe("ModuleSearch", () => {
  it("menyatakan bahwa pencarian menyaring daftar keputusan, bukan langkah", () => {
    const html = renderToStaticMarkup(
      <ModuleSearch
        query=""
        onQuery={() => {}}
        commodity={null}
        onCommodity={() => {}}
        verification="all"
        onVerification={() => {}}
        commodities={[{ value: "beras", label: "beras", count: 3 }]}
        counts={{ all: 3, terverifikasi: 1, menunggu: 2, ditolak: 0 }}
        total={3}
      />
    );
    expect(html).toContain("daftar keputusan");
    // Teks dipendekkan pada Tahap 2 redesign (29 Okt 2026): kalimatnya tetap
    // menyatakan hal yang sama — filter menyaring daftar keputusan, bukan trace.
    expect(html).toContain("bukan langkah trace");
  });

  it("filter status punya jumlah + aria-pressed", () => {
    const html = renderToStaticMarkup(
      <ModuleSearch
        query=""
        onQuery={() => {}}
        commodity={null}
        onCommodity={() => {}}
        verification="menunggu"
        onVerification={() => {}}
        commodities={[]}
        counts={{ all: 3, terverifikasi: 1, menunggu: 2, ditolak: 0 }}
        total={3}
      />
    );
    expect(html).toContain('aria-pressed="true"');
    expect(html).toContain("Menunggu verifikasi");
  });
});

describe("SupervisorStatusLine", () => {
  it("belum dimuat ≠ sehat", () => {
    const html = renderToStaticMarkup(<SupervisorStatusLine health={null} />);
    expect(html).toContain("belum dimuat");
    expect(html).toContain("jangan dibaca sebagai sehat");
  });

  it("konfigurasi ada tetapi belum diuji → tidak hijau", () => {
    const html = renderToStaticMarkup(
      <SupervisorStatusLine health={{ status: "configured", live: null }} />
    );
    expect(html).toContain("belum diuji hidup");
    expect(html).toContain("aa-tone-neutral");
    expect(html).not.toContain("aa-tone-safe");
  });

  it("ok/healthy/up → aktif (hijau) dengan model", () => {
    const html = renderToStaticMarkup(
      <SupervisorStatusLine health={{ status: "ok", model: "claude-x" }} />
    );
    expect(html).toContain("Supervisor aktif");
    expect(html).toContain("aa-tone-safe");
    expect(html).toContain("claude-x");
  });

  it("status tak dikenal → bahaya, disebut apa adanya", () => {
    const html = renderToStaticMarkup(
      <SupervisorStatusLine health={{ status: "degraded" }} />
    );
    expect(html).toContain("Supervisor: degraded");
    expect(html).toContain("aa-tone-danger");
  });
});

describe("AgentRoster", () => {
  it("dua agent, masing-masing menyebut sumber klaimnya", () => {
    const html = renderToStaticMarkup(<AgentRoster />);
    expect(html).toContain("Supervisor Agent");
    expect(html).toContain("Verifier Agent");
    expect(html).toContain("tahap SUPERVISE");
    expect(html).toContain("tahap VERIFY");
    expect(html.match(/class="aa-agent-card"/g)).toHaveLength(2);
  });
});

describe("AgentRunSummary", () => {
  it("membedakan 'belum ada trace' dari 'trace tanpa langkah model'", () => {
    const kosong = renderToStaticMarkup(
      <AgentRunSummary providers={{}} traceCount={0} modelSteps={0} />
    );
    const tanpaModel = renderToStaticMarkup(
      <AgentRunSummary providers={{}} traceCount={4} modelSteps={0} />
    );
    expect(kosong).toContain("Belum ada trace");
    expect(tanpaModel).toContain("tidak satu pun langkah model");
    expect(kosong).not.toContain("tidak satu pun langkah model");
  });

  it("selalu menampilkan panel status model (satu-satunya tempat)", () => {
    const html = renderToStaticMarkup(
      <AgentRunSummary providers={{ verifier: { status: "unavailable" } }} traceCount={2} modelSteps={1} />
    );
    expect(html).toContain("Status Model Agent");
  });
});

/* ------------------------------------------------------------------ *
 *  CSS
 * ------------------------------------------------------------------ */

describe("CSS modul", () => {
  it("target sentuh chip ≥44px + fokus terlihat", () => {
    expect(CSS).toMatch(/\.aa-stage\s*\{[^}]*min-height:\s*44px/);
    expect(CSS).toContain(":focus-visible");
  });

  it("warna solid: tanpa gradasi", () => {
    expect(CSS).not.toContain("gradient");
  });

  it("radius & bayangan memakai token", () => {
    expect(CSS).not.toMatch(/border-radius:\s*(?!999px)\d+px/);
    expect(CSS).not.toMatch(/box-shadow:[^;]*rgba\(/);
  });
});
