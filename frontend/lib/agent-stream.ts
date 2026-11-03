// Pembaca aliran SSE (text/event-stream) untuk log langsung Demo Control.
//
// Kenapa ditulis sendiri, bukan `EventSource`: `EventSource` tidak bisa
// mengirim header `Authorization`, sedangkan endpoint kemajuan dijaga peran
// SPPG. Streaming lewat `fetch` + `ReadableStream` membuat token tetap di
// header seperti panggilan API lain (lihat `streamDemoAgent` di `lib/api.ts`).
//
// Fungsi di berkas ini MURNI: tidak menyentuh jaringan, tidak menyentuh DOM.
// Itu membuat batas potongan jaringan bisa diuji langsung — dan potongan
// jaringan memang sembarang: satu `data:` bisa tiba terbelah dua.

export type PeristiwaSse = { nama: string; data: string };

export type LangkahAgent = {
  step: string;
  tool: string | null;
  ringkas: string;
  at: string;
};

/** Normalkan akhir baris lalu pecah menjadi peristiwa utuh. */
export function bacaSse(potongan: string): { peristiwa: PeristiwaSse[]; sisa: string } {
  const teks = potongan.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  // Peristiwa dipisahkan baris kosong. Potongan terakhir yang belum diakhiri
  // baris kosong DISIMPAN: memprosesnya sekarang berarti membuang data separuh.
  const bagian = teks.split("\n\n");
  const sisa = bagian.pop() ?? "";
  const peristiwa: PeristiwaSse[] = [];

  for (const blok of bagian) {
    if (!blok.trim()) continue;
    let nama = "";
    const data: string[] = [];
    let komentar = false;

    for (const baris of blok.split("\n")) {
      if (baris.startsWith(":")) {
        komentar = true;
        const isi = baris.slice(1).trim();
        if (isi) data.push(isi);
        continue;
      }
      const pisah = baris.indexOf(":");
      const kunci = (pisah === -1 ? baris : baris.slice(0, pisah)).trim();
      let isi = pisah === -1 ? "" : baris.slice(pisah + 1);
      if (isi.startsWith(" ")) isi = isi.slice(1);
      if (kunci === "event") nama = isi.trim();
      else if (kunci === "data") data.push(isi);
      // `id:`/`retry:` tidak dipakai: kanal ini berumur satu putaran.
    }

    if (!nama && komentar) {
      peristiwa.push({ nama: "komentar", data: data.join("\n") });
      continue;
    }
    if (!nama && data.length === 0) continue;
    peristiwa.push({ nama: nama || "pesan", data: data.join("\n") });
  }

  return { peristiwa, sisa };
}

/** JSON satu peristiwa → langkah; `null` bila bukan langkah atau JSON rusak.
 *
 *  Baris rusak DILEWATI, bukan melempar: satu baris cacat di tengah aliran
 *  tidak boleh mematikan log yang sedang dibaca operator.
 */
export function langkahDari(peristiwa: PeristiwaSse): LangkahAgent | null {
  if (peristiwa.nama !== "langkah") return null;
  let isi: unknown;
  try {
    isi = JSON.parse(peristiwa.data);
  } catch {
    return null;
  }
  if (!isi || typeof isi !== "object") return null;
  const data = isi as Record<string, unknown>;
  const step = typeof data.step === "string" ? data.step.trim() : "";
  if (!step) return null;
  return {
    step,
    tool: typeof data.tool === "string" && data.tool.trim() ? data.tool : null,
    ringkas: typeof data.ringkas === "string" ? data.ringkas : "",
    at: typeof data.at === "string" ? data.at : "",
  };
}

/** Nama sumber data satu langkah → daftar, dipisah `+`.
 *
 *  Server menyiarkan `tool_called` sebagai `supply.get+demand.get+supplier.get`
 *  (satu langkah sering memanggil beberapa sumber). Untuk log pengambilan data
 *  satu baris panjang itu terbaca sebagai slug internal; dipecah per sumber ia
 *  terbaca sebagai daftar "apa yang sedang diambil".
 *
 *  Tidak ada penerjemahan nama: nilai yang dicetak harus sama dengan yang
 *  dipanggil server, supaya operator bisa mencocokkannya dengan Agent Log.
 */
export function sumberDari(tool: string | null | undefined): string[] {
  if (typeof tool !== "string") return [];
  return tool
    .split("+")
    .map((bagian) => bagian.trim())
    .filter((bagian) => bagian.length > 0);
}
