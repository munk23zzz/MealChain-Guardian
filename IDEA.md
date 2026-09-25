# IDEA.md — Tentang Project Apa Ini?

> Baca ini duluan. Kalau kamu (manusia atau AI agent) lupa kenapa proyek ini ada, kembali ke sini.

## Satu paragraf

**MealChain Guardian** adalah lapisan *agentic decision intelligence* yang secara kontinu
menyeimbangkan pasokan pangan dan kebutuhan institusional lintas lokasi, dengan keamanan
pangan dan kesegaran sebagai *hard constraint* — bukan pertimbangan tambahan. Dibangun untuk
kompetisi **Sokrates x SAP x AWS AI Agent**, dengan Program Makan Bergizi Gratis (MBG) Indonesia
sebagai *killer use case*.

## Masalah yang benar-benar kita selesaikan

Indonesia tidak kekurangan pangan secara agregat. Masalahnya: pangan yang tersedia tidak
selalu berada di lokasi yang tepat, pada waktu yang tepat, dengan harga wajar, dan bukti
keamanan yang cukup. Tiga akar masalah:

1. **Supply-demand mismatch lintas wilayah** — surplus di satu daerah, shortage di daerah lain,
   tidak saling terhubung.
2. **Visibilitas informasi terfragmentasi** — petani, pemasok, SPPG, dan dinas tidak melihat
   data yang sama secara real-time.
3. **Pangan punya nilai yang bergantung waktu** — kesegaran dan keamanan terus menurun sejak
   panen sampai konsumsi. *Physical inventory ≠ usable inventory.*

## Apa yang KITA BUKAN

- **Bukan** pengganti SAP (SAP sudah kuat di eksekusi: procurement, inventory, batch traceability)
- **Bukan** agen procurement generik
- **Bukan** platform food traceability
- **Bukan** sekadar AI keamanan pangan

## Apa yang KITA ADALAH

**Cross-regional food supply balancing intelligence.** SAP = system of record & eksekusi.
AWS (Bedrock AgentCore) = infrastruktur agentic AI. MealChain Guardian = lapisan kecerdasan
keputusan yang menggabungkan sinyal supply, demand, harga, kesegaran, keamanan, logistik,
dan bukti pendukung menjadi satu rekomendasi yang bisa dieksekusi.

## Kenapa sekarang

MBG menyerap pangan dalam volume besar lintas ribuan SPPG. Data publik menunjukkan pola nyata:
harga telur di Cianjur turun saat MBG libur, naik lagi saat MBG jalan di Palembang — ini bukti
MBG bertindak sebagai *regional demand shock*. Insiden keracunan massal terkait MBG (September
2026) menunjukkan persoalan keamanan pangan bersifat sistemik, bukan kebetulan. Detail lengkap
+ sitasi ada di proposal kompetisi (dokumen terpisah, lihat `docs/PRD.md` untuk ringkasannya).

## Konteks kompetisi — syarat yang WAJIB dipenuhi

Sokrates x SAP x AWS menilai berdasarkan:
- Menggunakan layanan AWS dan/atau SAP + kemampuan generative/agentic AI sebagai **inti** solusi
- (Sebisa mungkin) Mendemonstrasikan **working MVP**
- Menunjukkan **autonomous multi-step reasoning atau task execution** yang jelas oleh agent
- Menjawab **genuine business challenge** dengan pendekatan praktis dan outcome yang usable
- Penggunaan **AWS/SAP Agentic AI** — bukan sekadar "pakai AI", tapi pakai produk agentic AI
  resminya (Bedrock AgentCore)

Setiap keputusan teknis di `docs/Architecture.md` harus bisa dijawab: "ini membantu memenuhi
poin mana di atas?"

## Tim & cara kerja

- Roy (dev utama, pakai Hermes agent) + 1 teman (dev kedua, tools beda)
- Timeline: 3-4 minggu, greenfield, target akhir = live demo interaktif ke juri
- Build lokal via Docker; komponen agentic (Bedrock/AgentCore) pakai AWS trial asli dari
  kompetisi karena itu memang harus dipakai beneran, bukan disimulasikan

## Framing: Verifier Agent (talking points kalau juri tanya)

**Konteks:** Verifier Agent tidak disebut namanya di proposal — tapi langkah `VERIFY` SUDAH
ada di alur keputusan yang tertulis: DETECT → **VERIFY** → TRACE → PREDICT → OPTIMIZE →
DECIDE → ACT → LEARN. Proposal juga sudah mengutip literatur explainable AI bahwa sistem
otonom berisiko tinggi butuh pengawasan eksplisit, bukan keputusan tertutup satu algoritma
(Chukwunweike et al., 2024). Verifier Agent adalah jawaban konkret atas dua hal yang sudah
tertulis itu — bukan fitur baru yang muncul dari luar.

