"use client";

// Halaman gabungan "Location Network" / "Pasokan & Kebutuhan" (dokumen 03 §3,
// §6.3, §6.5).
//
// BENTUK: memakai bahasa desain yang sama dengan halaman lain di konsol ini —
// `board-page` → `PageHeader` → kartu `card` berjudul → tabel `location-table`,
// filter komoditas `commodity-filters`, tombol `button`. Tidak ada gaya sendiri:
// dulu halaman ini memakai CSS modul sendiri (grid, radius, warna) sehingga
// terasa seperti aplikasi lain di dalam aplikasi.
//
// ISI: satu fakta satu tempat.
//   - Angka jaringan hanya di kalimat ringkasan; tidak ada baris angka kedua.
//   - Kelengkapan hanya muncul bila ada yang perlu diketahui.
//   - "N lokasi" hanya sebagai pil kepala halaman; tanggal catatan cukup sekali.
//   - Rincian satu lokasi ada di kartu TERSENDIRI di bawah tabel, bukan di dalam
//     sel tabel: panel berisi tabel batch, dan tabel di dalam <td> merusak lebar
//     kolom tabel luar (terukur di browser).
//
// Yang dijaga: angka tak terbaca ditulis "—", tidak pernah 0; jumlah 0 dicetak
// tanpa "kg"; selama data belum datang halaman ini tidak menyimpulkan apa pun.
// Tidak ada peta, tidak ada garis koridor (keputusan pemilik 28 Okt 2026).

import { useMemo } from "react";

import AllocationTable from "./AllocationTable";
import FactList from "./FactList";
import PageHeader from "./PageHeader";
import ScrollHint from "./ScrollHint";
import SupplyDemandPanel from "./SupplyDemandPanel";
import {
  dataCompleteness,
  hampirKedaluwarsa,
  hasCoordinates,
  networkHeadline,
  rekomendasiTerbuka,
  sortBySeverity,
} from "../lib/location-network";
import { formatBalanceGap, tanpaCatatan, type BalanceMapLocation } from "../lib/overview-format";
import { wasteRingkas } from "../lib/surplus";
import type { SupplyDemandDetail } from "../lib/supply-demand";
import styles from "./LocationNetworkBoard.module.css";
import TombolTutup from "./TombolTutup";

