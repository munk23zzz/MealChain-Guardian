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

import PageShell from "./PageShell";
import { PAGE_TITLES } from "../lib/navigation";
import { SUPPLIER_SECTION_IDS, supplierSections } from "../lib/section-jump";
import SupplierSummary from "./SupplierSummary";
import Pager from "./Pager";
import ShipmentBoard from "./ShipmentBoard";
import SupplierReceipts from "./SupplierReceipts";
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
  shippingMetaLine,
  shippingTagLabel,
  supplierDistanceReference,
  withinReachKm,
} from "../lib/supplier-pins";
import { supplierRoutes as barisRute } from "../lib/supplier-routes";

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
  receiptHistory = null,
  receiptLoading = false,
  receiptError = null,
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
  /**
   * Amplop `GET /receipts/riwayat` untuk kartu "Riwayat penerimaan"
   * (Dok 05 §8.5). `null` = belum dimuat.
   */
  receiptHistory?: unknown;
  receiptLoading?: boolean;
  receiptError?: string | null;
}) {
  const directoryDimuat = suppliers !== null && suppliers !== undefined;
  const rows = supplierDirectory(suppliers);
  const reference = supplierDistanceReference(suppliers);
  const metrics = directoryMetrics(rows, reachKm);
  // Penyaring tabel (29 Okt 2026): hanya SATU — "Hanya dalam jangkauan" di atas
  // kolom cari. Kartu Ringkasan sengaja hanya dibaca (keputusan pemilik: bentuk
  // tile/chip/kalimat yang bisa diklik semuanya dinilai sulit dipahami), jadi
  // angkanya dihitung dari daftar PENUH dan tidak pernah menyusut.
  const [hanyaJangkauan, setHanyaJangkauan] = useState(false);
  const shownRows = hanyaJangkauan ? filterDirectoryByReach(rows, reachKm) : rows;
  // Halaman tabel pemasok: nomor halaman dijepit oleh `paginate`, jadi data yang
  // menyusut (penyaring/segarkan) berakhir di halaman terakhir yang terisi —
  // bukan tabel kosong. Penyaring mengembalikan pembaca ke halaman 1.
  const [halamanPemasok, setHalamanPemasok] = useState(1);
  // Mengubah penyaring berarti isi tabel berubah → pembaca selalu kembali ke
  // halaman 1 (halaman terakhir yang terisi akan terasa seperti "data hilang").
  const ubahJangkauan = (next: boolean) => {
    setHanyaJangkauan(next);
    setHalamanPemasok(1);
  };
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
  // S1 (29 Okt 2026): pil ketiga menyebut jumlah KIRIMAN, bukan hanya pemasok.
  // Dihitung dari payload yang sama dengan papan kiriman (bukan angka karangan),
  // dan tidak dirender saat jalur belum dimuat — "0 kiriman" akan bohong.
  const ruteDimuat = supplierRoutes !== null && supplierRoutes !== undefined;
  const jumlahKiriman = ruteDimuat ? barisRute(supplierRoutes).length : null;
  // Satu kalimat konteks menggantikan deskripsi dua baris yang mendaftar ulang
  // isi halaman; daftar bagiannya sudah dibawa lima tautan di bawah judul.
  // `exclusions` bisa berbentuk {items: []} (endpoint register) — exclusionCounts
  // memanggil exclusionRows yang mengharapkan array, jadi kirim daftar yang sama
  // dengan tabel register (`register`), bukan payload mentah.
  const eksklusi = exclusionCounts(register);
  const ringkasEksklusi =
    !registerDimuat
      ? "eksklusi belum dimuat"
      : eksklusi.total === 0
      ? "belum ada eksklusi"
      : `eksklusi: ${[
          eksklusi.active ? `${eksklusi.active} aktif` : null,
          eksklusi.proposed ? `${eksklusi.proposed} menunggu` : null,
        ]
          .filter(Boolean)
          .join(" · ")}`;
  const ringkasKepala =
    reachKm !== null
      ? `Pemasok jaringan SPPG Anda — ringkasan, kiriman aktif, daftar (dapat disaring dalam jangkauan ${reachKm} km), dan register eksklusi.`
      : "Pemasok jaringan SPPG Anda — ringkasan, kiriman aktif, daftar, dan register eksklusi.";

  return (
    <PageShell
      className="board-page"
      busy={loading}
      wideDescription
      title={PAGE_TITLES.suppliers}
      description={ringkasKepala}
      sections={supplierSections()}
      jumpAriaLabel="Bagian halaman Suppliers"
      meta={
        <span className="page-header-pills">
          <span className="commodity-pill">{metrics.suppliers} pemasok</span>
          {jumlahKiriman !== null ? (
            <span className="commodity-pill">{jumlahKiriman} kiriman</span>
          ) : null}
          <span className="commodity-pill">{ringkasEksklusi}</span>
        </span>
      }
    >

      {error ? (
        <article className="card">
          <h2>Tidak bisa memuat data pemasok</h2>
          <p className="evidence-note">
            Data pemasok tidak bisa dimuat saat ini. Coba muat ulang; kalau masih
            gagal, periksa koneksi lalu coba lagi.
          </p>
          {onRetry ? (
            <button type="button" className="button button-secondary" onClick={onRetry}>
              Coba lagi
            </button>
          ) : null}
        </article>
      ) : null}

      {/* Ringkasan hanya dibaca (keputusan pemilik 29 Okt 2026): satu baris
          angka besar, tanpa tombol. Penyaring tetap satu — tombol "Hanya dalam
          jangkauan" di atas kolom cari, dekat tabel yang ia saring. */}
      <div className="board-grid jump-target" id={SUPPLIER_SECTION_IDS.ringkasan}>
        <SupplierSummary
          metrics={metrics}
          reachKm={reachKm}
          loading={!directoryDimuat && loading}
        />
      </div>

      {/* Papan kiriman (Arah B riset 16 Okt 2026): satu baris per KIRIMAN —
          pemasok, tujuan, muatan, jalur, berangkat, ETA, sisa, masa layak, mutu,
          keadaan — dengan urutan "paling mendesak". Menggantikan kartu ringkas
          di halaman ini (dan peran kolom teks "Jalur kirim"): papan sudah memuat
          semua angka itu per kiriman, dan menyimpan keduanya hanya akan menjadi
          dua penyaji data yang sama. */}
      <div className="jump-target" id={SUPPLIER_SECTION_IDS.kiriman}>
        <ShipmentBoard
          routes={supplierRoutes}
          note="Satu baris per kiriman aktif. Angka jalur, waktu, dan mutu dibaca di sini, bukan di daftar pemasok."
          // S3: kepala papan menawarkan jalan ke daftar; tanpa kiriman pun
          // kartunya tetap tampil supaya jangkar "Kiriman" tidak menunjuk
          // ruang kosong.
          empty="Belum ada kiriman aktif di jaringan."
          tautan={{ href: `#${SUPPLIER_SECTION_IDS.daftar}`, label: "Ke daftar pemasok" }}
        />
      </div>

      <article className="card jump-target" id={SUPPLIER_SECTION_IDS.daftar}>
        {/* Kepala kartu: judul kiri, pencarian kanan (permintaan pemilik 19 Okt
            2026). Kolom cari menyaring daftar yang SUDAH dimuat, sesudah
            penyaring jangkauan dan SEBELUM paginasi — angka kartu Ringkasan
            tetap dihitung dari daftar penuh. Label terlihat, ikon kaca pembesar
            dekoratif (aria-hidden), hasil diumumkan lewat role="status". */}
        <div className="card-header directory-head">
          {/* Kepala kartu: judul + pil jumlah. Kolom cari pindah ke bilah di
              ATAS TABEL (permintaan pemilik 19 Okt 2026) supaya berdiri dekat
              daftar yang disaringnya, bukan di kepala kartu. */}
          {/* S4: pil jumlah tinggal SATU — di bilah kontrol, dekat daftar yang
              ia hitung. Dulu pil yang sama juga dicetak di sini, sehingga satu
              angka tampil dua kali dan `id`-nya kembar. */}
          <div className="directory-title">
            <h2>Daftar pemasok</h2>
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
            {/* S4 (29 Okt 2026) — SATU bilah kontrol. Sebelumnya tiga lapis:
                baris penyaring jangkauan, baris ringkasan + kolom cari, dan pil
                jumlah di kepala kartu. Kini satu baris: cari · jumlah hasil ·
                penyaring jangkauan · keterangan cakupan. */}
            <div className="directory-toolbar">
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
              {reachKm !== null && metrics.outOfReach > 0 ? (
                <button
                  type="button"
                  className="directory-reach-toggle"
                  aria-pressed={hanyaJangkauan}
                  onClick={() => ubahJangkauan(!hanyaJangkauan)}
                >
                  {hanyaJangkauan
                    ? "Tampilkan semua pemasok"
                    : `Hanya dalam jangkauan (${metrics.suppliers - metrics.outOfReach})`}
                </button>
              ) : null}
            </div>
            <p className="directory-toolbar-note">
              {/* Satu kalimat keadaan, mengikuti penyaring yang sedang aktif —
                  dulu dua kalimat di dua baris berbeda. */}
              {reachKm !== null && metrics.outOfReach > 0 && hanyaJangkauan
                ? `${metrics.suppliers - metrics.outOfReach} pemasok dalam ${reachKm} km${
                    reference ? ` dari ${kodeWilayah(reference.location)}` : ""
                  }; ${metrics.outOfReach} di luarnya disembunyikan, bukan dihapus.`
                : reachSummary}
            </p>
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
                      Tidak ada pemasok dalam jangkauan {reachKm} km
                      {reference ? ` dari ${kodeWilayah(reference.location)}` : ""}.
                    </p>
                    <button
                      type="button"
                      className="button button-secondary"
                      onClick={() => ubahJangkauan(false)}
                    >
                      Tampilkan semua pemasok
                    </button>
                  </>
                )}
              </div>
            ) : (
            <>
            <div className="board-table-wrap">
              <table className="location-table directory-table">
                <thead>
                  <tr>
                    <th scope="col">Pemasok</th>
                    <th scope="col">Komoditas</th>
                    <th scope="col" className="num">
                      Keandalan
                    </th>
                    <th scope="col" className="num">
                      Jarak
                    </th>
                    <th scope="col">Sertifikasi</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {halaman.items.map((row) => {
                    return (
                    <tr key={row.id}>
                      <td data-label="Pemasok">
                        {/* Hub & koordinat = baris sekunder di bawah nama (Fase 12c):
                            keduanya tetap terbaca penuh, tapi tidak lagi memakan dua
                            kolom dari sembilan. */}
                        <span className="cell-stack">
                          <span className="cell-name">{row.name}</span>
                          <span className="cell-meta">{supplierMetaLine(row)}</span>
                        </span>
                      </td>
                      <td data-label="Komoditas">{row.commodity}</td>
                      <td className="num" data-label="Keandalan">
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
                      <td className="num" data-label="Jarak">{row.distanceLabel}</td>
                      <td data-label="Sertifikasi">{row.certification}</td>
                      <td data-label="Status">
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

      {/* Riwayat penerimaan (Dok 05 §8.5): pertanyaan audit "berapa yang benar-
          benar diterima dari pemasok ini, dan berapa nilainya" — jawabannya
          data yang sudah tersimpan di `batch_receipts`, bukan kalimat. Ditaruh
          sesudah daftar pemasok dan sebelum register eksklusi: dua register
          itu dibaca berurutan (apa yang datang · siapa yang tidak boleh
          dipakai lagi). */}
      <SupplierReceipts
        riwayat={receiptHistory}
        loading={receiptLoading}
        error={receiptError}
      />

      {/* S5 (29 Okt 2026) — register (baca) dan usul (tulis) jadi satu keluarga:
          bentuk kepala sama dengan Riwayat penerimaan (judul + pil jumlah + satu
          kalimat keadaan), dan di ≥1200 px keduanya berdampingan sehingga form
          usul tidak lagi menjadi ekor halaman. */}
      <div className="register-grid">
      <article className="card jump-target" id={SUPPLIER_SECTION_IDS.register}>
        <div className="card-header">
          <div className="directory-title">
            <h2>Register eksklusi</h2>
            {registerDimuat && register.length > 0 ? (
              <span className="count-pill">{register.length} catatan</span>
            ) : null}
          </div>
        </div>
        {!registerDimuat ? (
          <p className="evidence-note">
            {loading
              ? "Memuat register eksklusi…"
              : "Register eksklusi belum dimuat — data ini diambil saat tab Pemasok dibuka."}
          </p>
        ) : register.length === 0 ? (
          <>
            <p className="evidence-note">
              Tidak ada pemasok yang sedang dieksklusi dalam cakupan Anda.
            </p>
            <p className="register-note">
              Eksklusi maupun pemulihannya sama-sama lewat keputusan yang disetujui. Kotak usul di
              samping adalah jalan masuknya.
            </p>
            <a className="button button-secondary" href={`#${SUPPLIER_SECTION_IDS.usul}`}>
              Ajukan eksklusi
            </a>
          </>
        ) : (
          <>
            <p className="register-note">
              Tiap baris adalah keputusan yang sudah disetujui. Pemulihan tidak mengubah status
              keamanan batch — ia hanya memulihkan hak pemasok.
            </p>
            <div className="board-table-wrap">
              <table className="location-table register-table">
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
                      <td data-label="Pemasok">{row.supplier}</td>
                      <td data-label="Alasan">{row.reason}</td>
                      <td data-label="Status">{exclusionStatusLabel(row.status)}</td>
                      <td data-label="Waktu">{row.at}</td>
                      <td data-label="Keputusan">
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

      <div className="jump-target" id={SUPPLIER_SECTION_IDS.usul}>
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
      </div>
      </div>
    </PageShell>
  );
}
