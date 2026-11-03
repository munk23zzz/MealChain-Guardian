"use client";

// Penjelasan satu KPI, di bawah grid (permintaan pemilik 29 Okt 2026).
//
// Revisi kedua (masih 29 Okt): isinya harus INFORMATIF, bukan teknis. Versi
// pertama memamerkan versi metode, rumus, kode tabel sumber, jumlah sampel, dan
// tingkat bukti — semuanya berguna untuk audit, tidak berguna bagi orang yang
// bertanya "angka ini artinya apa". Sekarang panel menjawab empat hal:
//
//   1. berapa nilainya dan apakah angkanya bisa dipakai,
//   2. apa arti angka itu (satu kalimat bahasa manusia),
//   3. cara membacanya (makin tinggi/rendah makin baik, skala bila ada),
//   4. dari mana dan periode mana (nama yang bisa dibaca, bukan nama tabel).
//
// Angka TIDAK dihitung di sini: semuanya dari amplop `GET /kpi`, lewat helper
// yang sama dengan kartu. Metrik tanpa angka menampilkan sebabnya dari server.

import {
  bulletOf,
  coverageSentence,
  directionLabel,
  KPI_WINDOWS,
  metricDescription,
  metricLabel,
  metricPlain,
  periodeBulan,
  sumberLabel,
  rapikanTeksBackend,
  type KpiWindowKey,
} from "../lib/kpi";
import { estimateLine } from "../lib/kpi-provenance";
import { fmtValue, unitLabel } from "./KPIDashboard";

const STATE_LABEL: Record<string, string> = {
  available: "Angka tersedia",
  no_data: "Belum ada data",
  unavailable: "Belum bisa dihitung",
};

const TREND_LABEL: Record<string, string> = {
  up: "▲ naik",
  down: "▼ turun",
  flat: "■ datar",
};

/** Definisi estimasi yang dikirim server (satu kalimat, tanpa nama tabel). */
function metadataEstimasi(metric: any): string | null {
  const teks = metric?.estimate?.definition;
  return typeof teks === "string" && teks.trim() ? teks.trim() : null;
}

export default function KpiDetailPanel({
  metric,
  windowKey,
  onClose,
  panelRef,
}: {
  metric: any;
  windowKey?: KpiWindowKey;
  onClose: () => void;
  /** Dipegang `KPIDashboard` supaya ia bisa menggulir panel ke layar dan
   *  memindahkan fokus ke judulnya saat dibuka (tahap 3 redesign). */
  panelRef?: React.RefObject<HTMLElement | null>;
}) {
  const nama = String(metric?.name ?? "");
  const shown = fmtValue(String(metric?.unit ?? ""), metric?.value ?? null);
  const keadaan = String(metric?.state ?? "");
  const bullet = bulletOf(metric);
  const arah = bullet ? directionLabel(bullet.direction) : null;
  const arti = metricPlain(nama) ?? metricDescription(nama);
  const sumber = sumberLabel(metric?.provenance?.source);
  const periode =
    periodeBulan(metric?.provenance?.period?.start, metric?.provenance?.period?.end) !== "—"
      ? periodeBulan(metric?.provenance?.period?.start, metric?.provenance?.period?.end)
      : (KPI_WINDOWS.find((w) => w.key === windowKey)?.label ?? null);
  const tren = typeof metric?.trend === "string" ? TREND_LABEL[metric.trend] : null;
  // Cakupan sebagai KALIMAT (konsep Performance & Audit, §7.3): angka efektif
  // per kg diterima tidak berarti apa-apa tanpa "berapa PO yang sudah diterima".
  const cakupan = coverageSentence(metric);
  // Estimasi penerimaan (proyeksi porsi / susut) — angka TERPISAH dari metrik.
  // Selalu disebut di panel, termasuk saat kosong: di sinilah pembaca mencari
  // "kalau bukan angka utama, lalu angka apa yang bergerak saat barang diterima".
  const estimasi = metric?.estimate ? estimateLine(metric) : null;
  const definisiEstimasi = metadataEstimasi(metric);
  // Alasan dari backend memuat sisipan audit — "(penyebut kosong)",
  // "— penyebut nol", "committed" — yang terbaca sebagai kode di layar.
  // Dibersihkan lewat satu fungsi murni (diuji di tests/kpi-teks-backend.test.ts).
  const alasan = rapikanTeksBackend(metric?.reason);

  const caraBaca = [
    arah ? `Angka ini ${arah}.` : null,
    bullet?.max !== null && bullet?.max !== undefined
      ? `Skalanya 0 sampai ${bullet!.max}.`
      : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section
      className="card kpi-detail"
      id="kpi-detail"
      data-testid="kpi-detail"
      data-window={windowKey ?? undefined}
      /* Wilayah bernama (tahap 3, 29 Okt 2026): pembaca layar mengenalinya
         sebagai wilayah rincian dan menyebut namanya dari judul di bawah. */
      role="region"
      aria-labelledby="kpi-detail-judul"
      ref={panelRef as React.RefObject<HTMLElement>}
    >
      <div className="kpi-detail-head">
        {/* `tabIndex={-1}`: judul ini yang menerima fokus saat panel dibuka,
            supaya pengguna papan ketik langsung berada di isi rincian dan
            Tab berikutnya menelusuri panel, bukan melompat ke tempat lama. */}
        <h3 className="kpi-detail-title" id="kpi-detail-judul" tabIndex={-1}>
          {metricLabel(nama)}
          <span className="kpi-detail-canon" lang="en" title={nama}>
            {nama}
          </span>
        </h3>
        <button
          type="button"
          className="kpi-detail-close"
          onClick={onClose}
          aria-label={`Tutup penjelasan ${metricLabel(nama)}`}
          title="Tutup penjelasan"
        >
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <div className="kpi-detail-hero">
        <p className="kpi-detail-value">
          {shown !== null ? (
            <>
              {shown}
              <small> {unitLabel(String(metric?.unit ?? ""))}</small>
            </>
          ) : (
            "—"
          )}
        </p>
        <p className="kpi-detail-state" data-state={keadaan}>
          {STATE_LABEL[keadaan] ?? (keadaan || "—")}
          {tren ? <span className="kpi-detail-trend"> · {tren}</span> : null}
        </p>
      </div>

      {arti || caraBaca ? (
        <div className="kpi-detail-block">
          <h4>Apa artinya</h4>
          {arti ? <p>{arti}</p> : null}
          {caraBaca ? <p className="kpi-detail-sub">{caraBaca}</p> : null}
        </div>
      ) : null}



      {alasan ? (
        <div className="kpi-detail-block" data-testid="kpi-detail-reason">
          <h4>Kenapa belum ada angka</h4>
          <p>{alasan}</p>
        </div>
      ) : null}

      {estimasi ? (
        <div className="kpi-detail-block" data-testid="kpi-detail-estimate">
          <h4>Estimasi dari penerimaan</h4>
          <p>{estimasi}</p>
          {definisiEstimasi ? (
            <p className="kpi-detail-sub">{definisiEstimasi}</p>
          ) : null}
        </div>
      ) : null}

      {cakupan ? (
        <div className="kpi-detail-block" data-testid="kpi-detail-coverage">
          <h4>Cakupan data</h4>
          <p>{cakupan}</p>
        </div>
      ) : null}

      {sumber || periode ? (
        <p className="kpi-detail-meta" data-testid="kpi-detail-meta">
          {[periode ? `Periode ${periode}` : null, sumber ? `Sumber ${sumber}` : null]
            .filter(Boolean)
            .join(" · ")}
        </p>
      ) : null}
    </section>
  );
}
