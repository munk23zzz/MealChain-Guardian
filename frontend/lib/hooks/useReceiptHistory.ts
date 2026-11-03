"use client";

/**
 * Riwayat penerimaan barang (GET /receipts/riwayat) — Dok 05 §8.5.
 *
 * Dimuat hanya saat tab Pemasok (atau Overview) aktif, sama seperti daftar
 * pemasok: riwayat ini tidak dipakai layar lain, dan tab lain tidak perlu
 * membayar satu permintaan tambahan setiap kali dibuka.
 *
 * `staleTime` panjang dan tanpa polling: catatan penerimaan berubah hanya saat
 * ada yang mencatat/menyetujui, bukan karena waktu berjalan. Session yang baru
 * menyetujui penerimaan bisa memanggil `refetch()` (dikembalikan di sini)
 * alih-alih menunggu cache kedaluwarsa.
 */
import { useQuery } from "@tanstack/react-query";

import { errorMessage, queryKeys, SUPPLIERS_STALE_MS } from "../query";
import { fetchReceiptHistory } from "../api";
import { shouldLoadSuppliers } from "../supplier-pins";

export function useReceiptHistory(token: string | null, scope: string, tab: string) {
  const query = useQuery({
    queryKey: queryKeys.receiptHistory(scope),
    queryFn: () => fetchReceiptHistory(token as string),
    enabled: Boolean(token) && shouldLoadSuppliers(tab, token ?? null),
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
