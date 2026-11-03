"use client";

// Panel "Surplus wilayah lain" — pasangan grafik kecukupan di tab Overview
// (28 Okt 2026; REDESIGN kolom 29 Okt 2026).
//
// Grafik di kiri menjawab "lokasi saya cukup atau tidak"; panel ini menjawab
// pertanyaan berikutnya: "kalau kurang, surplusnya ada di mana?".
//
// Sumber angka HANYA `GET /surplus/regions` (dihitung server, lintas lokasi).
// Klien tidak boleh menghitungnya dari peta: peta akun SPPG dibatasi cakupan,
// jadi satu lokasi — dan "daerah lain" akan selalu kosong (Ruling 2026-10-14).
//
// BENTUK (29 Okt 2026): kolom berdiri, bukan baris bertumpuk. Sebelumnya panel
// ini memakai daftar baris horizontal sementara grafik di sebelahnya memakai
// kolom vertikal — dua geometri untuk satu pertanyaan menuntut pembaca
// menerjemahkan dua bahasa. Lebih buruk lagi, lebar batang baris dihitung
// relatif terhadap wilayah terbesar, sehingga saat hanya ada SATU wilayah
// batangnya selalu 100% dan tidak menyampaikan apa pun. Kini keduanya memakai
// kelas `ac-*` yang sama (satu kartu, satu plot, satu garis acuan), dan semua
// wilayah digambar: wilayah di bawah ambang tampil pucat dengan catatan
// "di bawah ambang", bukan disembunyikan ke satu kalimat.

import { useEffect, useState, type CSSProperties } from "react";

import { formatDateTime } from "../lib/datetime";
import { formatKg } from "../lib/overview-format";
import {
  komoditasToneClass,
  regionSurplus,
  regionSurplusReason,
  surplusCommoditySlices,
} from "../lib/surplus-regions";
import CompositionDonut from "./CompositionDonut";

type Props = {
  /** Respons `GET /surplus/regions` (belum di-parse). */
  payload: unknown;
  /** Komoditas yang dibandingkan grafik di sebelahnya — untuk label & legenda. */
  commodities: readonly string[];
  /** Nama lokasi pengguna (dipakai bila server tidak memfilter). */
  locationName: string;
  /** Catatan tanggal sumber data, sama dengan grafik kecukupan. */
  sourceNote?: string | null;
  updatedAt?: number | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
};

