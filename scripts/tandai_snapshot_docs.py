#!/usr/bin/env python3
"""Beri label "snapshot" pada laporan bertanggal (idempoten).

Laporan audit/QA/verifikasi adalah potret keadaan pada tanggal tertentu. Menimpa
angkanya akan menghapus bukti, jadi yang ditambahkan hanya satu blok kutipan di
bawah judul:

    > **Snapshot 22 Oktober 2026** — angka di dokumen ini hasil pengukuran saat
    > itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Aturan:
- Hanya menambah teks; isi dokumen tidak diubah.
- Idempoten: berkas yang sudah punya penanda dilewati.
- Tanggal diambil dari nama berkas (YYYY-MM-DD), lalu baris "Tanggal:", lalu mtime.

Jalankan:
  python scripts/tandai_snapshot_docs.py            # lihat rencana (dry-run)
  python scripts/tandai_snapshot_docs.py --apply    # tulis perubahan
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PENANDA = "angka di dokumen ini hasil pengukuran saat itu"

# Laporan yang memang potret tanggal tertentu.
SASARAN = [
    "docs/verification",
    "docs/qa",
    "_qa",
]
BERKAS_TUNGGAL = [
    "AUDIT.md",
    "INDEPENDENT_PROJECT_REVIEW.md",
    "FINAL_VERIFICATION_REPORT.md",
    "PROJECT_AUDIT_REPORT.md",
    "REPAIR_LOG.md",
    "REPAIR_PLAN.md",
]
LEWATI_NAMA = {"README.md", "_INDEX.md"}

BULAN = {1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
         7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November",
         12: "Desember"}


def tanggal_manusia(d: tuple[int, int, int]) -> str:
    return f"{d[2]} {BULAN[d[1]]} {d[0]}"


def cari_tanggal(path: Path, teks: str) -> str:
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", path.name)
    if m:
        y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return tanggal_manusia((y, mo, dd))
    m = re.search(r"(?:^|\n)\s*(?:Tanggal|Date)\s*:?\s*.*?(20\d{2})", teks)
    nama_bulan = re.search(
        r"(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|"
        r"Oktober|November|Desember)\s+(20\d{2})", teks[:800], re.I)
    if m and nama_bulan:
        return f"{int(nama_bulan.group(1))} {nama_bulan.group(2).title()} {nama_bulan.group(3)}"
    if m:
        return f"tahun {m.group(1)} (tanggal tidak tertulis)"
    return tanggal_manusia(tuple(time.localtime(path.stat().st_mtime)[:3])) + " (dari waktu berkas)"


def titik_sisip(teks: str) -> int:
    """Baris setelah judul pertama, atau setelah frontmatter YAML."""
    baris = teks.splitlines(keepends=True)
    mulai = 0
    if baris and baris[0].strip() == "---":
        for i in range(1, len(baris)):
            if baris[i].strip() == "---":
                mulai = i + 1
                break
    for i in range(mulai, len(baris)):
        if baris[i].startswith("# "):
            return sum(len(b) for b in baris[: i + 1])
    return 0


def main() -> int:
    apply = "--apply" in sys.argv
    berkas: list[Path] = []
    for d in SASARAN:
        p = ROOT / d
        if p.exists():
            berkas += [x for x in p.rglob("*.md") if x.name not in LEWATI_NAMA]
    for f in BERKAS_TUNGGAL:
        p = ROOT / f
        if p.exists():
            berkas.append(p)

    diubah, dilewati, gagal = [], [], []
    for p in sorted(set(berkas)):
        teks = p.read_text(encoding="utf-8", errors="ignore")
        if PENANDA in teks:
            dilewati.append(p)
            continue
        pos = titik_sisip(teks)
        if pos == 0:
            gagal.append(p)
            continue
        blok = (f"\n> **Snapshot {cari_tanggal(p, teks)}** — angka di dokumen ini hasil pengukuran "
                f"saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.\n")
        baru = teks[:pos] + blok + teks[pos:]
        diubah.append(p)
        if apply:
            p.write_text(baru, encoding="utf-8")

    mode = "DITERAPKAN" if apply else "DRY-RUN"
    print(f"{mode}: {len(diubah)} berkas ditandai, {len(dilewati)} sudah bertanda, "
          f"{len(gagal)} tanpa judul")
    for p in diubah[:80]:
        print("  +", p.relative_to(ROOT).as_posix())
    if gagal:
        print("tanpa judul (dilewati):")
        for p in gagal:
            print("  -", p.relative_to(ROOT).as_posix())
    if not apply:
        print("\nJalankan dengan --apply untuk menulis.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
