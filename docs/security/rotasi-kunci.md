# Rotasi kunci setelah `.env` pernah masuk riwayat git (SEC-01)

Status: **belum dikerjakan** — butuh tindakan pemilik akun. Dokumen ini daftar
langkah manual; tidak ada nilai rahasia yang ditulis di sini.

## Kenapa

Audit 24 Okt 2026 menemukan `.env` pernah ter-commit (`c4d22b3`) lalu dikeluarkan
(`8f95c98`). Menghapus berkas dari commit terakhir **tidak** menghapusnya dari
riwayat: siapa pun yang pernah meng-clone atau mengunduh repo masih bisa membaca
nilai lama. Terukur saat audit: **42 nilai masih identik** dengan `.env` hari ini
— artinya kunci yang sama masih hidup, bukan sekadar sisa historis.

`.env` sekarang tidak dilacak git (`.gitignore` baris 52), dan kunci AWS baru
sudah dipisah ke `secrets/aws-app.env` (baris 84). Itu mengurangi paparan ke
depan, tetapi tidak menggugurkan kewajiban rotasi.

## Kunci yang wajib dianggap bocor

| Variabel | Dampak bila disalahgunakan | Cara rotasi |
|---|---|---|
| `JWT_SECRET` | Bisa membuat token untuk peran apa pun (termasuk `sppg_head`) | Ganti nilai acak 32+ byte, lalu **semua sesi lama otomatis gugur** |
| `SIGNING_KEY_HEX` | Bisa memalsukan segel dossier keputusan | Ganti; dossier lama akan gagal verifikasi — itu perilaku yang benar |
| `POSTGRES_PASSWORD` | Akses penuh ke DB (termasuk data keputusan) | Ganti di `postgres` + `.env`, lalu recreate stack |
| `INFERHUB_API_KEY` | Pemakaian model atas biaya Anda | Revoke di dashboard InferHub, buat kunci baru |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Akses ke Bedrock/AgentCore | Nonaktifkan access key lama di IAM, buat yang baru, simpan di `secrets/aws-app.env` |
| `SAP_AI_CORE_CLIENT_SECRET` | Akses OAuth ke AI Core | Rotasi di BTP, perbarui `.env` |
| `MEALCHAIN_API_TOKEN` | Memanggil API lintas layanan (mock SAP/agent) | Ganti; perbarui pemanggilnya |

## Urutan yang aman

1. **Siapkan nilai baru** di berkas lokal (`secrets/rotasi-<tanggal>.env`), jangan
   di chat dan jangan di commit.
2. **Rotasi yang tidak memutus layanan lebih dulu**: InferHub → AWS → SAP →
   `MEALCHAIN_API_TOKEN`.
3. **`POSTGRES_PASSWORD`**: `ALTER USER mealchain WITH PASSWORD '<baru>';` lalu
   perbarui `.env`, kemudian `docker compose up -d postgres backend`. Perhatikan
   volume DB tidak perlu dihapus.
4. **`JWT_SECRET` dan `SIGNING_KEY_HEX` paling akhir**, karena keduanya
   membatalkan artefak lama: semua token login gugur (pengguna harus login ulang)
   dan dossier yang sudah tersegel tidak lagi lolos verifikasi. Untuk demo, itu
   justru yang diinginkan.
5. **Verifikasi**:
   - `POST /auth/login` → 200, dan token baru berumur 720 menit.
   - `GET /ledger/verify` → `valid: true`.
   - Dossier baru: segel `signed` + `verify: true`.
   - Dossier lama: `verify: false` — bukti bahwa kunci lama benar-benar mati.
6. **Cabut token lama yang tersimpan di browser** (localStorage): login ulang
   cukup, karena token lama tidak lagi lolos tanda tangan.

## Membersihkan riwayat git (opsional, tapi disarankan bila repo pernah publik)

Repo demo GitHub Pages adalah repo lain dan **tidak** memuat `.env`; yang perlu
dibersihkan adalah repo kerja ini bila pernah di-push ke remote mana pun.

```bash
# 1) pastikan tidak ada perubahan yang belum di-commit
git status --short

# 2) hapus .env dari SELURUH riwayat (git-filter-repo, lebih aman dari rebase manual)
pip install git-filter-repo
git filter-repo --path .env --invert-paths

# 3) remote ikut terhapus oleh filter-repo; pasang ulang lalu force-push
git remote add origin <url>
git push --force --all && git push --force --tags
```

Setelah itu minta setiap kolaborator meng-clone ulang; clone lama mereka masih
menyimpan riwayat berisi kunci — karena itu rotasi (langkah 1–5) tetap wajib,
terlepas dari pembersihan riwayat.

## Yang TIDAK akan menyelesaikan masalah

- Menghapus `.env` di commit baru saja (sudah dicoba di `8f95c98`).
- Mengganti nilai di `.env` tanpa mencabut kunci di penyedia layanan: kunci lama
  tetap hidup di sisi mereka.
- Mengandalkan `.gitignore` untuk riwayat yang sudah terlanjur ada.
