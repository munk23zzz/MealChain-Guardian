// Wiring kalender agenda (langkah 2, 2026-10-16): halaman memuat agenda lewat
// hook React Query (Rules.md §3), dan HANYA hook itu yang memanggil fetchAgenda.
// Bulan & hari terpilih dimiliki halaman — bukan komponen — supaya rentang yang
// diminta ke server dan penanda "hari aktif" di layar tak pernah berbeda sumber.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const pageSrc = readFileSync("app/page.tsx", "utf8");
const hookSrc = readFileSync("lib/hooks/useAgenda.ts", "utf8");
const dashboardSrc = readFileSync("components/TodayDashboard.tsx", "utf8");
const apiSrc = readFileSync("lib/api.ts", "utf8");
const querySrc = readFileSync("lib/query.ts", "utf8");

describe("wiring kalender agenda di app/page.tsx", () => {
  it("halaman memuat agenda lewat hook useAgenda", () => {
    expect(pageSrc).toMatch(/from "\.\.\/lib\/hooks\/useAgenda"/);
    expect(pageSrc).toMatch(/useAgenda\(token[^)]*agendaRange/);
  });

  it("bulan & hari terpilih dimiliki halaman, bukan komponen", () => {
    expect(pageSrc).toContain("agendaMonth");
    expect(pageSrc).toContain("agendaDate");
    expect(pageSrc).toMatch(/agendaDay[^\n]*\n/);
    expect(pageSrc).toMatch(/agendaDate,\s*setAgendaDate\]\s*=\s*useState/);
    expect(pageSrc).toMatch(/onAgendaSelect=\{selectAgendaDate\}/);
  });

  it("rentang yang diminta = rentang grid bulan yang terlihat", () => {
    expect(pageSrc).toContain("monthGrid");
    expect(pageSrc).toContain("gridRange");
  });

  it("halaman menyerahkan agenda + state kalender ke TodayDashboard", () => {
    expect(pageSrc).toMatch(/<TodayDashboard/);
    expect(pageSrc).toMatch(/agenda=\{agenda\}/);
    expect(pageSrc).toMatch(/agendaDate=\{agendaDay/);
    expect(pageSrc).toMatch(/agendaMonth=\{agendaBulan/);
  });
});

describe("wiring kalender agenda di TodayDashboard", () => {
  it("merender kalender dengan data dari props (tidak fetch sendiri)", () => {
    expect(dashboardSrc).toMatch(/<TodayAgendaCalendar/);
    expect(dashboardSrc).toMatch(/agenda=\{agenda\}/);
    expect(dashboardSrc).toMatch(/selected=\{agendaDate\}/);
    expect(dashboardSrc).toMatch(/onSelect=\{onAgendaSelect\}/);
    expect(dashboardSrc).not.toMatch(/fetchAgenda\(/);
  });
});

describe("hook useAgenda", () => {
  it("hanya hook ini yang memanggil fetchAgenda, dan memakai kunci query sendiri", () => {
    expect(hookSrc).toContain("fetchAgenda");
    expect(hookSrc).toContain("queryKeys.agenda");
    expect(hookSrc).toContain("shouldLoadKpi");
  });
});

describe("lapisan API & kunci query", () => {
  it("fetchAgenda memanggil GET /agenda dengan start & end", () => {
    expect(apiSrc).toMatch(/export async function fetchAgenda/);
    expect(apiSrc).toMatch(/\/agenda\?start=/);
  });

  it("kunci query menyertakan scope dan rentang", () => {
    expect(querySrc).toMatch(/agenda: \(scope: string, start: string, end: string\)/);
  });
});
