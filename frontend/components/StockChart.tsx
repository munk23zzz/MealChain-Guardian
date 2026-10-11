"use client";

import { useEffect, useState } from "react";
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

const SHORTAGE = "#C62828";
const SURPLUS = "#2E7D32";

type ChartPoint = { lokasi: string; Shortage: number | null; Surplus: number | null };

function toChartValue(value: BalanceMapLocation["shortage_kg"]): number | null {
  if (value == null || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export default function StockChart({
  locations,
  stretch = false,
}: {
  locations: readonly BalanceMapLocation[];
  /** Jika true, chart mengisi tinggi flex parent (pakai height="100%"). */
  stretch?: boolean;
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

  // Judul bagian ini ditulis pembungkus halaman ("Pasokan per Lokasi"); h3 di
  // dalam komponen dulu membuat dua judul bertumpuk dalam satu kartu.
  if (!mounted) {
    return (
      <section
        className={`stock-chart${stretch ? " stock-chart-stretch" : ""}`}
        aria-label="Grafik stok"
      >
        <p className="sr-only">Grafik batang: Surplus dan Shortage per lokasi.</p>
        <div className="stock-chart-placeholder" aria-hidden="true" />
      </section>
    );
  }

  return (
    <section
      className={`stock-chart${stretch ? " stock-chart-stretch" : ""}`}
      aria-label="Grafik stok"
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
              ).toLocaleString("id-ID")} kg. Angka rinci per lokasi ada di tabel Rincian Pasokan per Lokasi.`
            : "Grafik stok belum punya data."
        }
      >
        {/* Batang HORIZONTAL: kartu ini hanya sepertiga lebar halaman, dan 10
            label lokasi yang diputar tetap saling tumpang tindih di sana.
            Mendatar = label terbaca penuh tanpa rotasi. */}
        <ResponsiveContainer width="100%" height={stretch ? "100%" : 380}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 16, left: 4, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#DCE6E9" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fontSize: 12, fill: "#555" }}
              tickFormatter={(value: number) => value.toLocaleString("id-ID")}
            />
            <YAxis
              type="category"
              dataKey="lokasi"
              width={76}
              interval={0}
              tick={{ fontSize: 12, fill: "#555" }}
            />
            <Tooltip formatter={(value) => {
              const numeric = Number(value);
              return Number.isFinite(numeric) ? `${numeric.toLocaleString("id-ID")} kg` : "—";
            }} />
            <Legend />
            <Bar dataKey="Shortage" fill={SHORTAGE} radius={[0, 3, 3, 0]} />
            <Bar dataKey="Surplus" fill={SURPLUS} radius={[0, 3, 3, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
