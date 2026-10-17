/**
 * Kontrak cakupan lokasi di panel chaos (Ruling 2026-10-14).
 *
 * Yang dijaga dua hal, dan keduanya pernah salah:
 *  1. target event = lokasi SPPG PEMAKAI (bukan lokasi batch — dulu begitu dan
 *     setelah cakupan ditegakkan server hasilnya 403);
 *  2. batch dari lokasi lain tetap boleh dipilih, karena batch itu data sisi
 *     SUMBER dan justru isi skenarionya.
 */

import { describe, expect, it } from "vitest";

import {
  MISSING_LOCATION_REASON,
  batchLabel,
  blockedReason,
  eventTargetNote,
  resolveEventTarget,
} from "../lib/chaos-scope";

const JAKARTA = "11111111-1111-1111-1111-111111111111";

const surabayaBatch = {
  id: "b2",
  commodity: "telur",
  location: "Surabaya",
  location_id: "22222222-2222-2222-2222-222222222222",
  quantity_kg: 600,
  safety_status: "fail",
};

describe("resolveEventTarget", () => {
  it("memakai lokasi SPPG pemakai sebagai target keputusan", () => {
    expect(resolveEventTarget(JAKARTA)).toBe(JAKARTA);
  });

  it("kosong bila identitas belum terbaca (tidak menebak lokasi batch)", () => {
    expect(resolveEventTarget(null)).toBe("");
    expect(resolveEventTarget(undefined)).toBe("");
  });
});

describe("blockedReason", () => {
  it("null saat lokasi SPPG diketahui", () => {
    expect(blockedReason(JAKARTA)).toBeNull();
  });

  it("menyebut tindakan perbaikan saat lokasi belum diketahui", () => {
    const reason = blockedReason(null);
    expect(reason).toBe(MISSING_LOCATION_REASON);
    expect(reason).toContain("/auth/me");
  });
});

describe("batchLabel", () => {
  it("menulis lokasi batch apa adanya tanpa penanda larangan", () => {
    const label = batchLabel(surabayaBatch);
    // Status keamanan dulu "· fail" (enum Inggris) di opsi skenario — temuan QA
    // 17 Okt 2026. Niat tes tetap: status keamanan batch HARUS ikut terbaca.
    expect(label).toBe("telur · Surabaya · 600 kg · Gagal");
    expect(label).not.toContain("SPPG lain");
  });
});

describe("eventTargetNote", () => {
  it("menyebut SPPG pemakai sebagai tujuan", () => {
    const note = eventTargetNote(JAKARTA, "Jakarta");
    expect(note).toContain("Jakarta");
    expect(note).toContain("menyasar SPPG Anda");
  });

  it("jujur saat lokasi tujuan belum diketahui", () => {
    expect(eventTargetNote(null, null)).toContain("belum diketahui");
  });
});
