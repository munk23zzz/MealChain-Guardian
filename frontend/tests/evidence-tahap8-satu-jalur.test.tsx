// TAHAP 8 (29 Okt 2026) — SATU JALUR RENDER.
//
// Yang dijaga di sini bukan tampilan, melainkan fakta bahwa halaman tidak lagi
// punya dua kebenaran:
//   1. saklar `ISI_DIBANGUN_ULANG` benar-benar hilang dari sumber;
//   2. `DecisionDetail` (versi lama) tidak diimpor siapa pun — berkasnya masih
//      ada hanya karena empat tes audit lama masih membaca teksnya;
//   3. enam komponen bagian diimpor dan dirender;
//   4. keadaan kosong memakai `EvidenceEmptyState` (bukan salinan ketiga di
//      dalam komponen halaman).
//
// Kenapa sumber, bukan render: sifat yang diperiksa adalah "hanya ada satu
// jalur", dan itu bisa benar walau markahnya kebetulan mirip. Render saja tidak
// membedakan "satu jalur" dari "dua jalur yang kebetulan sama".
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const baca = (relatif: string) => readFileSync(join(__dirname, "..", relatif), "utf8");

const halaman = baca("components/DecisionEvidence.tsx");
const detail = baca("components/DecisionDetail.tsx");

describe("tahap 8 — satu jalur render", () => {
  it("saklar isi-dibangun-ulang sudah dicabut dari halaman", () => {
    // Komentar yang MENCERITAKAN pencabutan itu boleh tinggal (ia menjelaskan
    // sebab); yang tidak boleh ada adalah kodenya — penetapan nilai atau
    // pemakaian sebagai syarat.
    const kode = halaman
      .replace(/\{\/\*[\s\S]*?\*\/\}/g, "") // komentar JSX
      .replace(/\/\*[\s\S]*?\*\//g, "") // komentar blok
      .split("\n")
      .filter((baris) => !baris.trim().startsWith("//"))
      .join("\n");
    expect(kode).not.toContain("ISI_DIBANGUN_ULANG");
  });

  it("versi lama tidak diimpor lagi, dan berkasnya mengaku pensiun", () => {
    expect(halaman).not.toMatch(/import\s+DecisionDetail\s+from/);
    // Berkasnya masih ada untuk empat tes audit lama; kalau ia diam-diam dipakai
    // lagi, peringatan di kepalanya hilang dan utangnya terlupakan.
    expect(detail).toContain("SUDAH TIDAK DIRENDER");
  });

  it("enam komponen bagian diimpor dan dirender berurutan", () => {
    const urutan = [
      "DecisionSummary",
      "DecisionApproval",
      "DecisionCostEvidence",
      "DecisionSafetySupplier",
      "DecisionIdentityBatch",
      "DecisionTraceIntegrity",
    ];
    let posisiTerakhir = -1;
    for (const nama of urutan) {
      expect(halaman, `${nama} tidak diimpor`).toMatch(
        new RegExp(`import ${nama} from "\\./${nama}";`),
      );
      const posisi = halaman.indexOf(`<${nama}`);
      expect(posisi, `${nama} tidak dirender`).toBeGreaterThan(posisiTerakhir);
      posisiTerakhir = posisi;
    }
  });

  it("keadaan kosong memakai EvidenceEmptyState, bukan salinan di halaman", () => {
    expect(halaman).toContain('import EvidenceEmptyState from "./EvidenceEmptyState";');
    expect(halaman).toContain("<EvidenceEmptyState");
    // Kalimat keadaan kosong hanya boleh hidup di satu berkas.
    expect(halaman).not.toContain("Belum ada keputusan dipilih");
    expect(halaman).not.toContain("Memuat keputusan…");
  });

  it("tiap bagian tetap membawa penanda data-bagian untuk urutan", () => {
    const penanda: Array<[string, string]> = [
      ["DecisionSummary.tsx", "ringkasan"],
      ["DecisionApproval.tsx", "keputusan"],
      ["DecisionCostEvidence.tsx", "bukti"],
      ["DecisionSafetySupplier.tsx", "keamanan"],
      ["DecisionIdentityBatch.tsx", "identitas"],
      ["DecisionTraceIntegrity.tsx", "jejak"],
    ];
    for (const [berkas, bagian] of penanda) {
      expect(baca(`components/${berkas}`), `${berkas} tanpa data-bagian="${bagian}"`).toContain(
        `data-bagian="${bagian}"`,
      );
    }
  });
});
