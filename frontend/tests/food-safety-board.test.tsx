// Kontrak markup halaman "Keamanan Pangan" (halaman sidebar acuan /compliance).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

const NOW = new Date("2026-10-11T06:00:00Z");
const BATCHES = [
  { id: "b1", location: "Cianjur", commodity: "telur", quantity_kg: 400, safety_status: "pass", freshness_score: 0.69, usable_until: "2026-10-11T18:00:00Z" },
  { id: "b2", location: "Surabaya", commodity: "ayam", quantity_kg: 120, safety_status: "fail", freshness_score: null, usable_until: null },
];

function render(props: Partial<Parameters<typeof FoodSafetyBoard>[0]> = {}) {
  return renderToStaticMarkup(
    <FoodSafetyBoard batches={BATCHES} now={NOW} {...props} />
  );
}

describe("FoodSafetyBoard", () => {
  it("judul + ringkasan pengawasan tampil dengan angka dari batch", () => {
    const html = render();
    expect(html).toContain("Keamanan Pangan");
    expect(html).toContain("Ringkasan pengawasan");
    expect(html).toContain("Batch diperiksa");
    expect(html).toContain("Gagal uji");
    expect(html).toContain("120 kg");
  });

  it("lima angka eksklusif: jumlahnya = batch diperiksa, tanpa bar atau persentase", () => {
    // Pemilik 29 Okt 2026: "desain begitu masih sulit dipahami". Versi lama
    // menampilkan empat angka yang TIDAK menjumlah ke total, lalu menambal
    // selisihnya dengan bar komposisi, persentase per angka, titik warna, dan
    // lipatan "Cara membaca". Kontrak sekarang: lima kelompok eksklusif
    // (aman, gagal, perlu verifikasi, belum diuji, ditahan) yang jumlahnya
    // selalu = total, sehingga tidak ada yang perlu dijelaskan lagi.
    const html = render();
    // Hanya kartu Ringkasan yang diperiksa: persen di kolom Kesegaran tabel
    // adalah angka lain, bukan pengkodean kedua untuk partisi yang sama.
    const kartu = html.slice(
      html.indexOf('id="safety-ringkasan"'),
      html.indexOf("</article>", html.indexOf('id="safety-ringkasan"'))
    );
    const angka = Array.from(kartu.matchAll(/class="safety-count-value">(\d+)</g)).map((m) => Number(m[1]));
    expect(kartu.match(/class="safety-count /g) ?? []).toHaveLength(5);
    expect(angka).toHaveLength(5);
    expect(angka.reduce((a, b) => a + b, 0)).toBe(2);
    expect(kartu).toContain("dari 2 batch");
    // Tidak ada pengkodean kedua untuk himpunan data yang sama.
    expect(kartu).not.toContain("safety-ratio");
    expect(kartu).not.toContain("safety-figure-swatch");
    expect(kartu).not.toContain("%");
    expect(kartu).not.toContain("Cara membaca angka ini");
  });

  it("penanda memisahkan hitungan dari beratnya (tidak terbaca 1540 kg)", () => {
    const html = render({
      batches: [
        ...BATCHES,
        {
          id: "b3",
          location: "Cianjur",
          commodity: "beras",
          quantity_kg: 540,
          safety_status: "pass",
          freshness_score: 0.5,
          usable_until: "2026-10-11T18:00:00Z",
          quarantine_status: "quarantined",
        },
      ],
    });
    // Angka penanda (jumlah batch) dan berat karantina dulu berdempet tanpa
    // pemisah sehingga "1 540 kg" terbaca sebagai satu berat. Yang diuji adalah
    // teks yang dibaca pengguna (tag dibuang lebih dulu).
    const teks = html.replace(/<[^>]+>/g, "");
    // Berat kini menempel pada angka yang diterangkannya: catatan kecil di bawah
    // label "DITAHAN", bukan baris kaki kartu. Alasan larangan ada di title.
    expect(html).toContain("safety-count-note");
    expect(teks).toContain("540 kg");
    expect(html).toContain("tidak boleh dialokasikan");
    expect(teks).not.toContain("1 540 kg");
  });

  it("batch gagal dinyatakan terang-terangan beserta lokasinya", () => {
    const html = render();
    expect(html).toContain("Batch gagal uji: Surabaya");
    // Jaminan "gagal uji tidak boleh dialokasikan" kini dibawa kalimat peringatan,
    // bukan lagi hint penanda karantina: penanda bernilai nol tidak dirender
    // (28 Okt 2026), jadi hint-nya tidak muncul saat tidak ada batch ditahan.
    expect(html).toContain("alokasi hanya boleh memakai batch berstatus aman");
  });

  // Permintaan pemilik 29 Okt 2026: "kerjakan dari bagian atas dulu".
  // Di kartu Ringkasan, kalimat putusan dulu duduk PALING BAWAH — di bawah bar
  // komposisi, penanda, dan dua lipatan — sehingga pembaca melihat empat angka
  // dan cetakan kecil sebelum tahu ada batch gagal. Kontrak yang dijaga sekarang:
  // putusan lebih dulu, angka sesudahnya.
  it("putusan gagal uji tampil sebelum angka ringkasan", () => {
    const html = render();
    const putusan = html.indexOf("safety-verdict");
    const angka = html.indexOf("safety-counts");
    expect(putusan).toBeGreaterThan(-1);
    expect(angka).toBeGreaterThan(-1);
    expect(putusan).toBeLessThan(angka);
  });

  // 29 Okt 2026 (putaran kedua, "UI kurang enak dilihat"): putusan tidak lagi
  // berupa bidang peringatan selebar kartu. Bidang penuh membuat satu batch gagal
  // terbaca sebagai halaman galat dan menenggelamkan angka di bawahnya; nada
  // status dipindah ke titik kecil + aksen tepi kartu.
  it("putusan memakai titik status, bukan bidang peringatan penuh", () => {
    const html = render();
    const kartu = html.slice(
      html.indexOf('id="safety-ringkasan"'),
      html.indexOf("</article>", html.indexOf('id="safety-ringkasan"'))
    );
    expect(kartu).toContain("safety-verdict-dot");
    expect(kartu).not.toContain("board-alert");
    // Status tidak diulang sebagai lencana di kepala kartu.
    expect(kartu).not.toContain("board-badge");
  });

  it("satu penanda per kondisi: batch ditahan yang lolos uji tidak dihitung dua kali", () => {
    const html = render({
      batches: [
        ...BATCHES,
        {
          id: "b9",
          location: "Cianjur",
          commodity: "beras",
          quantity_kg: 540,
          safety_status: "pass",
          freshness_score: 0.5,
          usable_until: "2026-10-11T18:00:00Z",
          quarantine_status: "quarantined",
        },
      ],
    });
    // Batch karantina menjadi kelompok sendiri ("Ditahan"), BUKAN penanda
    // terpisah di samping empat angka. Karena itu aman turun (karantina tidak
    // dihitung aman) dan jumlah lima angka tetap = total:
    // 1 aman + 1 gagal + 0 verifikasi + 0 belum + 1 ditahan = 3 batch.
    const angka = Array.from(html.matchAll(/class="safety-count-value">(\d+)</g)).map((m) => Number(m[1]));
    expect(angka.reduce((a, b) => a + b, 0)).toBe(3);
    expect(html).toContain("Ditahan");
    expect(html).toContain("540 kg");
    // Satu catatan saja: tidak ada baris kedua yang menghitung batch sama.
    expect((html.match(/safety-count-note/g) ?? []).length).toBe(1);
    expect(html).not.toContain("Ditahan walau uji lolos");
  });

  it("tabel per batch memuat status, kesegaran, dan sisa masa", () => {
    const html = render();
    expect(html).toContain("Status keamanan per batch");
    expect(html).toContain("Aman");
    expect(html).toContain("69%");
    expect(html).toContain("12 jam lagi");
    expect(html).toContain("—"); // batch tanpa skor/tanggal
  });

  it("nilai kosong tidak diganti angka nol", () => {
    const html = render({
      batches: [{ id: "x", location: "Bogor", commodity: "telur", quantity_kg: 10, safety_status: null }],
    });
    expect(html).toContain("0"); // hitungan aman 0 memang benar
    expect(html).not.toMatch(/>0 kg</);
    expect(html).toContain("—");
  });

  it("galat pemuatan dijelaskan, bukan halaman kosong", () => {
    const html = render({ batches: null, error: "batches 500" });
    expect(html).toContain("Tidak bisa memuat batch");
    expect(html).toContain("batches 500");
  });

  it("tidak ada catatan internal (path API / nama kolom) di layar", () => {
    const html = render();
    expect(html).not.toContain("Catatan sumber");
    expect(html).not.toContain("/batches");
    expect(html).not.toContain("usable_until");
  });
});

// ── Navigasi "lompat ke bagian" (20 Okt 2026) ───────────────────────────────
// Halaman ini lima bagian dan panjang; nav dipasang lewat komponen bersama
// (components/SectionJump.tsx). Kontrak yang dijaga di sini: nav hanya memuat
// tujuan yang bagiannya BENAR-BENAR dirender — "Penerimaan barang" hanya untuk
// peran yang punya SPPG sendiri, "Keputusan keamanan lokasi ini" hanya bila
// daftar keputusan tersedia. Tautan mati lebih buruk daripada tanpa nav.
describe("FoodSafetyBoard — navigasi bagian", () => {
  function tujuan(html: string): string[] {
    // Loop exec, bukan matchAll + spread: target TS proyek ini tidak
    // mengaktifkan downlevelIteration untuk iterator RegExp.
    const hasil: string[] = [];
    const pola = /class="section-jump-link" href="#([^"]+)"/g;
    let cocok: RegExpExecArray | null;
    while ((cocok = pola.exec(html)) !== null) hasil.push(cocok[1]);
    return hasil;
  }

  it("tanpa lokasi sendiri dan tanpa keputusan: tiga tujuan yang pasti ada", () => {
    // `safety-bukti-suhu` masuk sejak Fase 3 MG butir 5: panel bukti suhu
    // selalu dirender, jadi jangkarnya ikut di navigasi.
    // "Segera dipakai" tidak lagi memegang jatah nav (maks lima tujuan,
    // docs/design.md §24): kartunya hanya satu baris di bawah panel bukti.
    expect(tujuan(render())).toEqual([
      "safety-ringkasan",
      "safety-bukti-suhu",
      "safety-batch",
    ]);
  });

  it("kepala SPPG mendapat tujuan penerimaan barang", () => {
    const html = render({ ownLocation: "Jakarta", ownLocationId: "loc-jkt" });
    expect(tujuan(html)).toEqual([
      "safety-ringkasan",
      "safety-bukti-suhu",
      "safety-terima",
      "safety-batch",
    ]);
  });

  it("setiap tujuan punya tepat satu sasaran ber-id di halaman", () => {
    const html = render({ ownLocation: "Jakarta", ownLocationId: "loc-jkt", decisions: [] });
    const nav = tujuan(html);
    expect(nav).toContain("safety-keputusan");
    for (const id of nav) {
      expect((html.match(new RegExp(`id="${id}"`, "g")) ?? []).length).toBe(1);
    }
  });

  it("bagian tanpa sumber tetap punya sasaran (nav tidak menunjuk ruang kosong)", () => {
    // Batch gagal dimuat: ringkasan & tabel tetap dirender sebagai keadaan kosong.
    const html = render({ batches: null, error: "batches 500" });
    for (const id of tujuan(html)) {
      expect((html.match(new RegExp(`id="${id}"`, "g")) ?? []).length).toBe(1);
    }
  });
});

