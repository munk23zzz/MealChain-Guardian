"use client";

// Kartu "Jejak kepercayaan" di kolom kanan Overview (permintaan Roy 2026-10-28).
//
// Kenapa kartu ini ada: antrean "Perlu keputusan" hanya bercerita tentang
// pekerjaan yang BELUM selesai. Setelah dipangkas setengah, ruang di bawahnya
// dipakai untuk menjawab pertanyaan yang lebih dasar — "kenapa angka di halaman
// ini bisa dipercaya?" Empat buktinya: rantai ledger, batch yang lolos uji,
// keputusan yang benar-benar tereksekusi, dan node yang melaporkan angka.
//
// Tampilan (revisi 28 Okt 2026, arah pemilik "dibuat 2 baris … ada teks yang
// hilang … kurang center atas-bawah"):
//  - EMPAT bukti disusun 2 baris × 2 kolom, bukan satu daftar memanjang, jadi
//    seluruh kartu terbaca sekali pandang;
//  - alasan/keadaan (`foot`) SELALU dicetak apa adanya. Versi sebelumnya
//    menyembunyikannya saat metrik aman dan memotongnya dengan elipsis,
//    sehingga kalimat bukti ("78 blok tertaut keputusan · checkpoint luar
//    cocok") hilang dari layar — angka tanpa alasan tidak bisa diperiksa;
//  - isi sel dan seluruh grid di-center vertikal, jadi tidak ada sel yang
//    menggantung di atas sementara sel sebelahnya kosong di bawah.
// Keadaan SELALU ditulis sebagai kata (bukan warna saja): titik nada + label di
// kepala kartu, dan kata keadaan pendek per sel — aturan aksesibilitas yang sama
// dengan `.provider-live`/`.node-badge` di stylesheet.
//
// Semua angka datang dari `lib/trust-trail` (murni, diuji): komponen ini tidak
// menghitung apa pun, jadi tidak ada rumus kedua yang bisa menyimpang.
import { trustSummary, type TrustMetric } from "../lib/trust-trail";

export default function TrustTrailCard({
  metrics,
}: {
  metrics: readonly TrustMetric[];
}) {
  const ringkas = trustSummary(metrics);

  return (
    <section className="map-panel trust-card" aria-label="Jejak kepercayaan">
      <div className="trust-head">
        <h3>Jejak kepercayaan</h3>
        <span className={`trust-badge trust-badge-${ringkas.tone}`}>
          <span className="trust-dot" aria-hidden="true" />
          {ringkas.label}
        </span>
      </div>
      <div className="trust-grid" role="list">
        {metrics.map((metric) => (
          <div
            key={metric.id}
            className={`trust-cell trust-cell-${metric.tone}`}
            data-metric={metric.id}
            role="listitem"
          >
            <span className="trust-label">{metric.label}</span>
            <span className="trust-value">
              <span className="trust-number">
                {metric.value}
                {metric.unit && (
                  <span
                    className={`trust-unit${
                      metric.unit.startsWith("/") ? " trust-unit-ratio" : ""
                    }`}
                  >
                    {metric.unit}
                  </span>
                )}
              </span>
              <span className="trust-state">
                <span className="trust-dot" aria-hidden="true" />
                {metric.state}
              </span>
            </span>
            {/* Alasan SELALU dicetak: angka tanpa alasannya tidak bisa
                diperiksa. Dulu baris ini disembunyikan saat metrik aman dan
                dipotong elipsis, sehingga kalimat buktinya hilang. */}
            <span className="trust-foot">{metric.foot}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
