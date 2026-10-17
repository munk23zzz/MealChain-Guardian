// Kontrak markup halaman "Decision & Evidence" (Langkah 4). Yang dipin:
// - tanpa keputusan terpilih: keadaan kosong yang jelas + saran dari data;
// - dengan keputusan: empat kartu fakta + riwayat iterasi + bukti tersimpan;
// - nilai yang tidak ada ditulis "—", bukan 0 / "Rp0" / "Tidak".
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DecisionEvidence from "../components/DecisionEvidence";

const NOW = new Date("2026-10-11T02:30:00Z");

const SUMMARY = {
  decision_id: "d1",
  decision_type: "regional_balance",
  status: "pending_approval",
  iteration: 3,
  supersedes_id: "0267f818-f8f2-4e65-a299-f2627ad8ec71",
  proposed_by: "supervisor_agent",
  source_location: "Cianjur",
  target_location: "Jakarta",
  commodity: "telur",
  quantity_kg: 600,
  safe_delivered_cost: 16206000,
  cost_breakdown: { note: "seed demo — angka konsisten docs", purchase: "15720000", logistics: "486000" },
  material_number: "MAT-TELUR",
  supplier: { id: "s1", name: "Supplier A Cianjur", reliability_score: 0.8 },
  execution_target: "MOCK",
  verifier: { verdict: "unavailable", verified_by: "verifier_agent" },
  safety: { worst_status: "pass", blocked: false, batches_checked: 1 },
  expiry: { expires_at: "2026-10-11T02:16:47.973521+00:00", valid: false, seconds_remaining: 0 },
  approval_requirement: { verdict: "unavailable", min_approvals: 2, requirement: "2 dari 2" },
  approvals: [{ approver: "a1", role: "sppg_head" }],
  can_approve: false,
  can_execute: false,
  blocking_reasons: ["Kuota SPPG Jakarta penuh minggu ini"],
  approver_roles: ["sppg_head"],
};

const SELECTED = {
  decision_id: "d1",
  decision_type: "regional_balance",
  status: "pending_approval",
  quantity_kg: 600,
  safe_delivered_cost: 16206000,
  created_at: "2026-10-07T02:16:47Z",
  expires_at: "2026-10-11T02:16:47.973521+00:00",
};

const DECISIONS = [
  { decision_id: "d1", decision_type: "regional_balance", status: "pending_approval", quantity_kg: 600, expires_at: "2026-10-11T02:16:47.973521+00:00" },
  { decision_id: "d2", decision_type: "safety_disruption", status: "verifier_flagged", quantity_kg: 780, expires_at: "2026-10-11T09:00:00Z" },
];

const CHAIN = [
  { decision_id: "v1", iteration: 1, status: "rejected", quantity_kg: 600, safe_delivered_cost: 16206000, rejection_reason: "Kuota penuh" },
  { decision_id: "v2", iteration: 2, status: "pending_approval", quantity_kg: 600, safe_delivered_cost: 16206000 },
];

function render(over: Record<string, unknown> = {}) {
  return renderToStaticMarkup(
    <DecisionEvidence
      decisions={DECISIONS as any}
      selected={SELECTED}
      selectedId="d1"
      onSelect={() => {}}
      chain={CHAIN}
      summary={SUMMARY}
      supplierContext={null}
      role="sppg_head"
      token="t"
      now={NOW}
      {...over}
    />
  );
}

describe("Decision & Evidence — tanpa pilihan", () => {
  it("menjelaskan cara memilih dan menyarankan yang menunggu tindakan", () => {
    const html = render({ selected: null, selectedId: null, summary: null, chain: [] });
    expect(html).toContain("Belum ada keputusan dipilih");
    expect(html).toContain("evidence-suggest");
    expect(html).toContain("regional balance");
    expect(html).toContain("safety disruption");
  });

  it("tanpa keputusan menunggu tindakan: dikatakan apa adanya", () => {
    const html = render({ selected: null, selectedId: null, decisions: [], summary: null, chain: [] });
    expect(html).toContain("Tidak ada keputusan yang menunggu tindakan saat ini");
  });

  it("tanpa saran yang menunggu, keputusan lama tetap bisa dipilih lewat dropdown", () => {
    const html = render({
      selected: null,
      selectedId: null,
      summary: null,
      chain: [],
      decisions: [{ decision_id: "old", decision_type: "price_anomaly", status: "rejected", expires_at: "2026-10-01T00:00:00Z" }],
    });
    expect(html).toContain("Tidak ada keputusan yang menunggu tindakan saat ini");
    expect(html).toContain('value="old"');
  });
});

