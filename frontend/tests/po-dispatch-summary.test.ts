import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { ringkasanBatchPo } from "../components/DecisionActions";

/**
 * Gerbang review PO mengembalikan `dikirim` dan `ditahan`.
 *
 * Alasan (terukur 29 Okt 2026): keputusan bef077a8 menjadi `executed` dan PO
 * MC-BEF077A8A935 `submitted`, tetapi batch terikat b772248c dilaporkan backend
 * sebagai DITAHAN ("sudah berangkat"). UI waktu itu hanya menampilkan status
 * PO/keputusan, jadi layar seolah menyatakan truk berangkat. Backend sudah
 * mengirim alasannya — yang hilang hanya pembacanya.
 */

describe("ringkasanBatchPo — satu sumber teks UI", () => {
  it("menyebut batch yang benar-benar diberangkatkan", () => {
    expect(
      ringkasanBatchPo({
        dikirim: [{ batch_id: "a", dispatched_at: "2026-10-29T03:56:00+00:00" }],
        ditahan: [],
      })
    ).toBe("1 batch diberangkatkan.");
  });

  it("menyebut batch yang DITAHAN beserta alasannya (kasus bef077a8)", () => {
    const teks = ringkasanBatchPo({
      dikirim: [],
      ditahan: [
        { batch_id: "b772248c", alasan: "sudah berangkat 2026-10-28T05:15:30+00:00" },
      ],
    });
    expect(teks).toBe("1 batch ditahan: sudah berangkat 2026-10-28T05:15:30+00:00.");
    expect(teks).not.toContain("0 batch");
  });

  it("memisahkan kirim dan tahan, tanpa saling menutupi", () => {
    const teks = ringkasanBatchPo({
      dikirim: [{ batch_id: "a" }, { batch_id: "b" }],
      ditahan: [{ batch_id: "c", alasan: "quarantined" }],
    });
    expect(teks).toBe("2 batch diberangkatkan · 1 batch ditahan: quarantined.");
  });

  it("tidak mengarang pemberangkatan saat PO tanpa binding batch", () => {
    expect(ringkasanBatchPo({})).toBe(
      "Tidak ada batch terikat pada PO ini, jadi tidak ada barang yang diberangkatkan."
    );
    expect(ringkasanBatchPo({ dikirim: null, ditahan: null })).toContain(
      "tidak ada barang yang diberangkatkan"
    );
  });

  it("alasan kosong tidak menyisakan tanda baca menggantung", () => {
    expect(ringkasanBatchPo({ dikirim: [], ditahan: [{ batch_id: "c" }] })).toBe(
      "1 batch ditahan."
    );
  });
});

describe("reviewPo — memakai ringkasan itu", () => {
  const sumber = readFileSync(
    new URL("../components/DecisionActions.tsx", import.meta.url),
    "utf8"
  );

  it("pesan review PO membaca dikirim/ditahan lewat ringkasanBatchPo", () => {
    const badan = /async function reviewPo\(\)[\s\S]*?\n  \}/.exec(sumber)?.[0] ?? "";
    expect(badan).toContain("ringkasanBatchPo(result)");
    expect(badan).toContain("terkirim ke SAP");
  });
});
