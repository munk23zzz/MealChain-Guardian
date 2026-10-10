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

export default function StockChart({ locations }: { locations: readonly BalanceMapLocation[] }) {
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

  if (!mounted) {
    return (
      <section className="stock-chart card" aria-label="Grafik stok">
        <h3>Surplus &amp; Shortage per Lokasi</h3>
        <div className="stock-chart-placeholder" aria-hidden="true" />
      </section>
    );
  }

  return (
    <section className="stock-chart card" aria-label="Grafik stok">
      <h3>Surplus &amp; Shortage per Lokasi</h3>
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
        <ResponsiveContainer width="100%" height={380}>
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
              width={84}
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
