// Kontrak kartu "Jejak kepercayaan" di Overview.
//
// Empat angka ini adalah bukti yang bisa diperiksa ulang (rantai ledger, uji
// keamanan batch, eksekusi keputusan, kelengkapan laporan node) — bukan hiasan.
// Karena itu aturan proyek "tanpa angka karangan" diuji di sini:
//   * data tidak terbaca → "—" dan alasannya, BUKAN 0 yang terbaca "tidak ada";
//   * nilai 0 hanya sah bila memang terukur (mis. 0 node tanpa catatan);
//   * total selalu ditulis di sebelah angkanya ("101/118") supaya pembaca tahu
//     skala yang dibicarakan, termasuk saat peran hanya melihat lokasinya.
import { describe, expect, it } from "vitest";

import { trustSummary, trustTrail, type TrustLedger } from "../lib/trust-trail";
import type { BalanceMapLocation } from "../lib/overview-format";

const node = (extra: Record<string, unknown> = {}) => ({
  location: "Jakarta",
  status: "shortage",
  supply_state: "terukur",
  demand_state: "terukur",
  ...extra,
});

describe("trustTrail — blok ledger", () => {
  it("rantai valid + checkpoint luar cocok: angka blok apa adanya, nada aman", () => {
    const [ledger] = trustTrail({
      ledger: {
        valid: true,
        blocks: 978,
        entity_blocks: 78,
        linked_blocks: 78,
        orphan_blocks: 0,
        anchor: { configured: true, match: true },
      },
      batches: [],
      decisions: [],
      locations: [],
    });
    expect(ledger.id).toBe("ledger");
    expect(ledger.label).toBe("Rantai bukti");
    expect(ledger.value).toBe("978");
    expect(ledger.unit).toBe("blok");
    expect(ledger.tone).toBe("ok");
    expect(ledger.state).toBe("utuh");
    expect(ledger.foot).toContain("Salinan di luar sistem cocok.");
    // Kalimat penjelas tidak lagi dirangkai dengan " · " (dibaca sebagai
    // potongan istilah, bukan kalimat).
    expect(ledger.foot).not.toContain(" · ");
  });

  it("rantai putus: nada peringatan dan blok patahnya disebut", () => {
    const [ledger] = trustTrail({
      ledger: { valid: false, blocks: 42, broken_at: 17, anchor: null },
      batches: [],
      decisions: [],
      locations: [],
    });
    expect(ledger.value).toBe("42");
    expect(ledger.tone).toBe("warn");
    expect(ledger.state).toBe("putus");
    expect(ledger.foot).toContain("17");
  });

  it("ledger belum termuat: '—', bukan 0 blok", () => {
    const [ledger] = trustTrail({
      ledger: null,
      batches: [],
      decisions: [],
      locations: [],
    });
    expect(ledger.value).toBe("—");
    expect(ledger.unit).toBeNull();
    expect(ledger.tone).toBe("plain");
    expect(ledger.state).toBe("menunggu");
  });

  it("blok yatim dilaporkan, bukan disembunyikan di balik 'valid'", () => {
    const [ledger] = trustTrail({
      ledger: {
        valid: true,
        blocks: 900,
        entity_blocks: 80,
        linked_blocks: 78,
        orphan_blocks: 2,
        anchor: null,
      },
      batches: [],
      decisions: [],
      locations: [],
    });
    expect(ledger.foot).toContain("2 dari 900 blok tidak tertaut ke keputusan mana pun.");
    expect(ledger.tone).toBe("warn");
  });
});

describe("trustTrail — batch lolos", () => {
  it("hanya batch pass yang tidak ditahan yang dihitung lolos", () => {
    const [, batch] = trustTrail({
      ledger: null,
      batches: [
        { safety_status: "pass", quarantine_status: "none" },
        { safety_status: "pass", quarantine_status: "quarantined" },
        { safety_status: "fail", quarantine_status: "none" },
        { safety_status: "needs_verification", quarantine_status: "none" },
        { safety_status: "pending", quarantine_status: "none" },
      ],
      decisions: [],
      locations: [],
    });
    expect(batch.label).toBe("Batch lolos uji");
    expect(batch.value).toBe("1");
    expect(batch.unit).toBe("/5");
    expect(batch.tone).toBe("warn");
    expect(batch.foot).toContain("1 gagal uji");
    expect(batch.foot).toContain("1 ditahan");
    expect(batch.foot).toContain("1 perlu diuji ulang");
    // Status yang tidak masuk kategori mana pun tetap disebut, bukan hilang:
    // 1 lolos + 1 ditahan + 1 gagal + 1 belum diuji + 1 tanpa status = /5.
    expect(batch.foot).toContain("1 tanpa status");
  });

  it("semua batch lolos: nada aman dan kalimatnya jujur", () => {
    const [, batch] = trustTrail({
      ledger: null,
      batches: [
        { safety_status: "pass", quarantine_status: "none" },
        { safety_status: "PASS", quarantine_status: "none" },
      ],
      decisions: [],
      locations: [],
    });
    expect(batch.value).toBe("2");
    expect(batch.unit).toBe("/2");
    expect(batch.tone).toBe("ok");
    expect(batch.state).toBe("bersih");
    expect(batch.foot).toBe("Semua 2 batch lolos uji dan boleh dipakai.");
  });

  it("belum ada batch terbaca: '—' dan alasan", () => {
    const [, batch] = trustTrail({
      ledger: null,
      batches: null,
      decisions: [],
      locations: [],
    });
    expect(batch.value).toBe("—");
    expect(batch.unit).toBeNull();
    expect(batch.state).toBe("menunggu");
    expect(batch.foot).toBe("Belum ada batch yang terbaca.");
  });
});

