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

import { Fragment, useMemo, type ReactNode } from "react";

import AllocationTable from "./AllocationTable";
// FactList tidak lagi dipakai: bagian Limbah menjadi tiga angka sejajar (L5).
import PageShell from "./PageShell";
import { NETWORK_SECTION_IDS, networkSections } from "../lib/section-jump";
import { klikBaris } from "../lib/baris-klik";
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
import { formatBalanceGap, formatKg, tanpaCatatan, type BalanceMapLocation } from "../lib/overview-format";
import { planRingkas, wasteRingkas, wasteSentence } from "../lib/surplus";
import type { SupplyDemandDetail } from "../lib/supply-demand";
import styles from "./LocationNetworkBoard.module.css";
import TombolTutup from "./TombolTutup";

/**
 * Nada jaringan sebagai KATA (L2). Aturan aksesibilitas: jangan pernah
 * menyampaikan keadaan lewat warna saja. Kata-kata ini tidak memuat angka —
 * angka jaringan tetap hanya di kalimat neraca.
 */
function nadaJaringan(tone: string): string {
  switch (tone) {
    case "danger":
      return "ada kekurangan";
    case "safe":
      return "kebutuhan tertutup";
    case "neutral":
      return "tidak ada selisih";
    default:
      return "belum terbaca";
  }
}