// ── Fase 11 — cakupan kepala SPPG (permintaan pemilik: "data harus akurat,
//    fitur harus jalan dengan backend") ───────────────────────────────────────
describe("FoodSafetyBoard — cakupan lokasi sendiri", () => {
  const JAKARTA = [
    {
      id: "j1",
      location: "Jakarta",
      commodity: "telur",
      quantity_kg: 800,
      // Barang baru datang: kartu Penerimaan hanya menampilkan batch `pending`.
      safety_status: "pending",
      freshness_score: 0.9,
      usable_until: "2026-11-07T12:00:00Z",
    },
  ];
  const ROUTES = {
    routes: [
      {
        id: "r1",
        batch_id: null,
        supplier_id: "s1",
        supplier_name: "Supplier A Cianjur",
        origin: { latitude: -6.854, longitude: 107.1306, name: "Supplier A Cianjur" },
        destination_id: "loc-jkt",
        destination_name: "Jakarta",
        destination: { latitude: -6.2088, longitude: 106.8456, name: "Jakarta" },
        commodity: "telur",
        quantity_kg: 800,
        usable_until: "2026-11-07T12:00:00+00:00",
        safety_status: "pass",
        straight_km: 78.35,
        road: {
          distance_km: 110.4,
          duration_min: 84.3,
          ratio_vs_straight: 1.41,
          geometry: { type: "LineString", coordinates: [[107.13, -6.85], [106.84, -6.2]] },
          source: "osrm",
          fetched_at: null,
        },
      },
    ],
  };
  const BALANCE = {
    commodity: "telur",
    locations: [
      { location: "Jakarta", region: "DKI Jakarta", supply_kg: 300, demand_kg: 1080, surplus_kg: 0, shortage_kg: 780 },
    ],
  };
  const DECISIONS = [
    {
      decision_id: "d1",
      decision_type: "safety_disruption",
      status: "proposed",
      quantity_kg: 492,
      valid: false,
      seconds_remaining: 0,
      created_at: "2026-10-16T09:27:02Z",
    },
    { decision_id: "d2", decision_type: "regional_balance", status: "proposed", quantity_kg: 600, valid: false },
    {
      decision_id: "d3",
      decision_type: "safety_disruption",
      status: "rejected",
      quantity_kg: 80,
      valid: false,
      created_at: "2026-10-15T09:00:00Z",
    },
  ];

  function renderOwn(props: Partial<Parameters<typeof FoodSafetyBoard>[0]> = {}) {
    return renderToStaticMarkup(
      <FoodSafetyBoard
        batches={JAKARTA}
        now={NOW}
        ownLocation="Jakarta"
        routes={ROUTES}
        balance={BALANCE}
        decisions={DECISIONS}
        {...props}
      />
    );
  }

  it("kartu Pasokan masuk menyebut pemasok, jalur jalan, dan kekurangan dari server", () => {
    const html = renderOwn();
    expect(html).toContain("Pasokan masuk menuju Jakarta");
    expect(html).toContain("Supplier A Cianjur");
    expect(html).toContain("110,4 km");
    // Kartu kiriman menyebut waktu tempuh dengan `durationLabel` (jam+menit),
    // bukan "84 menit" — angka server 84,3 menit yang sama, dibaca lebih enak.
    expect(html).toContain("1 jam 24 menit");
    expect(html).toContain("1,41× jarak lurus");
    expect(html).toContain("Kebutuhan 1.080 kg");
    expect(html).toContain("menutup kekurangan (+20 kg)");
  });

  it("kartu Pasokan masuk memakai stepper tahap perjalanan (bukan daftar angka saja)", () => {
    const html = renderOwn();
    expect(html).toContain("shipment-steps");
    expect(html).toContain("Dipanen");
    expect(html).toContain("Rincian kiriman");
    // Jalur belum dilaporkan server → kartu menyebut sebabnya, bukan mengarang.
    expect(html).toContain("Perjalanan belum dilaporkan server");
  });

  it("kolom tabel jadi Asal (pemasok) saat ber-scope lokasi sendiri", () => {
    const html = renderOwn();
    expect(html).toContain("Asal");
    expect(html).toContain("Supplier A Cianjur");
  });

  it("batch kedaluwarsa ditandai keadaan, bukan hanya 'kesegaran 0%'", () => {
    const html = renderToStaticMarkup(
      <FoodSafetyBoard
        batches={[
          {
            id: "e1",
            location: "Jakarta",
            commodity: "telur",
            quantity_kg: 250,
            safety_status: "pass",
            freshness_score: 0,
            usable_until: "2026-09-10T12:00:00Z",
          },
        ]}
        now={NOW}
        ownLocation="Jakarta"
      />
    );
    expect(html).toContain("Kedaluwarsa");
    expect(html).toContain("lewat");
  });

  it("keputusan keamanan: hanya jenis keamanan, dan dikatakan kalau tidak ada yang berlaku", () => {
    const html = renderOwn();
    expect(html).toContain("Keputusan keamanan lokasi ini");
    expect(html).toContain("2 keputusan keamanan");
    expect(html).toContain("1 ditolak (bisa diajukan ulang)");
    expect(html).toContain("menurut aturan server hanya keputusan yang");
    expect(html).toContain("Gangguan keamanan");
    expect(html).toContain("492 kg");
  });

  it("tombol Ajukan ulang hanya untuk keputusan yang DITOLAK (kontrak /actions/repropose)", () => {
    const html = renderOwn({ canMutate: true, onRepropose: async () => "x" });
    // hanya satu dari dua baris yang boleh punya tombol: yang ditolak
    expect(html.match(/Ajukan ulang/g) ?? []).toHaveLength(1);
  });

  it("tombol tindakan hanya muncul untuk peran yang boleh menulis", () => {
    expect(renderOwn({ canMutate: true, onRecheck: async () => null as never })).toContain("Uji ulang");
    expect(renderOwn({ canMutate: false })).not.toContain("Uji ulang");
    expect(renderOwn({ canMutate: true, onRepropose: async () => "x" })).toContain("Ajukan ulang");
  });

  it("tanpa cakupan lokasi (pengawas nasional) kolom Lokasi tetap dipakai", () => {
    const html = renderToStaticMarkup(<FoodSafetyBoard batches={JAKARTA} now={NOW} />);
    expect(html).toContain("Lokasi");
    expect(html).not.toContain("Pasokan masuk");
    expect(html).not.toContain("Penerimaan barang");
  });

  it("kartu Penerimaan barang: lima titik periksa + kalimat kemajuan", () => {
    const html = renderOwn({ canMutate: true, onRecheck: async () => null as never });
    expect(html).toContain("Penerimaan barang");
    expect(html).toContain("daftar periksa petugas");
    expect(html).toContain("0 dari 5 titik periksa sudah ditandai");
    expect(html).toContain("Catat hasil terima");
    expect(html).toContain("Nomor lot");
  });

  it("kalimat kemajuan tidak memerintah dan tidak menjanjikan gerbang", () => {
    const html = renderOwn({ canMutate: true, onRecheck: async () => null as never });
    expect(html).toContain("Boleh disimpan sebagian");
    expect(html).not.toContain("tandai sisanya sebelum barang dipakai");
    // Penghitung berubah setiap kotak dicentang — pembaca layar harus dengar.
    expect(html).toContain('aria-live="polite"');
  });

  it("lima kotak centang dibungkus satu kelompok bernama 'Titik periksa'", () => {
    const html = renderOwn({ canMutate: true, onRecheck: async () => null as never });
    expect(html).toContain("<fieldset");
    expect(html).toContain("<legend>Titik periksa</legend>");
  });

  it("komoditas & batch tampil sebagai pilihan terlihat, bukan dua dropdown bertingkat", () => {
    const html = renderOwn({ canMutate: true, onRecheck: async () => null as never });
    expect(html).toContain("Keadaan batch:");
    expect(html).toMatch(/(Aman|Gagal uji|Belum)[^<]*layak s\/d/);
    // Tanggal tidak boleh pecah antara bulan dan tahun di 375 px.
    expect(html).toContain('class="safety-nobr"');
    // Revisi 20 Okt: tidak ada <select> untuk batch (opsi datang/menghilang)
    // dan tidak ada keadaan yang dijejalkan ke dalam <option>.
    expect(html).not.toContain("<select");
    expect(html).not.toContain("<option");
    expect(html).toContain('type="radio"');
    expect(html).toContain("1. Komoditas");
    expect(html).toContain("2. Barang yang belum diuji");
  });

  it("opsi Lainnya: petugas bisa menulis keadaan di luar daftar, bukan titik periksa ke-6", () => {
    const html = renderOwn({
      canMutate: true,
      onRecheck: async () => null as never,
      onRecordReceipt: async () => ({}) as never,
      loadReceipts: async () => ({ items: [] }),
    });
    expect(html).toContain("Lainnya — tuliskan keadaan yang tidak ada di daftar");
    expect(html).toContain("<textarea");
    // Contoh keadaan nyata, supaya petugas tahu apa yang boleh ditulis — dan
    // HANYA sekali (dulu muncul tiga kali: label, placeholder, catatan bawah).
    expect(html).toContain("karung lapis kedua basah");
    expect(html.match(/karung lapis kedua basah/g)?.length).toBe(1);
    // Hitungan titik periksa TIDAK ikut bertambah oleh opsi ini.
    expect(html).toContain("0 dari 5 titik periksa sudah ditandai");
    // Kartu menyatakan terang-terangan apa yang disimpan.
    expect(html).toContain("dua hal ke database");
  });

  it("tanpa jalur simpan, kartu tidak menjanjikan catatan tersimpan", () => {
    const html = renderOwn({ canMutate: true, onRecheck: async () => null as never });
    expect(html).toContain("<textarea");
    expect(html).toContain("Ikut tersimpan ke database");
  });

  it("tanpa izin menulis, kartu penerimaan menyatakan batasnya (bukan tombol mati)", () => {
    const html = renderOwn({ canMutate: false });
    expect(html).toContain("Hanya kepala SPPG dan ahli gizi");
    expect(html).not.toContain("Catat hasil terima");
  });

  it("tombol Ajukan keputusan hanya untuk baris GAGAL UJI (dan hanya Kepala SPPG)", () => {
    const ajukan = (batch: Record<string, unknown>, canPropose = true) =>
      renderToStaticMarkup(
        <FoodSafetyBoard
          batches={[batch]}
          now={NOW}
          ownLocation="Jakarta"
          canMutate
          canPropose={canPropose}
          onTriggerDisruption={async () => ({ status: "disruption", decision_id: "d1" })}
        />
      );
    const gagal = ajukan({
      id: "f1",
      location: "Jakarta",
      commodity: "ayam",
      quantity_kg: 100,
      safety_status: "fail",
      freshness_score: 0.5,
      usable_until: "2026-10-20T12:00:00Z",
    });
    expect(gagal).toContain("Ajukan keputusan");
    // Ahli gizi (canMutate true, canPropose false) tidak melihat tombol usul.
    expect(
      ajukan(
        {
          id: "f2",
          location: "Jakarta",
          commodity: "ayam",
          quantity_kg: 100,
          safety_status: "fail",
          freshness_score: 0.5,
          usable_until: "2026-10-20T12:00:00Z",
        },
        false
      )
    ).not.toContain("Ajukan keputusan");
    const aman = ajukan({
      id: "a1",
      location: "Jakarta",
      commodity: "telur",
      quantity_kg: 100,
      safety_status: "pass",
      freshness_score: 0.9,
      usable_until: "2026-10-20T12:00:00Z",
    });
    expect(aman).not.toContain("Ajukan keputusan");
  });
});

