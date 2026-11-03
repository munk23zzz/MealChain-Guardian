"use client";

/**
 * Daftar pemasok (GET /suppliers) lewat React Query.
 *
 * Dibuat di Fase 3 (2026-10-14) bersama layer pemasok di peta: dua permukaan
 * memakai data yang sama (peta Overview + halaman Pemasok), jadi satu query
 * dengan kunci tunggal supaya keduanya tidak memuat dua kali.
 *
 * Fase 7b (2026-10-15) memecahnya jadi DUA pemakaian dengan kunci berbeda:
 * - peta (Overview) memakai `maxDistanceKm` untuk peran SPPG → hanya pemasok
 *   dalam jangkauan yang dikirim server, dan jumlah yang dibuang dilaporkan
 *   server di blok `reach`. Filter komoditas ikut dikirim ke server supaya angka
 *   "N di luar jangkauan" berlaku untuk komoditas yang sedang dilihat;
 * - halaman Pemasok memakai pemanggilan tanpa ambang → daftar penuh, setiap
 *   baris diberi jarak + label "di luar jangkauan" (tidak ada yang hilang diam-diam).
 *
 * Muat hanya di tab yang memang menampilkannya (`shouldLoadSuppliers`) —
 * gerbangnya di lib/supplier-pins.ts dan diuji di tests/supplier-pins.test.ts.
 * `staleTime` panjang + tanpa polling: data pemasok nyaris statis, sedangkan
 * peta di bawahnya tetap punya siklus polling sendiri.
 */
import { useQuery } from "@tanstack/react-query";

import { errorMessage, queryKeys, SUPPLIERS_STALE_MS } from "../query";
import { fetchSuppliers } from "../api";
import { shouldLoadSuppliers } from "../supplier-pins";

export function useSuppliers(
  token: string | null,
  scope: string,
  tab: string,
  maxDistanceKm: number | null = null,
  commodity: string | null = null
) {
  const query = useQuery({
    queryKey: queryKeys.suppliers(scope, maxDistanceKm, commodity),
    queryFn: () => fetchSuppliers(token as string, maxDistanceKm, commodity),
    enabled: Boolean(token) && shouldLoadSuppliers(tab, token),
    staleTime: SUPPLIERS_STALE_MS,
    refetchInterval: false,
  });
  return {
    data: query.data ?? null,
    isFetching: query.isFetching,
    loading: query.isFetching,
    error: errorMessage(query.error),
    refetch: query.refetch,
  };
}
