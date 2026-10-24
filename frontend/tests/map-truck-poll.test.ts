/**
 * Kontrak audit 24 Okt 2026: mobil kiriman di peta harus BERGERAK.
 *
 * Temuan saat audit: `useSupplierRoutes` memakai `refetchInterval: false`,
 * sehingga posisi mobil beku di angka saat halaman dimuat dan kiriman yang
 * sudah tiba tetap digambar "di jalan". Perbaikan: hanya query PETA yang
 * memakai denyut `MAP_TRUCK_POLL_MS`; pemanggil lain (Pemasok, Keamanan
 * Pangan) tetap tanpa polling supaya tidak menambah beban yang tak perlu.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const root = join(process.cwd());
const hookSrc = readFileSync(
  join(root, "lib/hooks/useSupplierRoutes.ts"),
  "utf8"
);
const pageSrc = readFileSync(join(root, "app/page.tsx"), "utf8");
const querySrc = readFileSync(join(root, "lib/query.ts"), "utf8");

describe("denyut data kiriman untuk peta", () => {
  it("hook menerima pollMs dan memakainya sebagai refetchInterval", () => {
    expect(hookSrc).toContain("pollMs: number | false = false");
    expect(hookSrc).toContain("refetchInterval: hidup ? (pollMs as number) : false");
    expect(hookSrc).toContain("refetchIntervalInBackground: false");
  });

  it("staleTime ikut nol saat polling hidup, supaya angka tidak dibekukan cache", () => {
    expect(hookSrc).toContain("staleTime: hidup ? 0 : SUPPLIERS_STALE_MS");
  });

  it("query peta memakai MAP_TRUCK_POLL_MS", () => {
    expect(querySrc).toContain("export const MAP_TRUCK_POLL_MS = 15_000");
    const blok = pageSrc.slice(pageSrc.indexOf("const mapSupplierRoutesQuery"));
    expect(blok.slice(0, 400)).toContain("MAP_TRUCK_POLL_MS");
  });

  it("query Pemasok dan Keamanan Pangan tetap tanpa polling", () => {
    const pemasok = pageSrc.slice(pageSrc.indexOf("const supplierRoutesQuery"));
    expect(pemasok.slice(0, 200)).not.toContain("MAP_TRUCK_POLL_MS");
    const safety = pageSrc.slice(pageSrc.indexOf("const safetyRoutesQuery"));
    expect(safety.slice(0, 300)).not.toContain("MAP_TRUCK_POLL_MS");
  });
});
