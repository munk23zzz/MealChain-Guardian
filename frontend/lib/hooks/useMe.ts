"use client";

/**
 * Identitas pemakai (GET /auth/me) lewat React Query (Rules.md §3).
 *
 * Kontrak yang dipertahankan dari efek lama: gagal membaca identitas berarti top
 * bar gagal-tertutup (`me` null) — bukan jatuh ke "semua lokasi". Karena itu
 * `retry: false` dan galatnya tidak diulang-ulang di latar.
 */
import { useQuery } from "@tanstack/react-query";

import { fetchMe } from "../api";
import { queryKeys } from "../query";

export function useMe(token: string | null, scope: string) {
  const query = useQuery({
    queryKey: queryKeys.me(scope),
    queryFn: () => fetchMe(token as string),
    enabled: Boolean(token),
    retry: false,
    refetchInterval: false,
  });
  return { me: query.data ?? null, isFetching: query.isFetching };
}
