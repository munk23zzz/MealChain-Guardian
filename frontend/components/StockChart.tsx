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

  const data: ChartPoint[] = locations.map((location) => ({
    lokasi: location.location,
    Shortage: toChartValue(location.shortage_kg),
    Surplus: toChartValue(location.surplus_kg),
  }));

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
      <div className="stock-chart-holder">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#DCE6E9" />
            <XAxis dataKey="lokasi" tick={{ fontSize: 12, fill: "#555" }} interval={0} angle={-30} textAnchor="end" height={54} />
            <YAxis tick={{ fontSize: 12, fill: "#555" }} tickFormatter={(value: number) => value.toLocaleString("id-ID")} />
            <Tooltip formatter={(value) => {
              const numeric = Number(value);
              return Number.isFinite(numeric) ? `${numeric.toLocaleString("id-ID")} kg` : "—";
            }} />
            <Legend />
            <Bar dataKey="Shortage" fill={SHORTAGE} radius={[3, 3, 0, 0]} />
            <Bar dataKey="Surplus" fill={SURPLUS} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
