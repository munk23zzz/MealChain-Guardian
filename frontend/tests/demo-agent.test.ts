// Tes murni peringkas blok bukti Demo Control (tanpa DOM, tanpa jaringan).
//
// Aturan yang dipaku di sini: tidak ada angka/keadaan karangan. Nilai kosong
// tetap kosong ("—"/"tidak tercatat"), dan status review runtime yang mati
// TIDAK boleh tampil seolah pipeline agent gagal.

import { describe, expect, it } from "vitest";

import {
  agentReviewLine,
  demoAgentCards,
  idKeputusanPutaran,
  defaultCommodity,
  elapsedLine,
  kmLabel,
  proofFacts,
  quantityLabel,
  rupiahLabel,
  routeLabel,
  ringkasPutaran,
  ringkasSatuKomoditas,
  runButtonLabel,
  stepNames,
  supervisorLine,
  type AgentRun,
} from "../lib/demo-agent";

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
    { step_name: "SUPERVISE", tool_called: "supervisor.narration" },
  ],
  supervisor: {
    status: "narrated",
    provider: "fallback_1:sap_ai_core",
    fallback_used: true,
    summary: "ringkasan",
  },
  agent_review: { status: "unavailable", error: "AgentApiError: ...", run_id: null },
};

describe("defaultCommodity", () => {
  it("memilih beras bila server memang punya beras", () => {
    expect(defaultCommodity(["ayam", "beras", "telur", "wortel"])).toBe("beras");
  });

  it("daftar tanpa beras memakai pilihan pertama server, bukan tebakan", () => {
    expect(defaultCommodity(["ayam", "telur"])).toBe("ayam");
  });

  it("daftar kosong tidak memaksa satu nama", () => {
    expect(defaultCommodity([])).toBe("");
    expect(defaultCommodity([] as string[])).toBe("");
  });
});

describe("quantityLabel", () => {
  it("memakai pemisah ribuan Indonesia dan membuang nol desimal yang tak bermakna", () => {
    expect(quantityLabel("1257.14")).toBe("1.257,14 kg");
    expect(quantityLabel("78")).toBe("78 kg");
    expect(quantityLabel("2500.00")).toBe("2.500 kg");
  });

  it("nilai kosong tidak menjadi 0", () => {
    expect(quantityLabel(null)).toBe("—");
    expect(quantityLabel(undefined)).toBe("—");
    expect(quantityLabel("")).toBe("—");
    expect(quantityLabel("bukan-angka")).toBe("—");
  });
});

describe("routeLabel", () => {
  it("menyusun rute hanya dari sisi yang ada", () => {
    expect(routeLabel("Cianjur", "Jakarta")).toBe("Cianjur → Jakarta");
    expect(routeLabel("Cianjur", null)).toBe("Cianjur");
    expect(routeLabel(null, null)).toBe("—");
  });
});

describe("proofFacts", () => {
  it("mengembalikan fakta berurutan dari payload, bukan karangan", () => {
    const fakta = proofFacts(RUN);
    expect(fakta.map((f) => f.label)).toEqual([
      "Komoditas",
      "Rute",
      "Kuantitas",
      "Status keputusan",
      "Verdict verifier",
    ]);
    expect(fakta[0].value).toBe("beras");
    expect(fakta[2].value).toBe("1.257,14 kg");
    expect(fakta[4].value).toBe("NEEDS_VERIFICATION");
  });

  it("tanpa putaran agent tidak ada fakta yang ditampilkan", () => {
    expect(proofFacts(null)).toEqual([]);
    expect(proofFacts({ found: false })).toEqual([]);
  });

  it("verdict yang tidak tercatat dikatakan apa adanya", () => {
    const fakta = proofFacts({ ...RUN, verifier_note: null });
    expect(fakta[4].value).toBe("tidak tercatat");
  });
});

describe("stepNames", () => {
  it("hanya langkah yang benar-benar tercatat, urut dari server", () => {
    expect(stepNames(RUN)).toEqual(["DETECT", "SUPERVISE"]);
  });

  it("langkah tanpa nama tidak dikarang; ditulis —", () => {
    expect(stepNames({ ...RUN, steps: [{ step_name: "" }] })).toEqual(["—"]);
  });
});

