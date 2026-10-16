"use client";

/**
 * Identitas pemakai (GET /auth/me) lewat React Query (Rules.md §3).
 *
 * Kontrak yang dipertahankan dari efek lama: gagal membaca identitas berarti top
 * bar gagal-tertutup (`me` null) — bukan jatuh ke "semua lokasi". Karena itu
 * `retry: false` dan galatnya tidak diulang-ulang di latar.
 */
import { useQuery } from "@tanstack/react-query";

import { ApiError, fetchMe } from "../api";
import { queryKeys } from "../query";

export function useMe(token: string | null, scope: string) {
  const query = useQuery({
    queryKey: queryKeys.me(scope),
    queryFn: () => fetchMe(token as string),
    enabled: Boolean(token),
    retry: false,
    refetchInterval: false,
  });
  // 401 = token tersimpan sudah tidak sah (kedaluwarsa/dicabut). HANYA status ini
  // yang boleh memaksa sesi dibuang; galat jaringan/5xx tidak boleh mengeluarkan
  // pengguna dari sesi yang masih sah.
  const unauthorized =
    query.error instanceof ApiError && query.error.status === 401;
  return { me: query.data ?? null, isFetching: query.isFetching, unauthorized };
}
