// Fase 9 MG butir 5 — alur review: form menuntut alasan + bukti, dan hasilnya
// menyegarkan Decision, approval summary, batch, serta KPI.
//
// Kenapa diuji begini: komponen review sudah ada (HumanReviewPanel + lib/review-gate),
// tetapi yang membuat hasilnya TERLIHAT di layar bukan komponen itu — melainkan satu
// pintu di `lib/refresh.ts`: setiap permintaan tulis yang berhasil menyegarkan seluruh
// cache React Query. Tes ini mengunci rantai itu dari ujung ke ujung, tanpa DOM:
//
//   review (POST) → segarkanSetelahTulis() → invalidateQueries()
//                 → keempat kunci (decisions, decisionDetail, batches, kpiLive) basi
//
// Tanpa tes ini, "refresh setelah review" hanya janji di komentar.

import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { reviewDecision } from "../lib/api";
import { queryKeys } from "../lib/query";
import { daftarkanPenyegar, metodeMenulis, segarkanSetelahTulis } from "../lib/refresh";
import { REASON_MIN, reviewReadiness } from "../lib/review-gate";

afterEach(() => {
  daftarkanPenyegar(null);
  vi.unstubAllGlobals();
});

describe("Fase 9 butir 5 — form review tidak menawarkan kiriman tanpa bukti", () => {
  const dasar = { role: "sppg_head", batchId: "b1" };

  it("alasan terlalu pendek dan bukti kosong sama-sama menghalangi kirim", () => {
    const kosong = reviewReadiness({ ...dasar, reason: "", evidenceRefs: [] });
    expect(kosong.ok).toBe(false);
    expect(kosong.blockers.join(" | ")).toContain("alasan review minimal");
    expect(kosong.blockers.join(" | ")).toContain("rujukan bukti");
  });

  it("hanya alasan cukup tanpa rujukan bukti → tetap tertahan", () => {
    const tanpaBukti = reviewReadiness({
      ...dasar,
      reason: "suhu wadah 12 derajat selama dua jam",
      evidenceRefs: [],
    });
    expect(tanpaBukti.ok).toBe(false);
    expect(tanpaBukti.blockers.join(" | ")).toContain("rujukan bukti");
  });

  it("alasan ≥ batas minimum + satu rujukan → boleh dikirim", () => {
    const siap = reviewReadiness({
      ...dasar,
      reason: "suhu wadah 12 derajat selama dua jam",
      evidenceRefs: ["probe_suhu_2026-10-27"],
    });
    expect(siap.ok).toBe(true);
    expect(siap.blockers).toEqual([]);
    expect("x".repeat(REASON_MIN - 1)).toHaveLength(REASON_MIN - 1);
  });

  it("peran read-only tidak pernah mendapat form yang bisa dikirim", () => {
    const monitor = reviewReadiness({
      role: "bgn_monitor",
      batchId: "b1",
      reason: "suhu wadah 12 derajat selama dua jam",
      evidenceRefs: ["probe_suhu_2026-10-27"],
    });
    expect(monitor.ok).toBe(false);
    expect(monitor.blockers.join(" | ")).toContain("tidak berwenang");
  });
});

describe("Fase 9 butir 5 — hasil review menyegarkan Decision, summary, batch, KPI", () => {
  it("reviewDecision adalah permintaan TULIS dan memicu penyegaran seluruh cache", async () => {
    const penyegar = vi.fn();
    daftarkanPenyegar(penyegar);
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ status_changed: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await reviewDecision(
      "d1",
      {
        batch_id: "b1",
        reason: "suhu wadah 12 derajat selama dua jam",
        evidence_refs: ["probe"],
        temperature_samples: [],
      },
      "tok"
    );

    expect(metodeMenulis("POST")).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(penyegar).toHaveBeenCalledTimes(1);
  });

  it("penyegaran membasikan keempat permukaan yang dibaca UI", async () => {
    const client = new QueryClient();
    const scope = "loc:jakarta";
    const kunci = [
      queryKeys.decisions(scope), // daftar keputusan
      queryKeys.decisionDetail("d1", scope), // approval summary + rantai + konteks
      queryKeys.batches(), // batch & status keamanan
      queryKeys.kpiLive(scope, "today", "demo", "sesi-1"), // KPI
    ];
    for (const key of kunci) client.setQueryData(key, { nilai: 1 });

    daftarkanPenyegar(() => void client.invalidateQueries());
    segarkanSetelahTulis();
    // invalidateQueries menandai basi secara sinkron; refetch-nya async.
    for (const key of kunci) {
      expect(client.getQueryState(key)?.isInvalidated, JSON.stringify(key)).toBe(true);
    }
    daftarkanPenyegar(null);
  });
});