describe("supervisorLine", () => {
  it("menyebut provider yang menjawab dan penanda jalur cadangan", () => {
    const kalimat = supervisorLine(RUN.supervisor);
    expect(kalimat).toContain("fallback_1:sap_ai_core");
    expect(kalimat).toContain("jalur cadangan dipakai");
  });

  it("status tidak tercatat tidak disembunyikan", () => {
    expect(supervisorLine(null)).toContain("tidak tercatat");
  });
});

describe("agentReviewLine", () => {
  it("unavailable dinyatakan sebagai runtime tidak terjangkau, bukan pipeline gagal", () => {
    const kalimat = agentReviewLine(RUN.agent_review);
    expect(kalimat).toContain("tidak terjangkau");
    expect(kalimat).toContain("pipeline utama");
    // Alamat runtime internal tidak boleh bocor ke layar.
    expect(kalimat).not.toContain("AgentApiError");
  });

  it("selesai menyebut id run singkat bila ada", () => {
    expect(
      agentReviewLine({ status: "completed", run_id: "abcdef1234567890" })
    ).toContain("abcdef12");
  });

  it("vetoed dinyatakan sebagai veto guardian, bukan selesai biasa", () => {
    const kalimat = agentReviewLine({
      status: "vetoed",
      run_id: "abcdef1234567890",
    });
    expect(kalimat.toLowerCase()).toContain("veto");
    expect(kalimat).toContain("abcdef12");
    // Enum mentah tidak boleh bocor ke layar.
    expect(kalimat).not.toContain("berstatus vetoed");
  });

  it("tidak tercatat tetap dikatakan", () => {
    expect(agentReviewLine(undefined)).toContain("tidak tercatat");
    expect(agentReviewLine({ status: "missing" })).toContain("tidak tercatat");
  });
});

describe("elapsedLine & runButtonLabel", () => {
  it("detik negatif/tidak sah tidak menghasilkan angka aneh", () => {
    expect(elapsedLine(0)).toContain("mulai bekerja");
    expect(elapsedLine(-5)).toContain("mulai bekerja");
    expect(elapsedLine(Number.NaN)).toContain("mulai bekerja");
    expect(elapsedLine(12)).toContain("12 detik");
  });

  it("label tombol tunggal untuk keadaan sibuk/idle", () => {
    expect(runButtonLabel(false)).toBe("Jalankan agent");
    expect(runButtonLabel(true)).toBe("Agent bekerja…");
  });
});

// --- pengadaan pemasok (keputusan 2026-10-19) ------------------------------

const RUN_PENGADAAN: AgentRun = {
  found: true,
  mode: "supplier_procurement",
  decision_id: "e1ebe066-361f-4fdd-b19f-7f155055c640",
  status: "proposed",
  commodity: "telur",
  quantity_kg: "779.86",
  source_location: null,
  target_location: "Jakarta",
  verifier_note: "consistent",
  supplier: {
    supplier_id: "036f2597-83e8-4985-81c2-47626a8a1395",
    name: "Telur Berkah Bekasi",
    leg_km: "17.671",
    available_kg: "900.00",
    quote_price_per_kg: "30864.49",
    rank: 1,
    candidates_total: 3,
  },
  supply_gap: { supply_kg: "291.09", demand_kg: "1070.95", gap_kg: "779.86" },
  steps: [],
};

describe("proofFacts — pengadaan pemasok", () => {
  it("menampilkan pemasok, SPPG tujuan, dan jarak angkut dari DB", () => {
    const fakta = proofFacts(RUN_PENGADAAN);
    const peta = Object.fromEntries(fakta.map((f) => [f.label, f.value]));
    expect(peta["Pemasok"]).toBe("Telur Berkah Bekasi");
    expect(peta["SPPG"]).toBe("Jakarta");
    expect(peta["Kuantitas"]).toBe("779,86 kg");
    expect(peta["Kekurangan"]).toBe("779,86 kg");
    expect(peta["Stok pemasok"]).toBe("900 kg");
    expect(peta["Jarak pemasok → SPPG"]).toBe("17,671 km");
    expect(peta["Harga penawaran"]).toBe("Rp 30.864,49 /kg");
  });

  it("tidak menampilkan rute antar SPPG untuk pengadaan", () => {
    const label = proofFacts(RUN_PENGADAAN).map((f) => f.label);
    expect(label).not.toContain("Rute");
  });

  it("nilai kosong tetap jujur, bukan 0 atau karangan", () => {
    const tanpa: AgentRun = {
      ...RUN_PENGADAAN,
      supplier: { ...RUN_PENGADAAN.supplier, leg_km: null, quote_price_per_kg: null },
    };
    const peta = Object.fromEntries(proofFacts(tanpa).map((f) => [f.label, f.value]));
    expect(peta["Jarak pemasok → SPPG"]).toBe("tidak tercatat");
    expect(peta["Harga penawaran"]).toBe("tidak tercatat /kg");
  });

  it("putaran pemindahan lama tetap memakai format rute", () => {
    const lama: AgentRun = {
      found: true,
      mode: "regional_balance",
      commodity: "telur",
      source_location: "Cianjur",
      target_location: "Jakarta",
      quantity_kg: "600",
      status: "proposed",
    };
    const peta = Object.fromEntries(proofFacts(lama).map((f) => [f.label, f.value]));
    expect(peta["Rute"]).toBe("Cianjur → Jakarta");
    expect(peta["Pemasok"]).toBeUndefined();
  });
});

