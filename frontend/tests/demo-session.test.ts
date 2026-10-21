/**
 * Kontrak sesi demo (024/025) — logika murni + bentuk sumber komponen.
 *
 * Yang dijaga:
 * - Hitungan mundur memakai `remaining_seconds` SERVER; jam browser hanya
 *   mengurangi detik yang berjalan di layar, tidak menghitung sendiri.
 * - Label waktu berbahasa Indonesia dan tidak pernah negatif.
 * - "Data hanya bisa diubah selama sesi" bisa diuji sebagai fungsi, bukan
 *   hanya niat di komentar.
 * - Banner kosong TIDAK pernah muncul saat mode sesi mati (pengembangan) —
 *   kalau muncul, aplikasi dev terlihat "kosong" padahal datanya ada.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  bolehUbahData,
  formatSisa,
  keadaanSesi,
  pesanSesi,
  peringatanWaktu,
  sisaDetik,
  type StatusSesiDemo,
} from "../lib/demo-session";

const dasar: StatusSesiDemo = {
  active: true,
  enforced: true,
  session_id: "abc",
  status: "active",
  expires_at: "2026-10-20T05:00:00+00:00",
  anchor_now: "2026-10-20T03:00:00+00:00",
  server_now: "2026-10-20T03:00:00+00:00",
  remaining_seconds: 3600,
};

describe("sisaDetik — server yang menentukan", () => {
  it("mengurangi detik yang berjalan di layar", () => {
    expect(sisaDetik(dasar, 0)).toBe(3600);
    expect(sisaDetik(dasar, 60)).toBe(3540);
  });

  it("tidak pernah negatif", () => {
    expect(sisaDetik(dasar, 99999)).toBe(0);
  });

  it("sesi mati selalu 0, walau angka server masih tersisa", () => {
    expect(sisaDetik({ ...dasar, active: false }, 0)).toBe(0);
    expect(sisaDetik(null, 0)).toBe(0);
  });
});

describe("formatSisa — satuan Indonesia", () => {
  it("jam dan menit", () => {
    expect(formatSisa(3600)).toBe("1 j 00 m");
    expect(formatSisa(6420)).toBe("1 j 47 m");
  });
  it("menit dan detik", () => {
    expect(formatSisa(432)).toBe("7 m 12 d");
  });
  it("detik saja dan habis", () => {
    expect(formatSisa(9)).toBe("9 d");
    expect(formatSisa(0)).toBe("habis");
    expect(formatSisa(-5)).toBe("habis");
  });
});

describe("keadaanSesi", () => {
  it("mati saat mode sesi tidak diberlakukan", () => {
    expect(keadaanSesi({ ...dasar, enforced: false, active: false })).toBe("mati");
    expect(keadaanSesi(null)).toBe("mati");
  });
  it("berjalan saat aktif", () => {
    expect(keadaanSesi(dasar)).toBe("berjalan");
  });
  it("kosong dan habis dibedakan", () => {
    expect(keadaanSesi({ ...dasar, active: false, status: "kosong" })).toBe("kosong");
    expect(keadaanSesi({ ...dasar, active: false, status: "expired" })).toBe("habis");
    expect(keadaanSesi({ ...dasar, active: false, status: "ended" })).toBe("habis");
  });
});

describe("bolehUbahData — aturan 'hanya selama sesi'", () => {
  it("mode sesi mati: boleh (pengembangan tidak berubah)", () => {
    expect(bolehUbahData({ ...dasar, enforced: false, active: false })).toBe(true);
    expect(bolehUbahData(null)).toBe(true);
  });
  it("mode sesi menyala: hanya saat aktif", () => {
    expect(bolehUbahData(dasar)).toBe(true);
    expect(bolehUbahData({ ...dasar, active: false, status: "expired" })).toBe(false);
    expect(bolehUbahData({ ...dasar, active: false, status: "kosong" })).toBe(false);
  });
});

describe("pesanSesi & peringatanWaktu", () => {
  it("menyebut sisa waktu saat berjalan", () => {
    expect(pesanSesi(dasar, 0)).toContain("Sesi demo berjalan");
    expect(pesanSesi(dasar, 0)).toContain("1 j 00 m");
  });
  it("jujur saat kosong dan habis", () => {
    expect(pesanSesi({ ...dasar, active: false, status: "kosong" })).toContain(
      "Belum ada sesi demo"
    );
    expect(pesanSesi({ ...dasar, active: false, status: "expired" })).toContain(
      "sudah berakhir"
    );
  });

  it("tidak menjanjikan data hilang padahal data contoh tetap tampil", () => {
    // Audit 21 Okt 2026: template sengaja TIDAK berstempel, jadi "Akhiri sesi"
    // hanya membuang perubahan sesi. Kalimat lama ("dikosongkan kembali")
    // membuat pengguna mengira layar akan kosong.
    const habis = pesanSesi({ ...dasar, active: false, status: "expired" });
    expect(habis).not.toContain("dikosongkan");
    expect(habis).toContain("data contoh");
    const kosong = pesanSesi({ ...dasar, active: false, status: "kosong" });
    expect(kosong).not.toContain("dikosongkan");
  });
  it("peringatan hanya saat sisa ≤ 5 menit", () => {
    expect(peringatanWaktu(600)).toBeNull();
    expect(peringatanWaktu(300)).toContain("Sisa 5 m 00 d");
    expect(peringatanWaktu(0)).toContain("habis");
  });
});

describe("kontrak sumber komponen", () => {
  const akar = path.resolve(__dirname, "..");
  const panel = readFileSync(path.join(akar, "components/DemoControlPanel.tsx"), "utf8");
  const banner = readFileSync(path.join(akar, "components/DemoSessionBanner.tsx"), "utf8");
  const api = readFileSync(path.join(akar, "lib/api.ts"), "utf8");

  it("panel memakai endpoint sesi, bukan jam browser", () => {
    expect(api).toContain('"/demo/session"');
    expect(api).toContain('"/demo/session/start"');
    expect(api).toContain('"/demo/session/extend"');
    expect(api).toContain('"/demo/session/end"');
    expect(panel).toContain("startDemoSession");
    expect(panel).toContain("extendDemoSession");
    expect(panel).toContain("endDemoSession");
    // Hitungan mundur dihitung lewat helper yang menerima `remaining_seconds`
    // server — bukan jam browser.
    expect(panel).toContain("sisaDetik(sesi, tickSesi)");
    expect(panel).toContain("formatSisa(sisaSekarang)");
    expect(panel).toContain('role="timer"');
    // Hitungan mundur tersinkron ulang berkala, bukan sekali baca.
    expect(panel).toContain("20000");
  });

  it("tombol utama memulai sesi saat mode sesi menyala", () => {
    expect(panel).toContain("if (sesi?.enforced)");
    expect(panel).toContain("refreshDemoToToday(token)");
    expect(panel).toContain("Sesi demo sudah berjalan — data tidak di-reset.");
  });

  it("banner kosong hanya muncul saat enforced dan tidak aktif", () => {
    expect(banner).toContain("if (!status?.enforced || status.active) return null;");
    expect(banner).toContain("Buka Demo Control");
    expect(banner).not.toContain("fetch(");
  });

  it("banner memakai satu sumber kalimat (pesanSesi), bukan salinan sendiri", () => {
    // Dua kalimat berbeda untuk keadaan yang sama = satu di antaranya pasti salah.
    expect(banner).toContain("pesanSesi(");
    expect(banner).not.toContain("sudah dibersihkan");
  });

  it("kartu sesi berbahasa pengguna, tanpa petunjuk tombol panel lain", () => {
    // Status di kartu sesi sempat menyuruh menekan “Buat/perbarui data” yang
    // tinggal di panel DATA, dan mengulang pesanSesi dengan kalimat lain.
    // Saat sesi kosong, petunjuknya sudah dibawa pesanSesi — baris status
    // kedua yang mengulang kalimat itu justru mengulang informasi.
    expect(panel).not.toContain("Data demo belum dimuat — mulai dengan Siapkan data demo.");
    expect(panel).toContain("Data demo siap dipakai selama sesi ini.");
    expect(panel).not.toContain("Buat/perbarui data");
    expect(panel).not.toContain("Data demo hanya bisa diubah selama sesi");
    expect(panel.toLowerCase()).not.toContain("snapshot kanonik");
    expect(panel).not.toContain("Seeder relatif");
  });
});
