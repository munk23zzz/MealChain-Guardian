// Bukti suhu di layar "Keamanan Pangan" (Fase 3 MG butir 5).
//
// Kontrak yang dikunci berkas ini:
//   1. `evidenceRows` menerjemahkan blok `evidence` dari `GET /batches` menjadi
//      baris yang bisa dibaca petugas: apa yang diamati, cukup atau tidak, dan
//      DARI MANA log itu berasal.
//   2. Label asal log menyebut "log simulasi" untuk seed/demo — repo ini tidak
//      punya satu pun jalur penulisan log dari sensor sungguhan, jadi klaim
//      "sensor aktif" tidak boleh muncul di layar.
//   3. Bukti yang tidak cukup TIDAK tampil sebagai "cukup": batch rantai dingin
//      tanpa log harus terbaca perlu-verifikasi, bukan aman.
//   4. Komoditas ambient (beras) tidak dibaca sebagai pelanggaran rantai dingin.
//   5. Data lama tanpa blok `evidence` tidak dikarang: nilainya "tidak tercatat"
//      dan tidak dihitung sebagai bukti cukup.

import { describe, expect, it } from "vitest";

import {
  evidenceLabel,
  evidenceRows,
  evidenceStateOf,
  evidenceSummary,
  evidenceTone,
  sourceLabelOf,
} from "../lib/food-safety";

const PROFIL_TELUR = {
  commodity: "telur",
  cold_chain_required: true,
  safe_temp_min_c: 0,
  safe_temp_max_c: 8,
  shelf_life_days: 28,
  min_temperature_samples: 2,
  max_observation_age_minutes: 360,
  max_excursion_minutes: 30,
  policy_version: "sim-2026-10-27.v1",
  policy_basis: "asumsi demo",
  policy_kind: "simulated_policy",
};

const PROFIL_BERAS = {
  ...PROFIL_TELUR,
  commodity: "beras",
  cold_chain_required: false,
  safe_temp_min_c: null,
  safe_temp_max_c: null,
  min_temperature_samples: 0,
  max_observation_age_minutes: null,
};

function batch(over: Record<string, unknown> = {}) {
  return {
    id: "b1",
    location: "Cianjur",
    commodity: "telur",
    quantity_kg: 400,
    safety_status: "pass",
    freshness_score: 0.9,
    usable_until: "2026-10-30T00:00:00Z",
    evidence: {
      commodity_profile: PROFIL_TELUR,
      profile_source: "commodity_policies",
      temperature_observation: "observed",
      evidence_state: "sufficient",
      sample_count: 2,
      observed_at: "2026-10-25T10:00:00Z",
      evaluation_time: "2026-10-25T11:00:00Z",
      source: "seed",
      source_label: "log simulasi",
      evidence_sufficient: true,
      evidence_reasons: [],
      stored_safety_status: "pass",
      evaluated_safety_status: "pass",
    },
    ...over,
  };
}

describe("evidenceRows", () => {
  it("membaca blok bukti seed sebagai log simulasi yang cukup", () => {
    const rows = evidenceRows([batch()]);
    expect(rows).toHaveLength(1);
    expect(rows[0].commodity).toBe("telur");
    expect(rows[0].observation).toBe("observed");
    expect(rows[0].state).toBe("sufficient");
    expect(rows[0].sufficient).toBe(true);
    expect(rows[0].sampleCount).toBe(2);
    expect(rows[0].source).toBe("seed");
    expect(rows[0].sourceLabel).toBe("log simulasi");
    expect(rows[0].profileVersion).toBe("sim-2026-10-27.v1");
    expect(rows[0].policyKind).toBe("simulated_policy");
  });

  it("label asal log tidak pernah mengklaim sensor sungguhan", () => {
    const rows = evidenceRows([batch()]);
    for (const row of rows) {
      expect(row.sourceLabel.toLowerCase()).not.toContain("sensor");
    }
  });

  it("batch rantai dingin tanpa log tidak dibaca sebagai cukup", () => {
    const rows = evidenceRows([
      batch({
        evidence: {
          ...batch().evidence,
          temperature_observation: "missing",
          evidence_state: "insufficient",
          sample_count: 0,
          observed_at: null,
          evidence_sufficient: false,
          evidence_reasons: ["log suhu kosong"],
          evaluated_safety_status: "needs_verification",
        },
      }),
    ]);
    expect(rows[0].observation).toBe("missing");
    expect(rows[0].state).toBe("insufficient");
    expect(rows[0].sufficient).toBe(false);
    expect(rows[0].reasons).toEqual(["log suhu kosong"]);
    expect(rows[0].observedAt).toBeNull();
  });

  it("log lama dibaca stale, bukan observasi real-time", () => {
    const rows = evidenceRows([
      batch({
        evidence: {
          ...batch().evidence,
          temperature_observation: "stale",
          evidence_state: "insufficient",
          observed_at: "2026-10-20T10:00:00Z",
          evidence_sufficient: false,
          evidence_reasons: ["sampel terakhir 7200 menit lalu, lewat batas 360 menit"],
        },
      }),
    ]);
    expect(rows[0].observation).toBe("stale");
    expect(rows[0].state).toBe("insufficient");
    expect(rows[0].observedAt).toBe("2026-10-20T10:00:00Z");
  });

  it("komoditas ambient tidak dibaca sebagai pelanggaran rantai dingin", () => {
    const rows = evidenceRows([
      batch({
        commodity: "beras",
        evidence: {
          ...batch().evidence,
          commodity_profile: PROFIL_BERAS,
          temperature_observation: "missing",
          evidence_state: "insufficient",
          evidence_sufficient: false,
          evaluated_safety_status: "pass",
        },
      }),
    ]);
    expect(rows[0].coldChainRequired).toBe(false);
    expect(rows[0].tone).toBe("muted");
  });

  it("data lama tanpa blok evidence tidak dikarang sebagai cukup", () => {
    const rows = evidenceRows([{ ...batch(), evidence: undefined }]);
    expect(rows[0].state).toBe("unknown");
    expect(rows[0].sufficient).toBe(false);
    expect(rows[0].sourceLabel).toBe("tidak tercatat");
    expect(rows[0].observation).toBeNull();
    expect(rows[0].observationLabel).toBe("tidak tercatat");
  });

  it("menerima bentuk amplop {batches: [...]} maupun array", () => {
    expect(evidenceRows({ batches: [batch()] })).toHaveLength(1);
    expect(evidenceRows(null)).toEqual([]);
    expect(evidenceRows(undefined)).toEqual([]);
    expect(evidenceRows({})).toEqual([]);
  });

  it("komoditas tanpa profil tidak ditebak profilnya", () => {
    const rows = evidenceRows([
      batch({
        commodity: "jagung",
        evidence: {
          ...batch().evidence,
          commodity_profile: null,
          profile_source: "tidak ada",
          temperature_observation: "missing",
          evidence_state: "insufficient",
          evidence_sufficient: false,
          evaluated_safety_status: null,
        },
      }),
    ]);
    expect(rows[0].profileVersion).toBeNull();
    expect(rows[0].policyKind).toBeNull();
    expect(rows[0].sufficient).toBe(false);
    expect(rows[0].state).toBe("insufficient");
  });
});