describe("label angka & uang", () => {
  it("rupiah memakai pemisah Indonesia dan menolak nilai kosong", () => {
    expect(rupiahLabel("30864.49")).toBe("Rp 30.864,49");
    expect(rupiahLabel(1500)).toBe("Rp 1.500");
    expect(rupiahLabel(null)).toBe("tidak tercatat");
    expect(rupiahLabel("bukan angka")).toBe("tidak tercatat");
  });

  it("km menyimpan tiga desimal koordinat", () => {
    expect(kmLabel("17.671")).toBe("17,671 km");
    expect(kmLabel(null)).toBe("tidak tercatat");
  });
});

describe("kartu sembilan agen di Demo Control", () => {
  const agen = [
    { key: "supply", label: "Pasokan", status: "ok", duration_ms: 1250, warnings: 0 },
    { key: "demand", label: "Permintaan", status: "degraded", duration_ms: 400, warnings: 2 },
    { key: "freshness", label: "Kesegaran", status: "error", duration_ms: null },
    { key: "safety", label: "Keamanan Pangan", status: "missing" },
    { key: "price", label: "Harga", status: "ok", duration_ms: 90 },
    { key: "logistics", label: "Logistik", status: "ok", duration_ms: 800 },
    { key: "evidence", label: "Bukti", status: "ok", duration_ms: 300 },
    {
      key: "verifier",
      label: "Verifikasi",
      status: "ok",
      verdict: "consistent",
      duration_ms: 12264,
      warnings: 0,
    },
  ];
  const SUPERVISOR = {
    status: "narrated",
    provider: "primary:agentcore",
    fallback_used: false,
    summary: "Jakarta kekurangan 2.110 kg beras; keputusan menunggu approval.",
  };

  function fakta(kartu: { meta: Array<{ label: string; value: string }> }, label: string) {
    return kartu.meta.find((f) => f.label === label)?.value;
  }

  it("sembilan kartu berurutan: tujuh worker, supervisor, verifier", () => {
    const kartu = demoAgentCards({
      found: true,
      agents_run_id: "r1",
      agents: agen,
      supervisor: SUPERVISOR,
    } as any);
    expect(kartu).toHaveLength(9);
    expect(kartu.map((k) => k.key)).toEqual([
      "supply",
      "demand",
      "freshness",
      "safety",
      "price",
      "logistics",
      "evidence",
      "supervisor",
      "verifier",
    ]);
  });

  it("memetakan status tersimpan ke keadaan dan label manusia", () => {
    const kartu = demoAgentCards({
      found: true,
      agents_run_id: "r1",
      agents: agen,
      supervisor: SUPERVISOR,
    } as any);
    expect(kartu.slice(0, 7).map((k) => k.state)).toEqual([
      "ok",
      "limited",
      "failed",
      "idle",
      "ok",
      "ok",
      "ok",
    ]);
    expect(kartu[0].statusLabel).toBe("Selesai");
    expect(kartu[1].statusLabel).toBe("Terbatas");
    expect(kartu[2].statusLabel).toBe("Gagal");
    expect(kartu[3].statusLabel).toBe("Tidak dijalankan");
    expect(kartu[0].duration).toBe("1,3 dtk");
    expect(kartu[4].duration).toBe("90 md");
    // Agen tanpa baris tidak boleh mengarang angka.
    expect(kartu[3].duration).toBe("—");
    expect(kartu[3].warnings).toBe("—");
    expect(kartu[1].warnings).toBe("2 peringatan");
  });

  it("kartu supervisor memakai run.supervisor: status, provider, ringkasan narasi", () => {
    const kartu = demoAgentCards({
      found: true,
      agents_run_id: "r1",
      agents: agen,
      supervisor: SUPERVISOR,
    } as any);
    const sup = kartu[7];
    expect(sup.label).toBe("Supervisor");
    expect(sup.state).toBe("ok");
    expect(sup.statusLabel).toBe("Narasi selesai");
    expect(fakta(sup, "Provider")).toBe("primary:agentcore");
    expect(sup.note).toContain("2.110 kg");
    // Supervisor tidak punya durasi/peringatan di payload → "—", bukan 0.
    expect(sup.duration).toBe("—");
    expect(fakta(sup, "Peringatan")).toBe("—");
  });

  it("narasi supervisor yang tidak tersedia dikatakan apa adanya", () => {
    const kartu = demoAgentCards({
      found: true,
      agents_run_id: "r1",
      agents: agen,
      supervisor: { status: "unavailable", provider: null, summary: null },
    } as any);
    expect(kartu[7].state).toBe("limited");
    expect(kartu[7].statusLabel).toBe("Narasi tidak tersedia");
    expect(fakta(kartu[7], "Provider")).toBe("—");
    expect(kartu[7].note).toBeNull();
  });

  it("supervisor belum tercatat tetap kartu, tanpa angka karangan", () => {
    const kartu = demoAgentCards({
      found: true,
      agents_run_id: "r1",
      agents: agen,
      supervisor: undefined,
    } as any);
    expect(kartu).toHaveLength(9);
    expect(kartu[7].state).toBe("idle");
    expect(kartu[7].statusLabel).toBe("Belum tercatat");
    expect(fakta(kartu[7], "Provider")).toBe("—");
    expect(kartu[7].duration).toBe("—");
  });

  it("putaran sedang berjalan → sembilan kartu Berjalan, tanpa angka lama", () => {
    const kartu = demoAgentCards(
      { found: true, agents_run_id: "r1", agents: agen, supervisor: SUPERVISOR } as any,
      true
    );
    expect(kartu).toHaveLength(9);
    expect(kartu.every((k) => k.state === "running")).toBe(true);
    expect(kartu.every((k) => k.duration === "—")).toBe(true);
    expect(kartu[0].statusLabel).toBe("Berjalan");
    expect(kartu[7].statusLabel).toBe("Berjalan");
  });

  it("tanpa daftar agen tidak mengarang sembilan kartu", () => {
    expect(demoAgentCards({ found: false } as any)).toEqual([]);
    expect(demoAgentCards(null)).toEqual([]);
  });

  it("verdict flagged → label definitif 'Ditinjau', bukan 'Terbatas'", () => {
    // Audit yang SELESAI dan menandai masalah adalah hasil definitif. Tanpa
    // verdict, baris verifier berstatus `degraded` dan labelnya "Terbatas" —
    // sama dengan keadaan "model tidak dikonfigurasi" yang belum mengaudit.
    const kartu = demoAgentCards({
      found: true,
      agents_run_id: "r1",
      agents: [
        ...agen.slice(0, 7),
        {
          key: "verifier",
          label: "Verifikasi",
          status: "degraded",
          verdict: "flagged",
          duration_ms: 16001,
          warnings: 3,
        },
      ],
      supervisor: SUPERVISOR,
    } as any);

    expect(kartu[8].state).toBe("flagged");
    expect(kartu[8].statusLabel).toBe("Ditinjau");
    expect(kartu[8].duration).toBe("16,0 dtk");
    expect(kartu[8].warnings).toBe("3 peringatan");
  });

  it("verifier yang tidak terkirim tetap kartu 'Belum tercatat'", () => {
    const kartu = demoAgentCards({
      found: true,
      agents_run_id: "r1",
      agents: agen.slice(0, 7),
      supervisor: SUPERVISOR,
    } as any);
    expect(kartu[8].key).toBe("verifier");
    expect(kartu[8].state).toBe("idle");
    expect(kartu[8].statusLabel).toBe("Belum tercatat");
    expect(kartu[8].duration).toBe("—");
  });

  it("verdict terisi tetapi bukan flagged tetap memakai status baris", () => {
    const kartu = demoAgentCards({
      found: true,
      agents_run_id: "r1",
      agents: [
        {
          key: "verifier",
          label: "Verifikasi",
          status: "degraded",
          verdict: "unavailable",
          duration_ms: 12,
        },
      ],
    } as any);

    // `unavailable` = audit belum bisa menyimpulkan → tetap jujur "Terbatas".
    expect(kartu[8].state).toBe("limited");
    expect(kartu[8].statusLabel).toBe("Terbatas");
  });
});

