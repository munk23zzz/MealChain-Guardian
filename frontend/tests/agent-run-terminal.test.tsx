// Terminal log "Proses pengambilan data" (blok 3 Demo Control; sejak 29 Okt 2026
// blok itu TIDAK lagi memuat sembilan kartu agen).
//
// Ditulis MERAH lebih dulu: komponen `AgentRunTerminal` belum ada. Yang diuji
// adalah keadaan yang dibaca operator, bukan kelas CSS: label siaran, jumlah
// baris, baris tunggu, dan janji bahwa log kosong tidak berpura-pura berisi.

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import AgentRunTerminal, { jamLangsung } from "../components/AgentRunTerminal";
import type { LangkahAgent } from "../lib/agent-stream";

const CONTOH: LangkahAgent[] = [
  { step: "DETECT", tool: "supply.gap", ringkas: "gap_kg=780 · supplier_total=14", at: "2026-10-29T03:21:04Z" },
  { step: "VERIFY", tool: null, ringkas: "", at: "2026-10-29T03:21:09Z" },
];

describe("jamLangsung", () => {
  it("mencetak jam WIB dari waktu ISO server", () => {
    expect(jamLangsung("2026-10-29T03:21:04Z")).toBe("10.21.04");
  });

  it("mengembalikan tanda kosong bila waktu tidak sah", () => {
    expect(jamLangsung("")).toBe("--.--.--");
    expect(jamLangsung("bukan tanggal")).toBe("--.--.--");
  });
});

describe("AgentRunTerminal", () => {
  it("menampilkan baris langkah apa adanya: jam, nama, dan ringkasan", () => {
    const html = renderToStaticMarkup(<AgentRunTerminal langkah={CONTOH} aktif={false} />);
    expect(html).toContain("10.21.04");
    expect(html).toContain("DETECT");
    expect(html).toContain("gap_kg=780 · supplier_total=14");
    expect(html).toContain("VERIFY");
  });

  it("menyebut jumlah baris di kepala terminal", () => {
    const html = renderToStaticMarkup(<AgentRunTerminal langkah={CONTOH} aktif={false} />);
    expect(html).toContain("2 langkah");
  });

  it("menandai siaran hidup hanya saat aktif", () => {
    const hidup = renderToStaticMarkup(<AgentRunTerminal langkah={CONTOH} aktif />);
    const selesai = renderToStaticMarkup(<AgentRunTerminal langkah={CONTOH} aktif={false} />);
    expect(hidup).toContain("live");
    expect(selesai).toContain("selesai");
    expect(selesai).not.toContain(">live<");
  });

  it("menulis baris tunggu saat putaran berjalan tanpa langkah", () => {
    const html = renderToStaticMarkup(<AgentRunTerminal langkah={[]} aktif />);
    expect(html).toContain("menunggu langkah pertama");
    expect(html).toContain("0 langkah");
  });

  it("tidak mengarang baris saat diam dan kosong", () => {
    const html = renderToStaticMarkup(<AgentRunTerminal langkah={[]} aktif={false} />);
    expect(html).not.toContain("menunggu langkah pertama");
    expect(html).toContain("siap");
  });

  it("memakai aria-live dan role log supaya pembaca layar mengikuti baris baru", () => {
    const html = renderToStaticMarkup(<AgentRunTerminal langkah={CONTOH} aktif />);
    expect(html).toContain('role="log"');
    expect(html).toContain('aria-live="polite"');
    expect(html).toContain('aria-label="Log proses pengambilan data"');
  });

  it("menampilkan galat aliran sebagai baris tersendiri, bukan menelan pesannya", () => {
    const html = renderToStaticMarkup(
      <AgentRunTerminal langkah={CONTOH} aktif={false} galat="Kanal terputus" />,
    );
    expect(html).toContain("Kanal terputus");
    expect(html).toContain("galat");
  });

  it("tidak mencetak pemisah menggantung saat ringkasan kosong", () => {
    const html = renderToStaticMarkup(
      <AgentRunTerminal langkah={[CONTOH[1]]} aktif={false} />,
    );
    expect(html).not.toContain(" · </span>");
  });
});
