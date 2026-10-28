// S4-06 polish wiring — page.tsx: sidebar per role + peta & stok.
// Node-env (kontrak pada source, pola sama dengan kpi-wiring.test.tsx).
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

const pageSrc = readFileSync("app/page.tsx", "utf8");
const apiSrc = readFileSync("lib/api.ts", "utf8");
const opsSrc = readFileSync("components/OpsConsole.tsx", "utf8");
// Langkah 4 (11 Okt): detail keputusan pindah ke halaman tersendiri
// "Decision & Evidence" — kontraknya diperiksa di komponen itu.
// 28 Okt 2026: isi detail dipindah lagi ke DecisionDetail.tsx (dipakai halaman
// DAN popup), jadi kontrak dibaca dari keduanya.
const evidenceSrc =
  readFileSync("components/DecisionEvidence.tsx", "utf8") +
  readFileSync("components/DecisionDetail.tsx", "utf8");

describe("wiring sidebar + map di app/page.tsx (S4-06 polish)", () => {
  it("page memakai layout sidebar (side-nav) + SupplyMap", () => {
    expect(pageSrc).toContain("side-nav");
    expect(pageSrc).toContain("SupplyMap");
    expect(pageSrc).toMatch(/<SupplyMap/);
  });

  it("page memuat data map via hook React Query → fetchBalanceMap (data REAL)", () => {
    // Rules.md §3: peta dipoll lewat useBalanceMap, bukan efek+setInterval lagi.
    const hookSrc = readFileSync("lib/hooks/useBalanceMap.ts", "utf8");
    expect(pageSrc).toContain("useBalanceMap");
    expect(hookSrc).toContain("fetchBalanceMap");
    expect(hookSrc).toContain("setInterval");
    expect(apiSrc).toContain("fetchBalanceMap");
    // Endpoint resmi:
    expect(apiSrc).toContain("/balance/map");
    // Kredensial via Bearer (bukan query):
    expect(apiSrc).toMatch(/fetchBalanceMap[\s\S]*Bearer/);
  });

  it("RoleHero tidak lagi dirender di Overview", () => {
    // 28 Okt 2026: pemilik meminta blok "Konsol ..." (judul + batas domain)
    // dihapus untuk SEMUA peran. Komponennya masih diuji terpisah, tetapi
    // halaman tidak boleh memasangnya lagi.
    expect(pageSrc).not.toMatch(/<RoleHero/);
  });

  it("feed traceable: chip filter status + count, EXPIRED tampil", () => {
    // Arah Roy 2026-10-09: EXPIRED TIDAK disembunyikan — harus tetap
    // terbaca; filter status = visual only, semua status punya chip+count.
    // 14 Okt 2026: chip + angkanya dihitung lib/decision-feed (label bahasa
    // manusia, "Perlu tindakan" di chip pertama).
    expect(pageSrc).toMatch(/feed-filters/);
    // 24 Okt 2026: chip menghitung daftar BERJENDELA (periode terpilih), bukan
    // seluruh riwayat — angka chip harus cocok dengan kartu di bawahnya.
    expect(pageSrc).toMatch(/feedChips\(feedWindowDecisions\)/);
    expect(pageSrc).toMatch(/filter-chip/);
  });

  it("angka sidebar Recommendations = yang PERLU TINDAKAN, bukan total keputusan", () => {
    // Dulu `Recommendations (126)` = seluruh keputusan yang pernah dibuat;
    // pengguna tidak bisa menebak artinya. Sekarang = jumlah yang menunggu
    // tindakan manusia, satu definisi dengan lonceng notifikasi top bar.
    expect(pageSrc).toMatch(/perluKeputusan = countActionable\(decisions, undefined, role\)/);
    expect(pageSrc).toMatch(/Recommendations\$\{perluKeputusan/);
    expect(pageSrc).not.toMatch(/Recommendations\$\{decisions\.length/);
  });

  it("fitur lama tetap ada: konsol agent di tab Demo Control + feed + detail", () => {
    // 2026-10-19 (keputusan Roy): tab Demo Control disederhanakan jadi tiga
    // blok (siapkan data → jalankan agent → bukti). OpsConsole/Event2Panel
    // tidak lagi dipasang di page; komponennya tetap ada dan tetap diuji di
    // tests/ops-console.test.tsx + tests/event2-panel.test.tsx.
    expect(pageSrc).toMatch(/<DemoControlPanel/);
    expect(pageSrc).not.toMatch(/<OpsConsole/);
    // Halaman bukti keputusan kini tab tersendiri (sidebar acuan halaman 3):
    expect(pageSrc).toMatch(/<DecisionEvidence/);
    expect(evidenceSrc).toMatch(/<DecisionActions/);
    // Desain baru halaman bukti (17 Okt 2026) mengganti kartu ala feed dengan
    // hero "catatan keputusan" + lini masa audit; yang dipin sekarang: tindakan
    // keputusan, lini masa, integritas bukti — dan badge kasus demo tetap
    // diambil dari sumber yang sama (caseLabelOf di RecommendationCard).
    expect(evidenceSrc).toMatch(/<DecisionAudit/);
    expect(evidenceSrc).toMatch(/caseLabelOf/);
    expect(evidenceSrc).toMatch(/<IntegrityPanel/);
    expect(pageSrc).toMatch(/Recommendation Feed/);
    expect(pageSrc).toMatch(/Agent Activity Log/);
    // Event2Panel dirender DI DALAM OpsConsole (komposisi) —
    // page cukup memasang OpsConsole; kedua panel tetap ter-wire.
    expect(opsSrc).toMatch(/<Event2Panel/);
  });

  it("nav dipilih per role — monitor tanpa tab analisis", () => {
    // Approver-only analisis: monitor (read-only) tidak melihat tab Analisis.
    expect(pageSrc).toMatch(/isApprover/);
    expect(pageSrc).not.toMatch(/APPROVER_TABS/);
  });

  it("tab Decision & Evidence memilih keputusan default (halaman tidak kosong)", () => {
    const page = readFileSync("app/page.tsx", "utf8");
    // 17 Okt: argumen `now` ditambahkan supaya keputusan yang MASIH BERLAKU
    // didahulukan (dulu halaman terbuka pada keputusan kedaluwarsa).
    expect(page).toMatch(/defaultEvidenceId\(decisions, now\)/);
    // WS-D memindahkan nav ke components/SideNav.tsx, jadi handler-nya sekarang
    // menerima id tab (`id`), bukan item nav (`n`). Niat tesnya tetap sama:
    // menekan tab bukti langsung memilih keputusan yang butuh tindakan.
    expect(page).toMatch(/id === "evidence" && !selectedId/);
  });
});
