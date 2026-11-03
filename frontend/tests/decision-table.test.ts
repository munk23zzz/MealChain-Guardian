// Kontrak logika tabel keputusan Agent Log (dokumen 06-agent-log §1, §2.5).
//
// Yang diuji: pemetaan status → keadaan verifikasi, penyaring yang dipakai
// bersama pencarian/komoditas/status, ringkasan yang menyebut sebab, dan
// paginasi. Komponen tabel hanya menyusun markup dari fungsi-fungsi ini.
import { describe, expect, it } from "vitest";

import { paginate } from "../lib/pagination";

import {
  TANPA_KOMODITAS,
  commodityOptions,
  decisionTypeLabel,
  filterDecisions,
  statusLabel,
  tableSummary,
  verificationCounts,
  verificationState,
  DECISION_PAGE_SIZE,
} from "../lib/decision-table";

const baris = (over: Record<string, unknown> = {}) => ({
  decision_id: "aaaa1111-2222-3333-4444-555566667777",
  decision_type: "supplier_procurement",
  status: "pending_approval",
  quantity_kg: 640,
  commodity_name: "beras",
  supplier_name: "CV Tunas",
  target_location_name: "Bandung",
  ...over,
});

describe("verificationState", () => {
  it("approved/executed = terverifikasi (tak mungkin tanpa verifikasi)", () => {
    expect(verificationState(baris({ status: "approved" }))).toBe("terverifikasi");
    expect(verificationState(baris({ status: "executed" }))).toBe("terverifikasi");
  });

  it("pending = menunggu, rejected = ditolak", () => {
    expect(verificationState(baris({ status: "pending_approval" }))).toBe("menunggu");
    expect(verificationState(baris({ status: "rejected" }))).toBe("ditolak");
  });

  it("status tak dikenal tidak dikarang menjadi salah satu keadaan", () => {
    expect(verificationState(baris({ status: "draft" }))).toBe("lainnya");
    expect(verificationState(baris({ status: "" }))).toBe("lainnya");
  });
});

describe("label manusia", () => {
  it("jenis keputusan diterjemahkan; kode tak dikenal ditampilkan apa adanya", () => {
    expect(decisionTypeLabel("supplier_procurement")).toBe("Pengadaan dari pemasok");
    expect(decisionTypeLabel("regional_balance")).toBe("Penyeimbangan pasokan regional");
    expect(decisionTypeLabel("sesuatu_baru")).toBe("sesuatu_baru");
    expect(decisionTypeLabel(null)).toBe("—");
  });

  it("status diterjemahkan; kosong jadi —", () => {
    expect(statusLabel("pending_approval")).toBe("Menunggu persetujuan");
    expect(statusLabel("executed")).toBe("Dieksekusi");
    expect(statusLabel(undefined)).toBe("—");
  });
});

describe("filterDecisions", () => {
  const rows = [
    baris(),
    baris({ decision_id: "bbbb2222-2222-3333-4444-555566667777", status: "executed", commodity_name: "telur", decision_type: "regional_balance" }),
    baris({ decision_id: "cccc3333-2222-3333-4444-555566667777", status: "rejected", commodity_name: null }),
  ];

  it("tanpa filter mengembalikan semua", () => {
    expect(filterDecisions(rows)).toHaveLength(3);
  });

  it("teks mencari kode DAN label (pengguna mengetik bahasa manusia)", () => {
    // Dua baris jenisnya supplier_procurement (baris 2 punya status rejected).
    expect(filterDecisions(rows, { query: "pengadaan" })).toHaveLength(2);
    expect(filterDecisions(rows, { query: "supplier_procurement" })).toHaveLength(2);
    expect(filterDecisions(rows, { query: "dieksekusi" })).toHaveLength(1);
    expect(filterDecisions(rows, { query: "tunas" })).toHaveLength(3);
  });

  it("id pendek (8 karakter) bisa dicari — itulah yang tampil di tabel", () => {
    expect(filterDecisions(rows, { query: "cccc3333" })).toHaveLength(1);
  });

  it("komoditas dicocokkan persis, bukan sebagian", () => {
    expect(filterDecisions(rows, { commodity: "telur" })).toHaveLength(1);
    expect(filterDecisions(rows, { commodity: "tel" })).toHaveLength(0);
  });

  it("status verifikasi memakai pemetaan yang sama dengan kolom", () => {
    expect(filterDecisions(rows, { verification: "menunggu" })).toHaveLength(1);
    expect(filterDecisions(rows, { verification: "terverifikasi" })).toHaveLength(1);
    expect(filterDecisions(rows, { verification: "ditolak" })).toHaveLength(1);
  });

  it("filter digabung dengan AND", () => {
    expect(
      filterDecisions(rows, { query: "telur", commodity: "telur", verification: "terverifikasi" })
    ).toHaveLength(1);
    expect(
      filterDecisions(rows, { query: "telur", commodity: "beras" })
    ).toHaveLength(0);
  });

  it("query spasi tidak menyaring apa pun", () => {
    expect(filterDecisions(rows, { query: "   " })).toHaveLength(3);
  });
});

