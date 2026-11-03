// Kontrak halaman "Decision & Evidence" — BAGIAN YANG TETAP BERLAKU.
//
// Tahap 8 (29 Okt 2026): berkas ini dihidupkan kembali dari `.pause`. Dua belas
// tes lamanya memaku markah kartu fakta versi `DecisionDetail` (tile fakta,
// "kotak langkah berikutnya", "Jalur persetujuan", urutan region) — markah itu
// sudah pensiun, dan penggantinya ada di `evidence-tahap1..7-*.test.tsx`.
// Yang dipertahankan di sini adalah yang masih dijalankan kode hari ini:
// keadaan kosong (memuat · di luar cakupan · diganti Muat Demo · saran), peran
// baca-saja, dan pemilih keputusan. Versi utuh tes lama diarsipkan di
// docs/arsip/decision-evidence-20261029/tes-lama/.
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


  it("tenggat memakai jam yang diberikan pemanggil", () => {
    expect(render()).toContain("Lewat 13 menit");
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

  it("keputusan yang sudah diganti Muat Demo tidak dituduh di luar cakupan", () => {
    // 404 = barisnya sudah tidak ada, bukan soal cakupan peran. Pesan lama
    // menyesatkan operator tepat setelah ia menekan "Muat Demo".
    const html = render({ selected: null, selectedId: "id-mati", diganti: true });
    expect(html).toContain("sudah diganti oleh Muat Demo");
    expect(html).not.toContain("tidak ada di cakupan");
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
    expect(html).toContain("Dossier keputusan ini");
  });

  it("jam klien belum siap: label tenggat '—' (bukan jam server)", () => {
    const html = render({ now: null });
    expect(html).toContain("Tenggat");
    expect(html).not.toContain("Lewat 13 menit");
  });


});

