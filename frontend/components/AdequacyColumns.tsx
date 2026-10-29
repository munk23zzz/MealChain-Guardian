"use client";

// Kartu "Kecukupan pasokan" sebagai BAR VERTIKAL (28 Okt 2026).
//
// Permintaan pemilik: "bar chart berdiri, ukuran tidak terlalu besar, redesign
// lebih soft ui". Yang berubah hanya BENTUK; angka, urutan, dan arti segmen
// tetap milik modul murni `lib/adequacy-columns.ts` (dan lewat itu,
// `lib/supply-adequacy.ts` / `lib/location-balance.ts`) — jadi tidak ada aturan
// baru yang lahir di JSX.
//
// Dua isi, satu bentuk:
// - mode "commodity": empat komoditas untuk satu lokasi (SPPG Head, Ahli Gizi,
//   BGN yang memilih satu lokasi) — segmen = kualitas batch;
// - mode "location": satu komoditas untuk semua lokasi (BGN nasional) —
//   satu segmen pasokan, warna mengikuti cakupan.
//
// Kejujuran yang dipertahankan: kolom tanpa kebutuhan terukur ditandai "—" dan
// tidak digambar sebagai 0%; garis putus-putus = kebutuhan.

import { useEffect, useState, type CSSProperties } from "react";

import { formatDateTime } from "../lib/datetime";
import {
  columnFillPct,
  columnOverflow,
  commodityColumns,
  locationColumns,
  type AdequacyColumn,
} from "../lib/adequacy-columns";
import {
  adequacySummary,
  type AdequacyLens,
  type CommodityAdequacy,
  type SupplyTone,
} from "../lib/supply-adequacy";
import { sortAdequacyRows } from "../lib/supply-adequacy";
import type { BalanceMapLocation } from "../lib/overview-format";
import RadialRing from "./RadialRing";
import CompositionDonut from "./CompositionDonut";
import { komoditasToneClass } from "../lib/surplus-regions";
import { formatKg } from "../lib/overview-format";

type Props = {
  mode: "commodity" | "location";
  /** Wajib untuk mode "commodity". */
  rows?: readonly CommodityAdequacy[];
  /** Wajib untuk mode "location". */
  locations?: readonly BalanceMapLocation[];
  /** Komoditas yang sedang dilihat (mode lokasi) — untuk judul kecil. */
  commodity?: string | null;
  role: string | null;
  locationName: string;
  updatedAt: number | null;
  sourceNote?: string | null;
  now: Date | null;
  loading?: boolean;
  error?: string | null;
  onSelect?: (commodity: string) => void;
  onRetry?: () => void;
};

const LABEL_LENS: Record<AdequacyLens, string> = {
  quantity: "Kuantitas",
  freshness: "Kesegaran",
};

function toneClass(tone: SupplyTone): string {
  return `ac-tone-${tone}`;
}

