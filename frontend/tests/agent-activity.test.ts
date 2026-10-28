// Kontrak model "Agent Activity" (dokumen 06-agent-log, 28 Okt 2026).
//
// Empat invarian dokumen yang dipaku di sini:
// 1. Kosong bukan sukses — tiga keadaan trace (belum dimuat / tidak ada /
//    ada) tidak boleh disederhanakan.
// 2. `null` bukan `[]` — belum dimuat ≠ tidak ada.
// 3. ACT punya rumah sendiri di ledger; blok `execute` berarti tercatat,
//    bukan "belum tercatat".
// 4. Provenance dipisah dari penilaian — banner hanya melaporkan apa yang
//    tercatat, bukan bahwa hasilnya benar.
import { describe, expect, it } from "vitest";

import {
  PIPELINE_STAGES,
  buildPipeline,
  pipelineSummary,
  provenanceLine,
  slowSteps,
  traceBanner,
  type LedgerBlockView,
  type TraceStep,
} from "../lib/agent-activity";

function step(
  step_name: string,
  menit: number,
  extra: Partial<TraceStep> = {}
): TraceStep {
  return {
    step_name,
    step_at: new Date(Date.UTC(2026, 9, 28, 3, menit, 0)).toISOString(),
    tool_called: null,
    duration_ms: null,
    agent_name: null,
    ...extra,
  };
}

function blok(action: string, height = 12): LedgerBlockView {
  return {
    height,
    action,
    created_at: new Date(Date.UTC(2026, 9, 28, 3, 30, 0)).toISOString(),
  };
}

describe("daftar tahap", () => {
  it("sembilan tahap, urutan pipeline, bukan urutan abjad", () => {
    expect(PIPELINE_STAGES.map((s) => s.code)).toEqual([
      "DETECT",
      "VERIFY",
      "TRACE",
      "PREDICT",
      "OPTIMIZE",
      "DECIDE",
      "SUPERVISE",
      "ACT",
      "LEARN",
    ]);
  });

  it("tiap tahap punya label manusia dan keterangan tool", () => {
    for (const tahap of PIPELINE_STAGES) {
      expect(tahap.label.length).toBeGreaterThan(3);
      expect(tahap.tool.length).toBeGreaterThan(3);
    }
  });
});

describe("buildPipeline — keadaan tiap tahap", () => {
  it("trace belum dimuat: SEMUA tahap 'not_loaded', bukan 'absent'", () => {
    const stages = buildPipeline({ steps: null, ledger: null });
    expect(stages).toHaveLength(9);
    expect(stages.every((s) => s.state === "not_loaded")).toBe(true);
  });

  it("trace kosong: semua tahap 'absent' (kecuali ACT yang melihat ledger)", () => {
    const stages = buildPipeline({ steps: [], ledger: [] });
    expect(stages.every((s) => s.state === "absent")).toBe(true);
  });

  it("tahap yang punya baris trace = 'present' dan membawa waktu", () => {
    const stages = buildPipeline({
      steps: [step("DETECT", 0), step("VERIFY", 1), step("DECIDE", 4)],
      ledger: null,
    });
    const byCode = Object.fromEntries(stages.map((s) => [s.code, s]));
    expect(byCode.DETECT.state).toBe("present");
    expect(byCode.DETECT.at).toBe(step("DETECT", 0).step_at);
    expect(byCode.PREDICT.state).toBe("absent");
    expect(byCode.PREDICT.at).toBeNull();
  });

  it("nama tahap tidak peka huruf besar/kecil", () => {
    const stages = buildPipeline({
      steps: [step("detect", 0)],
      ledger: null,
    });
    expect(stages.find((s) => s.code === "DETECT")?.state).toBe("present");
  });

  it("ACT tanpa baris trace tapi ada blok execute = 'ledger', bukan 'absent'", () => {
    const stages = buildPipeline({
      steps: [step("DETECT", 0)],
      ledger: [blok("execute", 21)],
    });
    const act = stages.find((s) => s.code === "ACT")!;
    expect(act.state).toBe("ledger");
    expect(act.at).toBe(blok("execute").created_at);
    expect(act.note).toContain("#21");
  });

  it("ACT dengan baris trace tetap 'present'; ledger tidak menimpa trace", () => {
    const stages = buildPipeline({
      steps: [step("DETECT", 0), step("ACT", 9)],
      ledger: [blok("execute", 21)],
    });
    expect(stages.find((s) => s.code === "ACT")?.state).toBe("present");
  });

  it("blok ledger selain 'execute' tidak membuat ACT tercatat", () => {
    const stages = buildPipeline({
      steps: [step("DETECT", 0)],
      ledger: [blok("approve"), blok("verify")],
    });
    expect(stages.find((s) => s.code === "ACT")?.state).toBe("absent");
  });

  it("ledger belum dimuat (null) ≠ ledger kosong: ACT tetap 'not_loaded'", () => {
    const stages = buildPipeline({
      steps: [step("DETECT", 0)],
      ledger: null,
    });
    expect(stages.find((s) => s.code === "ACT")?.state).toBe("absent");
  });
});

