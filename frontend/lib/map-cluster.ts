/** Pengelompokan penanda peta yang bertumpuk.
 *
 *  Masalah nyata: dua penanda bisa duduk 5–9 px dari satu sama lain saat peta
 *  diperkecil, sehingga lingkaran 24 px saling berpotongan (WCAG 2.5.8 gagal)
 *  dan ketukan jari bisa mengenai penanda yang salah. Solusinya bukan
 *  menggeser penanda — koordinat harus tetap benar — tetapi mengganti kelompok
 *  yang bertumpuk dengan satu gelembung berisi jumlah lokasi yang bisa diketuk
 *  untuk memperbesar peta. Semua fungsi di sini murni (tanpa DOM) supaya bisa
 *  diuji tanpa peta sungguhan.
 */

export type TitikPeta = { id: string; x: number; y: number };
export type Klaster = TitikPeta[];

/** Jarak pusat (piksel) di bawah mana dua penanda dianggap bertumpuk.
 *  34 px = gelembung 30 px + 4 px jarak aman, sekaligus di atas ambang target
 *  WCAG 2.5.8 (24 px) sehingga cincin target tidak pernah bersinggungan. */
export const KLASTER_JARAK_PIKSEL = 34;

/** Di atas zoom ini penanda kota sudah terpisah sendiri, jadi tidak perlu
 *  dikelompokkan lagi. */
export const KLASTER_ZOOM_MAKS = 14;

/** Kelompokkan penanda yang pusatnya lebih dekat dari `jarak` piksel.
 *
 *  Algoritma rakus deterministik: titik diproses berurutan, masing-masing masuk
 *  ke kelompok PERTAMA yang pusat massanya masih dalam radius. Hasilnya stabil
 *  untuk input yang sama — penting agar gelembung tidak "berkedip" setiap kali
 *  data disinkronkan ulang. */
export function kelompokkanBertumpuk(titik: readonly TitikPeta[], jarak = KLASTER_JARAK_PIKSEL): Klaster[] {
  const grup: Klaster[] = [];
  for (const t of titik) {
    let tujuan: Klaster | undefined;
    for (const g of grup) {
      const c = pusatKlaster(g);
      if (Math.hypot(t.x - c.x, t.y - c.y) <= jarak) {
        tujuan = g;
        break;
      }
    }
    if (tujuan) tujuan.push(t);
    else grup.push([t]);
  }
  return grup;
}

/** Titik tengah kelompok (dipakai sebagai posisi gelembung). */
export function pusatKlaster(grup: readonly TitikPeta[]): { x: number; y: number } {
  if (!grup.length) return { x: 0, y: 0 };
  const jumlah = grup.length;
  return {
    x: grup.reduce((s, p) => s + p.x, 0) / jumlah,
    y: grup.reduce((s, p) => s + p.y, 0) / jumlah,
  };
}

/** Hanya kelompok berisi 2+ penanda yang perlu diganti gelembung. */
export function klasterPerluGelembung(grup: readonly Klaster[]): Klaster[] {
  return grup.filter((g) => g.length > 1);
}

/** Gabungkan kelompok yang GELEMBUNGNYA sendiri akan bertumpuk.
 *
 *  Dua kelompok bisa terpisah anggotanya (jarak tiap anggota > radius) tetapi
 *  pusat massanya berdekatan — akibatnya dua gelembung saling menutup, dan
 *  masalah jarak target yang mau diperbaiki muncul lagi. Penggabungan diulang
 *  sampai tidak ada pasangan pusat yang berdekatan, jadi hasilnya stabil. */
export function gabungKlasterBerdekatan(grup: readonly Klaster[], jarak = KLASTER_JARAK_PIKSEL): Klaster[] {
  const hasil = grup.map((g) => [...g]);
  let berubah = true;
  while (berubah) {
    berubah = false;
    for (let i = 0; i < hasil.length && !berubah; i += 1) {
      for (let j = i + 1; j < hasil.length; j += 1) {
        const a = pusatKlaster(hasil[i]);
        const b = pusatKlaster(hasil[j]);
        if (Math.hypot(a.x - b.x, a.y - b.y) <= jarak) {
          hasil[i] = [...hasil[i], ...hasil[j]];
          hasil.splice(j, 1);
          berubah = true;
          break;
        }
      }
    }
  }
  return hasil;
}

/** Sebar penanda pada lingkaran — dipakai saat zoom sudah maksimum dan penanda
 *  benar-benar berimpit (koordinat sama). Urutan sebar tetap agar bisa diuji. */
export function offsetSpider(jumlah: number, radius = 28): { dx: number; dy: number }[] {
  if (jumlah <= 1) return [{ dx: 0, dy: 0 }];
  return Array.from({ length: jumlah }, (_, i) => {
    const sudut = (2 * Math.PI * i) / jumlah - Math.PI / 2;
    return { dx: Math.round(Math.cos(sudut) * radius), dy: Math.round(Math.sin(sudut) * radius) };
  });
}

/** Nama aksesibel gelembung: menyebut lokasinya, bukan sekadar angka —
 *  pembaca layar tidak bisa "melihat" angka di peta. */
export function labelKlaster(nama: readonly string[]): string {
  const bersih = nama.map((n) => n.trim()).filter(Boolean);
  if (!bersih.length) return "Lokasi berdekatan. Tekan untuk memperbesar peta.";
  return `${bersih.length} lokasi berdekatan: ${bersih.join(", ")}. Tekan untuk memperbesar peta.`;
}
