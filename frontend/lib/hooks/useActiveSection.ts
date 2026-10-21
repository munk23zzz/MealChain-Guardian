"use client";

// Bagian halaman yang sedang dibaca — untuk nav "lompat ke bagian".
//
// Dipakai listener gulir, BUKAN IntersectionObserver: bagian seperti panel bukti
// di Decision & Evidence lebih tinggi dari viewport, sehingga rasio irisannya
// selalu kecil dan ia tidak pernah "menang" melawan bagian pendek. Yang diukur
// di sini sederhana dan bisa dijelaskan: bagian TERAKHIR yang tepinya sudah
// melewati ambang atas layar (di bawah top bar + nav yang menempel).
//
// Pengukuran di-throttle requestAnimationFrame: satu pengukuran per frame,
// bukan satu per event gulir. Bagian yang id-nya tidak ada di DOM dilewati —
// halaman yang bagiannya bergantung pada data tidak boleh punya posisi "aktif"
// yang menunjuk elemen tak ada.

import { useEffect, useRef, useState } from "react";

/** Tinggi top bar (64) + nav menempel (± 44) + jarak 32. */
export const SECTION_JUMP_OFFSET = 140;

export function useActiveSection(ids: readonly string[], offset = SECTION_JUMP_OFFSET): string {
  const [aktif, setAktif] = useState<string>(ids[0] ?? "");
  // Daftar id bisa berupa array baru setiap render (hasil map di komponen);
  // yang menentukan perlu-tidaknya mengukur ulang adalah ISINYA, bukan
  // identitas array-nya.
  const kunci = ids.join("|");
  const idsRef = useRef<readonly string[]>(ids);
  idsRef.current = ids;

  useEffect(() => {
    if (!kunci) return;
    let raf = 0;
    // Penjaga "sudah dijadwalkan" terpisah dari id frame: menulis id hasil
    // requestAnimationFrame bisa tertimpa oleh callback-nya sendiri bila
    // callback berjalan segera (lingkungan uji), dan penjadwalan berikutnya
    // akan tertelan selamanya.
    let menunggu = false;
    const ukur = () => {
      const daftar = idsRef.current;
      let sekarang = daftar[0] ?? "";
      for (const id of daftar) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top - offset <= 0) sekarang = id;
      }
      // Di dasar halaman, bagian TERAKHIR yang menang walau tepinya belum
      // melewati ambang: bagian penutup biasanya lebih pendek daripada sisa
      // layar, sehingga tanpa aturan ini nav tetap menandai bagian sebelumnya
      // padahal pembaca sudah sampai ujung (terlihat di Overview, 20 Okt 2026).
      // Halaman yang tidak bisa digulir dilewati — di sana "dasar" bukan posisi.
      const bisaGulir = document.documentElement.scrollHeight - window.innerHeight;
      if (bisaGulir > 0 && window.scrollY >= bisaGulir - 4) {
        const terakhir = daftar[daftar.length - 1];
        if (terakhir && document.getElementById(terakhir)) sekarang = terakhir;
      }
      setAktif((sebelum) => (sebelum === sekarang ? sebelum : sekarang));
    };
    const onScroll = () => {
      if (menunggu) return;
      menunggu = true;
      raf = requestAnimationFrame(() => {
        menunggu = false;
        raf = 0;
        ukur();
      });
    };
    ukur();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [kunci, offset]);

  return aktif;
}
