// Kontrak kartu "Bukti suhu" versi redesign 27 Okt 2026.
//
// Yang diuji adalah JANJI kartu, bukan kelas CSS-nya: angka keadaan berasal dari
// ringkasan server, baris yang membelokkan alokasi tampil lebih dulu, asal log
// disebut apa adanya, dan tidak ada label yang dikarang saat data kosong.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import TemperatureEvidenceCard from "../components/TemperatureEvidenceCard";
import type { EvidenceRow, EvidenceSummary } from "../lib/food-safety";

function baris(over: Partial<EvidenceRow> = {}): EvidenceRow {
  const dasar: EvidenceRow = {
    id: "b1",
    commodity: "telur",
    observation: "observed",
    observationLabel: "Teramati",
    state: "sufficient",
    stateLabel: "Bukti cukup",
    tone: "ok",
    sufficient: true,
    sampleCount: 4,
    observedAt: null,
    source: "seed",
    sourceLabel: "log simulasi",
    profileVersion: "sim-2026-10-27.v1",
    policyKind: "simulated_policy",
    coldChainRequired: true,
    reasons: [],
  };
  return { ...dasar, ...over };
}

function ringkasan(rows: readonly EvidenceRow[]): EvidenceSummary {
  const out: EvidenceSummary = {
    total: rows.length,
    sufficient: 0,
    insufficient: 0,
    ambiguous: 0,
    unknown: 0,
    perluVerifikasi: 0,
  };
  for (const row of rows) {
    out[row.state] += 1;
    if (!row.sufficient && row.coldChainRequired !== false) out.perluVerifikasi += 1;
  }
  return out;
}

function render(rows: EvidenceRow[]): string {
  return renderToStaticMarkup(
    <TemperatureEvidenceCard rows={rows} summary={ringkasan(rows)} />
  );
}