// Opsi penerimaan barang tidak boleh ikut cakupan tabel (audit 20 Okt 2026):
// batch kota lain pasti ditolak server (403 "lokasi batch di cakupan lokasi di
// luar SPPG Anda"). Penyaringnya harus lewat `receivingBatchOptions`, bukan
// baris yang sudah disaring cakupan (`tampil` / `urut`).
describe("FoodSafetyBoard — opsi penerimaan terpisah dari cakupan tabel", () => {
  const sumber = readFileSync(join(__dirname, "..", "components", "FoodSafetyBoard.tsx"), "utf8");

  it("daftar opsi memakai receivingBatchOptions(rows, ownLocation)", () => {
    expect(sumber).toContain("receivingBatchOptions(rows, ownLocation)");
    expect(sumber).not.toMatch(/batchOpsi\s*=\s*urut/);
    expect(sumber).not.toMatch(/incomingBatchId\(rows,/);
  });
});

// Fase 3 MG butir 5: "Goods Receipt menjelaskan apakah bukti suhu cukup."
// Penjelasan itu wajib memakai blok `evidence` dari server apa adanya —
// sumber log, kelengkapan, dan waktu observasi — bukan disimpulkan di layar.
describe("FoodSafetyBoard — penerimaan menjelaskan bukti suhu", () => {
  const denganBukti = [
    {
      id: "t1",
      location: "Cianjur",
      commodity: "telur",
      quantity_kg: 300,
      // Hanya batch "pending" yang muncul di daftar penerimaan (lihat
      // receivingBatchOptions): batch yang sudah dinilai bukan pekerjaan terima.
      safety_status: "pending",
      freshness_score: 0.7,
      usable_until: "2026-10-12T12:00:00Z",
      evidence: {
        temperature_observation: "missing",
        evidence_state: "insufficient",
        source: "seed",
        source_label: "log simulasi",
        observed_at: null,
        sample_count: 0,
        evidence_sufficient: false,
      },
    },
  ];

  it("menyebut kelengkapan bukti + asal log untuk batch yang diterima", () => {
    const html = renderToStaticMarkup(
      <FoodSafetyBoard batches={denganBukti} now={NOW} ownLocation="Cianjur" />
    );
    expect(html).toContain('data-role="bukti-terima"');
    expect(html).toContain("Bukti suhu kiriman ini");
    expect(html).toContain("log simulasi");
    expect(html).not.toContain("sensor aktif");
  });

  it("bukti tidak cukup dinyatakan, bukan disembunyikan", () => {
    const html = renderToStaticMarkup(
      <FoodSafetyBoard batches={denganBukti} now={NOW} ownLocation="Cianjur" />
    );
    expect(html).toContain("periksa dulu sebelum dipakai");
  });
});
