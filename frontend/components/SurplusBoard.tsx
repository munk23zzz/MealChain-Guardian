"use client";

// Halaman "Surplus & Limbah" — halaman sidebar acuan /surplus, disesuaikan ke
// data repo ini (/balance/map). Panel alokasi memakai surplus nyata; bagian
// limbah memakai GET /waste/summary (kolom `partner_name`, migrasi 022) —
// "—" hanya muncul bila server bilang datanya tidak ada.

import PageHeader from "./PageHeader";
import FactList from "./FactList";
import {
  alasanTanpaRencana,
  allocationPlan,
  angkaLimbahAda,
  planFromServer,
  surplusSummary,
  wasteFacts,
} from "../lib/surplus";
import { formatKg } from "../lib/overview-format";
import { LoadingState } from "./LoadingState";
import ScrollHint from "./ScrollHint";

export default function SurplusBoard({
  locations,
  commodity,
  commodities,
  onChangeCommodity,
  loading = false,
  error = null,
  onRetry,
  onOpenLocation,
  waste,
  plan,
  planLoading = false,
  planError = null,
}: {
  locations: unknown[] | null;
  commodity?: string | null;
  commodities?: string[];
  onChangeCommodity?: (c: string) => void;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onOpenLocation?: (location: string) => void;
  /** Respons GET /waste/summary — sumber tiga baris limbah (bukan angka klien). */
  waste?: unknown;
  /**
   * Respons GET /surplus/allocations — rencana lintas lokasi dari server.
   * Tanpa prop ini komponen menghitung sendiri dari `locations` (perilaku lama,
   * dipakai tes render): untuk peran SPPG hasilnya kosong karena peta dibatasi
   * cakupan, karena itu halaman asli WAJIB mengirim prop ini.
   */
  plan?: unknown;
  planLoading?: boolean;
  planError?: string | null;
}) {
  const summary = surplusSummary(locations);
  // Server lebih dulu; hitungan klien hanya cadangan saat prop tidak dikirim.
  const dariServer = plan === undefined ? null : planFromServer(plan, 6);
  const rows = dariServer ? dariServer.rows : allocationPlan(locations, 6);
  const planKosong = rows.length === 0;

  return (
    <section className="board-page" aria-busy={loading || undefined}>
      <PageHeader
        title="Surplus & Limbah"
        description="Surplus yang bisa dialihkan antar-SPPG, rencana alokasinya, dan keadaan pencatatan limbah untuk komoditas yang dipilih di peta."
        meta={
          <span className="page-header-pills">
            <span className="commodity-pill">Komoditas {commodity ? commodity : "—"}</span>
            {/* Lencana surplus: angka JARINGAN dari server bila ada. Peta akun
                SPPG hanya memuat satu lokasi, jadi memakai hitungan peta akan
                menulis "0 lokasi surplus" di atas rencana yang punya sumber. */}
            <span className="commodity-pill">
              {dariServer?.surplusLocations !== null && dariServer?.surplusLocations !== undefined
                ? `${dariServer.surplusLocations} lokasi surplus jaringan`
                : `${summary.surplusCount} lokasi surplus`}
            </span>
            {summary.unmeasuredCount > 0 && (
              // Lokasi yang salah satu sisinya belum tercatat TIDAK hilang diam-
              // diam dari hitungan: jumlahnya dikatakan (PLAN-023).
              <span className="commodity-pill">
                {summary.unmeasuredCount} lokasi tanpa catatan lengkap
              </span>
            )}
          </span>
        }
      />

      {commodities && commodities.length > 0 && onChangeCommodity && (
        <div className="commodity-filters filter-card" role="group" aria-label="Komoditas peta">
          <span className="commodity-filters-label">Komoditas:</span>
          {commodities.map((c) => (
            <button
              key={c}
              type="button"
              className={`commodity-pill${commodity === c ? " commodity-pill-active" : ""}`}
              data-komoditas={c}
              aria-pressed={commodity === c}
              onClick={() => onChangeCommodity(c)}
            >
              {c}
            </button>
          ))}
        </div>
      )}

      {error ? (
        <article className="card">
          <h2>Tidak bisa memuat neraca lokasi</h2>
          <p className="evidence-note">{error}</p>
          {onRetry ? (
            <button type="button" className="button button-secondary" onClick={onRetry}>
              Coba lagi
            </button>
          ) : null}
        </article>
      ) : null}

      <div className="board-grid board-grid-2">
        <article className="card">
          <h2>Neraca hari ini</h2>
          {/* Fase 5: neraca jadi satu aliran surplus → kekurangan. Angkanya tetap
              dari `surplusSummary`; tidak ada angka baru yang dikarang di sini. */}
          <div
            className="balance-flow"
            /* Bila salah satu sisi tidak punya angka, panahnya tidak boleh tetap
               berwarna aksen: itu akan menggambar aliran yang tidak terbukti. */
            data-kosong={summary.surplusKg === null || summary.shortageKg === null ? "true" : undefined}
          >
            <div className="balance-side balance-side-surplus">
              <span className="balance-label">Total surplus</span>
              <span className="balance-value">
                {loading && !locations ? "…" : summary.surplusKg === null ? "—" : formatKg(summary.surplusKg)}
              </span>
            </div>
            <svg
              className="balance-arrow"
              viewBox="0 0 120 24"
              role="img"
              aria-label="Surplus dialihkan untuk menutup kekurangan"
              focusable="false"
            >
              <defs>
                <marker
                  id="balance-arrowhead"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" />
                </marker>
              </defs>
              <line
                x1="2"
                y1="12"
                x2="102"
                y2="12"
                stroke="currentColor"
                strokeWidth="2"
                strokeDasharray="7 6"
                markerEnd="url(#balance-arrowhead)"
              />
            </svg>
            <div className="balance-side balance-side-shortage">
              <span className="balance-label">Total kekurangan</span>
              <span className="balance-value">
                {summary.shortageKg === null ? "—" : formatKg(summary.shortageKg)}
              </span>
            </div>
          </div>
          <FactList
            rows={[
              { label: "Lokasi surplus", value: String(summary.surplusCount) },
              { label: "Lokasi kekurangan", value: String(summary.shortageCount) },
              { label: "Lokasi seimbang", value: String(summary.balancedCount) },
            ]}
          />
          <p className="evidence-note">
            Surplus = stok − kebutuhan pada satu komoditas. Kartu ini mengikuti cakupan peta akun Anda
            (peran SPPG hanya melihat lokasinya sendiri); rencana di bawah dihitung lintas lokasi oleh
            server. Angka kekurangan di sini juga muncul di kartu “lokasi shortage” halaman Hari Ini.
          </p>
        </article>

        <article className="card">
          <h2>Pencatatan limbah</h2>
          <FactList rows={wasteFacts(waste)} />
          {/* Catatan ini hanya benar saat memang belum ada data. Begitu server
              mengirim angka (recorded.available), kalimat "sengaja kosong"
              berubah jadi bohong — jadi ia ikut hilang. */}
          {!angkaLimbahAda(waste) && (
            <p className="evidence-note">
              Bagian ini sengaja kosong: menuliskan 0 kg akan terbaca “tidak ada limbah”, padahal
              yang benar “belum dicatat”.
            </p>
          )}
        </article>
      </div>

      <article className="card">
        <h2>Rencana alokasi surplus</h2>
        <p className="evidence-note">
          Hanya surplus {dariServer?.minSurplusKg ?? 150} kg ke atas per lokasi yang
          direncanakan, dan tiap pengiriman minimal {dariServer?.minSurplusKg ?? 150} kg —
          di bawah itu biaya tetap pengiriman tidak sebanding.
        </p>
        {planError ? (
          <p className="evidence-note">Rencana tidak bisa dimuat: {planError}</p>
        ) : null}
        {planKosong ? (
          <p className="evidence-note">
            {planLoading ? (
              <LoadingState label="Memuat rencana alokasi…" />
            ) : planError ? null : (
              alasanTanpaRencana(dariServer?.reason)
            )}
          </p>
        ) : (
          <>
            <>
              <div className="board-table-wrap">
              <table className="location-table">
              <thead>
                <tr>
                  <th scope="col">Dari</th>
                  <th scope="col">Tujuan</th>
                  <th scope="col" className="num">
                    Jumlah
                  </th>
                  <th scope="col" className="num">
                    Jarak
                  </th>
                  <th scope="col" className="num">
                    Biaya tetap
                  </th>
                  <th scope="col">Wilayah tujuan</th>
                  <th scope="col">Tindakan</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.from}-${row.to}-${row.kg}`}>
                    <td>{row.from}</td>
                    <td>{row.to}</td>
                    <td className="num">{formatKg(row.kg)}</td>
                    <td className="num">{row.distanceKm === null ? "—" : `${row.distanceKm} km`}</td>
                    <td className="num">
                      {row.costSharePct === null || row.costSharePct === undefined
                        ? "—"
                        : `${row.costSharePct.toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`}
                    </td>
                    <td>{row.region ?? "—"}</td>
                    <td>
                      {onOpenLocation ? (
                        <button
                          type="button"
                          className="button button-secondary"
                          onClick={() => onOpenLocation(row.to)}
                        >
                          Lihat di peta
                        </button>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
            <ScrollHint />
              </>
            <p className="evidence-note">
              Urutan: kebutuhan terbesar diisi surplus terbesar lebih dulu, sampai salah satu sisi
              habis. Jarak memakai koordinat lokasi (jarak lurus, bukan rute jalan). Rencana dihitung
              lintas lokasi oleh server, karena itu barisnya bisa memuat kota di luar cakupan peta
              akun ini — sementara peta tetap hanya menampilkan lokasi yang boleh Anda lihat.
              Kolom “Biaya tetap” = (penanganan Rp150.000 + angkut) ÷ nilai barang pada harga acuan
              terakhir: pengiriman kecil selalu mahal, dan angka itu yang membuatnya terbaca.
            </p>
          </>
        )}
      </article>

    </section>
  );
}