// --- ringkasan satu putaran "Jalankan agent" --------------------------------
// Server menjawab dengan `created`/`skipped` per komoditas (atau `decision_id`
// untuk satu komoditas di backend lama). Ringkasannya MURNI: setiap nama dan
// angka diambil dari payload, tidak ada yang dikarang.
describe("ringkasPutaran", () => {
  it("menyebut jumlah dan nama komoditas yang menghasilkan keputusan", () => {
    const baris = ringkasPutaran({
      created: [
        { commodity: "telur", decision_id: "d1" },
        { commodity: "ayam", decision_id: "d2" },
        { commodity: "wortel", decision_id: "d3" },
      ],
      skipped: [],
    });
    expect(baris).toBe("3 keputusan dibuat (telur, ayam, wortel)");
  });

  it("menyebut komoditas yang dilewati BESERTA alasannya, bukan menyembunyikannya", () => {
    const baris = ringkasPutaran({
      created: [{ commodity: "telur", decision_id: "d1" }],
      skipped: [{ commodity: "beras", reason: "SPPG ini tidak kekurangan komoditas tersebut" }],
    });
    expect(baris).toBe(
      "1 keputusan dibuat (telur) · beras dilewati: SPPG ini tidak kekurangan komoditas tersebut"
    );
  });

  it("memotong alasan yang panjang tanpa menghapus sebabnya", () => {
    const panjang = "x".repeat(400);
    const baris = ringkasPutaran({ created: [], skipped: [{ commodity: "beras", reason: panjang }] }, 40);
    expect(baris).toContain("beras dilewati: ");
    expect(baris).toContain("…");
    expect((baris ?? "").length).toBeLessThan(120);
  });

  it("payload lama tanpa created/skipped tidak menghasilkan baris kosong", () => {
    expect(ringkasPutaran({ commodity: "beras", decision_id: "d1" })).toBeNull();
    expect(ringkasPutaran(null)).toBeNull();
  });

  it("nol keputusan tetap dinyatakan, bukan disembunyikan", () => {
    expect(ringkasPutaran({ created: [], skipped: [] })).toBe("0 keputusan dibuat");
  });
});