describe("Decision & Evidence — dengan keputusan", () => {
  it("judul halaman + kartu bukti utama", () => {
    const html = render();
    expect(html).toContain("Decision &amp; Evidence");
    expect(html).toContain("Ringkasan keputusan");
    expect(html).toContain("Biaya");
    expect(html).toContain("Keamanan &amp; pemasok");
    expect(html).toContain("Governance &amp; persetujuan");
    expect(html).toContain("Jejak &amp; riwayat");
  });

  it("mengisi fakta nyata: rute, komoditas, biaya, keamanan, pemasok", () => {
    const html = render();
    expect(html).toContain("Cianjur → Jakarta");
    expect(html).toContain("telur");
    expect(html).toContain("Rp15.720.000");
    expect(html).toContain("Rp16.206.000");
    expect(html).toContain("Lolos");
    expect(html).toContain("Supplier A Cianjur");
    expect(html).toContain("keandalan 80%");
    expect(html).toContain("1 dari 2");
  });

  it("tenggat memakai jam yang diberikan pemanggil", () => {
    expect(render()).toContain("Lewat 13 mnt");
  });

  it("riwayat iterasi memuat alasan penolakan (bahan belajar agen)", () => {
    const html = render();
    expect(html).toContain("v1");
    expect(html).toContain("alasan: Kuota penuh");
    expect(html).toContain("v1 diajukan");
  });

  it("selama daftar dimuat: keadaan memuat, bukan tuduhan 'tidak ada di cakupan'", () => {
    const html = render({ selected: null, selectedId: "id-tidak-ada", loading: true });
    expect(html).toContain("Memuat keputusan…");
    expect(html).not.toContain("tidak ada di cakupan");
  });

  it("tautan yang menunjuk keputusan di luar cakupan dikatakan, bukan disembunyikan", () => {
    const html = render({ selected: null, selectedId: "id-tidak-ada" });
    expect(html).toContain("Keputusan itu tidak ada di cakupan akun ini");
    // id dipotong seperti di seluruh halaman (shortId), bukan dikarang-kurangi.
    expect(html).toContain("id-tidak");
    // Tanpa tautan: keadaan kosong yang biasa, tanpa tuduhan cakupan.
    expect(render({ selected: null, selectedId: null })).toContain("Belum ada keputusan dipilih");
  });

  it("badge kasus demo ikut terbawa ke kepala keputusan (dulu dari kartu feed)", () => {
    const denganKasus = render({ selected: { ...SELECTED, demo_case: "gangguan-logistik" } });
    expect(denganKasus).toContain("Kasus: Gangguan Logistik");
    expect(render()).not.toContain("rec-case");
  });

  it("umur jendela ditulis sebagai persen terpakai, bukan jam mentah", () => {
    const html = render();
    // NOW = 11 Okt 02.30Z; jendela habis 02.16Z → lewat.
    expect(html).toContain('data-state="lewat"');
    expect(html).toContain("Jendela lewat");
    const aman = render({
      selected: {
        ...SELECTED,
        created_at: "2026-10-07T02:16:47Z",
        expires_at: "2026-10-12T02:16:47Z",
      },
    });
    // 4 dari 5 hari terpakai.
    expect(aman).toContain("Jendela terpakai 80%");
    expect(aman).toContain('data-state="aman"');
  });

  it("ekspor bukti satu tombol di kepala halaman, mati tanpa token", () => {
    const html = render();
    expect(html).toContain("Unduh bukti (JSON)");
    expect(html).toContain("evidence-export");
    expect(html).toContain("evidence-hero-actions");
    expect(render({ token: null })).toContain("disabled");
  });

  it("lini masa audit: cerita satu keputusan, waktu tidak dikarang", () => {
    const html = render();
    expect(html).toContain('class="audit-list"');
    // Daftar diberi nama: pembaca layar mengumumkan "Jejak keputusan, daftar".
    expect(html).toContain('aria-label="Jejak keputusan"');
    expect(html).toContain("v1 diajukan");
    expect(html).toContain("ditolak · alasan: Kuota penuh");
    // Verifikasi tidak punya kolom jam di DB → dikatakan apa adanya.
    expect(html).toContain("waktu tidak tercatat");
    // Baris approval tanpa nilai true/false BUKAN penolakan (klaim palsu).
    expect(html).not.toContain(">Ditolak</strong>");

    const denganKeputusan = render({
      summary: {
        ...SUMMARY,
        approvals: [
          { approver: "u1", role: "sppg_head", approved: true, approved_at: "2026-10-08T03:00:00Z" },
          { approver: "u2", role: "bgn_monitor", approved: false, approved_at: "2026-10-09T01:00:00Z", comment: "Data penerima belum lengkap" },
        ],
      },
    });
    // Peran backend diterjemahkan ke label manusia, bukan enum mentah.
    expect(denganKeputusan).toContain("Kepala SPPG");
    expect(denganKeputusan).toContain("Disetujui");
    expect(denganKeputusan).toContain("8 Okt 2026");
    expect(denganKeputusan).toContain("Data penerima belum lengkap");
    expect(denganKeputusan).toContain("audit-danger");
  });

  it("tanpa iterasi sebelumnya: dikatakan, bukan dibiarkan kosong", () => {
    const html = render({ chain: [] });
    expect(html).toContain("v3 diajukan");
    // Tidak ada iterasi lama yang dikarang ketika riwayatnya kosong.
    expect(html).not.toContain("v1 diajukan");
  });

  it("panel bukti & integritas terpasang (isi muncul setelah data diambil)", () => {
    const html = render();
    // IntegrityPanel mengambil dossier saat mount, jadi pada markup statis yang
    // terlihat adalah kerangkanya — inilah kontrak yang bisa dipin.
    expect(html).toContain('data-testid="integrity-panel"');
    expect(html).toContain('data-testid="ledger-status"');
    expect(html).toContain('data-testid="dossier-status"');
    expect(html).toContain("Dossier Keputusan");
  });

  it("jam klien belum siap: label tenggat '—' (bukan jam server)", () => {
    const html = render({ now: null });
    expect(html).toContain("Tenggat");
    expect(html).not.toContain("Lewat 13 mnt");
  });

  it("summary belum dimuat: fakta kosong ditulis '—', riwayat iterasi tetap tampil", () => {
    const html = render({ summary: null });
    expect(html).toContain("—");
    expect(html).not.toContain("Rp0");
    // Yang masih diketahui dari payload keputusan tetap terisi:
    expect(html).toContain("600 kg");
    expect(html).toContain("Lewat 13 mnt");
    // Riwayat iterasi tidak ikut hilang.
    expect(html).toContain("v1");
    expect(html).toContain("alasan: Kuota penuh");
    expect(html).toContain("v1 diajukan");
  });
});

