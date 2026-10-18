// Karantina di papan "Keamanan Pangan": badge, tile ringkasan, dan tombol
// keputusan manusia. Dirender statis (tanpa jaringan), sama seperti tes papan lain.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import FoodSafetyBoard from "../components/FoodSafetyBoard";

const NOW = new Date("2026-10-18T06:00:00Z");

const BATCH_DITAHAN = {
  id: "b-tahan",
  location: "Jakarta",
  commodity: "telur",
  quantity_kg: 120,
  safety_status: "needs_verification",
  freshness_score: 0.9,
  usable_until: "2026-10-19T06:00:00Z",
  quarantine_status: "quarantined",
};

const BATCH_BEBAS = {
  ...BATCH_DITAHAN,
  id: "b-bebas",
  commodity: "ayam",
  quarantine_status: "none",
};

const BATCH_GAGAL = {
  ...BATCH_DITAHAN,
  id: "b-gagal",
  commodity: "wortel",
  safety_status: "fail",
  quarantine_status: "failed",
};

function render(
  props: Partial<Parameters<typeof FoodSafetyBoard>[0]> = {},
  batches: unknown[] = [BATCH_DITAHAN, BATCH_BEBAS, BATCH_GAGAL]
) {
  return renderToStaticMarkup(
    <FoodSafetyBoard batches={batches} now={NOW} ownLocation="Jakarta" {...props} />
  );
}

describe("FoodSafetyBoard — karantina", () => {
  it("batch yang ditahan diberi label eksplisit di barisnya", () => {
    const html = render();
    expect(html).toContain("Ditahan");
  });

  it("ringkasan memisahkan batch ditahan dari gagal uji", () => {
    const html = render();
    expect(html).toContain("Ditahan (karantina)");
    expect(html).toContain("120 kg tidak boleh dialokasikan");
  });

  it("peran yang boleh memutuskan melihat tombol Tahan pada batch bebas", () => {
    const html = render({ canMutate: true, onKarantina: async () => {} });
    expect(html).toContain("Tahan");
  });

  it("batch yang sedang ditahan menawarkan Lepas dan Gagal", () => {
    const html = render({ canMutate: true, onKarantina: async () => {} }, [BATCH_DITAHAN]);
    expect(html).toContain("Lepas");
    expect(html).toContain("Gagal");
    expect(html).not.toContain(">Tahan<");
  });

  it("pengawas read-only tidak melihat tombol karantina", () => {
    const html = render({ canMutate: false });
    expect(html).not.toContain(">Tahan<");
    expect(html).not.toContain(">Lepas<");
  });

  it("batch yang sudah gagal tidak ditawari tindakan karantina lagi", () => {
    const html = render({ canMutate: true, onKarantina: async () => {} }, [BATCH_GAGAL]);
    expect(html).not.toContain(">Tahan<");
    expect(html).not.toContain(">Lepas<");
  });
});
