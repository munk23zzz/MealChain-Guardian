"use client";

// Panel audit performa (konsep Performance & Audit, 29 Okt 2026).
//
// Satu aturan yang dipegang: panel ini TIDAK menghitung metrik apa pun. Semua
// angka diambil dari amplop `GET /kpi` yang sama dengan kartu di atasnya —
// `method_version`, `data_mode`, `computed_at`, `provenance`, dan `facts` per
// metrik. Kalau backend tidak mengirim sebuah nilai, panel menulis "—" dan
// menjelaskan kenapa; ia tidak mengisi sendiri dengan asumsi.
//
// Panel ini hanya membaca jejak perhitungan yang dikirim backend — angka apa
// pun tidak dihitung ulang di sini. Kalau backend tidak mengirim sebuah nilai,
// panel menulis "—" dan menjelaskan kenapa; ia tidak mengisi sendiri dengan
// asumsi.
//
// Isi: jejak perhitungan + cakupan per metrik (termasuk alasan `no_data`).
//
// 29 Okt 2026 — bagian "Pengiriman & penyelesaian" dilepas bersama KPI
// "Effective Price per Accepted Kg" yang dihapus dari kontrak `GET /kpi`
// (keputusan pemilik): rincian PO/kg diterima hanya hidup di `facts` metrik
// itu, jadi menampilkannya tanpa metriknya berarti mengarang sumber angka.

import {
  coverageSentence,
  rapikanTeksBackend,
  KPI_WINDOWS,
  periodeBulan,
  type KpiWindowKey,
} from "../lib/kpi";
import { scopeLabel } from "../lib/kpi-provenance";
import { formatClockWib } from "../lib/datetime";


const STATE_LABEL: Record<string, string> = {
  available: "Tersedia",
  no_data: "Belum ada data",
  unavailable: "Tidak tersedia",
};

const BASIS_LABEL: Record<string, string> = {
  rencana_menu: "dari rencana menu",
  asumsi_siklus_harian: "asumsi siklus harian SPPG",
};

function teks(nilai: unknown): string {
  if (nilai === null || nilai === undefined || nilai === "") return "—";
  return String(nilai);
}

function angka(nilai: unknown, satuan = ""): string {
  if (nilai === null || nilai === undefined || nilai === "") return "—";
  const n = Number(nilai);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("id-ID", { maximumFractionDigits: 2 }) + satuan;
}