// Dropdown 126 keputusan dulu mencetak istilah backend mentah
// ("regional_balance · pending_approval · ef347f91") berurutan apa adanya,
// sehingga pengguna tidak tahu mana yang perlu ditindak. Kontrak barunya:
// dikelompokkan + kata manusia (lib/decision-picker).
describe("Decision & Evidence — pemilih keputusan", () => {
  it("dikelompokkan dan memakai bahasa manusia, bukan istilah backend mentah", () => {
    const html = render();
    expect(html).toContain("<optgroup");
    expect(html).toContain("Menunggu tindakan (2)");
    expect(html).toContain("Alokasi regional direkomendasikan");
    expect(html).toContain("Pengalihan pasokan (gangguan keamanan)");
    // Bentuk lama label opsi: "<jenis> · <status> · <id 8>".
    expect(html).not.toContain("regional_balance ·");
    expect(html).not.toContain("safety_disruption ·");
    expect(html).not.toContain("pending_approval ·");
  });

  it("yang menunggu tindakan membawa sisa waktu supaya bisa diprioritaskan", () => {
    expect(render()).toContain("Lewat 13 mnt · d1");
  });

  it("tanpa jam klien, sisa waktu tidak dikarang jadi '—' di dalam opsi", () => {
    const html = render({ now: null });
    expect(html).toContain('value="d1"');
    expect(html).not.toContain("— · d1");
  });

  it("keputusan lama tetap dapat dipilih sendiri (nilai opsi = id utuh)", () => {
    const html = render({
      decisions: [
        {
          decision_id: "0267f818-f8f2-4e65-a299-f2627ad8ec71",
          decision_type: "price_anomaly",
          status: "rejected",
          created_at: "2026-10-01T00:00:00Z",
        },
      ],
    });
    expect(html).toContain('value="0267f818-f8f2-4e65-a299-f2627ad8ec71"');
    expect(html).toContain("Tidak menunggu tindakan (1)");
    expect(html).toContain("ditolak");
    expect(html).toContain("Penyesuaian harga direkomendasikan");
  });
});

