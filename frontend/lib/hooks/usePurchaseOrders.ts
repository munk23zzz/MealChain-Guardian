"use client";

/**
 * Purchase order mock SAP (GET /sap/purchase-orders + /summary, W-5 2026-10-17).
 *
 * Dua query dipisah supaya chip ringkasan tetap tampil walau daftar gagal:
 * ringkasan menjawab "berapa banyak & berapa nilainya", daftar menjawab "yang
 * mana". Keduanya TIDAK di-poll — PO hanya bertambah saat keputusan dieksekusi,
 * dan `lib/refresh.ts` sudah menyegarkan seluruh cache setelah setiap tulis.
 *
 * `scope` masuk kunci query karena isinya berbeda per peran (lokasi vs nasional);
 * tanpanya, berganti peran di browser yang sama akan menampilkan PO milik peran
 * sebelumnya.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchPurchaseOrderSummary, fetchPurchaseOrders } from "../api";
import { QUERY_STALE_MS, errorMessage, queryKeys } from "../query";

export function usePurchaseOrders(token: string | null, scope: string) {
  const daftar = useQuery({
    queryKey: queryKeys.purchaseOrders(scope),
    queryFn: () => fetchPurchaseOrders(token as string, { limit: 200 }),
    enabled: Boolean(token),
    staleTime: QUERY_STALE_MS,
    refetchInterval: false,
    retry: false,
  });

  const ringkas = useQuery({
    queryKey: queryKeys.purchaseOrderSummary(scope),
    queryFn: () => fetchPurchaseOrderSummary(token as string),
    enabled: Boolean(token),
    staleTime: QUERY_STALE_MS,
    refetchInterval: false,
    retry: false,
  });

  return {
    data: daftar.data ?? null,
    summary: ringkas.data ?? null,
    error: daftar.error
      ? errorMessage(daftar.error) ?? "Purchase order tidak tersedia."
      : null,
    isFetching: daftar.isFetching || ringkas.isFetching,
    refetch: () => {
      void daftar.refetch();
      void ringkas.refetch();
    },
  };
}