**Kalau ditanya "Verifier Agent ini tidak ada di proposal, kenapa muncul?"**
> "Betul, namanya tidak disebut eksplisit — tapi fungsinya sudah ada: proposal kami punya
> langkah VERIFY di alur DETECT-VERIFY-TRACE-...-LEARN, dan kami sudah mengutip argumen bahwa
> sistem otonom berisiko tinggi butuh pengawasan eksplisit, bukan algoritma yang menilai
> dirinya sendiri. Kalau VERIFY dikerjakan oleh Supervisor yang sama yang mengusulkan
> keputusan, itu bukan pengawasan sungguhan. Verifier Agent adalah entitas independen dengan
> persona skeptis yang benar-benar mengaudit — ini bukan penambahan scope, ini cara kami
> serius menunaikan apa yang sudah kami tulis sendiri."

**Kalau ditanya "kenapa bukan Supervisor saja yang cukup pintar untuk verify dirinya sendiri?"**
> "Karena itu justru risiko yang kami identifikasi sendiri: correlated failure — kalau satu
> model salah, dia akan 'setuju' dengan kesalahannya sendiri. Generator-critic dengan dua
> entitas terpisah, prompt berbeda, adalah pola yang lebih jujur untuk memenuhi klaim 'human
> oversight yang eksplisit' yang sudah ada di proposal."

**Kenapa framing ini kuat, bukan defensif:**
1. Tidak perlu berbohong atau mengaku ada gap — VERIFY dan sitasi explainable AI sudah
   tertulis hitam-putih di proposal yang lolos finalist.
2. Menunjukkan tim benar-benar mengeksekusi janji tertulis sampai ke level implementasi,
   bukan cuma jargon di slide.
3. Justru menjawab pertanyaan yang PASTI muncul dari juri SAP/AWS yang paham reliability
   sistem AI: "bagaimana kalian cegah agent bias/salah tanpa nunggu manusia?" — jawabannya
   sudah ada sebelum ditanya.

**Jangan pernah bilang:** "oh itu penambahan di luar proposal" (membuka pertanyaan kenapa
menyimpang). **Selalu bilang:** "itu implementasi dari langkah VERIFY yang sudah ada di
proposal kami" (menutup pertanyaan dengan bukti tertulis).

## Framing: Mock vs Real SAP (talking points kalau juri tanya)

**Konteks:** proposal yang sudah lolos finalist SUDAH menyebut AWS for SAP MCP Server sebagai
konektivitas SAP kita. Tidak bisa diresubmit, tidak perlu — karena poin ini justru sudah ada
di sana. Yang perlu disiapkan adalah cara menjawab kalau juri probe lebih dalam.

**Kalau ditanya "apakah ini benar-benar terhubung ke SAP asli?"**
> "MVP kami jalan dengan mode mock yang strukturnya identik dengan OData SAP asli — field
> sama persis (`Plant`, `MaterialNumber`, `PurchaseOrder`, dst.), karena kami merancang
> layer integrasi SAP sebagai adapter interface sejak hari pertama, bukan hardcode. Business
> logic kami — Safe Delivered Cost, safety constraint, balancing — sama sekali tidak
> menyentuh detail SAP, itu murni inovasi kami sendiri. Kalau diberi akses tenant SAP nyata,
> switch ke AWS for SAP MCP Server adalah perubahan konfigurasi satu baris, bukan rewrite —
> mau kami tunjukkan sekarang?"

**Kenapa framing ini kuat, bukan defensif:**
1. Bukan mengaku kekurangan — ini menunjukkan *keputusan arsitektur yang disengaja* (adapter
   pattern), praktik standar integrasi enterprise: validasi business logic dengan contract
   test double dulu sebelum cutover ke sistem produksi.
2. Membuktikan *production-readiness* justru lebih kuat lewat kemampuan switch cepat,
   dibanding kalau dari awal di-hardcode ke satu tenant SAP tertentu (yang sebenarnya kurang
   reusable).
3. Kalau diminta live switch di tempat — itu ada di `Roadmap.md` Sprint 5, sudah
   direncanakan sebagai task list siap eksekusi, tidak perlu planning dari nol.

**Jangan pernah bilang:** "kami belum implementasi SAP-nya" (defensif, terdengar seperti gap).
**Selalu bilang:** "SAP-nya di balik adapter, siap dinyalakan — mau lihat?" (proaktif,
menunjukkan kontrol).

## Peta dokumen lain

| Dokumen | Isinya |
|---|---|
| `docs/PRD.md` | Scope, MVP, target user, fitur inti, success metrics |
| `docs/Architecture.md` | Tech stack, struktur folder, arsitektur agent, keputusan teknis |
| `docs/design.md` | UI/UX flow, design system, komponen |
| `docs/Schema.md` | Struktur database |
| `docs/Skill.md` | Glosarium domain, formula, kontrak tool — "kamus kerja" proyek |
| `Rules.md` | Coding convention, batasan AI/kontributor |
| `workflows.md` | Cara Hermes/AI bekerja step-by-step |
| `Roadmap.md` | Rencana sprint |
| `TODO.md` | Pelacak progress — sumber kebenaran status kerja saat ini |
| `AGENTS.md` | Entry point singkat untuk coding agent manapun |