// Ajakan "Klik untuk rincian & jejak agen" benar di feed (seluruh kartu
// dibungkus <button>), tapi di halaman ini kartu dirender tanpa pembungkus:
// kursor auto, tak ada induk yang bisa diklik, klik tidak mengubah apa pun.
// Jadi di sini diganti tombol nyata ke tab Agent Log.
describe("Decision & Evidence — jejak agen", () => {
  it("tidak ada lagi ajakan klik yang mati di kartu ringkasan", () => {
    const html = render({ onOpenTraces: () => {} });
    expect(html).not.toContain("Klik untuk rincian");
    expect(html).not.toContain("rec-hint");
  });

  it("jejak agen punya tombol nyata + keterangan ke mana ia membawa", () => {
    const html = render({ onOpenTraces: () => {} });
    expect(html).toContain("Buka jejak agen");
    expect(html).toContain("evidence-traces");
    expect(html).toContain("tab Agent Log");
  });

  it("tanpa callback, tombolnya tidak dirender (bukan tombol mati)", () => {
    expect(render()).not.toContain("Buka jejak agen");
  });
});

describe("Decision & Evidence — kerapian kartu fakta (17 Okt 2026)", () => {
  it("pemilih keputusan punya label terlihat + jumlah dari data", () => {
    const html = render();
    expect(html).toContain("Keputusan yang diperiksa");
    expect(html).toContain('for="pilih-keputusan"');
    expect(html).toContain("menunggu tindakan ·");
    expect(html).toContain("keputusan tersedia");
    expect(html).toContain("<optgroup");
  });

  it("baris kosong (\"—\") masuk rincian yang bisa dibuka; fakta terisi tetap tampil", () => {
    // Tanpa rincian biaya: Harga beli / Logistik / Catatan tidak punya data,
    // sementara biaya aman terkirim tetap ada.
    const html = render({
      selected: { decision_id: "d1", decision_type: "regional_balance", status: "pending_approval" },
      summary: { ...SUMMARY, cost_breakdown: {} },
    });
    const posisiTampak = html.indexOf("Biaya aman terkirim");
    const posisiRincian = html.indexOf('class="fact-more"');
    expect(posisiTampak).toBeGreaterThanOrEqual(0);
    expect(posisiRincian).toBeGreaterThan(posisiTampak);
    expect(html).toContain("rincian belum ada datanya");
    // Jangan pernah mengumumkan jumlah nol.
    expect(html).not.toContain("0 rincian belum ada datanya");
  });

  it("rincian kosong tidak dirender kalau semua barisnya terisi", () => {
    const html = render({
      summary: {
        ...SUMMARY,
        cost_breakdown: { purchase: 15720000, logistics: 486000, note: "seed demo" },
        verifier: { verdict: "consistent", verified_by: "verifier_agent" },
        material_number: "MAT-TELUR",
        execution_target: "MOCK",
      },
    });
    // Kartu Biaya bersih: blok rinciannya tidak memuat label biaya apa pun.
    const blokRincian = html.split('class="fact-more"').slice(1).join("");
    expect(blokRincian).not.toContain("Harga beli");
  });
});

describe("Decision & Evidence — kalimat langkah berikutnya (17 Okt 2026)", () => {
  it("kartu ringkasan dibuka oleh satu kalimat tindakan dari data", () => {
    const html = render();
    expect(html).toContain("Langkah berikutnya");
    expect(html).toContain("evidence-next");
    // SUMMARY pada fixture: jendela berlaku sudah lewat (expiry.valid=false).
    expect(html).toContain("Jendela berlaku keputusan sudah lewat");
  });

  it("peran pengawas: kalimatnya jujur bahwa ia tidak bisa menindaklanjuti", () => {
    const html = render({ role: "bgn_monitor", summary: { ...SUMMARY, expiry: { valid: true } } });
    expect(html).toContain("bersifat pengawasan");
    expect(html).toContain("evidence-next-muted");
  });
});