describe("commodityOptions & counts", () => {
  const rows = [
    baris({ commodity_name: "beras" }),
    baris({ commodity_name: "Beras" }),
    baris({ commodity_name: "telur" }),
    baris({ commodity_name: null }),
  ];

  it("komoditas diambil dari data (case-insensitive), yang kosong dapat opsinya sendiri", () => {
    const opts = commodityOptions(rows);
    // Sejak 29 Okt 2026 baris tanpa komoditas TIDAK lagi "dilewati" diam-diam:
    // ia mendapat opsi "Tanpa komoditas" supaya hitungan "Semua" bisa
    // ditelusuri sampai baris terakhir.
    expect(
      opts.map((o) => o.value.toLowerCase()).filter((v) => v !== TANPA_KOMODITAS)
    ).toEqual(["beras", "telur"]);
    expect(opts[0].count).toBe(2);
    expect(opts.find((o) => o.value === TANPA_KOMODITAS)?.count).toBe(1);
  });

  it("hitungan status = hitungan baris yang sama dengan filter", () => {
    const counts = verificationCounts(rows);
    expect(counts.all).toBe(4);
    expect(counts.menunggu).toBe(4);
    expect(counts.terverifikasi + counts.ditolak).toBe(0);
  });
});

describe("tableSummary", () => {
  it("menyebut jumlah tampil/total + sebab penyaringan", () => {
    expect(tableSummary({ shown: 3, total: 9, query: "beras" })).toBe(
      '3 dari 9 keputusan · cocok "beras"'
    );
    expect(
      tableSummary({ shown: 1, total: 9, commodity: "telur", verification: "menunggu" })
    ).toContain("komoditas telur");
  });

  it("total nol punya kalimat sendiri, bukan '0 dari 0'", () => {
    expect(tableSummary({ shown: 0, total: 0 })).toBe(
      "Belum ada keputusan pada periode ini."
    );
  });
});

describe("status yang dulu lolos sebagai enum Inggris", () => {
  // Terlihat di aplikasi hidup 29 Okt 2026: kolom Status mencetak
  // "verifier_flagged" dan baris itu jatuh ke verificationState "lainnya",
  // sehingga tidak terjangkau chip mana pun (13 baris, chip 2+6+3 = 11).
  it("label manusia untuk verifier_flagged & review_only (istilah Fase 25)", () => {
    expect(statusLabel("verifier_flagged")).toBe("Ditandai verifikator");
    expect(statusLabel("review_only")).toBe("Temuan tinjauan");
    expect(statusLabel("proposed")).toBe("Diusulkan");
  });

  it("keduanya belum diverifikasi → chip Menunggu verifikasi", () => {
    expect(verificationState({ status: "verifier_flagged" })).toBe("menunggu");
    expect(verificationState({ status: "review_only" })).toBe("menunggu");
    expect(verificationState({ status: "proposed" })).toBe("menunggu");
  });

  it("hitungan chip menjumlah ke total (tidak ada baris yang tak terjangkau)", () => {
    const rows = [
      baris({ status: "approved" }),
      baris({ status: "pending_approval" }),
      baris({ status: "verifier_flagged" }),
      baris({ status: "rejected" }),
    ];
    const c = verificationCounts(rows);
    expect(c.all).toBe(4);
    expect(c.terverifikasi + c.menunggu + c.ditolak).toBe(4);
  });
});

describe("ukuran halaman", () => {
  // 29 Okt 2026: pemilik meminta tabel Agent Log menampilkan 10 baris —
  // sama dengan daftar pemasok/kiriman. Pemotongan halaman memakai `paginate`
  // (lib/pagination.ts) supaya rentang "1–10 dari 14" seragam antar panel;
  // helper `pageSlice`/`pageCount` milik modul ini dihapus, bukan diduplikasi.
  it("10 baris per halaman", () => {
    expect(DECISION_PAGE_SIZE).toBe(10);
    const rows = Array.from({ length: DECISION_PAGE_SIZE * 2 + 1 }, (_, i) => ({ i }));
    const satu = paginate(rows, 1, DECISION_PAGE_SIZE);
    expect(satu.items).toHaveLength(10);
    expect(satu.pageCount).toBe(3);
    expect(paginate(rows, 3, DECISION_PAGE_SIZE).items).toHaveLength(1);
    expect(paginate(rows, 0, DECISION_PAGE_SIZE).items[0]).toEqual({ i: 0 });
  });

  it("data kosong tetap 1 halaman (tabel tidak menghilang)", () => {
    expect(paginate([], 1, DECISION_PAGE_SIZE).pageCount).toBe(1);
  });
});
