"use client";

// Halaman "Pemasok" — halaman sidebar acuan /suppliers, disesuaikan ke repo ini.
//
// Fase 3 (2026-10-14): daftar pemasok kini dari `GET /suppliers` (endpoint Fase 2).
// Sebelumnya halaman ini menyusun daftarnya dari pemasok yang muncul pada sampel
// keputusan terakhir dan menuliskan keterbatasan itu di layar — keterbatasan itu
// sudah hilang, jadi catatannya juga hilang.
//
// Register eksklusi tetap dari /supplier-exclusions, dan form usul eksklusi tetap
// memakai panel yang sudah ada (alur approval-nya tidak berubah).
//
// Fase 7b (2026-10-15): kolom Jarak + penyaring "Dalam jangkauan". Tabel ini
// sengaja menampilkan SEMUA pemasok (jarak ditulis apa adanya, yang jauh diberi
// label "di luar jangkauan") — penyaringan di sini adalah pilihan pengguna, bukan
// default yang menyembunyikan baris. Angka jaraknya datang dari `distance_km`
// server, bukan hitungan UI.

import { useState } from "react";

import PageHeader from "./PageHeader";
import FactList from "./FactList";
import Pager from "./Pager";
import ShipmentBoard from "./ShipmentBoard";
import { SupplierExclusionView } from "./SupplierExclusionPanel";
import {
  directoryMetrics,
  directoryReachLabel,
  directoryReachSummary,
  directoryReachTagLabel,
  exclusionCounts,
  exclusionRows,
  exclusionStatusLabel,
  filterDirectoryByReach,
  supplierDirectory,
  supplierMetaLine,
} from "../lib/suppliers-board";
import {
  LOW_RELIABILITY,
  shippingMetaLine,
  shippingTagLabel,
  supplierDistanceReference,
  withinReachKm,
} from "../lib/supplier-pins";
import {
  routeCellLabel,
  routeCellTitle,
  routeLayerSummary,
  supplierRouteSummaries,
} from "../lib/supplier-routes";

/** Jarak baris ada di dalam ambang jangkauan (jarak tak diketahui = tidak diklaim dekat). */
function jarakDalamJangkauan(
  row: { distanceKm: number | null },
  reachKm: number
): boolean {
  return withinReachKm(row.distanceKm, reachKm);
}
import type { SupplierContext } from "../lib/supplier-exclusions";
import { LoadingState } from "./LoadingState";
import ScrollHint from "./ScrollHint";
import { kodeWilayah } from "../lib/wilayah";
import { paginate } from "../lib/pagination";
import { searchSuppliers } from "../lib/supplier-search";

/** Baris per halaman — permintaan pemilik 19 Okt 2026 (10 per halaman). */
const BARIS_PER_HALAMAN = 10;

