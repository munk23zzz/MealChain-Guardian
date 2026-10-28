"use client";

// Panel "Surplus wilayah lain" — pasangan grafik kecukupan di tab Overview
// (28 Okt 2026). Grafik di kiri menjawab "lokasi saya cukup atau tidak";
// panel ini menjawab pertanyaan berikutnya: "kalau kurang, surplusnya ada di
// mana?".
//
// Sumber angka HANYA `GET /surplus/regions` (dihitung server, lintas lokasi).
// Klien tidak boleh menghitungnya dari peta: peta akun SPPG dibatasi cakupan,
// jadi satu lokasi — dan "daerah lain" akan selalu kosong (Ruling 2026-10-14).
//
// Bentuk visual mengikuti bahasa grafik kecukupan (kelas `supply-adequacy` /
// `sa-*`): kartu, kepala, dan daftar baris yang sama; yang berbeda hanya arti
// baris (wilayah, bukan komoditas) dan susunan kolomnya.

import { useEffect, useState, type CSSProperties } from "react";

import { formatClockWib, formatDateTime } from "../lib/datetime";
import { formatKg } from "../lib/overview-format";
import {
  komoditasKeluarga,
  komoditasTone,
  regionSharePct,
  regionSurplus,
  regionSurplusReason,
  sumberRingkas,
  type RegionSurplusView,
  type SurplusWilayah,
} from "../lib/surplus-regions";

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

