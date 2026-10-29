"use client";

// Log "Proses pengambilan data" — gaya terminal, diperbarui saat langkah terjadi.
//
// Kenapa ada (29 Okt 2026): dulu tombol Jalankan agent hanya memperlihatkan
// "tunggu…", lalu seluruh langkah muncul sekaligus. Pemilik meminta prosesnya
// terlihat seperti terminal. Isi baris tetap APA ADANYA dari server
// (`_TraceStep`), tidak ada langkah yang dikarang di sisi klien.
//
// Keputusan tampilan (mengikuti bahasa desain konsol yang sudah ada,
// lihat `.agent-console` di globals.css):
// - permukaan `--terminal` yang sudah dipakai `.trace-output`, mono `--font-data`,
//   radius kontrol kecil — bukan jendela gelap baru yang berteriak beda;
// - jam kecil redup di kiri, nama langkah bertekanan, ringkasan sebagai isi;
// - satu pil keadaan di kanan kepala: live / selesai / siap / galat.

import { useEffect, useRef, useState } from "react";
import { sumberDari, type LangkahAgent } from "../lib/agent-stream";

const ZONA = "Asia/Jakarta";

/** Jam WIB dari waktu ISO server → "10.21.04". Nilai tak sah = "--.--.--". */
export function jamLangsung(at: string): string {
  if (!at) return "--.--.--";
  const waktu = new Date(at);
  if (Number.isNaN(waktu.getTime())) return "--.--.--";
  try {
    const bagian = new Intl.DateTimeFormat("id-ID", {
      timeZone: ZONA,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(waktu);
    return bagian.replace(/:/g, ".");
  } catch {
    // Lingkungan tanpa data zona waktu: lebih baik tanpa jam daripada jam salah.
    return "--.--.--";
  }
}

export default function AgentRunTerminal({
  langkah,
  aktif,
  galat = null,
}: {
  langkah: LangkahAgent[];
  aktif: boolean;
  galat?: string | null;
}) {
  const badanRef = useRef<HTMLDivElement | null>(null);
  // "Ikuti" = gulir otomatis ke baris terbaru. Dimatikan begitu operator
  // menggulir ke atas: log yang bergerak sendiri saat sedang dibaca balik
  // membuat baris yang ingin dibaca hilang dari pandangan.
  const [ikut, setIkut] = useState(true);

  useEffect(() => {
    const badan = badanRef.current;
    if (!badan || !ikut) return;
    badan.scrollTop = badan.scrollHeight;
  }, [langkah.length, ikut]);

  const keadaan = galat ? "galat" : aktif ? "live" : langkah.length > 0 ? "selesai" : "siap";
  const label =
    keadaan === "galat"
      ? "galat"
      : keadaan === "live"
        ? "live"
        : keadaan === "selesai"
          ? "selesai"
          : "siap";

  return (
    <div className="dc-term" data-keadaan={keadaan}>
      <div className="dc-term-bar">
        <span className="dc-term-lampu" aria-hidden="true" />
        <code className="dc-term-judul">proses-pengambilan-data.log</code>
        <span className="dc-term-jumlah">{langkah.length} langkah</span>
        {!ikut && langkah.length > 0 && (
          <button
            type="button"
            className="dc-term-ikut"
            onClick={() => {
              setIkut(true);
              const badan = badanRef.current;
              if (badan) badan.scrollTop = badan.scrollHeight;
            }}
          >
            Ikuti
          </button>
        )}
        <span className="dc-term-pil" data-keadaan={keadaan}>
          {label}
        </span>
      </div>

      <div
        className="dc-term-badan"
        role="log"
        aria-live="polite"
        aria-label="Log proses pengambilan data"
        ref={badanRef}
        onScroll={(e) => {
          const badan = e.currentTarget;
          const dekatBawah =
            badan.scrollHeight - badan.scrollTop - badan.clientHeight < 24;
          if (dekatBawah !== ikut) setIkut(dekatBawah);
        }}
      >
        {langkah.map((l, i) => {
          const sumber = sumberDari(l.tool);
          return (
            <p className="dc-term-baris" key={`${l.step}-${l.at}-${i}`}>
              <span className="dc-term-jam">{jamLangsung(l.at)}</span>
              <span className="dc-term-langkah" title={l.tool ?? undefined}>
                {l.step}
              </span>
              {(sumber.length > 0 || l.ringkas) && (
                <span className="dc-term-isi">
                  {sumber.length > 0 && (
                    // Satu langkah sering memanggil beberapa sumber (DETECT
                    // memanggil supply+demand+supplier). Dicetak per sumber
                    // supaya terbaca sebagai daftar pengambilan data, bukan
                    // satu slug panjang — dan tetap satu kolom dengan
                    // ringkasannya, supaya tepi kiri log tidak bergerigi.
                    <span className="dc-term-sumber" aria-label="Sumber data">
                      {sumber.map((nama) => (
                        <code
                          className="dc-term-sumber-item"
                          data-sumber={nama}
                          key={nama}
                        >
                          {nama}
                        </code>
                      ))}
                    </span>
                  )}
                  {l.ringkas}
                </span>
              )}
            </p>
          );
        })}

        {aktif && (
          <p className="dc-term-baris dc-term-baris--tunggu">
            <span className="dc-term-jam">--.--.--</span>
            <span className="dc-term-isi">
              {langkah.length === 0 ? "menunggu langkah pertama…" : "langkah berikutnya…"}
              <span className="dc-term-kursor" aria-hidden="true">
                ▍
              </span>
            </span>
          </p>
        )}

        {galat && (
          <p className="dc-term-baris dc-term-baris--galat" role="alert">
            <span className="dc-term-jam">--.--.--</span>
            <span className="dc-term-isi">{galat}</span>
          </p>
        )}
      </div>
    </div>
  );
}
