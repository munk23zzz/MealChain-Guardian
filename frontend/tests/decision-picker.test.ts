// Kontrak pemilih keputusan (dropdown "Pilih keputusan" di halaman Decision &
// Evidence dan Agent Log). Masalah yang diselesaikan: dulu satu <option> per
// keputusan dengan istilah backend mentah ("regional_balance · proposed · id"),
// berurutan apa adanya — pengguna tidak tahu mana yang perlu ditindak.
//
// Aturannya (semua dari data, tanpa istilah baru yang dikarang):
//   - urutan kelompok: menunggu tindakan → diusulkan → tidak menunggu tindakan;
//   - istilah jenis keputusan memakai peta yang SUDAH ada (DECISION_TYPE_LABELS);
//   - urutan di dalam "menunggu tindakan" memakai pendingDecisions(): yang sudah
//     lewat dulu, lalu jatuh tempo terdekat, lalu yang tanggalnya tidak terbaca;
//   - status tak dikenal ditulis apa adanya (garis bawah → spasi), tidak ditebak;
//   - keputusan tanpa id dilewati (tidak membuat opsi palsu).
import { describe, expect, it } from "vitest";

import { decisionGroups } from "../lib/decision-picker";

const NOW = new Date("2026-10-11T02:30:00Z");

const ID_A = "ef347f91-6ebf-481c-a790-128ad3eba6ec"; // lewat 13 mnt
const ID_B = "cdde80a9-7858-4274-ac2a-d3dceeac4635"; // 6 jam 30 mnt lagi
const ID_C = "5e0f758c-363f-4ab1-80f6-8c0d4afe23cf"; // tenggat tidak terbaca
const ID_D = "b24f509d-decc-40c0-bec7-4d083da70906"; // proposed
const ID_E = "fb6a5651-d20e-4437-b6d2-1aaaf312e112"; // rejected

const DECISIONS = [
  { decision_id: ID_D, decision_type: "safety_disruption", status: "proposed", created_at: "2026-10-10T18:16:47Z" },
  { decision_id: ID_A, decision_type: "regional_balance", status: "pending_approval", created_at: "2026-10-11T02:00:00Z", expires_at: "2026-10-11T02:16:47Z" },
  { decision_id: ID_E, decision_type: "regional_balance", status: "rejected", created_at: "2026-10-09T04:00:00Z" },
  { decision_id: ID_B, decision_type: "safety_disruption", status: "verifier_flagged", created_at: "2026-10-11T01:00:00Z", expires_at: "2026-10-11T09:00:00Z" },
  { decision_id: ID_C, decision_type: "price_anomaly", status: "pending_approval", created_at: "2026-10-11T00:30:00Z", expires_at: "" },
];

function optionsOf(groups: ReturnType<typeof decisionGroups>) {
  return groups.flatMap((group) => group.options.map((option) => option.value));
}

describe("decisionGroups — struktur", () => {
  it("mengelompokkan: menunggu tindakan, diusulkan, lalu sisanya", () => {
    const groups = decisionGroups(DECISIONS, NOW);
    expect(groups.map((g) => g.id)).toEqual(["action", "proposed", "rest"]);
    expect(groups.map((g) => g.label)).toEqual([
      "Menunggu tindakan (3)",
      "Diusulkan, belum masuk persetujuan (1)",
      "Tidak menunggu tindakan (1)",
    ]);
  });

  it("setiap keputusan muncul tepat sekali, tanpa duplikat", () => {
    const values = optionsOf(decisionGroups(DECISIONS, NOW));
    expect(values.sort()).toEqual([ID_A, ID_B, ID_C, ID_D, ID_E].sort());
    expect(new Set(values).size).toBe(values.length);
  });

  it("keputusan tanpa id dilewati, bukan jadi opsi palsu", () => {
    const groups = decisionGroups(
      [{ decision_type: "regional_balance", status: "pending_approval" }],
      NOW
    );
    expect(optionsOf(groups)).toEqual([]);
  });

  it("kelompok yang kosong tidak ditampilkan", () => {
    const groups = decisionGroups([{ decision_id: ID_D, decision_type: "safety_disruption", status: "proposed" }], NOW);
    expect(groups.map((g) => g.id)).toEqual(["proposed"]);
  });
});

describe("decisionGroups — urutan di dalam kelompok", () => {
  it("menunggu tindakan: sudah lewat dulu, lalu jatuh tempo terdekat, lalu tanpa tanggal", () => {
    const [action] = decisionGroups(DECISIONS, NOW);
    expect(action.options.map((o) => o.value)).toEqual([ID_A, ID_B, ID_C]);
  });

  it("diusulkan & sisanya: terbaru lebih dulu", () => {
    const groups = decisionGroups(
      [
        { decision_id: "x1", decision_type: "regional_balance", status: "proposed", created_at: "2026-10-08T00:00:00Z" },
        { decision_id: "x2", decision_type: "regional_balance", status: "proposed", created_at: "2026-10-10T00:00:00Z" },
      ],
      NOW
    );
    expect(groups[0].options.map((o) => o.value)).toEqual(["x2", "x1"]);
  });
});