/** Penanda bentuk arah selisih: terbaca tanpa warna. */
function markSelisih(status: string): string {
  if (status === "shortage") return "−";
  if (status === "surplus") return "+";
  if (status === "balanced") return "=";
  return "·";
}

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
  const limbahKalimat = useMemo(() => wasteSentence(limbah, wasteDays), [limbah, wasteDays]);
  const alih = useMemo(() => planRingkas(plan), [plan]);

  // Jumlah kolom yang benar-benar dipasang — dipakai `colSpan` baris rincian
  // supaya dossier di bawah baris tidak bergantung pada angka mati.
  const jumlahKolom = 3 + (adaHampir ? 1 : 0) + (adaRekomendasi ? 1 : 0);

  const menunggu = Boolean(loading) && urut.length === 0;
  const kosong = !error && !menunggu && urut.length === 0;
  const tanpaCatatanJumlah = kelengkapan.withoutSupply + kelengkapan.withoutDemand;
  const staleJumlah =
    kelengkapan.staleSupply === null || kelengkapan.staleDemand === null
      ? null
      : kelengkapan.staleSupply + kelengkapan.staleDemand;
  const adaIsu = tanpaCatatanJumlah > 0 || (staleJumlah ?? 0) > 0;

  return (
    <PageShell
      className="board-page network-page"
      busy={loading}
      title={heading}
      // Saat gagal memuat, kartu-kartunya tidak dirender — jadi nav juga tidak
      // dipasang. Nav yang menunjuk bagian yang tidak ada adalah tautan mati,
      // dan tes tata letak lama sudah menegaskan halaman gagal tidak boleh
      // menampilkan judul bagian apa pun.
      sections={error ? [] : networkSections({ hasRows: !kosong, hasTransfer: true })}
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
          {/* Keadaan kelengkapan sebagai TEKS, bukan hanya nada warna: warna
              saja tidak terbaca oleh pembaca layar dan tidak terlihat oleh
              pengguna buta warna. Angkanya tidak diulang di sini — rinciannya
              satu tempat, di daftar isu kartu keadaan jaringan. */}
          {!error && !menunggu && adaIsu ? (
            <span className="commodity-pill" data-state="sebagian">
              catatan belum lengkap
            </span>
          ) : null}
        </span>
      }
      filters={
        commodities && commodities.length > 0 && onCommodityChange ? (
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
        ) : null
      }
    >


      {error ? (
        <article className="card">
          <h2>Tidak bisa memuat saldo lokasi</h2>
          <p className="evidence-note">{error}</p>
          {onRetry ? (
            <button type="button" className="button button-secondary location-retry" onClick={onRetry}>
              Coba lagi
            </button>
          ) : null}
        </article>
      ) : null}

      {error ? null : (
        /* Kartu UTAMA halaman (L2). Bobotnya dinaikkan lewat ukuran kalimat dan
           garis tepi bernada, bukan lewat warna latar: nada jaringan dibaca dari
           kata ("ada kekurangan"), warnanya hanya penguat. */
        <article
          className="card jump-target network-lead"
          id={NETWORK_SECTION_IDS.keadaan}
          data-tone={menunggu ? "unknown" : headline.tone}
        >
          <div className="board-card-head">
            <h2>Keadaan jaringan</h2>
            {menunggu ? null : (
              <span
                className="network-lead-state"
                data-testid="network-lead-state"
                data-tone={headline.tone}
              >
                {nadaJaringan(headline.tone)}
              </span>
            )}
          </div>
          <p className="network-lead-text" data-testid="location-network-headline">
            {menunggu ? "Memuat saldo lokasi…" : headline.text}
          </p>
          {/* Satu baris, bukan daftar dua butir: isu kelengkapan adalah catatan
              kaki kalimat neraca, bukan bagian kedua halaman. Jejak audit tetap
              menempel sebagai `data-kind`. */}
          {menunggu || adaIsu === false ? null : (
            <p className="network-lead-issues" data-testid="location-network-completeness">
              {[
                tanpaCatatanJumlah > 0 ? (
                  <span key="missing" data-kind="missing">
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
                  </span>
                ) : null,
                staleJumlah !== null && staleJumlah > 0 ? (
                  <span key="stale" data-kind="stale">
                    {staleJumlah} catatan lebih dari {kelengkapan.staleAfterHours} jam
                  </span>
                ) : null,
              ]
                .filter(Boolean)
                .reduce<ReactNode[]>((kumpulan, butir, index) => {
                  if (index > 0) kumpulan.push(<span key={`pemisah-${index}`}> · </span>);
                  kumpulan.push(butir);
                  return kumpulan;
                }, [])}
            </p>
          )}
        </article>
      )}

      {/* Tabel lokasi tidak dirender saat kosong: kalimat "datanya belum masuk"
          sudah ada di kartu keadaan jaringan. Dua kalimat untuk satu keadaan
          kosong adalah pengulangan yang dikeluhkan pemilik. */}
      {error || kosong ? null : (
        <article className="card jump-target" id={NETWORK_SECTION_IDS.lokasi}>
          <div className="board-card-head">
            <h2>Lokasi</h2>
            <span className="evidence-note" data-testid="location-network-legend">
              − kurang · + lebih · = seimbang
              {adaRekomendasi ? " · Rekomendasi = usulan terbuka" : ""}
              {adaIsu ? " · bertanda = catatan belum lengkap" : null}
            </span>
          </div>

          <div className="board-table-wrap network-table-wrap">
            <table className="location-table network-table" data-testid="location-network-table">
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
                        <td data-label="Lokasi">
                          <span className="skeleton skeleton-line" />
                        </td>
                        <td data-label="Wilayah">
                          <span className="skeleton skeleton-line" />
                        </td>
                        <td data-label="Selisih">
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
                    <Fragment key={location.location}>
                    <tr
                      className={aktif ? styles.openRow : undefined}
                      data-open={aktif ? "true" : undefined}
                      /* Klik baris = buka/tutup rincian lokasi (29 Okt 2026),
                         sama dengan tombol nama lokasi di kolom pertama. */
                      data-klik-baris="true"
                      onClick={(e) =>
                        klikBaris(e, () => onSelect(aktif ? null : location.location))
                      }
                    >
                      <td data-label="Lokasi">
                        <button
                          type="button"
                          className={styles.rowButton}
                          /* Pola disclosure (L3): tombol ini membuka bagian, jadi
                             `aria-expanded` — bukan `aria-pressed` yang berarti
                             tombol tekan. `aria-controls` menunjuk kartu rincian
                             di halaman yang sama. */
                          aria-expanded={aktif}
                          aria-controls="rincian-lokasi"
                          onClick={() => onSelect(aktif ? null : location.location)}
                        >
                          <span
                            className="row-chevron"
                            aria-hidden="true"
                            data-open={aktif ? "true" : "false"}
                          />
                          {location.location}
                          {tanda.length > 0 ? (
                            <span className={styles.flag}> · {tanda.join(", ")}</span>
                          ) : null}
                        </button>
                      </td>
                      <td className={styles.region} data-label="Wilayah">
                        {location.region ?? "—"}
                      </td>
                      <td className={styles.num} data-label="Selisih" data-status={location.status}>
                        {/* Penanda bentuk di samping kata (L3): "kurang 780 kg"
                            sudah terbaca tanpa warna; tanda ini membuat arahnya
                            terlihat sekilas. `aria-hidden` karena kata di
                            sebelahnya sudah menyebut hal yang sama. */}
                        <span className="network-gap-mark" data-mark={location.status} aria-hidden="true">
                          {markSelisih(location.status)}
                        </span>
                        {formatBalanceGap(location)}
                        {/* Dua angka asal selisih, ditulis di bawahnya: tanpa ini
                            baris hanya menyebut HASIL, dan pembaca harus membuka
                            rincian untuk tahu dari mana angkanya. Nol yang tidak
                            terukur tetap "—" (tanpaCatatan). */}
                        <span className={styles.balanceSub}>
                          {tanpaCatatan(location.supply_state)
                            ? "pasokan belum dicatat"
                            : `pasokan ${formatKg(location.supply_kg)}`}
                          {" · "}
                          {tanpaCatatan(location.demand_state)
                            ? "kebutuhan belum dicatat"
                            : `kebutuhan ${formatKg(location.demand_kg)}`}
                        </span>
                      </td>
                      {adaHampir ? (
                        <td className={styles.num} data-label={`Batch ≤${expiryDays}h`} data-kind="expiry">
                          {(hampir[location.location] ?? 0) > 0
                            ? hampir[location.location]
                            : "—"}
                        </td>
                      ) : null}
                      {adaRekomendasi ? (
                        <td className={styles.num} data-label="Rekomendasi" data-kind="decision">
                          {(rekomendasi[location.location] ?? 0) > 0
                            ? rekomendasi[location.location]
                            : "—"}
                        </td>
                      ) : null}
                    </tr>
                    {aktif ? (
                      /* Dossier satu entitas (L4): rincian hidup DI DALAM tabel,
                         tepat di bawah baris yang dibuka. Sebelumnya ia kartu
                         ketiga di luar tabel — membuka rincian menggeser seluruh
                         halaman dan baris yang diklik hilang dari layar. */
                      <tr className="network-detail-row" id="rincian-lokasi">
                        <td colSpan={jumlahKolom}>
                          <div className="network-detail">
                            <div className="network-detail-head">
                              <h3>
                                {location.location} · {commodity ?? "komoditas"}
                              </h3>
                              <TombolTutup
                                label={`Tutup rincian ${location.location}`}
                                onClick={() => onSelect(null)}
                              />
                            </div>
                            <SupplyDemandPanel
                              detail={detail}
                              loading={detailLoading}
                              error={detailError}
                              commodity={commodity}
                            />
                          </div>
                        </td>
                      </tr>
                    ) : null}
                    </Fragment>
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

      {error ? null : (
        <article className="card jump-target" id={NETWORK_SECTION_IDS.alih}>
          <div className="board-card-head">
            <h2>Rencana alih</h2>
            <span className="count-pill">{alih.jumlah} pasangan</span>
          </div>
          {/* L5: kalimat yang dulu jadi catatan kaki di bawah tabel pindah ke
              kepala, supaya dua kartu terbawah dibaca dengan urutan sama:
              judul → pil jumlah → satu kalimat → isi. */}
          <p className="board-card-sentence">
            Hanya surplus ≥ {alih.ambang} kg per lokasi.
          </p>
          <AllocationTable
            plan={plan}
            loading={planLoading}
            error={planError}
            highlight={selected}
          />
        </article>
      )}

      {error ? null : (
        <article className="card jump-target" id={NETWORK_SECTION_IDS.limbah}>
          <div className="board-card-head">
            <h2>Limbah</h2>
            <span className="count-pill">{wasteDays} hari</span>
          </div>
          {wasteError ? (
            <p className="evidence-note">Limbah tidak bisa dimuat: {wasteError}</p>
          ) : limbah.length > 0 ? (
            <>
              <p className="board-card-sentence">{limbahKalimat}</p>
              {/* Tiga angka sejajar — bentuk yang sama dengan strip KPI di
                  halaman Pemasok. Angka tanpa pengukuran tetap `—` + kata. */}
              <ul className="card-figures">
                {limbah.map((row, i) => {
                  const kunci = ["tercatat", "dialihkan", "tanpa-mitra"][i] ?? `angka-${i}`;
                  const kosong = row.value.trim() === "—";
                  return (
                    <li className="card-figure" key={row.label} data-figure={kunci}>
                      <span className="card-figure-label">{row.label}</span>
                      <span
                        className="card-figure-value"
                        data-empty={kosong ? "true" : undefined}
                      >
                        {row.value}
                      </span>
                      {row.hint ? <span className="card-figure-hint">{row.hint}</span> : null}
                    </li>
                  );
                })}
              </ul>
            </>
          ) : (
            <p className="evidence-note">{wasteLoading ? "Memuat limbah…" : "Belum dicatat."}</p>
          )}
        </article>
      )}
    </PageShell>
  );
}
