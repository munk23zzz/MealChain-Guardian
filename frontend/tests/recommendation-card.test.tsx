// Kontrak RecommendationCard: kartu hanya menampilkan yang benar-benar ada di
// data, dan sejak 28 Okt 2026 kartu feed diringkas — judul + meta + status.
// Verdict verifier mentah ("consistent"/"flagged") tidak lagi dicetak; ia
// terbaca lengkap di Decision & Evidence.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import RecommendationCard, { CARD_HINT, caseLabelOf } from "../components/RecommendationCard";

const BASE = {
  decision_id: "d1",
  decision_type: "regional_balance",
  status: "pending_approval",
  quantity_kg: 600,
  safe_delivered_cost: 16206000,
  created_at: "2026-10-10T18:16:47.844642+00:00",
  expires_at: "2026-10-11T02:16:47.973521+00:00",
  valid: false,
  iteration: 3,
};

describe("RecommendationCard — label komoditas", () => {
  it("menulis nama barang yang direkomendasikan sebelum jumlahnya", () => {
    // Keluhan pemilik 29 Okt 2026: kartu tidak menyebut barang apa yang
    // direkomendasikan — hanya kg dan rupiah, jadi pembaca harus membuka popup.
    const html = renderToStaticMarkup(
      <RecommendationCard decision={{ ...BASE, commodity_name: "telur" } as any} />
    );
    expect(html).toContain("rec-komoditas");
    expect(html).toContain("telur");
    // Label muncul SEBELUM jumlah kg di baris meta yang sama.
    expect(html.indexOf("telur")).toBeLessThan(html.indexOf("rec-qty"));
  });

  it("tidak mengarang label saat komoditas tidak ada", () => {
    const html = renderToStaticMarkup(<RecommendationCard decision={BASE as any} />);
    expect(html).not.toContain("rec-komoditas");
  });
});

describe("RecommendationCard — biaya di baris meta", () => {
  // 29 Okt 2026: "SDC" adalah singkatan internal (Safe Delivered Cost). Di
  // kartu ia berderet dengan kg dan waktu, jadi pembaca tidak punya jalan
  // untuk tahu artinya. Dipakai bentuk pendek "biaya aman" — diulang 10x per halaman.
  it("menulis istilah Indonesia, bukan singkatan SDC", () => {
    const html = renderToStaticMarkup(<RecommendationCard decision={BASE as any} />);
    expect(html).toContain("biaya aman Rp16.206.000");
    expect(html).toContain("Rp16.206.000");
    expect(html).not.toContain("SDC");
  });
});

describe("RecommendationCard — narasi", () => {
  it("alasan penolakan dicetak apa adanya", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={{ ...BASE, rejection_reason: "Kuota SPPG Jakarta penuh" } as any} />
    );
    expect(html).toContain("Kuota SPPG Jakarta penuh");
  });

  it("catatan penanda 'unavailable' TIDAK dicetak sebagai paragraf", () => {
    const html = renderToStaticMarkup(<RecommendationCard decision={{ ...BASE, verifier_note: "unavailable" } as any} />);
    expect(html).not.toContain("rec-narrative");
    expect(html).not.toContain("unavailable");
  });

  it("catatan verifier bermakna PUN tidak dicetak (kartu feed ringkas)", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={{ ...BASE, verifier_note: "Konsisten dengan data batch" } as any} />
    );
    expect(html).not.toContain("Konsisten dengan data batch");
    expect(html).not.toContain("rec-narrative");
  });

  it("verdict verifier mentah 'consistent'/'flagged' tidak bocor ke layar", () => {
    for (const note of ["consistent", "flagged"]) {
      const html = renderToStaticMarkup(
        <RecommendationCard decision={{ ...BASE, verifier_note: note } as any} />
      );
      expect(html).not.toContain(`>${note}<`);
    }
  });

  it("tanpa narasi: tidak ada paragraf kosong", () => {
    const html = renderToStaticMarkup(<RecommendationCard decision={{ ...BASE } as any} />);
    expect(html).not.toContain("rec-narrative");
  });

  it("baris pengirim pemasok dan badge kasus tidak lagi dirender", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard
        decision={{
          ...BASE,
          supplier_name: "CV Berkah Telur Bekasi",
          target_location_name: "Jakarta",
          demo_case: "shortage-darurat",
        } as any}
      />
    );
    expect(html).not.toContain("rec-route");
    expect(html).not.toContain("Rencana kirim");
    expect(html).not.toContain("rec-case");
    expect(html).not.toContain("Kasus:");
  });

  it("label kasus komoditas memakai nama Indonesia, bukan slug", () => {
    // Sebelum 30 Okt 2026 lima kasus komoditas jatuh ke fallback slug sehingga
    // kepala halaman mencetak "Kasus: wortel coldchain hold" (huruf kecil,
    // tanda hubung ikut tercetak). Dua kunci telur/ayam baru ada hari itu.
    const harapan: Record<string, string> = {
      "wortel-coldchain-sah": "Kasus: Wortel Rantai Dingin (Bukti Lengkap)",
      "wortel-coldchain-hold": "Kasus: Wortel Rantai Dingin (Bukti Kurang)",
      "beras-ambient": "Kasus: Beras Suhu Ruang",
      "telur-rantai-dingin-sah": "Kasus: Telur Rantai Dingin (Bukti Lengkap)",
      "ayam-rantai-dingin-hold": "Kasus: Ayam Rantai Dingin (Bukti Kurang)",
    };
    for (const [key, label] of Object.entries(harapan)) {
      expect(caseLabelOf({ demo_case: key })).toBe(label);
    }
    // Kunci asing tetap jujur: slug dibaca apa adanya, bukan dikarang.
    expect(caseLabelOf({ demo_case: "kasus-baru" })).toBe("Kasus: kasus baru");
    expect(caseLabelOf({})).toBeNull();
  });

  it("valid tanpa sisa waktu: TIDAK mencetak '0 dtk' yang dikarang", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={{ ...BASE, valid: true, seconds_remaining: null } as any} />
    );
    expect(html).not.toContain("0 dtk");
    expect(html).not.toContain("dtk");
    expect(html).toContain("berlaku");
  });

  it("valid dengan sisa waktu: dicetak dalam menit, bukan detik", () => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={{ ...BASE, valid: true, seconds_remaining: 600 } as any} />
    );
    expect(html).toContain("berlaku 10 menit");
    expect(html).not.toContain("dtk");
  });

  it.each([
    [59, "kurang dari 1 menit"],
    [90, "1 menit"],
    [3600, "1 jam"],
    [5400, "1 jam 30 menit"],
    [90000, "1 hari 1 jam"],
  ])("sisa %i detik ditulis '%s'", (seconds, expected) => {
    const html = renderToStaticMarkup(
      <RecommendationCard decision={{ ...BASE, valid: true, seconds_remaining: seconds } as any} />
    );
    expect(html).toContain(`berlaku ${expected}`);
    expect(html).not.toContain("dtk");
  });
});