export default function SurplusRegionPanel({
  payload,
  commodities,
  locationName,
  sourceNote = null,
  updatedAt = null,
  loading = false,
  error = null,
  onRetry,
}: Props) {
  const view = regionSurplus(payload);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const komoditas = commodities.length ? commodities : view.komoditas;
  const tanggal = updatedAt ? formatDateTime(new Date(updatedAt).toISOString()) : "—";
  const asal = view.excludedLocation
    ? `di luar ${view.excludedLocation}`
    : locationName || "SPPG";
  // Judul & keterangan mengikuti cakupan: "daerah lain" hanya benar bila server
  // benar-benar membuang satu lokasi. Untuk BGN nasional panelnya seluruh
  // jaringan — menulis "daerah lain" di sana akan menyesatkan.
  const judul = view.excludedLocation ? "Surplus wilayah lain" : "Surplus per wilayah";
  // Sub pendek; rincian sumber dipindah ke title supaya kartu tidak penuh teks.
  // "dihitung server" adalah penjelasan MEKANISME, bukan bahasa pengguna.
  // Yang dibutuhkan pembaca: angkanya berasal dari data yang tercatat.
  const sub = `${asal} · dari data tercatat`;
  const subLengkap = `${asal} · ${komoditas.length || "—"} komoditas · ${
    sourceNote ? `${sourceNote} · ` : ""
  }dihitung ${tanggal}`;
  const catatanLengkap = [
    "Angka = pasokan tercatat dikurangi kebutuhan pada komoditas yang sama, dijumlahkan per wilayah (peta hanya memuat lokasi sendiri).",
    "Hanya lokasi yang permintaannya tercatat boleh menyumbang surplus.",
    view.minKg !== null
      ? `Surplus per lokasi ≥ ${formatKg(view.minKg)} dianggap layak dialihkan; wilayah yang seluruh surplusnya di bawah ambang digambar pucat.`
      : null,
    view.excludedKg !== null && view.excludedKg > 0
      ? `Surplus ${view.excludedLocation ?? "lokasi Anda"} sendiri (${formatKg(view.excludedKg)}) tidak dihitung di panel ini.`
      : null,
    view.unmeasured > 0
      ? `${view.unmeasured} lokasi bersurplus belum punya catatan permintaan, jadi belum dihitung.`
      : null,
  ]
    .filter(Boolean)
    .join(" ");

  if (loading) {
    return (
      <section
        className="adequacy-columns sr-panel"
        aria-label={judul}
        aria-busy="true"
      >
        <header className="ac-head">
          <div className="ac-title">
            <h3>{judul}</h3>
            <p className="ac-sub">{asal} · memuat wilayah…</p>
          </div>
        </header>
        <div className="ac-skeleton" aria-hidden="true">
          {[0, 1, 2, 3].map((i) => (
            <span
              className="ac-skeleton-col"
              key={i}
              style={{ "--i": i } as CSSProperties}
            />
          ))}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="adequacy-columns sr-panel" aria-label={judul}>
        <header className="ac-head">
          <div className="ac-title">
            <h3>{judul}</h3>
            <p className="ac-sub">{asal}</p>
          </div>
        </header>
        <p className="status-danger ac-error" role="alert">
          {error}{" "}
          {onRetry && (
            <button type="button" onClick={onRetry}>
              Coba lagi
            </button>
          )}
        </p>
      </section>
    );
  }

  // Irisan donat = komoditas penyumbang surplus (dijumlahkan antar wilayah).
  // Angkanya tetap dari server: kg per komoditas apa adanya.
  const irisan = surplusCommoditySlices(view).map((iris) => {
    const wilayah = view.regions.find((r) =>
      r.byCommodity.some((c) => String(c.commodity).toLowerCase() === iris.label.toLowerCase())
    );
    return {
      key: iris.key,
      label: iris.label,
      kg: iris.kg,
      toneClass: iris.toneClass,
      note: formatKg(iris.kg),
      aria: `${iris.label} ${formatKg(iris.kg)} surplus (${iris.sharePct}% dari surplus wilayah)${
        wilayah ? `, wilayah ${wilayah.region}` : ""
      }`,
    };
  });
  const totalTanpaSatuan = formatKg(
    irisan.reduce((jumlah, iris) => jumlah + iris.kg, 0)
  ).replace(/\s*kg$/, "");

  return (
    <section
      className={`adequacy-columns sr-panel${mounted ? " is-mounted" : ""}`}
      aria-labelledby="sr-title"
      data-wilayah={view.regions.length}
      title={catatanLengkap}
    >
      <header className="ac-head">
        <div className="ac-title">
          <h3 id="sr-title" title={subLengkap}>
            {judul}
          </h3>
          <p className="ac-sub" title={subLengkap}>
            {sub}
          </p>
        </div>
        <span className="ac-count sr-count" aria-live="polite">
          <strong>{view.totalKg === null ? "—" : formatKg(view.totalKg)}</strong>{" "}
          {view.regions.length} wilayah
        </span>
      </header>

      {/* Legenda komoditas sekarang hidup di dalam donat (titik warna + nama +
          kg). Baris alat tidak lagi dipakai kartu ini, jadi kedua kartu punya
          urutan identik: kepala → donat → keterangan. */}

      {view.kosong ? (
        <p className="ac-empty">{regionSurplusReason(view.reason)}</p>
      ) : irisan.length ? (
        // Satu donat, satu warna per komoditas — sama dengan kartu di sebelahnya.
        // Wilayah asal tetap terbaca di kepala kartu; donat menjawab "surplus ini
        // terdiri dari komoditas apa".
        <div className="rc-plot">
          <CompositionDonut
            slices={irisan}
            totalValue={totalTanpaSatuan}
            totalUnit="kg"
            aria={`${judul}: ${irisan.map((i) => i.aria).join("; ")}`}
            caption="irisan = kg surplus · warna = komoditas"
          />
          {/* Wilayah tetap disebut walau donat memakai warna komoditas: pembaca
              masih bisa melihat surplus siapa saja yang dijumlahkan, termasuk
              yang di bawah ambang kirim. */}
          <p className="cd-wilayah">
            {view.regions
              .map(
                (wilayah) =>
                  `${wilayah.region} ${formatKg(wilayah.surplusKg)}${
                    view.minKg !== null && (wilayah.layakKg ?? 0) <= 0
                      ? " (di bawah ambang)"
                      : ""
                  }`
              )
              .join(" · ")}
          </p>
        </div>
      ) : (
        <p className="ac-empty">
          Server belum memerinci surplus per komoditas untuk wilayah ini.
        </p>
      )}
    </section>
  );
}