function barisAria(wilayah: SurplusWilayah, view: RegionSurplusView): string {
  const komoditas = wilayah.byCommodity
    .map((c) => `${c.commodity} ${formatKg(c.surplusKg)}`)
    .join(", ");
  const layak =
    wilayah.layakKg !== null && wilayah.layakKg > 0
      ? `, layak dialihkan ${formatKg(wilayah.layakKg)}`
      : "";
  const ambang =
    wilayah.layakKg === 0 && view.minKg !== null
      ? `, seluruh surplusnya di bawah ambang ${formatKg(view.minKg)}`
      : "";
  return [
    `${wilayah.region}: surplus ${formatKg(wilayah.surplusKg)}${layak}${ambang}`,
    `${wilayah.locations} lokasi sumber (${sumberRingkas(wilayah, 3)})`,
    komoditas ? `rincian komoditas ${komoditas}` : "rincian komoditas belum tersedia",
  ].join(". ");
}

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
  // Kelas warna komoditas: keluarga identitas lebih dulu (telur/ayam/beras/wortel
  // → amber/rose/biru/violet, sama dengan pil di peta), indeks urutan hanya
  // cadangan untuk komoditas di luar empat kanonik.
  const kelasKomoditas = (nama: string) =>
    `sr-komod-${komoditasKeluarga(nama) ?? komoditasTone(komoditas, nama)}`;
  const terbesar = view.regions[0]?.surplusKg ?? 0;
  const tanggal = updatedAt ? formatDateTime(new Date(updatedAt).toISOString()) : "—";
  const jam = updatedAt ? formatClockWib(new Date(updatedAt).toISOString()) : null;
  const asal = view.excludedLocation
    ? `di luar ${view.excludedLocation}`
    : locationName || "SPPG";
  // Judul & keterangan mengikuti cakupan: "daerah lain" hanya benar bila server
  // benar-benar membuang satu lokasi. Untuk BGN nasional panelnya seluruh
  // jaringan — menulis "daerah lain" di sana akan menyesatkan.
  const judul = view.excludedLocation ? "Surplus wilayah lain" : "Surplus per wilayah";
  const keteranganHero = view.excludedLocation
    ? "surplus di daerah lain"
    : "surplus seluruh jaringan";
  // Sub pendek; rincian sumber dipindah ke title supaya kartu tidak penuh teks.
  // Tanpa jam: cukup dari mana surplusnya + bahwa angkanya dari server.
  // "dihitung server" adalah penjelasan MEKANISME, bukan bahasa pengguna.
  // Yang dibutuhkan pembaca: angkanya berasal dari data yang tercatat.
  const sub = `${asal} · dari data tercatat`;
  const subLengkap = `${asal} · ${komoditas.length || "—"} komoditas · ${
    sourceNote ? `${sourceNote} · ` : ""
  }dihitung ${tanggal}`;
  const catatanLengkap = [
    "Angka = pasokan tercatat dikurangi kebutuhan pada komoditas yang sama, dijumlahkan per wilayah oleh server (peta akun SPPG hanya memuat lokasi sendiri).",
    "Hanya lokasi yang permintaannya tercatat boleh menyumbang surplus.",
    view.minKg !== null
      ? `Surplus per lokasi ≥ ${formatKg(view.minKg)} dianggap layak dialihkan.`
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
        className="supply-adequacy sr-panel"
        aria-label="Surplus wilayah lain"
        aria-busy="true"
      >
        <header className="sa-head">
          <div className="sa-title">
            <h3>{judul}</h3>
            <p className="sa-sub">{asal} · memuat wilayah…</p>
          </div>
        </header>
        <div className="sa-skeleton" aria-hidden="true">
          {[0, 1, 2, 3].map((i) => (
            <div className="sa-skeleton-row sr-skeleton-row" key={i}>
              <span className="sa-skeleton-name" />
              <span className="sa-skeleton-track" />
              <span className="sa-skeleton-gap" />
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="supply-adequacy sr-panel" aria-label="Surplus wilayah lain">
        <header className="sa-head">
          <div className="sa-title">
            <h3>{judul}</h3>
            <p className="sa-sub">{asal}</p>
          </div>
        </header>
        <p className="status-danger sa-error" role="alert">
          {error} {onRetry && (
            <button type="button" onClick={onRetry}>
              Coba lagi
            </button>
          )}
        </p>
      </section>
    );
  }

  return (
    <section
      className="supply-adequacy sr-panel"
      aria-labelledby="sr-title"
      data-wilayah={view.regions.length}
      title={catatanLengkap}
    >
      <header className="sa-head">
        <div className="sa-title">
          <h3 id="sr-title">{judul}</h3>
          <p className="sa-sub" title={subLengkap}>
            {sub}
          </p>
        </div>
        <div className="sa-summary sr-summary" aria-live="polite">
          <span className="sr-hero" title={keteranganHero}>
            <strong>{view.totalKg === null ? "—" : formatKg(view.totalKg)}</strong>
            <em>
              {view.regions.length} wilayah · dari{" "}
              {view.sourceLocations ?? view.regions.length} lokasi
            </em>
          </span>
        </div>
      </header>

      {view.kosong ? (
        <p className="sa-empty">{regionSurplusReason(view.reason)}</p>
      ) : (
        <>
          {view.layak.length > 0 ? (
            <ol className="sa-rows">
              {view.layak.map((wilayah, index) => (
                <li
                  key={wilayah.region}
                  className={`sa-row sa-tone-safe ${
                    wilayah.byCommodity[0]
                      ? kelasKomoditas(wilayah.byCommodity[0].commodity)
                      : "sr-komod-netral"
                  }`}
                  style={{ "--i": index } as CSSProperties}
                >
                  <div
                    className="sa-row-btn sa-row-static sr-row-btn"
                    role="group"
                    aria-label={barisAria(wilayah, view)}
                  >
                    <span className="sa-name">
                      <span className="sa-commodity">
                        {wilayah.region}
                        {index === 0 && <span className="sr-badge">terbesar</span>}
                      </span>
                      <span className="sa-stock">
                        {wilayah.locations} lokasi · {sumberRingkas(wilayah)}
                      </span>
                    </span>

                    <span className="sa-track sr-track" aria-hidden="true">
                      <span className="sa-track-fill">
                        {wilayah.byCommodity.length > 0 ? (
                          wilayah.byCommodity.map((c) => (
                            <span
                              key={c.commodity}
                              className={`sa-seg sr-seg ${kelasKomoditas(c.commodity)}`}
                              style={{
                                width: `${regionSharePct(c.surplusKg, terbesar)}%`,
                              }}
                            />
                          ))
                        ) : (
                          // Wilayah tanpa pecahan komoditas tetap digambar: satu
                          // batang netral, bukan batang kosong yang terlihat 0.
                          <span
                            className="sa-seg sr-seg sr-komod-netral"
                            style={{
                              width: `${regionSharePct(wilayah.surplusKg, terbesar)}%`,
                            }}
                          />
                        )}
                      </span>
                    </span>

                    <span className="sa-gap sa-gap-ok">
                      <strong>{formatKg(wilayah.surplusKg)}</strong>
                      {/* Angka kecil hanya dicetak bila memang BERBEDA: menulis
                          "3.554,81 kg / 3.554,81 kg layak dialihkan" hanya
                          mengulang angka besar dengan kalimat tambahan. */}
                      {wilayah.layakKg !== wilayah.surplusKg && (
                        <small>
                          {wilayah.layakKg === null
                            ? "komposisi layak belum dihitung"
                            : `${formatKg(wilayah.layakKg)} layak dialihkan`}
                        </small>
                      )}
                    </span>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="sa-empty">
              Surplus hanya di bawah ambang{" "}
              {view.minKg === null ? "pengiriman" : formatKg(view.minKg)}.
            </p>
          )}

          {view.layak[0] && view.layak[0].byCommodity.length > 0 && (
            // Asal surplus wilayah teratas: pertanyaan lanjutan setelah "di mana"
            // adalah "dari komoditas apa". Chip ini menjawabnya tanpa tabel baru.
            <div className="sr-mix">
              <span className="sr-mix-label" title={`Komoditas penyumbang surplus ${view.layak[0].region}`}>
                Dari komoditas
              </span>
              {view.layak[0].byCommodity.map((c) => (
                <span className="sr-mix-chip" key={c.commodity}>
                  <i
                    className={`sr-dot ${kelasKomoditas(c.commodity)}`}
                    aria-hidden="true"
                  />
                  {c.commodity} {formatKg(c.surplusKg)}
                </span>
              ))}
            </div>
          )}

          {view.kecil.length > 0 && (
            // Surplus kecil TIDAK dibuang: ia dikumpulkan satu baris yang
            // menyebut nama wilayah dan totalnya. Baris 0,5 kg di daftar utama
            // hanya menghasilkan batang tak terlihat dan mengubur yang penting.
            <p
              className="sr-tail"
              title={view.kecil
                .map((r) => `${r.region} ${formatKg(r.surplusKg)}`)
                .join(" · ")}
            >
              <strong>Surplus kecil</strong> · {view.kecil.length} wilayah ·{" "}
              {formatKg(view.kecilKg)}
            </p>
          )}
        </>
      )}

    </section>
  );
}