describe("evidenceStateOf / evidenceLabel / evidenceTone", () => {
  it("menerjemahkan tiap keadaan bukti ke label yang berbeda", () => {
    const labels = ["sufficient", "insufficient", "ambiguous", "unknown"].map(
      (state) => evidenceLabel(state),
    );
    expect(new Set(labels).size).toBe(4);
    expect(evidenceLabel("sufficient")).toBe("Bukti cukup");
    expect(evidenceLabel("insufficient")).toBe("Bukti kurang");
    expect(evidenceLabel("ambiguous")).toBe("Bukti bertentangan");
    expect(evidenceLabel("unknown")).toBe("Tidak tercatat");
  });

  it("nilai asing tidak diteruskan mentah ke layar", () => {
    expect(evidenceStateOf("aneh")).toBe("unknown");
    expect(evidenceLabel("aneh")).toBe("Tidak tercatat");
    expect(evidenceTone("aneh")).toBe("muted");
  });

  it("hanya bukti cukup yang berwarna aman", () => {
    expect(evidenceTone("sufficient")).toBe("ok");
    expect(evidenceTone("insufficient")).toBe("warn");
    expect(evidenceTone("ambiguous")).toBe("warn");
    expect(evidenceTone("unknown")).toBe("muted");
  });

  it("label asal log tidak meneruskan nilai mentah", () => {
    expect(sourceLabelOf("seed")).toBe("log simulasi");
    expect(sourceLabelOf("demo")).toBe("log simulasi");
    expect(sourceLabelOf("unrecorded")).toBe("tanpa jejak asal log");
    expect(sourceLabelOf(null)).toBe("tidak tercatat");
    expect(sourceLabelOf("iot-gateway")).toBe("tidak tercatat");
  });
});

describe("evidenceSummary", () => {
  it("menghitung batch yang buktinya belum cukup tanpa menyembunyikan total", () => {
    const rows = evidenceRows([
      batch(),
      batch({
        id: "b2",
        evidence: {
          ...batch().evidence,
          temperature_observation: "missing",
          evidence_state: "insufficient",
          evidence_sufficient: false,
        },
      }),
      { ...batch(), id: "b3", evidence: undefined },
    ]);
    const ringkas = evidenceSummary(rows);
    expect(ringkas.total).toBe(3);
    expect(ringkas.sufficient).toBe(1);
    expect(ringkas.insufficient).toBe(1);
    expect(ringkas.unknown).toBe(1);
    expect(ringkas.perluVerifikasi).toBe(2);
  });

  it("komoditas ambient tanpa log tidak menambah hitungan perlu-verifikasi", () => {
    const rows = evidenceRows([
      batch({
        commodity: "beras",
        evidence: {
          ...batch().evidence,
          commodity_profile: PROFIL_BERAS,
          temperature_observation: "missing",
          evidence_state: "insufficient",
          evidence_sufficient: false,
          evaluated_safety_status: "pass",
        },
      }),
    ]);
    expect(evidenceSummary(rows).perluVerifikasi).toBe(0);
  });

  it("daftar kosong menghasilkan nol, bukan undefined", () => {
    expect(evidenceSummary([])).toEqual({
      total: 0,
      sufficient: 0,
      insufficient: 0,
      ambiguous: 0,
      unknown: 0,
      perluVerifikasi: 0,
    });
  });
});
