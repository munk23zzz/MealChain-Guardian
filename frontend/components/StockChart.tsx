"use client";

// StockChart (S4-06 polish) — bar surplus/shortage per lokasi (recharts).
// Data REAL dari /balance/map; tanpa data → null (bukan grafik kosong).
// SSR-safe: render penuh hanya di browser (recharts butuh ukuran), SSR
// merender placeholder stabil (CLS kecil, tanpa angka karangan).

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

const SHORTAGE = "#C62828"; // --status-danger (design.md)
const SURPLUS = "#2E7D32"; // --status-safe

export default function StockChart({ locations }: { locations: any[] }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!locations?.length) return null;

  const data = locations.map((l) => ({
    lokasi: l.location,
    Shortage: Number(l.shortage_kg) || 0,
    Surplus: Number(l.surplus_kg) || 0,
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
            <XAxis
              dataKey="lokasi"
              tick={{ fontSize: 12, fill: "#555" }}
              interval={0}
              angle={-30}
              textAnchor="end"
              height={54}
            />
            <YAxis
              tick={{ fontSize: 12, fill: "#555" }}
              tickFormatter={(v: number) => v.toLocaleString("id-ID")}
            />
            <Tooltip
              formatter={(v) => Number(v).toLocaleString("id-ID") + " kg"}
            />
            <Legend />
            <Bar dataKey="Shortage" fill={SHORTAGE} radius={[3, 3, 0, 0]} />
            <Bar dataKey="Surplus" fill={SURPLUS} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
