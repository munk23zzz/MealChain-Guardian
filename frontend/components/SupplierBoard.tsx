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
import ShipmentBoard from "./ShipmentBoard";
import { SupplierExclusionView } from "./SupplierExclusionPanel";
import {
  directoryMetrics,
  directoryReachLabel,
  directoryReachSummary,
  directoryReachTagLabel,
  exclusionRows,
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
                label: "Sedang mengirim barang",
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
                value: String(register.length),
                tone: register.length ? "danger" : "plain",
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
        <h2>Daftar pemasok</h2>
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
            <p className="evidence-note">{reachSummary}</p>
            {reachKm !== null && metrics.outOfReach > 0 ? (
              <p className="reach-filter">
                <button
                  type="button"
                  className="button button-secondary"
                  aria-pressed={penyaringAktif}
                  onClick={() => setHanyaJangkauan((value) => !value)}
                >
                  {penyaringAktif
                    ? "Tampilkan semua pemasok"
                    : `Hanya dalam jangkauan (${metrics.suppliers - metrics.outOfReach})`}
                </button>
                <span className="reach-filter-note">
                  Menyembunyikan {metrics.outOfReach} pemasok yang jaraknya di atas {reachKm} km
                  {reference ? ` dari ${reference.location}` : ""}. Baris yang disembunyikan bukan
                  dihapus — matikan penyaring untuk melihatnya lagi.
                </span>
              </p>
            ) : null}
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
                  {shownRows.map((row) => {
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
            <ScrollHint />
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
                    <th scope="col">Waktu</th>
                    <th scope="col">Keputusan</th>
                  </tr>
                </thead>
                <tbody>
                  {register.map((row) => (
                    <tr key={row.id}>
                      <td>{row.supplier}</td>
                      <td>{row.reason}</td>
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