describe("decisionGroups — label memakai bahasa manusia", () => {
  it("istilah backend mentah TIDAK muncul lagi di label", () => {
    const teks = decisionGroups(DECISIONS, NOW)
      .flatMap((g) => g.options.map((o) => o.label))
      .join(" | ");
    expect(teks).not.toContain("regional_balance");
    expect(teks).not.toContain("safety_disruption");
    expect(teks).not.toContain("price_anomaly");
    expect(teks).not.toContain("pending_approval");
    expect(teks).toContain("Alokasi regional direkomendasikan");
    expect(teks).toContain("Pengalihan pasokan (gangguan keamanan)");
    expect(teks).toContain("Penyesuaian harga direkomendasikan");
  });

  it("yang menunggu tindakan memuat sisa waktu dan id pendek 8 karakter", () => {
    const [action] = decisionGroups(DECISIONS, NOW);
    expect(action.options[0].label).toBe(
      "Alokasi regional direkomendasikan · Lewat 13 mnt · ef347f91"
    );
    expect(action.options[1].label).toContain("6 jam 30 mnt lagi");
  });

  it("tenggat yang tidak terbaca: bagian waktunya dihilangkan, bukan ditulis '—'", () => {
    const [action] = decisionGroups(DECISIONS, NOW);
    const tanpaTanggal = action.options.find((o) => o.value === ID_C)!;
    expect(tanpaTanggal.label).toBe("Penyesuaian harga direkomendasikan · 5e0f758c");
  });

  it("kalau jam klien belum siap (now null), tidak ada klaim sisa waktu", () => {
    const [action] = decisionGroups(DECISIONS, null);
    expect(action.options[0].label).toBe("Alokasi regional direkomendasikan · ef347f91");
  });

  it("status yang sudah diputus ditulis dalam bahasa manusia", () => {
    const [, , rest] = decisionGroups(DECISIONS, NOW);
    expect(rest.options[0].label).toContain("ditolak");
  });

  it("status tak dikenal ditulis apa adanya (garis bawah → spasi)", () => {
    const groups = decisionGroups(
      [{ decision_id: "z1", decision_type: "sesuatu_baru", status: "weird_state" }],
      NOW
    );
    expect(groups[0].options[0].label).toContain("weird state");
    expect(groups[0].options[0].label).toContain("sesuatu baru");
  });
});

// Keputusan owner 17 Okt: pemilih TIDAK menawarkan keputusan yang sudah lewat
// tenggat secara default. Alasannya terukur: dari 304 opsi, mayoritas berlabel
// "Lewat 2 jam…" dan yang dipilih juri berakhir tanpa tombol Eksekusi (backend
// menolak dengan 409 "decision expired") — terbaca seperti aplikasi rusak.
describe("decisionGroups — sembunyikan yang lewat tenggat", () => {
  it("default tetap memuat yang lewat (kompatibel dengan pemanggil lama)", () => {
    const ids = optionsOf(decisionGroups(DECISIONS, NOW));
    expect(ids).toContain(ID_A); // lewat 13 mnt
  });

  it("includeExpired=false membuang yang lewat, menyisakan yang masih berlaku", () => {
    const groups = decisionGroups(DECISIONS, NOW, { includeExpired: false });
    const ids = optionsOf(groups);
    expect(ids).not.toContain(ID_A);
    // yang masih hidup tetap ada, termasuk yang tenggatnya tak terbaca
    expect(ids).toContain(ID_B);
    expect(ids).toContain(ID_C);
    expect(groups[0].label).toBe("Menunggu tindakan (2)");
  });

  it("keputusan yang sedang dipilih tetap ditampilkan walau sudah lewat", () => {
    // Tanpa ini, tautan bersama ke keputusan lama membuat <select> tanpa opsi
    // yang cocok → nilainya tampak kosong dan halaman terlihat rusak.
    const groups = decisionGroups(DECISIONS, NOW, {
      includeExpired: false,
      keep: ID_A,
    });
    const ids = optionsOf(groups);
    expect(ids).toContain(ID_A);
    expect(ids.filter((id) => id === ID_A)).toHaveLength(1);
  });

  it("keep yang sudah termasuk daftar tidak diduplikasi", () => {
    const groups = decisionGroups(DECISIONS, NOW, {
      includeExpired: false,
      keep: ID_B,
    });
    const ids = optionsOf(groups);
    expect(ids.filter((id) => id === ID_B)).toHaveLength(1);
  });

  it("status proposed tidak ikut disaring (belum punya tenggat tindakan)", () => {
    const ids = optionsOf(decisionGroups(DECISIONS, NOW, { includeExpired: false }));
    expect(ids).toContain(ID_D);
  });

  it("keputusan yang sudah diputus tetap tampil walau tenggatnya lewat", () => {
    // Menyembunyikan riwayat karena tanggalnya lewat akan memutus jalan ke
    // bukti & re-propose. Yang disaring HANYA yang masih menunggu tindakan.
    const groups = decisionGroups(
      [
        {
          decision_id: "r1",
          decision_type: "regional_balance",
          status: "rejected",
          expires_at: "2026-10-01T00:00:00Z",
          created_at: "2026-09-30T00:00:00Z",
        },
        {
          decision_id: "x1",
          decision_type: "regional_balance",
          status: "pending_approval",
          expires_at: "2026-10-01T00:00:00Z",
          created_at: "2026-09-30T00:00:00Z",
        },
      ],
      NOW,
      { includeExpired: false }
    );
    const ids = optionsOf(groups);
    expect(ids).toContain("r1");
    expect(ids).not.toContain("x1");
  });
});
