"use client";

/**
 * Monitor harga komoditas (28 Okt 2026) — Overview.
 *
 * Datanya `GET /price/monitor`: salinan harian PIHPS Bank Indonesia (Pasar
 * Tradisional, Rp/kg). Panel ini menggantikan "Informasi pengiriman",
 * "Telemetri Node", dan daftar "Status Lokasi" di Overview.
 *
 * Aturan yang dipegang:
 *  - Cakupan mengikuti dropdown lokasi di bar atas; tanpa pilihan = baris
 *    nasional. Bila baris kota tidak diterbitkan (Cianjur), panel jatuh ke
 *    provinsi DAN menyebutkannya — tidak menyamar sebagai harga kota.
 *  - Sel kosong (Sabtu/Minggu) digambar sebagai jarak, bukan harga 0.
 *  - Sumber + waktu tarik selalu tertulis; tanpa itu grafik ini cuma gambar.
 *  - Angka juga tersedia sebagai tabel (pembaca layar & yang butuh presisi),
 *    bukan hanya warna garis.
 */
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { usePriceMonitor } from "../lib/hooks/usePriceMonitor";
import {
  KOMODITAS_PANEL,
  formatPersen,
  formatRp,
  kandidatWilayah,
  labelTanggalPanjang,
  labelJamTarik,
  labelTanggalPendek,
  ringkasKomoditas,
  ringkasanTeks,
  susunSeri,
} from "../lib/price-monitor";
import { ALL_LOCATIONS } from "../lib/topbar";
import { LoadingState } from "./LoadingState";

/** Warna garis: token di `app/globals.css` (bukan hex di komponen). */
/**
 * Pola garis pembeda selain warna (WCAG 1.4.1: warna tidak boleh satu-satunya
 * pembeda). Dipakai juga oleh contoh garis di legenda supaya cocok dengan grafik.
 */
const POLA_SERI: Record<string, string | undefined> = {
  com_3: undefined, // beras — solid
  com_10: "6 3", // telur — putus
  com_7: "2 2", // ayam — titik
};

const WARNA_SERI: Record<string, string> = {
  com_3: "var(--chart-series-1)",
  com_10: "var(--chart-series-2)",
  com_7: "var(--chart-series-3)",
};

const RENTANG = [
  { hari: 7, label: "7 hari" },
  { hari: 30, label: "30 hari" },
  { hari: 90, label: "90 hari" },
];

const KODE_AWAL = KOMODITAS_PANEL.map((k) => k.kode);

type Mode = "indeks" | "rupiah";

