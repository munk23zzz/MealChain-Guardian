"use client";

import { useEffect, useState, type CSSProperties } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BalanceMapLocation } from "../lib/overview-format";

// Warna batang datang dari token status, bukan hex: diuji hidup 20 Okt 2026,
// `fill="var(--status-danger)"` resolve jadi rgb(198, 40, 40) di Chrome, jadi
// perubahan token ikut terbawa ke grafik.
const SHORTAGE = "var(--status-danger)";
const SURPLUS = "var(--status-safe)";

type ChartPoint = { lokasi: string; Shortage: number | null; Surplus: number | null };

function toChartValue(value: BalanceMapLocation["shortage_kg"]): number | null {
  if (value == null || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export default function StockChart({
  locations,
}: {
  locations: readonly BalanceMapLocation[];
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!locations.length) return null;

  // Urut menurun menurut shortage (peringkat = inti wawasan operasional),
  // lalu surplus — panduan chart: urutkan menurun, bukan urutan acak.
  const data: ChartPoint[] = locations
    .map((location) => ({
      lokasi: location.location,
      Shortage: toChartValue(location.shortage_kg),
      Surplus: toChartValue(location.surplus_kg),
    }))
    .sort(
      (a, b) =>
        (b.Shortage ?? 0) - (a.Shortage ?? 0) ||
        (b.Surplus ?? 0) - (a.Surplus ?? 0),
    );

  // Tinggi grafik MENGIKUTI jumlah lokasi — arah pemilik 2026-10-16 ("shape
  // besar berisi teks terlalu besar"). Tinggi tetap 380px hanya masuk akal untuk
  // belasan lokasi; dengan SATU lokasi (data seed SPPG/Jakarta) kartunya jadi
  // 448px berisi satu batang raksasa selebar ~980px. Rumus: 96px untuk sumbu +
  // legenda, 34px per batang, dijepit 180..380. HARUS angka px (bukan persen):
  // ResponsiveContainer di dalam rantai flex bisa menghitung `height: 100%`
  // sebagai 0 dan grafiknya tidak dirender (bug nyata Fase 2).
  const chartHeight = Math.min(380, Math.max(180, data.length * 34 + 96));

  // Judul bagian ini ditulis pembungkus halaman ("Pasokan per Lokasi"); h3 di
  // dalam komponen dulu membuat dua judul bertumpuk dalam satu kartu.
  if (!mounted) {
    return (
      <section
        className="stock-chart"
        aria-label="Grafik stok"
        style={{ "--chart-h": `${chartHeight}px` } as CSSProperties}
      >
        <p className="sr-only">Grafik batang: Surplus dan Shortage per lokasi.</p>
        <div className="stock-chart-placeholder" aria-hidden="true" />
      </section>
    );
  }

  return (
    <section
      className="stock-chart"
      aria-label="Grafik stok"
      style={{ "--chart-h": `${chartHeight}px` } as CSSProperties}
    >
      <div
        className="stock-chart-holder"
        role="img"
        aria-label={
          data.length
            ? `Grafik batang ${data.length} lokasi: total surplus ${Math.round(
                data.reduce((t, d) => t + (Number(d.Surplus) || 0), 0)
              ).toLocaleString("id-ID")} kg dan total shortage ${Math.round(
                data.reduce((t, d) => t + (Number(d.Shortage) || 0), 0)
              ).toLocaleString("id-ID")} kg. Angka rinci per lokasi ada di kartu Status Lokasi.`
            : "Grafik stok belum punya data."
        }
      >
        {/* Batang HORIZONTAL: label lokasi terbaca penuh tanpa rotasi, dan
            urutan menurun membuat masalah terbesar langsung terlihat.
            Tinggi dari `chartHeight` (mengikuti jumlah lokasi) — angka px tetap,
            bukan persentase, supaya pasti dirender. `maxBarSize` menjaga batang
            tetap ramping ketika lokasinya cuma satu-dua (tanpa itu Recharts
            menggemukkan batang memenuhi seluruh tinggi kartu). */}
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 16, left: 4, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fontSize: "var(--fs-1)", fill: "var(--ink-muted)" }}
              tickFormatter={(value: number) => value.toLocaleString("id-ID")}
            />
            <YAxis
              type="category"
              dataKey="lokasi"
              width={76}
              interval={0}
              tick={{ fontSize: "var(--fs-1)", fill: "var(--ink-muted)" }}
            />
            <Tooltip formatter={(value) => {
              const numeric = Number(value);
              return Number.isFinite(numeric) ? `${numeric.toLocaleString("id-ID")} kg` : "—";
            }} />
            <Legend />
            {/* Sudut batang = --radius-chip (4). Recharts menghitung path dari
                angka, jadi nilainya tidak bisa berupa var(); angkanya disamakan
                manual dengan token. */}
            <Bar dataKey="Shortage" fill={SHORTAGE} radius={[0, 4, 4, 0]} maxBarSize={26} />
            <Bar dataKey="Surplus" fill={SURPLUS} radius={[0, 4, 4, 0]} maxBarSize={26} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