// ── Desain baru (17 Okt 2026): struktur "catatan keputusan" ───────────────
// Urutan region = urutan pengambilan keputusan manusia, bukan urutan tabel.
describe("Decision & Evidence — struktur catatan keputusan", () => {
  it("kepala keputusan: aksi + angka kunci dalam bahasa manusia", () => {
    const html = render();
    expect(html).toContain("evidence-hero-title");
    expect(html).toContain("Alihkan 600 kg telur: Cianjur → Jakarta");
    expect(html).toContain("Kuantitas");
    expect(html).toContain("600 kg");
    expect(html).toContain("Rp16.206.000");
    expect(html).toContain("+Rp486.000");
    expect(html).toContain("Tujuan");
    // Status ditulis sebagai kata, bukan enum mentah (copy hygiene).
    expect(html).toContain(">menunggu persetujuan<");
    expect(html).not.toContain(">PENDING_APPROVAL<");
  });

  it("flag triase hanya yang benar-benar perlu diperhatikan", () => {
    const html = render();
    expect(html).toContain("Perlu diperhatikan (1)");
    expect(html).toContain("Jendela berlaku habis");
    // Fixture punya verified_by + safety pass → tidak ada alarm palsu.
    expect(html).not.toContain("Belum diverifikasi");
  });

  it("konsekuensi tiap pilihan disebut, termasuk nomor iterasi berikutnya", () => {
    const html = render();
    expect(html).toContain("Kalau disetujui");
    expect(html).toContain("Belum bisa dieksekusi: Kuota SPPG Jakarta penuh minggu ini.");
    expect(html).toContain("Kalau ditolak");
    expect(html).toContain("v4");
  });

  it("jalur persetujuan: empat langkah berurutan dengan keadaan yang dibaca", () => {
    const html = render();
    // Empat langkah, berurutan (kelas langkah, bukan wadah "steps").
    expect(html.split('class="evidence-route-step ').length - 1).toBe(4);
    const label = ["Diajukan", "Verifikasi agent", "Persetujuan", "Eksekusi"].map((teks) =>
      html.indexOf(`>${teks}<`)
    );
    expect(label.every((pos) => pos >= 0)).toBe(true);
    expect(label[0]).toBeLessThan(label[1]);
    expect(label[1]).toBeLessThan(label[2]);
    expect(label[2]).toBeLessThan(label[3]);
    expect(html).toContain("Agen supervisor");
    expect(html).toContain("Keadaan langkah:");
    expect(html).toContain("evidence-route-waiting");
  });

  it("urutan region: kepala → rute → zona keputusan → bukti → jejak", () => {
    const html = render();
    const urut = ["evidence-hero", "evidence-route", "evidence-decide", "evidence-grid", "evidence-bottom"].map(
      (kelas) => html.indexOf(kelas)
    );
    for (let i = 1; i < urut.length; i += 1) {
      expect(urut[i]).toBeGreaterThan(urut[i - 1]);
    }
  });

  it("ada jalan pintas ke zona keputusan (dan id-nya benar-benar ada)", () => {
    const html = render();
    expect(html).toContain('href="#zona-keputusan"');
    expect(html).toContain('id="zona-keputusan"');
  });
});

// Keputusan owner 17 Okt: pemilih tidak menawarkan keputusan yang sudah lewat
// tenggat. Yang dipilih juri dari daftar "Lewat 2 jam…" berakhir tanpa tombol
// Eksekusi (backend 409 "decision expired") dan itu terbaca sebagai kerusakan.
describe("Pemilih keputusan — yang lewat tenggat disembunyikan", () => {
  it("opsi kedaluwarsa tidak ditawarkan dan jumlahnya disebut di sakelar", () => {
    const html = render({ selected: null, selectedId: null, summary: null, chain: [] });
    // d1 lewat 13 menit pada NOW, d2 masih 6,5 jam.
    expect(html).not.toContain('value="d1"');
    expect(html).toContain('value="d2"');
    expect(html).toContain("Tampilkan yang lewat tenggat (1)");
    expect(html).toContain("lewat tenggat disembunyikan");
  });

  it("keputusan yang sedang dipilih tetap bisa dibuka walau sudah lewat", () => {
    // Tautan bersama ke keputusan lama harus tetap menampilkan pilihannya —
    // kalau tidak, <select> tampak kosong dan halaman terbaca rusak.
    const html = render({ selectedId: "d1" });
    expect(html).toContain('value="d1"');
  });
});