export default function PerformanceAuditPanel({
  kpi,
  windowKey = null,
}: {
  /** Amplop `GET /kpi` (payload yang sama dengan kartu KPI). */
  kpi: any | null;
  windowKey?: KpiWindowKey | null;
}) {
  if (!kpi) return null;
  const metrics: any[] = Array.isArray(kpi.metrics) ? kpi.metrics : [];
  const sdc = metrics.find((m) => m?.name === "Safe Delivered Cost");
  const sdcFacts = sdc?.facts ?? {};
  const basis = String(sdcFacts?.storage_default_basis ?? "");
  const periode =
    periodeBulan(kpi?.period?.start, kpi?.period?.end) !== "—"
      ? periodeBulan(kpi?.period?.start, kpi?.period?.end)
      : (KPI_WINDOWS.find((w) => w.key === windowKey)?.label ?? "—");

  // Enam jejak perhitungan, satu strip. Urutannya tetap seperti versi dt/dd:
  // metode → rumus biaya → jendela simpan → periode → cakupan → waktu hitung.
  const jejak: { label: string; nilai: string; testid?: string }[] = [
    {
      label: "Metode agregasi",
      nilai: teks(kpi?.method_version),
      testid: "audit-method-version",
    },
    {
      label: "Versi rumus biaya kirim aman",
      nilai: teks(sdcFacts?.formula_version),
      testid: "audit-sdc-formula",
    },
    {
      label: "Jendela simpan gudang",
      nilai: sdcFacts?.storage_default_days
        ? `${teks(sdcFacts.storage_default_days)} hari` +
          (basis ? ` (${BASIS_LABEL[basis] ?? basis})` : "")
        : "—",
      testid: "audit-storage-basis",
    },
    { label: "Periode laporan", nilai: periode },
    { label: "Cakupan data", nilai: scopeLabel(kpi?.data_mode) },
    {
      label: "Dihitung",
      nilai:
        formatClockWib(kpi?.computed_at) !== "—"
          ? `${formatClockWib(kpi?.computed_at)} WIB`
          : "—",
    },
  ];

  // Tabel dilipat HANYA bila tidak ada yang perlu diperiksa. Audit yang
  // menyembunyikan metrik bermasalah gagal tujuannya; sebaliknya tujuh baris
  // "Tersedia" yang terbuka terus hanya menambah tinggi halaman.
  const semuaTersedia =
    metrics.length > 0 && metrics.every((m) => String(m?.state) === "available");

  // Ringkasan metrik bermasalah (Tahap 6, 29 Okt 2026). Yang dihitung HANYA
  // jumlah baris payload yang keadaannya bukan `available` — bukan metrik
  // turunan, bukan rata-rata, bukan persentase. Tujuannya satu: pembaca tidak
  // perlu memindai tujuh baris tabel untuk tahu ada yang tidak beres.
  const bermasalah = metrics.filter((m) => String(m?.state ?? "") !== "available");

  const tabel = (
    <>
      <h4 className="perf-audit-h4">Cakupan per metrik</h4>
      <div className="perf-audit-table-wrap">
        <table className="perf-audit-table">
          <caption className="sr-only">
            Keadaan, jumlah sampel, dan sebab tiap metrik pada periode ini
          </caption>
          <thead>
            <tr>
              <th scope="col">Metrik</th>
              <th scope="col">Keadaan</th>
              <th scope="col">Sampel</th>
              <th scope="col">Sebab</th>
            </tr>
          </thead>
          <tbody>
            {metrics.length === 0 ? (
              <tr>
                <td colSpan={4} className="perf-audit-empty">
                  Belum ada metrik pada respons ini. Coba ganti periode atau
                  cakupan data di bilah kendali di atas.
                </td>
              </tr>
            ) : (
              metrics.map((m) => {
                const keadaan = String(m?.state ?? "");
                const bermasalah = keadaan !== "available";
                const kalimat = coverageSentence(m);
                // Alasan backend memuat sisipan audit ("(penyebut kosong)",
                // "— penyebut nol", "committed"); dibersihkan sebelum dicetak
                // supaya tabel terbaca sebagai laporan, bukan log server.
                const alasan = rapikanTeksBackend(m?.reason) || null;
                return (
                  <tr
                    key={String(m?.name)}
                    className={`perf-audit-row${bermasalah ? " is-bermasalah" : ""}`}
                    data-state={keadaan}
                  >
                    <th scope="row">{teks(m?.name)}</th>
                    <td data-label="Keadaan">
                      <span className={`perf-audit-state is-${keadaan}`}>
                        {STATE_LABEL[keadaan] ?? teks(keadaan)}
                      </span>
                    </td>
                    <td className="perf-audit-sampel" data-label="Sampel">
                      {angka(m?.sample_count)}
                    </td>
                    <td className="perf-audit-sebab" data-label="Sebab">
                      {alasan ?? kalimat ?? "—"}
                      {alasan && kalimat ? (
                        <span className="perf-audit-reason">{kalimat}</span>
                      ) : null}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </>
  );

  return (
    <section
      className="card perf-audit"
      data-testid="performance-audit"
      aria-labelledby="perf-audit-title"
    >
      <header className="perf-audit-head">
        <h3 className="perf-audit-title" id="perf-audit-title">
          Audit performa
        </h3>
      </header>

      <dl className="perf-audit-strip">
        {jejak.map((sel) => (
          <div className="perf-audit-cell" key={sel.label}>
            <dt>{sel.label}</dt>
            <dd data-testid={sel.testid}>{sel.nilai}</dd>
          </div>
        ))}
      </dl>

      {bermasalah.length > 0 ? (
        <p
          className="perf-audit-bermasalah"
          data-testid="audit-ringkasan-bermasalah"
          role="status"
        >
          <strong>
            {bermasalah.length} dari {metrics.length} metrik perlu perhatian
          </strong>
          {" — "}
          {bermasalah
            .map(
              (m) =>
                `${teks(m?.name)} (${(
                  STATE_LABEL[String(m?.state)] ?? teks(m?.state)
                ).toLowerCase()})`
            )
            .join(" · ")}
        </p>
      ) : null}

      {semuaTersedia ? (
        <details className="perf-audit-fold">
          <summary className="perf-audit-summary">
            Rincian {metrics.length} metrik — semuanya tersedia
          </summary>
          {tabel}
        </details>
      ) : (
        tabel
      )}
    </section>
  );
}