describe("penanda langkah lambat", () => {
  it("jarak antar langkah > ambang menandai langkah itu", () => {
    const stages = buildPipeline({
      steps: [step("DETECT", 0), step("VERIFY", 1), step("DECIDE", 8)],
      ledger: null,
      slowGapMs: 120_000,
    });
    const byCode = Object.fromEntries(stages.map((s) => [s.code, s]));
    expect(byCode.DECIDE.slow).toBe(true);
    expect(byCode.VERIFY.slow).toBe(false);
  });

  it("durasi langkah > ambang juga menandai, walau jaraknya rapat", () => {
    const stages = buildPipeline({
      steps: [
        step("DETECT", 0),
        step("VERIFY", 1, { duration_ms: 9_000 }),
      ],
      ledger: null,
      slowStepMs: 5_000,
    });
    expect(stages.find((s) => s.code === "VERIFY")?.slow).toBe(true);
  });

  it("slowSteps melaporkan sebabnya, bukan cuma daftar nama", () => {
    const hasil = slowSteps(
      [step("DETECT", 0), step("DECIDE", 8, { duration_ms: 9_000 })],
      { slowGapMs: 120_000, slowStepMs: 5_000 }
    );
    const dec = hasil.find((s) => s.step_name === "DECIDE")!;
    expect(dec.reasons).toContain("durasi");
  });
});

describe("ringkasan strip", () => {
  it("menghitung tahap yang punya jejak dari sembilan", () => {
    const stages = buildPipeline({
      steps: [step("DETECT", 0), step("VERIFY", 1)],
      ledger: [blok("execute")],
    });
    const ringkas = pipelineSummary(stages);
    expect(ringkas).toContain("3 dari 9");
  });

  it("belum dimuat tidak ditulis 0 dari 9", () => {
    const stages = buildPipeline({ steps: null, ledger: null });
    const ringkas = pipelineSummary(stages);
    expect(ringkas).toContain("9 tahap");
    expect(ringkas).not.toContain("0 dari 9");
  });
});

describe("banner keadaan trace", () => {
  it("belum ada keputusan dipilih: keadaan tersendiri, bukan 'tidak ada trace'", () => {
    const banner = traceBanner(null, null);
    expect(banner.state).toBe("no_decision");
    expect(banner.sentence.toLowerCase()).toContain("pilih");
  });

  it("null = belum dimuat, dan kalimatnya melarang dibaca sebagai hasil", () => {
    const banner = traceBanner("abc", null);
    expect(banner.state).toBe("not_loaded");
    expect(banner.sentence.toLowerCase()).toContain("jangan dibaca sebagai hasil");
  });

  it("[] = backend menjawab kosong; kalimatnya menyangkal 'berhasil'", () => {
    const banner = traceBanner("abc", []);
    expect(banner.state).toBe("missing");
    expect(banner.sentence.toLowerCase()).toContain("bukan tanda keputusan berhasil");
  });

  it("ada langkah: menyebut jumlah dan memisahkan provenance dari penilaian", () => {
    const banner = traceBanner("abc", [step("DETECT", 0), step("VERIFY", 1)]);
    expect(banner.state).toBe("present");
    expect(banner.label).toContain("2");
    expect(banner.sentence.toLowerCase()).toContain("bukan bahwa hasilnya benar");
  });
});

describe("baris provenance", () => {
  it("memuat jumlah dan waktu pertama/terakhir, bukan jam polling", () => {
    const baris = provenanceLine([
      step("DETECT", 0),
      step("VERIFY", 1),
      step("DECIDE", 4),
    ])!;
    expect(baris).toContain("3 langkah");
    expect(baris.toLowerCase()).toContain("pertama");
    expect(baris.toLowerCase()).toContain("terakhir");
  });

  it("tanpa langkah tidak mencetak baris kosong berisi '0 langkah'", () => {
    expect(provenanceLine([])).toBeNull();
    expect(provenanceLine(null)).toBeNull();
  });
});