// Penanda "Semua komoditas" dihapus 28 Okt 2026 (permintaan pemilik): panel
// wajib menyebut satu komoditas nyata, jadi tidak ada konstanta yang perlu
// dikunci lagi.
describe("ringkasSatuKomoditas", () => {
  it("menyebut komoditas, jumlah langkah, dan potongan id dari payload", () => {
    const baris = ringkasSatuKomoditas(
      { commodity: "telur", decision_id: "82a2cf7d-c232-49e3-839a-6f7cf4bec9a9", trace_steps: [1, 2, 3, 4, 5, 6, 7] },
      "telur"
    );
    expect(baris).toBe("1 keputusan dibuat (telur) · 7 langkah agent tercatat · id 82a2cf7d");
  });

  it("tetap menyebut keputusan saat langkah belum tercatat", () => {
    expect(ringkasSatuKomoditas({ commodity: "beras", decision_id: "abcdef1234567890" }, "beras")).toBe(
      "1 keputusan dibuat (beras) · id abcdef12"
    );
  });

  it("tanpa decision_id tidak mengarang bukti", () => {
    expect(ringkasSatuKomoditas({ commodity: "telur" }, "telur")).toBeNull();
    expect(ringkasSatuKomoditas(null, "telur")).toBeNull();
  });
});


describe("idKeputusanPutaran", () => {
  it("memakai decision_id dari created[0] (backend baru)", () => {
    expect(
      idKeputusanPutaran({
        created: [{ commodity: "wortel", decision_id: "d-wortel" }],
        skipped: [],
      }),
    ).toBe("d-wortel");
  });

  it("jatuh ke decision_id akar untuk payload backend lama", () => {
    expect(idKeputusanPutaran({ decision_id: "d-lama" })).toBe("d-lama");
  });

  it("null bila tidak ada id — tidak menebak", () => {
    expect(idKeputusanPutaran({ created: [{ commodity: "wortel" }] })).toBeNull();
    expect(idKeputusanPutaran(null)).toBeNull();
  });
});