describe("trustTrail — keputusan tereksekusi", () => {
  it("menghitung status executed dan menyebut sisanya", () => {
    const exec = trustTrail({
      ledger: null,
      batches: [],
      decisions: [
        { status: "executed" },
        { status: "executed" },
        { status: "pending_approval" },
        { status: "rejected" },
        { status: "approved" },
      ],
      locations: [],
    })[2];
    expect(exec.label).toBe("Keputusan tereksekusi");
    expect(exec.value).toBe("2");
    expect(exec.unit).toBe("/5");
    expect(exec.tone).toBe("ok");
    // Hanya status yang benar-benar menunggu tindakan yang dihitung; yang
    // ditolak bukan pekerjaan yang bisa diselesaikan.
    expect(exec.foot).toBe("2 sudah dieksekusi. 2 menunggu tindakan dan 1 ditolak.");
  });

  it("belum pernah ada eksekusi: 0 yang terukur, bukan '—'", () => {
    const exec = trustTrail({
      ledger: null,
      batches: [],
      decisions: [{ status: "pending_approval" }],
      locations: [],
    })[2];
    expect(exec.value).toBe("0");
    expect(exec.unit).toBe("/1");
    expect(exec.state).toBe("belum ada");
    expect(exec.foot).toBe("1 menunggu tindakan.");
  });

  it("daftar keputusan belum termuat: '—'", () => {
    const exec = trustTrail({
      ledger: null,
      batches: [],
      decisions: null,
      locations: [],
    })[2];
    expect(exec.value).toBe("—");
    expect(exec.state).toBe("menunggu");
  });
});

describe("trustTrail — node tanpa angka terlapor", () => {
  it("menghitung sisi tanpa baris sebagai node yang tidak melapor", () => {
    const nodes = trustTrail({
      ledger: null,
      batches: [],
      decisions: [],
      locations: [
        node(),
        node({ supply_state: "tidak_ada_baris" }),
        node({ demand_state: "tidak_ada_baris", data_state: "sebagian" }),
        node({ demand_state: "sebagian" }),
      ],
    })[3];
    expect(nodes.label).toBe("Lokasi tanpa angka");
    expect(nodes.value).toBe("2");
    expect(nodes.unit).toBe("/4");
    expect(nodes.tone).toBe("warn");
    expect(nodes.foot).toBe("2 dari 4 lokasi belum melaporkan angka pasokan atau kebutuhan.");
  });

  it("satu lokasi yang melapor ditulis tanpa kata \"semua\" yang janggal", () => {
    const [, , , nodes] = trustTrail({
      ledger: null,
      batches: [],
      decisions: [],
      locations: [node({ supply_state: "terukur", demand_state: "terukur" })],
    } as never);
    expect(nodes.foot).toBe("Lokasi ini melaporkan angka pasokan dan kebutuhan.");
  });

  it("semua node melapor: 0 yang terukur, nada aman", () => {
    const nodes = trustTrail({
      ledger: null,
      batches: [],
      decisions: [],
      locations: [node(), node()],
    })[3];
    expect(nodes.value).toBe("0");
    expect(nodes.unit).toBe("/2");
    expect(nodes.tone).toBe("ok");
    expect(nodes.state).toBe("lengkap");
    expect(nodes.foot).toBe("Semua 2 lokasi melaporkan angka pasokan dan kebutuhan.");
  });

  it("tidak ada node pada komoditas ini: '—'", () => {
    const nodes = trustTrail({
      ledger: null,
      batches: [],
      decisions: [],
      locations: [],
    })[3];
    expect(nodes.value).toBe("—");
    expect(nodes.foot).toBe("Belum ada lokasi pada komoditas ini.");
  });
});

describe("trustSummary — satu kalimat keadaan untuk kepala kartu", () => {
  // `??` tidak bisa dipakai di sini: `null` adalah nilai uji yang sah
  // ("ledger belum termuat"), jadi yang menentukan adalah ada-tidaknya kuncinya.
  const metrics = (over: Partial<Record<"ledger" | "batch" | "eksekusi" | "node", unknown>>) =>
    trustTrail({
      ledger: ("ledger" in over ? over.ledger : { valid: true, blocks: 500, anchor: { match: true } }) as TrustLedger,
      batches: (over.batch as unknown[] | undefined) ?? [
        { safety_status: "pass", quarantine_status: "none" },
      ],
      decisions: (over.eksekusi as { status?: string }[] | undefined) ?? [
        { status: "executed" },
      ],
      locations: (over.node as BalanceMapLocation[] | undefined) ?? [
        node() as BalanceMapLocation,
      ],
    });

  it("semua bukti terbaca dan aman: 'terverifikasi'", () => {
    expect(trustSummary(metrics({}))).toEqual({ tone: "ok", label: "terverifikasi" });
  });

  it("satu bukti bermasalah: 'perlu tinjau'", () => {
    expect(
      trustSummary(
        metrics({ ledger: { valid: false, blocks: 10, broken_at: 3 } })
      )
    ).toEqual({ tone: "warn", label: "perlu tinjau" });
  });

  it("ada bukti yang belum termuat: 'sebagian belum terbaca'", () => {
    expect(trustSummary(metrics({ ledger: null }))).toEqual({
      tone: "plain",
      label: "sebagian belum terbaca",
    });
  });
});