export default function SupplierBoard({
  suppliers,
  exclusions,
  selectedDecisionId,
  supplierContext,
  role,
  token,
  loading = false,
  error = null,
  onRetry,
  onOpenDecision,
  onExclusionCreated,
  reachKm = null,
  supplierRoutes = null,
}: {
  /** Payload `GET /suppliers` (amplop atau array). `null` = belum dimuat. */
  suppliers: unknown;
  exclusions: unknown;
  selectedDecisionId: string | null;
  supplierContext: SupplierContext | null;
  role: string;
  token: string;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onOpenDecision?: (decisionId: string) => void;
  onExclusionCreated?: () => void;
  /** Ambang jangkauan (km) untuk penyaring tabel; `null` = tanpa ambang (nasional). */
  reachKm?: number | null;
  /**
   * Payload `GET /supplier-routes` untuk kolom "Jalur kirim". `null` = belum
   * dimuat (ditulis "…"), BUKAN "tidak punya jalur" — dua keadaan itu berbeda.
   */
  supplierRoutes?: unknown;
}) {
  const directoryDimuat = suppliers !== null && suppliers !== undefined;
  const rows = supplierDirectory(suppliers);
  const reference = supplierDistanceReference(suppliers);
  const metrics = directoryMetrics(rows, reachKm);
  const [hanyaJangkauan, setHanyaJangkauan] = useState(false);
  const penyaringAktif = hanyaJangkauan && reachKm !== null;
  const shownRows = penyaringAktif ? filterDirectoryByReach(rows, reachKm) : rows;
  // Halaman tabel pemasok: nomor halaman dijepit oleh `paginate`, jadi data yang
  // menyusut (penyaring/segarkan) berakhir di halaman terakhir yang terisi —
  // bukan tabel kosong. Penyaring mengembalikan pembaca ke halaman 1.
  const [halamanPemasok, setHalamanPemasok] = useState(1);
  // Pencarian "Daftar pemasok" (19 Okt 2026) menyaring daftar yang SUDAH dimuat,
  // setelah penyaring jangkauan dan SEBELUM paginasi — angka di kartu Ringkasan
  // tetap dihitung dari daftar penuh, jadi mencari tidak mengubah ringkasan.
  const [kueri, setKueri] = useState("");
  const dicari = searchSuppliers(shownRows, kueri);
  const halaman = paginate(dicari, halamanPemasok, BARIS_PER_HALAMAN);
  const hapusPencarian = () => {
    setKueri("");
    setHalamanPemasok(1);
  };
  const reachSummary = directoryReachSummary(rows, reachKm, reference?.location);
  // `null` = register belum dimuat (endpoint belum dipanggil / gagal) — beda dari
  // array kosong yang berarti "sudah dimuat, memang tidak ada eksklusi".
  const registerDimuat = exclusions !== null && exclusions !== undefined;
  const register = exclusionRows(
    exclusions && typeof exclusions === "object" && "items" in (exclusions as object)
      ? (exclusions as { items?: unknown }).items
      : exclusions
  );
  const lowThreshold = `${Math.round(LOW_RELIABILITY * 100)}%`;
  // Kolom "Jalur kirim": ringkasan per PEMASOK dari data jalur server. Baris
  // pemasok tanpa kiriman aktif tidak punya jalur — selnya "—", bukan "0 km".
  const jalurDimuat = supplierRoutes !== null && supplierRoutes !== undefined;
  const jalurPerPemasok = supplierRouteSummaries(supplierRoutes);
  const jalurRingkas = routeLayerSummary(supplierRoutes);

  return (
    <section className="board-page" aria-busy={loading || undefined}>
      <PageHeader
        title="Pemasok"
        description="Daftar pemasok di jaringan, kepercayaan, sebarannya di peta, register eksklusi, dan usul eksklusi baru."
        meta={
          <span className="page-header-pills">
            <span className="commodity-pill">{metrics.suppliers} pemasok</span>
            <span className="commodity-pill">{register.length} eksklusi</span>
          </span>
        }
      />

      {error ? (
        <article className="card">
          <h2>Tidak bisa memuat data pemasok</h2>
          <p className="evidence-note">
            Data pemasok tidak bisa diambil dari server aplikasi saat ini. Coba muat
            ulang; kalau masih gagal, periksa koneksi ke backend dan coba lagi.
          </p>
          {onRetry ? (
            <button type="button" className="button button-secondary" onClick={onRetry}>
              Coba lagi
            </button>
          ) : null}
        </article>
      ) : null}

      {/* Fase 12c (16 Okt 2026): kartu Ringkasan TIDAK lagi separuh halaman.
          Sebelumnya ia duduk di grid 2 kolom tanpa tetangga (terukur 466 px dari
          947 px) sehingga 7 baris fakta memanjang ke bawah; sekarang selebar
          halaman dengan fakta disusun beberapa kolom (lihat CSS `.supplier-summary`). */}
      <div className="board-grid">
        <article className="card supplier-summary">
          <h2>Ringkasan</h2>
          <FactList
            rows={[
              {
                label: "Pemasok terdaftar",
                value: !directoryDimuat && loading ? "…" : String(metrics.suppliers),
              },
              {
                label: "Rata-rata keandalan",
                value: metrics.avgReliabilityLabel,
                tone: metrics.avgReliability === null ? "plain" : metrics.avgReliability >= 0.8 ? "ok" : "warn",
              },
              {
                label: `Keandalan rendah (< ${lowThreshold})`,
                value: String(metrics.lowReliability),
                tone: metrics.lowReliability ? "warn" : "plain",
              },
              {
                label: "Punya titik peta",
                value: `${metrics.withCoordinates} dari ${metrics.suppliers}`,
              },
              // Keputusan pemilik 2026-10-16: kiriman berjalan = batch masih
              // layak hari ini. Angkanya dari `shipping` server, bukan hitungan UI.
              {
                label: "Pemasok dengan stok layak",
                value: `${metrics.shipping} dari ${metrics.suppliers}`,
                tone: metrics.shipping ? ("ok" as const) : ("plain" as const),
              },
              ...(reachKm === null
                ? []
                : [
                    {
                      label: `Di luar jangkauan ${reachKm} km`,
                      value: `${metrics.outOfReach} dari ${metrics.suppliers}`,
                      tone: metrics.outOfReach ? ("warn" as const) : ("plain" as const),
                    },
                  ]),
              ...(jalurDimuat
                ? [
                    {
                      label: "Jalur kiriman (jalan)",
                      value: `${jalurRingkas.withRoad} dari ${jalurRingkas.routes}`,
                      tone:
                        jalurRingkas.routes && jalurRingkas.withRoad < jalurRingkas.routes
                          ? ("warn" as const)
                          : ("plain" as const),
                    },
                  ]
                : []),
              {
                label: "Pemasok dieksklusi",
                // Audit 26 Okt 2026: `register.length` mencampur entri `active`
                // dan `proposed`, sehingga "2" terbaca dua pemasok sudah
                // dikecualikan. Sekarang dipisah sesuai statusnya.
                value: `${exclusionCounts(register).active} aktif · ${
                  exclusionCounts(register).proposed
                } menunggu`,
                tone: exclusionCounts(register).active ? "danger" : "plain",
              },
            ]}
          />
          <p className="evidence-note">
            Eksklusi bukan pelabelan hiasan: pemasok yang dikecualikan tidak dipilih lagi saat
            sistem menyusun pesanan pembelian.
          </p>
        </article>
      </div>

      {/* Papan kiriman (Arah B riset 16 Okt 2026): satu baris per KIRIMAN —
          pemasok, tujuan, muatan, jalur, berangkat, ETA, sisa, masa layak, mutu,
          keadaan — dengan urutan "paling mendesak". Menggantikan kartu ringkas
          di halaman ini (dan peran kolom teks "Jalur kirim"): papan sudah memuat
          semua angka itu per kiriman, dan menyimpan keduanya hanya akan menjadi
          dua penyaji data yang sama. */}
      <ShipmentBoard
        routes={supplierRoutes}
        note="Satu baris per kiriman aktif di jaringan. Kolom Jalur kirim di tabel bawah meringkas jalur per pemasok."
      />

      <article className="card">
        {/* Kepala kartu: judul kiri, pencarian kanan (permintaan pemilik 19 Okt
            2026). Kolom cari menyaring daftar yang SUDAH dimuat, sesudah
            penyaring jangkauan dan SEBELUM paginasi — angka kartu Ringkasan
            tetap dihitung dari daftar penuh. Label terlihat, ikon kaca pembesar
            dekoratif (aria-hidden), hasil diumumkan lewat role="status". */}
        <div className="card-header directory-head">
          {/* Kepala kartu: judul + pil jumlah. Kolom cari pindah ke bilah di
              ATAS TABEL (permintaan pemilik 19 Okt 2026) supaya berdiri dekat
              daftar yang disaringnya, bukan di kepala kartu. */}
          <div className="directory-title">
            <h2>Daftar pemasok</h2>
            {directoryDimuat ? (
              <span
                id="cari-pemasok-status"
                className={`count-pill${kueri.trim() ? " count-pill-active" : ""}`}
                role="status"
                aria-live="polite"
              >
                {kueri.trim()
                  ? `${dicari.length} dari ${shownRows.length} cocok`
                  : `${shownRows.length} pemasok`}
              </span>
            ) : null}
          </div>
        </div>
        {!directoryDimuat ? (
          <p className="evidence-note">
            {loading
              ? <LoadingState label="Memuat pemasok…" />
              : "Daftar pemasok belum dimuat — data ini diambil saat tab Pemasok dibuka."}
          </p>
        ) : rows.length === 0 ? (
          <p className="evidence-note">Tidak ada pemasok yang terdaftar.</p>
        ) : (
          <>
            {/* Urutan (permintaan pemilik 19 Okt 2026): penyaring jangkauan
                lebih dulu — tombol "Hanya dalam jangkauan / Tampilkan semua
                pemasok" berdiri TEPAT DI ATAS kolom cari — lalu ringkasan +
                kolom cari, lalu tabel. Tidak ada bilah kosong di antaranya. */}
            {reachKm !== null && metrics.outOfReach > 0 ? (
              <p className="reach-filter">
                <span className="reach-filter-note">
                  Menyembunyikan {metrics.outOfReach} pemasok yang jaraknya di atas {reachKm} km
                  {reference ? ` dari ${kodeWilayah(reference.location)}` : ""}. Baris yang disembunyikan bukan
                  dihapus — matikan penyaring untuk melihatnya lagi.
                </span>
                <button
                  type="button"
                  className="button button-secondary"
                  aria-pressed={penyaringAktif}
                  onClick={() => {
                    setHanyaJangkauan((value) => !value);
                    setHalamanPemasok(1);
                  }}
                >
                  {penyaringAktif
                    ? "Tampilkan semua pemasok"
                    : `Hanya dalam jangkauan (${metrics.suppliers - metrics.outOfReach})`}
                </button>
              </p>
            ) : null}
            <div className="board-summary-row">
              <p className="evidence-note">{reachSummary}</p>
              <div className="board-search">
                <label className="board-search-label" htmlFor="cari-pemasok">
                  Cari pemasok
                </label>
                <div className="board-search-field">
                  <svg
                    className="board-search-icon"
                    viewBox="0 0 20 20"
                    aria-hidden="true"
                    focusable="false"
                  >
                    <circle cx="8.5" cy="8.5" r="5.5" />
                    <path d="M12.8 12.8 17 17" />
                  </svg>
                  <input
                    id="cari-pemasok"
                    className="board-search-input"
                    type="search"
                    value={kueri}
                    placeholder="Nama, hub, komoditas, sertifikasi"
                    aria-describedby="cari-pemasok-status"
                    onChange={(event) => {
                      setKueri(event.target.value);
                      setHalamanPemasok(1);
                    }}
                  />
                  {kueri ? (
                    <button
                      type="button"
                      className="board-search-clear"
                      onClick={hapusPencarian}
                      aria-label="Hapus pencarian"
                    >
                      ×
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
            {dicari.length === 0 ? (
              <div className="board-search-empty">
                {kueri.trim() ? (
                  <>
                    <p className="evidence-note">
                      Tidak ada pemasok yang cocok dengan “{kueri.trim()}”. Pencarian memeriksa nama,
                      hub, komoditas, dan sertifikasi.
                    </p>
                    <button type="button" className="button button-secondary" onClick={hapusPencarian}>
                      Hapus pencarian
                    </button>
                  </>
                ) : (
                  <>
                    <p className="evidence-note">
                      Semua pemasok dalam daftar ini disembunyikan penyaring jangkauan.
                    </p>
                    <button
                      type="button"
                      className="button button-secondary"
                      onClick={() => {
                        setHanyaJangkauan(false);
                        setHalamanPemasok(1);
                      }}
                    >
                      Tampilkan semua pemasok
                    </button>
                  </>
                )}
              </div>
            ) : (
            <>
            <div className="board-table-wrap">
              <table className="location-table">
                <thead>
                  <tr>
                    <th scope="col">Pemasok</th>
                    <th scope="col">Komoditas</th>
                    <th scope="col" className="num">
                      Keandalan
                    </th>
                    <th scope="col">Sertifikasi</th>
                    <th scope="col" className="num">
                      Jarak
                    </th>
                    <th scope="col">Status</th>
                    <th scope="col">Jalur kirim</th>
                  </tr>
                </thead>
                <tbody>
                  {halaman.items.map((row) => {
                    const jalur = jalurPerPemasok.get(row.id) ?? null;
                    return (
                    <tr key={row.id}>
                      <td>
                        {/* Hub & koordinat = baris sekunder di bawah nama (Fase 12c):
                            keduanya tetap terbaca penuh, tapi tidak lagi memakan dua
                            kolom dari sembilan. */}
                        <span className="cell-stack">
                          <span className="cell-name">{row.name}</span>
                          <span className="cell-meta">{supplierMetaLine(row)}</span>
                        </span>
                      </td>
                      <td>{row.commodity}</td>
                      <td className="num">
                        {row.reliabilityMeter ? (
                          <span className="reliability-cell">
                            <span className="reliability-value">{row.reliabilityLabel}</span>
                            <span
                              className="mini-bar"
                              data-tone={row.reliabilityMeter.tone}
                              role="img"
                              aria-label={`Keandalan ${row.reliabilityLabel} dari 100`}
                            >
                              <span
                                className="mini-bar-fill"
                                aria-hidden="true"
                                style={{ width: `${row.reliabilityMeter.pct}%` }}
                              />
                            </span>
                          </span>
                        ) : (
                          row.reliabilityLabel
                        )}
                      </td>
                      <td>{row.certification}</td>
                      <td className="num">{row.distanceLabel}</td>
                      <td>
                        <span className="status-cell">
                        {row.excluded
                          ? `Dikecualikan di ${row.excludedScopes.join(", ")}`
                          : row.shipping
                            ? (
                                <>
                                  {/* Pil ringkas (satu baris, 22 px) — kalimat penuhnya
                                      (berat, batas layak) tetap terbaca lewat `title`.
                                      Kiriman yang gagal uji dapat pil sendiri karena itu
                                      fakta berbeda, bukan catatan tambahan. */}
                                  <span className="shipping-tag" title={row.shippingLabel}>
                                    {shippingTagLabel(row.shipping)}
                                  </span>
                                  {row.shipping.safetyFailCount > 0 ? (
                                    <span
                                      className="shipping-tag-fail"
                                      title={`${row.shipping.safetyFailCount} kiriman pemasok ini gagal uji keamanan`}
                                    >
                                      {row.shipping.safetyFailCount} gagal uji
                                    </span>
                                  ) : null}
                                  {/* Baris kedua: berat + batas layak pakai TERLIHAT
                                      (bukan hanya di `title`) — inilah fakta yang dipakai
                                      memutuskan, dan pemilik memintanya kembali terbaca. */}
                                  <span className="shipping-meta" title={row.shippingLabel}>
                                    {shippingMetaLine(row.shipping)}
                                  </span>
                                </>
                              )
                            : "Aktif"}
                        {reachKm !== null && !jarakDalamJangkauan(row, reachKm) ? (
                          <span className="reach-tag" title={directoryReachLabel(row, reachKm)}>
                            {directoryReachTagLabel(row, reachKm)}
                          </span>
                        ) : null}
                        </span>
                      </td>
                      <td className="route-cell">
                        {/* Jalur = rute JALAN kiriman pemasok ini (server). Sebelum
                            data jalur dimuat selnya "…", bukan "—": "belum dimuat"
                            dan "tidak punya jalur" adalah dua hal berbeda. */}
                        {jalurDimuat ? (
                          <span className="route-tag" title={routeCellTitle(jalur) ?? undefined}>
                            {routeCellLabel(jalur)}
                          </span>
                        ) : (
                          "…"
                        )}
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pager page={halaman} onChange={setHalamanPemasok} label="daftar pemasok" />
            <ScrollHint />
            </>
            )}
          </>
        )}
      </article>

      <article className="card">
        <h2>Register eksklusi</h2>
        {!registerDimuat ? (
          <p className="evidence-note">
            {loading
              ? "Memuat register eksklusi…"
              : "Register eksklusi belum dimuat — data ini diambil saat tab Pemasok dibuka."}
          </p>
        ) : register.length === 0 ? (
          <p className="evidence-note">
            Tidak ada pemasok yang sedang dieksklusi dalam cakupan Anda.
          </p>
        ) : (
          <>
            <div className="board-table-wrap">
              <table className="location-table">
                <thead>
                  <tr>
                    <th scope="col">Pemasok</th>
                    <th scope="col">Alasan</th>
                    <th scope="col">Status</th>
                    <th scope="col">Waktu</th>
                    <th scope="col">Keputusan</th>
                  </tr>
                </thead>
                <tbody>
                  {register.map((row) => (
                    <tr key={row.id}>
                      <td>{row.supplier}</td>
                      <td>{row.reason}</td>
                      <td>{exclusionStatusLabel(row.status)}</td>
                      <td>{row.at}</td>
                      <td>
                        <code>{row.decisionId.slice(0, 8)}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ScrollHint />
          </>
        )}
      </article>

      {selectedDecisionId && supplierContext ? (
        <SupplierExclusionView
          key={selectedDecisionId}
          context={supplierContext}
          role={role}
          token={token}
          onCreated={onExclusionCreated ?? (() => {})}
        />
      ) : (
        <article className="card">
          <h2>Usul eksklusi</h2>
          <p className="evidence-note">
            Pilih keputusan lebih dulu (tab Decision &amp; Evidence atau tombol di bawah) untuk
            mengusulkan eksklusi pemasok pada keputusan itu.
          </p>
          {onOpenDecision ? (
            <button
              type="button"
              className="button button-secondary"
              onClick={() => onOpenDecision("")}
            >
              Buka Decision &amp; Evidence
            </button>
          ) : null}
        </article>
      )}
    </section>
  );
}