/** Tooltip: selalu menyebut RUPIAH, dan indeks hanya sebagai alat pembanding. */
function TooltipHarga({
  active,
  payload,
  label,
  mode,
}: {
  active?: boolean;
  payload?: Array<{
    dataKey?: string | number;
    name?: string;
    value?: number;
    color?: string;
    payload?: Record<string, number | string | null>;
  }>;
  label?: string | number;
  mode: Mode;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const titik = payload[0]?.payload ?? {};
  return (
    <div className="pm-tooltip">
      <p className="pm-tooltip-judul">{String(label ?? "")}</p>
      <ul className="pm-tooltip-list">
        {payload.map((baris) => {
          const kode = String(baris.dataKey ?? "").replace("idx_", "");
          const rupiah = titik[kode];
          return (
            <li key={kode}>
              <span
                className="pm-swatch"
                data-pola={POLA_SERI[kode] ?? "solid"}
                style={{ ["--sw" as string]: String(baris.color ?? "currentColor") }}
                aria-hidden="true"
              />
              <span className="pm-tooltip-nama">{baris.name}</span>
              <span className="pm-tooltip-nilai">
                {formatRp(typeof rupiah === "number" ? rupiah : null)}
              </span>
              {mode === "indeks" && typeof baris.value === "number" && (
                <span className="pm-tooltip-indeks">
                  {baris.value.toLocaleString("id-ID", { maximumFractionDigits: 1 })}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function PriceMonitor({
  token,
  activeLocation,
  lokasiSendiri,
}: {
  token: string | null;
  /** Nilai dropdown cakupan top bar; `ALL_LOCATIONS` = tanpa lokasi terpilih. */
  activeLocation: string | null;
  /**
   * Lokasi akun SPPG/gizi yang sedang masuk. Dipakai sebagai cadangan ketika
   * top bar tidak mengirim pilihan: akun yang terikat satu SPPG selalu membaca
   * harga wilayahnya sendiri, bukan baris nasional — "harga pasar" tanpa
   * wilayah tidak bisa dipakai membeli apa pun.
   */
  lokasiSendiri?: string | null;
}) {
  const [hari, setHari] = useState(30);
  const [kodeAktif, setKodeAktif] = useState<string[]>(KODE_AWAL);
  const [pakaiCadangan, setPakaiCadangan] = useState(false);
  // Bawaan INDEKS: tiga komoditas punya level harga jauh berbeda, sehingga
  // grafik rupiah terbaca sebagai tiga garis datar. Rupiah tetap tersedia.
  const [mode, setMode] = useState<Mode>("indeks");
  const [terpasang, setTerpasang] = useState(false);

  // Recharts butuh DOM; render grafiknya setelah mount supaya SSR tidak
  // menghasilkan markup yang berbeda (dan tidak ada lompatan tata letak).
  useEffect(() => setTerpasang(true), []);

  const lokasiTopBar =
    activeLocation && activeLocation !== ALL_LOCATIONS ? activeLocation : null;
  const lokasiTerikat = (lokasiSendiri ?? "").trim() || null;
  const lokasi = lokasiTopBar ?? lokasiTerikat;
  /** true = wilayah diambil dari akun, bukan dari pemilih di bar atas. */
  const lokasiDariAkun = !lokasiTopBar && Boolean(lokasiTerikat);
  const kandidat = useMemo(() => kandidatWilayah(lokasi), [lokasi]);
  const wilayah = kandidat[Math.min(pakaiCadangan ? 1 : 0, Math.max(kandidat.length - 1, 0))] ?? null;

  // Kandidat berubah (lokasi lain dipilih) → mulai lagi dari kandidat utama.
  useEffect(() => setPakaiCadangan(false), [lokasi]);

  const kueri = usePriceMonitor(token, wilayah?.nama ?? null, hari, kodeAktif.join(","));

  const data = kueri.data;
  const kosong = data?.status === "kosong";

  // Baris kota tidak ada → coba cadangan provinsi sekali. Tidak ada tebakan
  // lain: bila cadangan juga kosong, panel menyebut alasannya.
  useEffect(() => {
    if (!kosong || pakaiCadangan || kandidat.length < 2) return;
    setPakaiCadangan(true);
  }, [kosong, pakaiCadangan, kandidat.length]);

  // `??` di dalam useMemo-mu sendiri: tanpa ini senarai baris baru setiap render
  // dan turunan (seri, ringkasan, pergerakan) dihitung ulang terus.
  const rows = useMemo(() => data?.rows ?? [], [data]);
  const seri = useMemo(() => susunSeri(rows, kodeAktif), [rows, kodeAktif]);
  const ringkasan = useMemo(
    () => kodeAktif.map((kode) => ringkasKomoditas(rows, kode)),
    [rows, kodeAktif]
  );
  // Pergerakan datang dari server (dihitung dari seluruh snapshot, bukan dari
  // satu wilayah yang sedang difilter panel).
  const pergerakan = data?.movers ?? [];
  const namaKomoditas = (kode: string) =>
    KOMODITAS_PANEL.find((k) => k.kode === kode)?.nama ??
    data?.commodities.find((k) => k.code === kode)?.label ??
    kode;

  const adaAngka = rows.length > 0;

  function toggleKode(kode: string) {
    setKodeAktif((sebelum) => {
      if (sebelum.includes(kode)) {
        // Jangan biarkan panel tanpa garis sama sekali: satu komoditas minimal.
        return sebelum.length === 1 ? sebelum : sebelum.filter((k) => k !== kode);
      }
      return [...sebelum, kode];
    });
  }

  return (
    <section className="card price-monitor" aria-labelledby="pm-judul">
      <div className="pm-head">
        <div className="pm-head-main">
          <h3 id="pm-judul">Monitor harga komoditas</h3>
          <p className="pm-source">
            {data?.source ? (
              <>
                Sumber: {data.source} · {data.market ?? "Pasar Tradisional"} · harga{" "}
                <strong>{wilayah?.nama ?? "nasional"}</strong> · data terakhir{" "}
                {labelTanggalPanjang(data.coverage?.tanggal_terakhir)} · ditarik{" "}
                {labelJamTarik(data.fetched_at)}
              </>
            ) : (
              "Sumber: PIHPS Bank Indonesia (harian, Rp/kg)"
            )}
          </p>
        </div>
        <div className="pm-controls">
          <div className="pm-chips" role="group" aria-label="Komoditas yang ditampilkan">
            {KOMODITAS_PANEL.map((k) => {
              const aktif = kodeAktif.includes(k.kode);
              return (
                <button
                  key={k.kode}
                  type="button"
                  className={`pm-chip${aktif ? " pm-chip-aktif" : ""}`}
                  aria-pressed={aktif}
                  onClick={() => toggleKode(k.kode)}
                >
                  <span
                    className="pm-swatch"
                    data-pola={POLA_SERI[k.kode] ?? "solid"}
                    style={{ ["--sw" as string]: WARNA_SERI[k.kode] }}
                    aria-hidden="true"
                  />
                  {k.nama}
                </button>
              );
            })}
          </div>
          <div className="pm-range" role="group" aria-label="Skala grafik">
            {(["indeks", "rupiah"] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                className={`pm-range-pil${mode === m ? " pm-range-aktif" : ""}`}
                aria-pressed={mode === m}
                onClick={() => setMode(m)}
                title={
                  m === "indeks"
                    ? "Tiap komoditas dimulai dari 100 supaya perubahan % bisa dibandingkan"
                    : "Harga apa adanya dalam rupiah per kg"
                }
              >
                {m === "indeks" ? "Indeks" : "Rupiah"}
              </button>
            ))}
          </div>
          <div className="pm-range" role="group" aria-label="Jendela waktu">
            {RENTANG.map((r) => (
              <button
                key={r.hari}
                type="button"
                className={`pm-range-pil${hari === r.hari ? " pm-range-aktif" : ""}`}
                aria-pressed={hari === r.hari}
                onClick={() => setHari(r.hari)}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {lokasiDariAkun && !wilayah?.catatan && (
        <p className="pm-note">
          Wilayah harga mengikuti SPPG ini ({lokasiTerikat}).
        </p>
      )}
      {wilayah?.catatan && <p className="pm-note">{wilayah.catatan}</p>}

      {!token && <p className="pm-empty">Masuk dulu untuk melihat harga pasar.</p>}

      {token && kueri.loading && !data && (
        <div className="pm-loading">
          <LoadingState label="Memuat harga pasar…" />
        </div>
      )}

      {token && kueri.error && (
        <p className="status-danger pm-error" role="alert">
          Gagal memuat harga pasar: {kueri.error}{" "}
          <button type="button" onClick={() => void kueri.refetch()}>
            Coba lagi
          </button>
        </p>
      )}

      {token && !kueri.loading && !kueri.error && !adaAngka && (
        <p className="pm-empty">
          {data?.alasan ??
            "Belum ada baris harga untuk wilayah dan komoditas ini pada jendela waktu tersebut."}
        </p>
      )}

      {adaAngka && (
        <>
          <p className="sr-only">{ringkasanTeks(ringkasan, namaKomoditas)}</p>
          <div className="pm-body">
            <div className="pm-chart">
              {terpasang ? (
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart
                    data={seri.data}
                    margin={{ top: 8, right: 16, bottom: 4, left: 0 }}
                    aria-label={`Grafik harga ${kodeAktif.map(namaKomoditas).join(", ")} per kg`}
                  >
                    <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="label"
                      tick={{ fill: "var(--ink-muted)", fontSize: 12 }}
                      tickLine={false}
                      axisLine={{ stroke: "var(--line)" }}
                      minTickGap={16}
                    />
                    <YAxis
                      width={52}
                      domain={["auto", "auto"]}
                      tick={{ fill: "var(--ink-muted)", fontSize: 12 }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(nilai: number) =>
                        mode === "indeks"
                          ? String(Math.round(nilai))
                          : `${Math.round(nilai / 1000)}rb`
                      }
                    />
                    <Tooltip
                      content={<TooltipHarga mode={mode} />}
                      wrapperStyle={{ outline: "none" }}
                    />
                    {kodeAktif.map((kode) => (
                      <Line
                        key={kode}
                        type="monotone"
                        dataKey={mode === "indeks" ? `idx_${kode}` : kode}
                        name={namaKomoditas(kode)}
                        stroke={WARNA_SERI[kode]}
                        strokeWidth={2}
                        strokeDasharray={POLA_SERI[kode]}
                        dot={false}
                        activeDot={{ r: 4 }}
                        // Hari tanpa publikasi = jarak, bukan garis turun ke nol.
                        connectNulls={false}
                        isAnimationActive={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="pm-chart-placeholder" aria-hidden="true" />
              )}
              {mode === "indeks" && seri.data.length > 0 && (
                <p className="pm-sumbu-note">
                  Skala indeks: 100 = harga pada {labelTanggalPanjang(String(seri.data[0].tanggal))}.
                  Tiap komoditas dibandingkan dengan titik awalnya sendiri, jadi naik-turunnya
                  sebanding meski harga dasarnya berbeda.
                </p>
              )}
            </div>

            <aside className="pm-side" aria-label="Ringkasan harga">
              <ul className="pm-stats">
                {ringkasan.map((r) => (
                  <li key={r.kode} className="pm-stat">
                    <span className="pm-stat-nama">
                      <span
                        className="pm-swatch"
                        data-pola={POLA_SERI[r.kode] ?? "solid"}
                        style={{ ["--sw" as string]: WARNA_SERI[r.kode] }}
                        aria-hidden="true"
                      />
                      {namaKomoditas(r.kode)}
                    </span>
                    <span className="pm-stat-angka">
                      <strong>{formatRp(r.terakhir)}</strong>
                      <span className="pm-stat-unit">/kg</span>
                    </span>
                    <span className="pm-stat-delta">
                      <span
                        className={
                          r.deltaTujuh === null
                            ? "pm-delta"
                            : r.deltaTujuh > 0
                              ? "pm-delta pm-naik"
                              : r.deltaTujuh < 0
                                ? "pm-delta pm-turun"
                                : "pm-delta"
                        }
                      >
                        {formatPersen(r.deltaTujuh)}
                      </span>
                      <span className="pm-stat-meta">
                        {r.tanggalPembanding
                          ? `sejak ${labelTanggalPendek(r.tanggalPembanding)}`
                          : "tanpa pembanding"}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>

              {pergerakan.length > 0 && (
                <>
                  <h4 className="pm-side-judul">
                    Pergerakan teratas · {namaKomoditas(kodeAktif[0] ?? "")}
                  </h4>
                  <ol className="pm-movers">
                    {pergerakan.map((p) => (
                      <li key={p.region_name} className="pm-mover">
                        <span className="pm-mover-wilayah">{p.region_name}</span>
                        <span
                          className={
                            p.delta_pct > 0
                              ? "pm-delta pm-naik"
                              : p.delta_pct < 0
                                ? "pm-delta pm-turun"
                                : "pm-delta"
                          }
                        >
                          {formatPersen(p.delta_pct)}
                        </span>
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </aside>
          </div>

          <details className="pm-tabel-wrap">
            <summary>Lihat tabel angka ({seri.data.length} tanggal publikasi)</summary>
            {/* Seluruh tanggal ditampilkan, terbaru di atas: ringkasan di atas
                menyebut jumlahnya, jadi tabel yang memotong baris akan membuat
                angka di kepala dan isi tabel bercerita beda. */}
            <div className="pm-tabel-gulir" tabIndex={0} role="group" aria-label="Tabel harga per tanggal">
              <table className="pm-tabel">
                <caption>
                  Harga {data?.unit ?? "Rp/kg"} — {wilayah?.nama ?? "nasional"} · sumber{" "}
                  {data?.source ?? "PIHPS"} · terbaru di atas
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Tanggal</th>
                    {kodeAktif.map((kode) => (
                      <th key={kode} scope="col">
                        {namaKomoditas(kode)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...seri.data].reverse().map((titik) => (
                    <tr key={String(titik.tanggal)}>
                      <th scope="row">{labelTanggalPanjang(String(titik.tanggal))}</th>
                      {kodeAktif.map((kode) => (
                        <td key={kode}>{formatRp(titik[kode] as number | null)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
