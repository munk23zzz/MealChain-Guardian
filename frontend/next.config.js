/** @type {import('next').NextConfig} */
// Proxy API — mengapa ada:
// backend/app/main.py hanya mengizinkan origin localhost:3000, sehingga UI
// yang dibuka dari origin lain (mis. GitHub Codespaces,
// https://<codespace>-3000.app.github.dev) akan diblokir CORS oleh browser.
// Solusinya: UI memanggil API lewat origin-nya sendiri, lalu Next meneruskan
// ke kontainer `backend` di jaringan compose (nama host `backend`).
// Aktif hanya kalau NEXT_PUBLIC_API_URL kosong (lihat docker-compose.override.yml);
// kalau diisi URL absolut, jalur ini tidak terpakai dan perilaku lama tetap sama.
const BACKEND_INTERNAL_URL =
  process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000";

// Root endpoint API backend (lihat frontend/lib/api.ts) — didaftarkan eksplisit
// supaya tidak menabrak aset Next (/_next) atau halaman aplikasi.
// WAJIB sinkron dengan prefix path di frontend/lib/api.ts; ada tes kontrak
// (tests/proxy-roots.test.ts) yang gagal kalau ada root terlewat — dulu "admin"
// tidak terdaftar sehingga tab Pengaturan membalas 404 HTML dari Next sendiri.
const API_ROOTS = [
  "admin",
  "auth",
  // Langkah 2 kalender (2026-10-16): agenda harian tab "Hari Ini". Tanpa akar
  // ini, /agenda jatuh ke router Next sendiri → 404 HTML, bukan JSON.
  "agenda",
  "decisions",
  "actions",
  "balance",
  "events",
  "price",
  "kpi",
  // 27 Okt 2026: angka pengadaan untuk tile Overview (PO terbit, keputusan
  // berjejak ACT, batch berangkat). Tanpa akar ini tile menerima 404 HTML dari
  // router Next sendiri dan menulis "gagal memuat angka pengadaan" — terukur
  // saat uji UI pertama.
  "procurement",
  "ledger",
  "demo",
  "batches",
  "supplier-exclusions",
  "suppliers",
  // Fase 10: rute JALAN kiriman pemasok → tujuan (dipakai peta untuk garis).
  "supplier-routes",
  // Limbah + mitra pengolahan (18 Okt 2026): /waste/summary untuk panel
  // Surplus & Limbah. Tanpa akar ini panel menerima 404 HTML dari Next sendiri
  // dan tiga baris limbah kembali menjadi "—".
  "waste",
  // Rencana alokasi surplus lintas lokasi (20 Okt 2026): /surplus/allocations
  // untuk panel "Rencana alokasi surplus". Tanpa akar ini Next menjawab 404 HTML
  // sendiri dan panel kembali menulis "tidak ada pasangan".
  "surplus",
  // Fase 11: dua hitung-ulang dari halaman Keamanan Pangan. Tanpa dua akar ini
  // tombol "Periksa kiriman"/"Uji ulang" membalas 404 HTML dari Next sendiri
  // (terukur: "Tidak bisa memeriksa: HTTP 404: /freshness/evaluate").
  "freshness",
  "safety",
  // Fase 11 lanjutan: catatan penerimaan barang (opsi "Lainnya" yang tersimpan,
  // migrasi 016) — jalur tulis kedua dari kartu "Penerimaan barang".
  "receipts",
  // W-3 (2026-10-17): papan status integrasi per komponen. Tanpa akar ini
  // panel di tab Agent Log menerima 404 HTML dari router Next sendiri.
  "integrations",
  // W-5 (2026-10-17): purchase order mock SAP (baca saja). Tanpa akar ini panel
  // PO di tab Decision & Evidence menerima 404 HTML dari router Next sendiri.
  "sap",
];

// ── SEC-05: header keamanan untuk halaman HTML ─────────────────────────────
// Backend hanya menyajikan JSON (CSP-nya `default-src none`), sedangkan UI
// butuh izin lebih: Next menyisipkan skrip inline, MapLibre membuat worker dari
// blob, dan tile/gambar peta datang sebagai data: atau blob:. Karena itu
// kebijakan di bawah dibuat per direktif, bukan "semua dilarang".
//
// Catatan dev: Next dev memakai eval untuk HMR, jadi `unsafe-eval` hanya
// ditambahkan saat NODE_ENV=development. Build produksi tidak memuatnya —
// itu sebabnya nilai ini disusun dari variabel, bukan konstanta.
const DEV = process.env.NODE_ENV === "development";

const CSP = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${DEV ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  // Tile peta: MapLibre mengambil raster OSM (lihat SupplyMap.tsx). Tanpa host
  // ini peta tampil kosong dan konsol dipenuhi "Failed to fetch" — terukur
  // 24 Okt 2026 saat CSP pertama dipasang.
  "img-src 'self' data: blob: https://tile.openstreetmap.org",
  "font-src 'self' data:",
  // UI memanggil API lewat origin sendiri (rewrites); ws: untuk HMR di dev.
  // MapLibre juga mem-fetch tile (bukan hanya <img>), jadi host tile harus ada
  // di connect-src; `ws:`/`wss:` khusus dev untuk HMR.
  `connect-src 'self' https://tile.openstreetmap.org${DEV ? " ws: wss:" : ""}`,
  "worker-src 'self' blob:",
  "child-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const HEADER_KEAMANAN = [
  { key: "Content-Security-Policy", value: CSP },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  // Sengaja BUKAN `no-referrer`: tile.openstreetmap.org menolak (membalas gambar
  // "Access blocked", HTTP 200 + header `x-blocked`) setiap request tanpa Referer.
  // `strict-origin-when-cross-origin` tetap tidak membocorkan path/query ke situs
  // lain — hanya origin — dan itu nilai yang diterima kebijakan tile OSM.
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "geolocation=(), microphone=(), camera=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // Folder build bisa dipindah lewat env. Alasan: di Windows, `next dev` yang
  // sedang hidup memegang `.next/trace` sehingga `next build` gagal EPERM
  // padahal port dev berbeda. Dengan NEXT_DIST_DIR=.next-build, build bisa
  // diverifikasi tanpa mematikan dev server orang lain. Default tetap `.next`.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  experimental: {
    // Proxy dev (rewrites di bawah) memutus koneksi ke backend pada 30 detik
    // (bawaan Next: node_modules/next/dist/server/lib/router-utils/
    // proxy-request.js → `proxyTimeout || 30000`). Itu memutus
    // POST /demo/event1 yang menjalankan alur penuh DETECT→…→SUPERVISE:
    // terukur 27,9–30 dtk di stack lokal, dan klien menerima
    // "socket hang up" walau keputusan SUDAH ditulis di backend.
    // 3 menit memberi ruang untuk rantai provider yang lambat; batas keras
    // per provider tetap berlaku di backend.
    proxyTimeout: 180000,
  },
  async headers() {
    return [
      {
        // Semua halaman & aset. Proxy API (/auth, /kpi, ...) ikut terkena,
        // dan itu tidak masalah: header ini tidak mengubah isi respons JSON.
        source: "/:path*",
        headers: HEADER_KEAMANAN,
      },
    ];
  },
  async rewrites() {
    return API_ROOTS.map((root) => ({
      source: `/${root}/:path*`,
      destination: `${BACKEND_INTERNAL_URL}/${root}/:path*`,
    }));
  },
};

module.exports = nextConfig;