// Ajakan "klik" hanya jujur kalau kartunya memang terbungkus tombol (di feed).
// Di halaman Decision & Evidence kartunya dirender polos, jadi pemanggil di
// sana mengirim hint={null} — lihat tests/decision-evidence.test.tsx.
describe("RecommendationCard — ajakan klik", () => {
  it("bawaan (dipakai feed): ajakan tampil, dan tetap disembunyikan dari pembaca layar", () => {
    const html = renderToStaticMarkup(<RecommendationCard decision={{ ...BASE } as any} />);
    // React meng-escape "&" jadi "&amp;" di markup — bandingkan setelah dibalik.
    expect(html.replace(/&amp;/g, "&")).toContain(CARD_HINT);
    expect(html).toContain('aria-hidden="true"');
  });

  it("hint={null}: tidak ada ajakan sama sekali", () => {
    const html = renderToStaticMarkup(<RecommendationCard decision={{ ...BASE } as any} hint={null} />);
    expect(html).not.toContain("rec-hint");
    expect(html).not.toContain("Klik untuk rincian");
  });

  it("hint kosong: juga tidak menghasilkan penanda kosong", () => {
    const html = renderToStaticMarkup(<RecommendationCard decision={{ ...BASE } as any} hint="" />);
    expect(html).not.toContain("rec-hint");
  });
});

// Dua tombol di kartu feed (permintaan pemilik 28 Okt 2026): "Rincian" untuk
// membaca/mengisi keputusan, "Persetujuan" langsung membuka panel persetujuan.
// Ajakan teks hilang. Jejak agen BUKAN tombol kartu — ia tautan tenang di kepala
// popup detail (lihat tests/decision-drawer.test.tsx).
describe("RecommendationCard — dua tombol buka", () => {
  const html = renderToStaticMarkup(
    <RecommendationCard
      decision={{ ...BASE } as any}
      onBuka={() => {}}
    />
  );

  it("mengganti ajakan teks dengan SATU tombol Tinjau", () => {
    expect(html).not.toContain("rec-hint");
    expect(html).not.toContain("Klik untuk rincian");
    expect(html).toContain("rec-act");
    expect(html).toContain(">Tinjau<");
    // Permintaan pemilik 28 Okt 2026: tombol "Rincian" dan "Persetujuan"
    // digabung jadi satu — popup yang dibuka sudah memuat keduanya.
    expect(html).not.toContain(">Rincian<");
    expect(html).not.toContain(">Persetujuan<");
    // Jejak agen tidak lagi ditawarkan sebagai tombol kartu.
    expect(html).not.toContain(">Jejak agen<");
  });

  it("menandai tombol Tinjau sebagai aksi utama", () => {
    expect(html).toContain("rec-act-btn rec-act-btn--utama");
  });

  it("hanya merender satu tombol di area aksi", () => {
    const area = html.slice(html.indexOf("rec-act"));
    expect(area.split("<button").length - 1).toBe(1);
  });

  it("memberi nama aksesibel yang menyebut kartunya", () => {
    expect(html).toContain('aria-label="Tinjau: ');
  });

  it("tidak menyembunyikan tombol dari pembaca layar (bukan hiasan)", () => {
    // Ajakan lama memakai aria-hidden karena hanya dekorasi; tombol tidak boleh.
    const potongan = html.slice(html.indexOf("rec-act"));
    expect(potongan).not.toContain('aria-hidden="true"');
  });

  it("tampilPersetujuan={false}: tetap satu tombol, dibuka di rincian", () => {
    // Peran pemantau dan keputusan yang sudah selesai tidak boleh ditawari
    // tindakan yang pasti ditolak server (dok 02 §7.5) — tetapi tombolnya tetap
    // satu; yang berbeda hanya tampilan awal popup.
    const tanpa = renderToStaticMarkup(
      <RecommendationCard
        decision={{ ...BASE } as any}
        onBuka={() => {}}
        tampilPersetujuan={false}
      />
    );
    expect(tanpa).toContain(">Tinjau<");
    expect(tanpa).not.toContain(">Persetujuan<");
    const area = tanpa.slice(tanpa.indexOf("rec-act"));
    expect(area.split("<button").length - 1).toBe(1);
  });
});
