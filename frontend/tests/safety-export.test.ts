// Dokumen `07-safety-evidence.md` §4.2 butir 6 — jalan ekspor dari modul safety.
//
// Halaman "Keamanan Pangan" dulu tidak punya tombol unduh sama sekali, padahal
// seluruh nilai yang dibutuhkan audit sudah ada di layar. Ekspor di sini
// BACA-SAJA: dibangun dari baris yang benar-benar tampil (`SafetyRow`) dan
// ringkasan yang sudah dipakai kartu — tidak memanggil endpoint baru dan tidak
// menghitung ulang aturan safety.
//
// Aturan yang dikunci:
//  - nilai yang diekspor = nilai yang tercetak (label Indonesia, "—" untuk yang
//    tidak terbaca), bukan enum mentah;
//  - sel berawalan `= + - @` diberi apostrof (formula injection), aturan yang
//    sama dengan ekspor dossier di `lib/export.ts`;
//  - skor/berat yang tidak terbaca tetap tidak terbaca (tidak diisi 0).
import { describe, expect, it } from "vitest";

import { safetySummaryOfRows, safetyRows, safetyDecisions } from "../lib/food-safety";
import { batchesToCsv, safetyExportJson } from "../lib/safety-export";

const NOW = new Date("2026-10-11T06:00:00Z");

const BATCHES = [
  {
    id: "b1",
    location: "Cianjur",
    commodity: "telur",
    quantity_kg: 400,
    safety_status: "pass",
    freshness_score: 0.69,
    usable_until: "2026-10-11T18:00:00Z",
  },
  {
    id: "b2",
    location: "Surabaya",
    commodity: "=CMD()",
    quantity_kg: 120,
    safety_status: "fail",
    freshness_score: null,
    usable_until: null,
    quarantine_status: "quarantined",
  },
];

const DECISIONS = [
  {
    decision_id: "d1",
    decision_type: "safety_disruption",
    status: "pending_approval",
    quantity_kg: 492,
    valid: true,
    seconds_remaining: 600,
    created_at: "2026-10-16T10:00:00Z",
    commodity_name: "telur",
  },
];

describe("batchesToCsv — ekspor baca-saja nilai yang tampil", () => {
  const rows = safetyRows(BATCHES, NOW);

  it("kepala kolom menyebut apa yang tercetak di tabel", () => {
    const csv = batchesToCsv(rows);
    const kepala = csv.split("\r\n")[0];
    expect(kepala).toBe(
      "lokasi,komoditas,jumlah,status keamanan,karantina,kesegaran,layak sampai,sisa masa,langkah"
    );
  });

  it("baris memakai label tampilan, bukan enum mentah", () => {
    const csv = batchesToCsv(rows);
    expect(csv).toContain('"Cianjur","telur","400 kg","Aman"');
    expect(csv).toContain('"Gagal uji"');
    expect(csv).toContain('"Ditahan"');
    // Nilai yang tidak terbaca tetap "—", bukan 0.
    expect(csv).toContain('"—"');
  });

  it("menjaga formula injection seperti ekspor dossier", () => {
    const csv = batchesToCsv(rows);
    expect(csv).toContain("\"'=CMD()\"");
    expect(csv).not.toContain(',"=CMD()"');
  });

  it("tidak ada baris → tetap kepala kolom saja", () => {
    const csv = batchesToCsv([]);
    expect(csv.trim().split("\r\n")).toHaveLength(1);
  });
});

describe("safetyExportJson — satu berkas untuk audit", () => {
  const rows = safetyRows(BATCHES, NOW);
  const summary = safetySummaryOfRows(rows);
  const decisions = safetyDecisions(DECISIONS);

  it("memuat batch, ringkasan, dan keputusan yang tampil", () => {
    const parsed = JSON.parse(safetyExportJson({ rows, summary, decisions }));
    expect(parsed.modul).toBe("Keamanan Pangan");
    expect(parsed.batch).toHaveLength(2);
    expect(parsed.batch[0]).toMatchObject({
      id: "b1",
      lokasi: "Cianjur",
      komoditas: "telur",
      jumlah: "400 kg",
      status_keamanan: "Aman",
    });
    // Satu batch dihitung sekali: b2 gagal uji SEKALIGUS ditahan, dan keadaan
    // terkuat (ditahan) yang dipakai — sama seperti tile di layar. Dulu berkas
    // ini menulis gagal 1 + ditahan 1 untuk dua batch, sehingga kategori
    // melebihi `batch_diperiksa` (audit 29 Okt 2026).
    expect(parsed.ringkasan).toMatchObject({
      batch_diperiksa: 2,
      aman: 1,
      gagal_uji: 0,
      ditahan: 1,
    });
    expect(parsed.keputusan_keamanan).toHaveLength(1);
    expect(parsed.keputusan_keamanan[0]).toMatchObject({
      id: "d1",
      komoditas: "telur",
      status: "Menunggu persetujuan",
    });
  });

  it("berat per keadaan: ditahan dan gagal dilaporkan terpisah", () => {
    const parsed = JSON.parse(safetyExportJson({ rows, summary, decisions }));
    // b2 ditahan → beratnya masuk `berat_ditahan`, bukan `berat_gagal_uji`,
    // karena ia tidak lagi dihitung sebagai baris keadaan "gagal".
    expect(parsed.ringkasan.berat_ditahan).toBe("120 kg");
    expect(parsed.ringkasan.berat_gagal_uji).toBe(null);

    // Batch yang gagal tanpa ditahan tetap menimbulkan berat gagal.
    const tanpaKarantina = safetyRows(
      [BATCHES[0], { ...BATCHES[1], quarantine_status: null }],
      NOW
    );
    const ringkasFail = safetySummaryOfRows(tanpaKarantina);
    const berkas = JSON.parse(
      safetyExportJson({ rows: tanpaKarantina, summary: ringkasFail, decisions })
    );
    expect(berkas.ringkasan.berat_gagal_uji).toBe("120 kg");

    // Berat yang tidak terbaca tetap null di berkas — bukan "0 kg": nol berarti
    // "tidak ada berat", padahal beratnya tak terbaca.
    const berkasNull = JSON.parse(
      safetyExportJson({
        rows: tanpaKarantina,
        summary: { ...ringkasFail, failedKg: null },
        decisions,
      })
    );
    expect(berkasNull.ringkasan.berat_gagal_uji).toBe(null);
  });

  it("JSON valid dan deterministik (tanpa cap waktu saat dibangun)", () => {
    const a = safetyExportJson({ rows, summary, decisions });
    const b = safetyExportJson({ rows, summary, decisions });
    expect(a).toBe(b);
    expect(() => JSON.parse(a)).not.toThrow();
    expect(a).not.toContain("undefined");
  });
});
