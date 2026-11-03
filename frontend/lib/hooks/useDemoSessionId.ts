"use client";

/**
 * Sesi demo aktif (Fase 8 MG) — HANYA untuk memberi tahu cakupan KPI mana yang
 * bisa diminta.
 *
 * Kenapa hook sendiri: `GET /kpi?include_demo=true` menolak 422 tanpa
 * `demo_session_id` eksplisit ("tidak ada jalur sesi terbaru"), jadi halaman
 * harus tahu id sesi yang sedang aktif. Banner demo (`DemoSessionBanner`)
 * menyimpan statusnya sendiri untuk tampilan; hook ini menyediakan id-nya untuk
 * permintaan data, tanpa mengubah banner itu.
 *
 * Sengaja TIDAK memakai `localStorage` atau menebak id dari data mana pun:
 * kepemilikan baris ditentukan server, dan id yang salah akan menyaring data
 * sesi lain (justru cacat yang ditutup Fase 8).
 */
import { useQuery } from "@tanstack/react-query";

import { fetchDemoSession } from "../api";
import { queryKeys } from "../query";

const JEDA_POLL_MS = 60_000;

export function useDemoSessionId(token: string | null, enabled = true) {
  const query = useQuery({
    queryKey: queryKeys.demoSession(),
    queryFn: () => fetchDemoSession(token as string) as Promise<any>,
    enabled: Boolean(token) && enabled,
    staleTime: 15_000,
    refetchInterval: JEDA_POLL_MS,
    refetchIntervalInBackground: false,
  });
  const aktif = Boolean(query.data?.active) && Boolean(query.data?.session_id);
  return {
    sessionId: aktif ? (String(query.data.session_id) as string) : null,
    active: aktif,
    mode: query.data?.mode ? String(query.data.mode) : null,
  };
}