export default function AdequacyColumns({
  mode,
  rows = [],
  locations = [],
  commodity = null,
  role,
  locationName,
  updatedAt,
  sourceNote = null,
  now,
  loading = false,
  error = null,
  onSelect,
  onRetry,
}: Props) {
  const preferred: AdequacyLens =
    role === "sppg_nutritionist" ? "freshness" : "quantity";
  const [lens, setLens] = useState<AdequacyLens>(preferred);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  useEffect(() => setLens(preferred), [preferred]);

  const judul = mode === "commodity" ? "Kecukupan pasokan" : "Pasokan per Lokasi";
  const tanggal = updatedAt ? formatDateTime(new Date(updatedAt).toISOString()) : "—";

  if (loading || !now) {
    return (
      <section className="adequacy-columns" aria-label={judul} aria-busy="true">
        <header className="ac-head">
          <div className="ac-title">
            <h3>{judul}</h3>
            <p className="ac-sub">
              {mode === "commodity" ? locationName || "SPPG" : commodity ?? "komoditas"} ·
              memuat…
            </p>
          </div>
        </header>
        <div className="ac-skeleton" aria-hidden="true">
          {[0, 1, 2, 3].map((i) => (
            <span className="ac-skeleton-col" key={i} style={{ "--i": i } as CSSProperties} />
          ))}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="adequacy-columns" aria-label={judul}>
        <header className="ac-head">
          <div className="ac-title">
            <h3>{judul}</h3>
            <p className="ac-sub">{locationName || "SPPG"}</p>
          </div>
        </header>
        <p className="status-danger ac-error" role="alert">
          {error} {onRetry && (
            <button type="button" onClick={onRetry}>
              Coba lagi
            </button>
          )}
        </p>
      </section>
    );
  }

  const view =
    mode === "commodity"
      ? commodityColumns(rows, lens)
      : locationColumns(locations);
  const { columns } = view;

  if (mode === "commodity" && !rows.length) return null;

  const ringkas = mode === "commodity" ? adequacySummary(sortAdequacyRows(rows, lens), lens) : null;
  // Redesign "simple, tidak banyak teks" (28 Okt 2026): kalimat panjangan
  // dipindah ke `title` (tetap terbaca saat ditunjuk) dan aria-label; yang
  // tercetak hanya satu baris kecil di bawah judul.
  const sub = `${commodity ?? "komoditas"} · ${columns.length} lokasi`;
  const subLengkap =
    mode === "commodity"
      ? `${locationName || "SPPG"} · ${columns.length} komoditas · ${
          sourceNote ? `${sourceNote} · ` : ""
        }dihitung ${tanggal}`
      : `${commodity ?? "komoditas"} · ${columns.length} lokasi · data ${tanggal}`;

  const ringkasAngka =
    mode === "commodity"
      ? `${ringkas?.short ?? 0} dari ${ringkas?.measured ?? 0}`
      : `${columns.filter((c) => c.gapTone === "danger" || c.gapTone === "warning").length} dari ${
          columns.filter((c) => c.demandKg !== null).length
        }`;
  const terburuk =
    mode === "commodity"
      ? ringkas?.worst
        ? {
            label: ringkas.worst.commodity,
            gap: columns[0]?.gap ?? "—",
            tone: columns[0]?.gapTone ?? "muted",
          }
        : null
      : columns[0]
        ? { label: columns[0].label, gap: columns[0].gap, tone: columns[0].gapTone }
        : null;

  // Donat dipakai bila kartu menampilkan KOMODITAS (4 irisan bernama) — satu
  // diagram, satu warna per komoditas. Mode lokasi bisa berisi 10+ baris, dan
  // donat 10 irisan tipis justru lebih sulit dibaca daripada cincin.
  const donat = mode === "commodity" && columns.length >= 2 && columns.length <= 6;
  const irisan = donat
    ? columns.map((column, index) => ({
        key: column.key,
        label: column.label,
        kg: column.numeratorKg,
        toneClass: komoditasToneClass(column.label, index),
        // Komoditas tanpa kebutuhan tetap dicatat di legenda — menghilangkannya
        // akan membuat pembaca mengira komoditas itu tidak ada.
        note: column.numeratorKg > 0 ? `${column.coverage} · ${column.gap}` : "belum tercatat",
        aria: column.aria,
      }))
    : [];
  const totalTanpaSatuan = formatKg(
    irisan.reduce((jumlah, iris) => jumlah + iris.kg, 0)
  ).replace(/\s*kg$/, "");

  return (
    <section
      className={`adequacy-columns${mounted ? " is-mounted" : ""}`}
      aria-labelledby="ac-title"
    >
      <header className="ac-head">
        <div className="ac-title">
          <h3 id="ac-title" title={subLengkap}>
            {judul}
          </h3>
          {/* Mode komoditas: tanpa baris kecil. Lokasi & jam sudah ada di bar
              atas dan di judul (hover) — permintaan pemilik 28 Okt 2026. */}
          {mode === "location" && (
            <p className="ac-sub" title={subLengkap}>
              {sub}
            </p>
          )}
        </div>
        <span className={`ac-count ${toneClass(terburuk?.tone ?? "muted")}`} aria-live="polite">
          <strong>{ringkasAngka}</strong> kurang
        </span>
        {/* Pil lensa duduk di KEPALA (bukan baris alat sendiri): tanpa baris
            alat, kedua kartu punya urutan identik kepala → donat → kaki, jadi
            donat kiri dan kanan sejajar. */}
        {mode === "commodity" ? (
          <div className="ac-toggle" role="group" aria-label="Sudut pandang kecukupan">
            {(["quantity", "freshness"] as const).map((pilihan) => (
              <button
                key={pilihan}
                type="button"
                aria-pressed={lens === pilihan}
                onClick={() => setLens(pilihan)}
              >
                {LABEL_LENS[pilihan]}
              </button>
            ))}
          </div>
        ) : null}
      </header>

      {columns.length === 0 ? (
        <p className="ac-empty">
          {mode === "commodity"
            ? "Belum ada komoditas yang bisa ditampilkan."
            : "Belum ada lokasi yang bisa ditampilkan untuk komoditas ini."}
        </p>
      ) : donat ? (
        // Satu donat, satu warna per komoditas: porsi terbaca sekali pandang,
        // angka cakupan tiap komoditas tetap tercetak di baris legenda.
        <div className="rc-plot">
          <CompositionDonut
            slices={irisan}
            totalValue={totalTanpaSatuan}
            totalUnit="kg"
            aria={`Kecukupan pasokan: ${irisan.map((i) => i.aria).join("; ")}`}
            caption="irisan = kg yang dihitung · warna = komoditas"
            onPick={
              onSelect && mode === "commodity" ? (label) => onSelect(label) : undefined
            }
          />
          {/* Baris kaki yang sama dengan kartu surplus (di sana: daftar wilayah).
              Tanpa baris ini donat kiri duduk lebih rendah dari donat kanan. */}
          <p className="cd-wilayah">{subLengkap}</p>
        </div>
      ) : (
        <div className="rc-plot">
          <ol
            className="rc-row"
            data-count={columns.length}
            data-dense={columns.length > 6 ? "true" : "false"}
            aria-label={`${judul} — ${columns.length} cincin`}
          >
          {columns.map((column, index) => {
            // SATU arti per cincin: busur = yang dihitung lensa ÷ kebutuhan.
            const isiTinggi = columnFillPct(column);
            const lebih = columnOverflow(column);
            return (
              <RadialRing
                key={column.key}
                index={index}
                pct={isiTinggi}
                tone={column.gapTone}
                value={column.coverage}
                label={column.label}
                note={column.gap}
                aria={column.aria}
                over={lebih}
                small={columns.length > 6}
                action={
                  onSelect && mode === "commodity"
                    ? {
                        label: "Tampilkan di peta",
                        title: `Tampilkan ${column.label} di peta`,
                        onClick: () => onSelect(column.label),
                      }
                    : undefined
                }
              />
            );
          })}
          </ol>
        </div>
      )}

      {/* Keterangan duduk di DASAR kartu, bukan di baris alat. Dua kartu ini
          berdampingan: dengan legenda di dasar, keduanya ditutup garis yang
          sama tingginya, dan sisa ruang kartu kiri jadi napas di tengah —
          bukan ekor kosong di bawah. Pada bentuk donat, keterangan itu sudah
          dibawa caption donat (warna = komoditas), jadi kaki kartu kosong. */}
      {donat ? null : (
      <div className="ac-foot">
        <span className="ac-key">
          <i className="ac-key-track" aria-hidden="true" />
          garis putus-putus = kebutuhan
        </span>
      </div>
      )}

    </section>
  );
}

/** Dipakai tes untuk memastikan tipe kolom tidak berubah tanpa sengaja. */
export type { AdequacyColumn };