export default function LocationNetworkBoard({
  locations,
  commodity,
  commodities,
  onCommodityChange,
  loading,
  error,
  onRetry,
  selected,
  onSelect,
  detail,
  detailLoading,
  detailError,
  snapshot,
  plan,
  planLoading,
  planError,
  waste,
  wasteDays = 30,
  wasteLoading = false,
  wasteError = null,
  batches,
  decisions,
  now,
  expiryDays = 7,
  heading = "Location Network",
  // Satu kalimat, istilah yang sama dengan tabel (kekurangan/kelebihan/selisih).
  // Versi lama berbunyi "…dan isi catatan tiap lokasi" — isi catatan tidak lagi
  // menjadi isi halaman ini, dan kata "berlebih" berbeda dari "kelebihan" di
  // kalimat ringkasan pada layar yang sama.
  description = "Siapa kekurangan, siapa kelebihan, apa yang dialihkan, dan apa yang terbuang.",
}: {
  locations: readonly BalanceMapLocation[];
  commodity?: string;
  commodities?: readonly string[];
  onCommodityChange?: (commodity: string) => void;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  /** Lokasi yang rinciannya sedang dibaca. `null` = tidak ada. */
  selected: string | null;
  onSelect: (name: string | null) => void;
  detail: SupplyDemandDetail | null;
  detailLoading?: boolean;
  detailError?: string | null;
  /** Tanggal catatan yang dipakai halaman ini (bukan jam pengambilan). */
  snapshot?: string | null;
  /** Respons GET /surplus/allocations — rencana alih lintas lokasi dari server. */
  plan?: unknown;
  planLoading?: boolean;
  planError?: string | null;
  /** Respons GET /waste/summary — tiga angka limbah, bukan hitungan klien. */
  waste?: unknown;
  wasteDays?: number;
  wasteLoading?: boolean;
  wasteError?: string | null;
  /** Respons GET /batches — dipakai kolom "Batch ≤7h". */
  batches?: readonly unknown[] | null;
  /** Daftar GET /decisions — dipakai kolom "Rekomendasi". */
  decisions?: readonly { status?: unknown; target_location_name?: unknown }[] | null;
  /** Waktu acuan untuk masa layak (bisa dikunci di tes). */
  now?: Date | null;
  expiryDays?: number;
  heading?: string;
  description?: string;
}) {
  const headline = useMemo(() => networkHeadline(locations), [locations]);
  const kelengkapan = useMemo(() => dataCompleteness(locations), [locations]);
  const urut = useMemo(() => sortBySeverity(locations), [locations]);
  const hampir = useMemo(
    () => hampirKedaluwarsa(batches ?? null, now ?? new Date(), expiryDays),
    [batches, now, expiryDays]
  );
  const rekomendasi = useMemo(() => rekomendasiTerbuka(decisions ?? null), [decisions]);
  // Kolom hanya dipasang bila ADA baris yang perlu dibaca: kolom berisi "—" di
  // semua baris adalah kolom tanpa informasi (aturan yang sama dengan
  // kelengkapan data di atas).
  const adaHampir = urut.some((l) => (hampir[l.location] ?? 0) > 0);
  const adaRekomendasi = urut.some((l) => (rekomendasi[l.location] ?? 0) > 0);
  const limbah = useMemo(() => wasteRingkas(waste), [waste]);

  const menunggu = Boolean(loading) && urut.length === 0;
  const kosong = !error && !menunggu && urut.length === 0;
  const tanpaCatatanJumlah = kelengkapan.withoutSupply + kelengkapan.withoutDemand;
  const staleJumlah =
    kelengkapan.staleSupply === null || kelengkapan.staleDemand === null
      ? null
      : kelengkapan.staleSupply + kelengkapan.staleDemand;
  const adaIsu = tanpaCatatanJumlah > 0 || (staleJumlah ?? 0) > 0;

  return (
    <section className="board-page" aria-busy={loading || undefined}>
      <PageHeader
        title={heading}
        description={description}
        meta={
          <span className="page-header-pills">
            {snapshot ? <span className="commodity-pill">{snapshot}</span> : null}
            {/* Jumlah lokasi hanya dicetak bila barisnya benar-benar terbaca:
                selama memuat atau saat gagal, "0 lokasi" terbaca sebagai hasil
                pengukuran padahal halaman belum tahu apa-apa. */}
            {!error && !menunggu ? (
              <span className="commodity-pill">{urut.length} lokasi</span>
            ) : null}
          </span>
        }
      />

      {commodities && commodities.length > 0 && onCommodityChange ? (
        <div className="commodity-filters" role="group" aria-label="Komoditas">
          <span className="commodity-filters-label">Komoditas:</span>
          {commodities.map((item) => (
            <button
              key={item}
              type="button"
              className={`commodity-pill${item === commodity ? " commodity-pill-active" : ""}`}
              aria-pressed={item === commodity}
              onClick={() => onCommodityChange(item)}
            >
              {item}
            </button>
          ))}
        </div>
      ) : null}

      {error ? (
        <article className="card">
          <h2>Tidak bisa memuat saldo lokasi</h2>
          <p className="evidence-note">{error}</p>
          {onRetry ? (
            <button type="button" className="button button-secondary" onClick={onRetry}>
              Coba lagi
            </button>
          ) : null}
        </article>
      ) : null}

      {error ? null : (
        <article className="card" data-tone={menunggu ? "unknown" : headline.tone}>
          <div className="board-card-head">
            <h2>Keadaan jaringan</h2>
          </div>
          <p className={styles.headline} data-testid="location-network-headline">
            {menunggu ? "Memuat saldo lokasi…" : headline.text}
          </p>
          {menunggu || adaIsu === false ? null : (
            <ul className={styles.issues} data-testid="location-network-completeness">
              {tanpaCatatanJumlah > 0 ? (
                <li data-kind="missing">
                  {[
                    kelengkapan.withoutSupply > 0
                      ? `${kelengkapan.withoutSupply} tanpa catatan pasokan`
                      : null,
                    kelengkapan.withoutDemand > 0
                      ? `${kelengkapan.withoutDemand} tanpa catatan permintaan`
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </li>
              ) : null}
              {staleJumlah !== null && staleJumlah > 0 ? (
                <li data-kind="stale">
                  {staleJumlah} catatan lebih dari {kelengkapan.staleAfterHours} jam
                </li>
              ) : null}
            </ul>
          )}
        </article>
      )}

      {/* Tabel lokasi tidak dirender saat kosong: kalimat "datanya belum masuk"
          sudah ada di kartu keadaan jaringan. Dua kalimat untuk satu keadaan
          kosong adalah pengulangan yang dikeluhkan pemilik. */}
      {error || kosong ? null : (
        <article className="card">
          <div className="board-card-head">
            <h2>Lokasi</h2>
            {adaIsu ? <span className="evidence-note">bertanda = catatan belum lengkap</span> : null}
          </div>

          <div className="board-table-wrap">
            <table className="location-table" data-testid="location-network-table">
              <thead>
                <tr>
                  <th scope="col">Lokasi</th>
                  <th scope="col" className={styles.region}>
                    Wilayah
                  </th>
                  <th scope="col" className={styles.num}>
                    Selisih
                  </th>
                  {adaHampir ? (
                    <th scope="col" className={styles.num} title={`Batch layak ≤ ${expiryDays} hari`}>
                      Batch ≤{expiryDays}h
                    </th>
                  ) : null}
                  {adaRekomendasi ? (
                    <th scope="col" className={styles.num}>
                      Rekomendasi
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {/* Tiga baris kerangka: menahan tinggi tabel supaya isi tidak
                    melompat saat data datang, tanpa mencetak angka apa pun. */}
                {menunggu
                  ? [0, 1, 2].map((baris) => (
                      <tr key={baris} aria-hidden="true">
                        <td>
                          <span className="skeleton skeleton-line" />
                        </td>
                        <td>
                          <span className="skeleton skeleton-line" />
                        </td>
                        <td>
                          <span className="skeleton skeleton-line" />
                        </td>
                      </tr>
                    ))
                  : null}
                {menunggu ? null : urut.map((location) => {
                  const aktif = location.location === selected;
                  const tanda: string[] = [];
                  if (tanpaCatatan(location.supply_state)) tanda.push("tanpa pasokan");
                  if (tanpaCatatan(location.demand_state)) tanda.push("tanpa permintaan");
                  if (!hasCoordinates(location)) tanda.push("tanpa koordinat");
                  return (
                    <tr key={location.location} className={aktif ? styles.openRow : undefined} data-open={aktif ? "true" : undefined}>
                      <td>
                        <button
                          type="button"
                          className={styles.rowButton}
                          aria-pressed={aktif}
                          aria-controls="rincian-lokasi"
                          onClick={() => onSelect(aktif ? null : location.location)}
                        >
                          <span className={styles.chevron} aria-hidden="true">
                            {aktif ? "▾" : "▸"}
                          </span>
                          {location.location}
                          {tanda.length > 0 ? (
                            <span className={styles.flag}> · {tanda.join(", ")}</span>
                          ) : null}
                        </button>
                      </td>
                      <td className={styles.region}>{location.region ?? "—"}</td>
                      <td className={styles.num} data-status={location.status}>
                        {formatBalanceGap(location)}
                      </td>
                      {adaHampir ? (
                        <td className={styles.num} data-kind="expiry">
                          {(hampir[location.location] ?? 0) > 0
                            ? hampir[location.location]
                            : "—"}
                        </td>
                      ) : null}
                      {adaRekomendasi ? (
                        <td className={styles.num} data-kind="decision">
                          {(rekomendasi[location.location] ?? 0) > 0
                            ? rekomendasi[location.location]
                            : "—"}
                        </td>
                      ) : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {/* Petunjuk geser HANYA muncul bila tabel memang tidak muat (diukur
              `ScrollHint`): pada 390 px empat kolom masih melebihi 316 px. */}
          <ScrollHint />
          {/* Cakupan satu lokasi: satu baris kaki, bukan paragraf di kepala
              (dulu halaman ini menjelaskan cakupan peran dalam tiga baris). */}
          {!menunggu && urut.length === 1 ? (
            <p className="evidence-note">Akun ini hanya mencakup satu lokasi.</p>
          ) : null}
        </article>
      )}

      {error || !selected || kosong ? null : (
        <article className="card" id="rincian-lokasi">
          <div className="board-card-head">
            <h2>
              {selected} · {commodity ?? "komoditas"}
            </h2>
            {/* 29 Okt 2026: kartu rincian ditutup dengan X bulat yang sama
                dengan penutup lain, bukan tombol teks selebar katanya. */}
            <TombolTutup
              label={`Tutup rincian ${selected}`}
              onClick={() => onSelect(null)}
            />
          </div>
          <SupplyDemandPanel
            detail={detail}
            loading={detailLoading}
            error={detailError}
            commodity={commodity}
          />
        </article>
      )}

      {error ? null : (
        <article className="card">
          <div className="board-card-head">
            <h2>Rencana alih</h2>
          </div>
          <AllocationTable
            plan={plan}
            loading={planLoading}
            error={planError}
            highlight={selected}
          />
        </article>
      )}

      {error ? null : (
        <article className="card">
          <div className="board-card-head">
            <h2>Limbah · {wasteDays} hari terakhir</h2>
          </div>
          {wasteError ? (
            <p className="evidence-note">Limbah tidak bisa dimuat: {wasteError}</p>
          ) : limbah.length > 0 ? (
            <FactList rows={limbah} />
          ) : (
            <p className="evidence-note">{wasteLoading ? "Memuat limbah…" : "Belum dicatat."}</p>
          )}
        </article>
      )}
    </section>
  );
}
