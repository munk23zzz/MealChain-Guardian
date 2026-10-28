"use client";

/**
 * Detail satu lokasi untuk pop-up "Pasokan & permintaan" (dokumen 03 §3).
 *
 * Satu tempat yang memutuskan mana yang 404 dan mana yang gagal, supaya UI
 * tidak pernah menampilkan 0 untuk "tidak ada catatan". Query baru dijalankan
 * ketika pop-up benar-benar dibuka (`enabled`), jadi modul Location Network
 * tidak menambah empat permintaan saat hanya dipandang.
 */
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { fetchBatches, fetchDemand, fetchDemandForecast, fetchSupply } from "../api";
import {
  buildSupplyDemandDetail,
  type BatchRow,
  type FailedPart,
} from "../supply-demand";

export function useSupplyDemand(
  token: string | null,
  target: { location: string; commodity: string } | null
) {
  const aktif = Boolean(token && target?.location && target?.commodity);
  const tokenValue = token ?? "";

  const balance = useQuery({
    queryKey: ["balance", target?.location ?? "", target?.commodity ?? "", tokenValue ? "auth" : "anon"],
    queryFn: async () => {
      const { fetchBalance } = await import("../api");
      return fetchBalance(target!.location, target!.commodity, tokenValue);
    },
    enabled: aktif,
    staleTime: 5_000,
  });

  const supply = useQuery({
    queryKey: ["supply", target?.location ?? "", target?.commodity ?? ""],
    queryFn: () => fetchSupply(target!.location, target!.commodity, tokenValue),
    enabled: aktif,
    retry: false, // 404 = "tidak ada catatan", bukan gangguan yang perlu diulang
    staleTime: 30_000,
  });

  const demand = useQuery({
    queryKey: ["demand", target?.location ?? "", target?.commodity ?? ""],
    queryFn: () => fetchDemand(target!.location, target!.commodity, tokenValue),
    enabled: aktif,
    retry: false,
    staleTime: 30_000,
  });

  // Perkiraan kebutuhan 7 hari (dokumen 03 §3 butir 3). 404 di sini berarti
  // server tidak punya perkiraan untuk pasangan ini — dicatat sebagai sebab,
  // bukan diterjemahkan menjadi 0 kg.
  const forecast = useQuery({
    queryKey: ["demand-forecast", target?.location ?? "", target?.commodity ?? ""],
    queryFn: () => fetchDemandForecast(target!.location, target!.commodity, tokenValue, 7),
    enabled: aktif,
    retry: false,
    staleTime: 60_000,
  });

  // `GET /batches` belum menerima filter lokasi/komoditas, jadi penyaringan
  // terjadi di `buildSupplyDemandDetail` — dan plafon yang tersentuh dinyatakan.
  const batches = useQuery({
    queryKey: ["batches", "supply-demand"],
    queryFn: () => fetchBatches(tokenValue),
    enabled: aktif,
    staleTime: 30_000,
  });

  const detail = useMemo(() => {
    if (!target) return null;
    const failed: Partial<Record<FailedPart, string>> = {};
    if (balance.isError) failed.balance = String(balance.error ?? "gagal");
    if (supply.isError) failed.supply = String(supply.error ?? "gagal");
    if (demand.isError) failed.demand = String(demand.error ?? "gagal");
    if (batches.isError) failed.batches = String(batches.error ?? "gagal");
    if (forecast.isError) failed.forecast = String(forecast.error ?? "gagal");

    const batchRows: BatchRow[] = Array.isArray(batches.data)
      ? (batches.data as BatchRow[])
      : [];

    return buildSupplyDemandDetail({
      location: target.location,
      commodity: target.commodity,
      // 404 ditandai `null` + pesan, bukan objek kosong (objek kosong akan
      // terbaca sebagai "ada catatan, isinya kosong").
      balance: balance.isError ? null : (balance.data as Record<string, unknown> | null),
      supply: supply.isError ? null : (supply.data as Record<string, unknown> | null),
      demand: demand.isError ? null : (demand.data as Record<string, unknown> | null),
      forecast: forecast.isError ? null : (forecast.data as Record<string, unknown> | null),
      batches: batches.isError ? null : batchRows,
      failed,
    });
  }, [
    target,
    balance.data,
    balance.isError,
    balance.error,
    supply.data,
    supply.isError,
    supply.error,
    demand.data,
    demand.isError,
    demand.error,
    batches.data,
    batches.isError,
    batches.error,
    forecast.data,
    forecast.isError,
    forecast.error,
  ]);

  // Kesalahan hanya dilaporkan bila TIDAK ADA satu pun bagian yang terbaca:
  // satu bagian gagal cukup dicatat per bagian (`detail.notes`), tetapi kalau
  // semuanya gagal, panel tidak boleh tampil sebagai deretan "—" tanpa sebab.
  const semuaGagal =
    aktif && balance.isError && supply.isError && demand.isError && batches.isError;

  return {
    detail,
    loading: aktif && (balance.isLoading || supply.isLoading || demand.isLoading),
    error: semuaGagal ? "pasokan, kebutuhan, saldo, dan batch tidak terjawab server" : null,
  };
}