describe("TemperatureEvidenceCard", () => {
  it("menampilkan komposisi bukti sebagai angka, bukan satu kalimat berjalan", () => {
    const html = render([
      baris(),
      baris({ id: "b2", commodity: "ayam", state: "insufficient", stateLabel: "Bukti kurang", tone: "warn", sufficient: false, sampleCount: 0 }),
      baris({ id: "b3", commodity: "beras", state: "unknown", stateLabel: "Tidak tercatat", tone: "muted", sufficient: false, sampleCount: null, coldChainRequired: null, profileVersion: null }),
    ]);
    // Lencana kepala kartu: "1 dari 3 cukup bukti" (bukan kalimat berjalan).
    expect(html).toContain("1 dari 3 cukup bukti");
    expect(html).toContain("bertentangan");
    expect(html).toContain("tidak tercatat");
    // aria-label meter memberi alternatif teks untuk grafiknya.
    expect(html).toContain("3 batch diperiksa");
    expect(html).toContain("1 bukti cukup");
  });

  it("mendahulukan batch yang membelokkan alokasi, tanpa membalik urutan sesama tone", () => {
    const html = render([
      baris({ id: "cukup-1", commodity: "telur" }),
      baris({ id: "kurang-1", commodity: "ayam", state: "insufficient", stateLabel: "Bukti kurang", tone: "warn", sufficient: false }),
      baris({ id: "cukup-2", commodity: "wortel" }),
    ]);
    const kurang = html.indexOf("Bukti kurang");
    const cukup = html.indexOf("Bukti cukup");
    expect(kurang).toBeGreaterThan(-1);
    expect(cukup).toBeGreaterThan(-1);
    expect(kurang).toBeLessThan(cukup);
    // sesama cukup: urutan asli dipertahankan (telur sebelum wortel)
    expect(html.indexOf("telur")).toBeLessThan(html.indexOf("wortel"));
  });

  it("menyebut asal log dan sifat profil apa adanya, tidak menaikkan jadi sensor", () => {
    const html = render([baris()]);
    expect(html).toContain("log simulasi");
    expect(html).toContain("simulasi, bukan standar regulasi");
    expect(html).not.toContain("sensor aktif");
  });

  it("komoditas tanpa profil dinyatakan tidak dinilai, bukan dianggap aman", () => {
    const html = render([
      baris({ profileVersion: null, policyKind: null, state: "unknown", stateLabel: "Tidak tercatat", tone: "muted", sufficient: false }),
    ]);
    expect(html).toContain("belum punya profil suhu — tidak dinilai");
  });

  it("menghitung batch yang menuntut bukti tetapi belum cukup", () => {
    const html = render([
      baris(),
      baris({ id: "b2", state: "insufficient", stateLabel: "Bukti kurang", tone: "warn", sufficient: false }),
      baris({ id: "b3", commodity: "beras", coldChainRequired: false, state: "unknown", stateLabel: "Tidak tercatat", tone: "muted", sufficient: false }),
    ]);
    // beras ambient tidak dihitung menuntut bukti suhu
    expect(html).toContain("1 batch");
    expect(html).toContain("menuntut bukti suhu tetapi belum cukup");
  });

  it("memotong daftar di 6 baris dan menautkan tabel lengkap", () => {
    const rows: EvidenceRow[] = [];
    for (let i = 0; i < 8; i += 1) rows.push(baris({ id: `x${i}`, commodity: `kom${i}` }));
    const html = render(rows);
    expect(html).toContain("Ditampilkan 6 dari 8 batch");
    expect(html).toContain('href="#safety-daftar"');
    expect(html).not.toContain("kom7");
  });

  it("keadaan kosong tidak mengarang angka", () => {
    const html = render([]);
    expect(html).toContain("Belum ada batch pada cakupan ini.");
    expect(html).not.toContain("cukup bukti</span>");
    expect(html).not.toContain("Bukti cukup");
  });

  it("profil suhu yang sama untuk semua baris dicetak SEKALI, bukan diulang tiap baris", () => {
    // Permintaan pemilik 28 Okt 2026: enam baris yang mengulang kalimat profil
    // yang sama menutupi hal yang memang beda antar-baris (asal log, sampel,
    // alasan server). Kontrak: kalimat sifat profil muncul tepat sekali.
    const html = render([
      baris({ id: "p1", commodity: "telur" }),
      baris({ id: "p2", commodity: "ayam" }),
    ]);
    expect((html.match(/simulasi, bukan standar regulasi/g) ?? []).length).toBe(1);
    expect(html).toContain("Profil suhu berlaku untuk semua batch di atas");
  });

  it("kalau profilnya TIDAK seragam, tiap baris tetap menyebut miliknya sendiri", () => {
    const html = render([
      baris({ id: "q1", commodity: "telur" }),
      baris({
        id: "q2",
        commodity: "beras",
        profileVersion: null,
        policyKind: null,
        state: "unknown",
        stateLabel: "Tidak tercatat",
        tone: "muted",
        sufficient: false,
      }),
    ]);
    expect(html).not.toContain("Profil suhu berlaku untuk semua batch di atas");
    expect(html).toContain("Profil sim-2026-10-27.v1 — simulasi, bukan standar regulasi");
    expect(html).toContain("belum punya profil suhu — tidak dinilai");
  });

  it("meneruskan alasan evaluasi sebagai kalimat, bukan diringkas ulang", () => {
    const html = render([
      baris({
        reasons: ["suhu di luar rentang selama 660 menit, melewati ambang gagal 30 menit"],
      }),
    ]);
    // Label kartu menyebut "Alasan", bukan "Alasan server": pembaca tidak perlu
    // tahu bagian sistem mana yang menghitungnya.
    expect(html).toContain("Alasan:");
    expect(html).not.toContain("Alasan server");
    // Kalimat server diteruskan utuh, tidak dipotong/diparafrase kartu.
    expect(html).toContain("suhu di luar rentang selama 660 menit, melewati ambang gagal 30 menit");
  });
});
