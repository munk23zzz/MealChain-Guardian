"use client";

/**
 * Jalur kiriman pemasok → tujuan (GET /supplier-routes) lewat React Query.
 *
 * Fase 10 (keputusan pemilik 2026-10-16): garis di peta mengikuti JALAN dan
 * hanya digambar dari geometri yang sudah tersimpan di cache server, jadi
 * permintaan ini tidak pernah membuat peramban memanggil OSRM.
 *
 * Gerbang muatnya sama dengan daftar pemasok (`shouldLoadSuppliers`): hanya tab
 * yang memang menampilkan peta/Pemasok yang memuat data ini. `staleTime` panjang
 * + tanpa polling — rute kiriman berubah hanya saat sinkronisasi baru dijalankan.
 *
 * `forceEnabled` (Fase 11): tab Keamanan Pangan butuh rute kiriman yang menuju
 * lokasi sendiri supaya kartu "Pasokan masuk" berisi data nyata, padahal tab itu
 * tidak menampilkan peta. Dipakai sebagai parameter, BUKAN dengan menambah tab
 * ke daftar di `lib/supplier-pins.ts` — daftar itu menentukan pemuatan PIN
 * pemasok, dan menambahnya akan mengubah perilaku peta.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchSupplierRoutes } from "../api";
import { errorMessage, queryKeys, SUPPLIERS_STALE_MS } from "../query";
import { shouldLoadSuppliers } from "../supplier-pins";

export function useSupplierRoutes(
  token: string | null,
  scope: string,
  tab: string,
  commodity: string | null = null,
  location: string | null = null,
  forceEnabled = false
) {
  const query = useQuery({
    queryKey: queryKeys.supplierRoutes(scope, commodity, location),
    queryFn: () => fetchSupplierRoutes(token as string, commodity, location),
    enabled: Boolean(token) && (forceEnabled || shouldLoadSuppliers(tab, token)),
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
