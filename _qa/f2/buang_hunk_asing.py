"""Buang hunk milik fase lain dari commit Fase 2 yang sudah jadi (amandemen).

Kenapa ada: `git add <berkas>` menelan SELURUH berkas, jadi kerja fase lain yang
kebetulan hidup di berkas yang sama ikut masuk commit. Skrip ini menyusun patch
yang HANYA berisi hunk asing (diambil apa adanya dari `git show HEAD -- berkas`)
lalu menerapkannya TERBALIK ke index (`git apply --cached -R`), sehingga blob
yang akan di-commit kembali ke isi Fase 2 saja. Working tree tidak disentuh —
kerja fase lain tetap utuh di sana.

Pakai:  python _qa/f2/buang_hunk_asing.py            (uji, cetak rencana)
        python _qa/f2/buang_hunk_asing.py --apply    (terapkan ke index)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]

#: berkas -> kepala hunk (awalan `@@ -N,...`) yang harus DIBUANG dari commit.
#: Dipilih dari `git show HEAD -- <berkas>`; setiap kepala hunk unik per berkas.
HUNK_ASING: dict[str, list[str]] = {
    # Fase 11: impor os, impor catat_learn, helper _memory_write_aktif,
    # blok tulis Memory sesudah commit, dan status "memory" di jejak.
    "backend/app/services/event1_orchestrator.py": [
        "@@ -12,6 +12,7 @@",
        "@@ -28,10 +29,27 @@",
        "@@ -373,6 +397,43 @@",
        "@@ -401,6 +462,8 @@",
    ],
    # Fase 10: fungsi `muatMode` dan dua tombol "Muat Demo …" di panel.
    "frontend/components/DemoControlPanel.tsx": [
        "@@ -449,6 +456,54 @@",
        "@@ -579,6 +667,28 @@",
    ],
}


def _diff(berkas: str) -> list[str]:
    hasil = subprocess.run(
        # `git show` ikut mencetak header commit (Author/Date/pesan) sebelum diff,
        # sehingga baris itu terbaca sebagai "header berkas" dan rusak jadi
        # "patch with only garbage". `git diff HEAD^ HEAD` hanya mencetak diff.
        ["git", "diff", "HEAD^", "HEAD", "--", berkas],
        cwd=AKAR,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    if hasil.returncode != 0:
        raise SystemExit(f"git show gagal untuk {berkas}: {hasil.stderr[:200]}")
    return hasil.stdout.splitlines()


def _pilih(berkas: str, kepala: list[str]) -> tuple[list[str], list[str]]:
    """Kembalikan (header berkas, baris hunk terpilih) dari diff `berkas`."""
    baris = _diff(berkas)
    header: list[str] = []
    terpilih: list[str] = []
    aktif = False
    ketemu: set[str] = set()
    sudah_hunk = False
    for isi in baris:
        if isi.startswith("diff --git"):
            aktif = False
            sudah_hunk = False
            header = [isi]
            continue
        if not isi.startswith("@@"):
            if aktif:
                terpilih.append(isi)
            elif header and not sudah_hunk:
                # Header berkas (index/---/+++) hanya ada SEBELUM hunk pertama.
                # Setelah itu baris non-hunk adalah badan hunk yang tidak
                # dipilih; menyalinnya ke header menghasilkan
                # "patch with only garbage".
                header.append(isi)
            continue
        sudah_hunk = True
        cocok = next((k for k in kepala if isi.startswith(k)), None)
        aktif = cocok is not None
        if aktif:
            ketemu.add(cocok)
            terpilih.append(isi)
    hilang = [k for k in kepala if k not in ketemu]
    if hilang:
        raise SystemExit(f"{berkas}: hunk tidak ditemukan -> {hilang}")
    return header, terpilih


def main(apply: bool) -> int:
    for berkas, kepala in HUNK_ASING.items():
        header, terpilih = _pilih(berkas, kepala)
        # Header diff asli memuat `index <lama>..<baru>`; saat menambah berkas
        # baru `git apply -R` butuh baris itu, jadi header diambil utuh.
        tambalan = "\n".join(header + terpilih) + "\n"
        slug = berkas.replace("/", "_")
        jalur = AKAR / "_qa" / "f2" / f"buang-{slug}.patch"
        jalur.write_bytes(tambalan.encode("utf-8"))
        print(f"{berkas}: {len(kepala)} hunk asing, patch {len(tambalan)} byte")
        if not apply:
            continue
        hasil = subprocess.run(
            ["git", "apply", "--cached", "-R", "--recount", str(jalur)],
            cwd=AKAR,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
        if hasil.returncode != 0:
            print(f"   GAGAL: {hasil.stderr.strip()[:300]}")
            return 1
        print("   dibuang dari index")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv))