// Dropdown 126 keputusan dulu mencetak istilah backend mentah
// ("regional_balance · pending_approval · ef347f91") berurutan apa adanya,
// sehingga pengguna tidak tahu mana yang perlu ditindak. Kontrak barunya:
// dikelompokkan + kata manusia (lib/decision-picker).
describe("Decision & Evidence — pemilih keputusan", () => {
  it("dikelompokkan dan memakai bahasa manusia, bukan istilah backend mentah", () => {
    const html = render();
    // 19 Okt 2026: penanda `<optgroup` diganti wadah milik DecisionPicker;
    // inti kontraknya tetap "dikelompokkan + kata manusia", bukan satu daftar
    // gepeng berisi istilah backend.
    expect(html).toContain("dpick-group-label");
    expect(html).toContain("Menunggu tindakan (2)");
    expect(html).toContain("Penyeimbangan pasokan regional");
    expect(html).toContain("Ganti sumber pasokan (gangguan keamanan)");
    // Bentuk lama label opsi: "<jenis> · <status> · <id 8>".
    expect(html).not.toContain("regional_balance ·");
    expect(html).not.toContain("safety_disruption ·");
    expect(html).not.toContain("pending_approval ·");
  });

  it("yang menunggu tindakan membawa sisa waktu supaya bisa diprioritaskan", () => {
    expect(render()).toContain("Lewat 13 menit · d1");
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

  // 29 Okt 2026 (keputusan pemilik, kedua): blok "Jejak agen keputusan ini"
  // DIHAPUS dari Decision & Evidence. Jejak agen punya rumahnya sendiri di tab
  // Agent Log; menduplikasinya di dossier membuat halaman bukti berisi dua
  // cerita langkah yang panjangnya berbeda (7 tahap pipeline vs 9 baris review).
  it("jejak agen tidak lagi dirender di dossier Decision & Evidence", () => {
    const html = render();
    expect(html).not.toContain("Jejak agen keputusan ini");
    expect(html).not.toContain('data-testid="trace-list"');
    // Bagian bukti lain tetap ada: yang dihapus hanya jejak agennya.
    expect(html).toContain("Jejak &amp; riwayat");
  });
});

describe("Decision & Evidence — peran baca-saja", () => {
  // Kontrak F9: kode peran mentah tidak dicetak, tetapi ALASANnya harus terbaca.
  it("bgn_monitor melihat alasan read-only, bukan tombol yang diam-diam hilang", () => {
    const html = render({
      role: "bgn_monitor",
      summary: { ...(SUMMARY as Record<string, unknown>), can_approve: false, can_reject: false, can_execute: false },
    });
    expect(html).toContain("read-only");
    expect(html).not.toContain("bgn_monitor");
  });
});

describe("Decision & Evidence — kerapian kartu fakta (17 Okt 2026)", () => {
  it("pemilih keputusan punya label terlihat + jumlah dari data", () => {
    const html = render();
    expect(html).toContain("Keputusan yang diperiksa");
    expect(html).toContain('for="pilih-keputusan"');
    expect(html).toContain("menunggu tindakan ·");
    expect(html).toContain("keputusan tersedia");
    // 19 Okt 2026: <select> diganti pemilih yang bisa dicari (DecisionPicker).
    // Inti yang dijaga tetap sama — pemicu yang menampilkan pilihan aktif dan
    // jumlah konteks; `<optgroup` hanya penanda implementasi lama.
    expect(html).toContain("dpick-trigger");
    expect(html).toContain('aria-haspopup="listbox"');
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


// ── Desain baru (17 Okt 2026): struktur "catatan keputusan" ───────────────
// Urutan region = urutan pengambilan keputusan manusia, bukan urutan tabel.
describe("Decision & Evidence — struktur catatan keputusan", () => {

  it("flag triase hanya yang benar-benar perlu diperhatikan", () => {
    const html = render();
    expect(html).toContain("Perlu diperhatikan (1)");
    expect(html).toContain("Jendela berlaku habis");
    // Fixture punya verified_by + safety pass → tidak ada alarm palsu.
    expect(html).not.toContain("Belum diverifikasi");
  });

  it("konsekuensi tiap pilihan tidak lagi dirender di halaman bukti", () => {
    const html = render();
    // Cabang "kalau disetujui / ditolak" adalah bahan memutuskan; popup
    // Recommendations yang menampilkannya sejak 29 Okt 2026.
    expect(html).not.toContain("Kalau disetujui");
    expect(html).not.toContain("Kalau ditolak");
  });



  it("zona keputusan tetap punya jangkar (nav bagian menunjuk ke sini)", () => {
    const html = render();
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

// Keluhan owner 30 Okt 2026: "kartu keputusan blok Bukti tidak ada panel
// Penerimaan barang, tidak ada tombol Tandai diterima". Sebabnya bukan data:
// sepanjang Tahap 8 kartu penerimaan hanya dipasang di `DecisionDetail`, berkas
// yang sudah tidak dirender di halaman mana pun. Tes ini mengunci janji yang
// sebenarnya: blok Bukti halaman keputusan WAJIB memuat kartunya.
describe("Blok Bukti — penerimaan barang", () => {
  const SUMMARY_GATE = {
    ...SUMMARY,
    status: "executed",
    can_receive: true,
    receipt_gate: {
      location_id: "loc-jkt",
      location_name: "Jakarta",
      batches: [
        {
          batch_id: "b1111111-2222-3333-4444-555555555555",
          status: "usable",
          can_receive: true,
          can_quarantine: false,
          receive_reasons: [],
          quarantine_reasons: [],
          next_step: null,
        },
      ],
      can_receive: true,
      can_quarantine: false,
      receive_reasons: [],
      quarantine_reasons: [],
      next_step: null,
    },
  };

  it("menampilkan kartu Penerimaan barang di halaman keputusan", () => {
    const html = render({ summary: SUMMARY_GATE });
    expect(html).toContain("Penerimaan barang");
    expect(html).toContain("b1111111");
  });

  it("tanpa `receipt_gate` server: kartu tidak dikarang", () => {
    const html = render({ summary: { ...SUMMARY } });
    expect(html).not.toContain("Penerimaan barang");
  });
});
