"""Geser jejak AKSI demo keluar dari jendela KPI 24 jam.

Kenapa ada (permintaan pemilik 23 Okt 2026): saat demo dimulai, kartu KPI
24 jam harus mencerminkan "hari ini belum ada aksi" — bukan angka yang sudah
gemuk sejak detik pertama. Angka aksi baru muncul ketika operator benar-benar
menjalankan alurnya, sehingga panel terasa realtime.

Pembagiannya bukan karangan, melainkan mengikuti penulis data yang ada:

- **Hanya penyemai yang bisa menulisnya** (karena itu TETAP di hari ini):
  Meal Continuity (`menu_plans` + `delivery_events`), Avoidable Food Loss
  (`disposal_events`), Procurement Price Deviation (`price_signals`
  `source='supplier_quote'` + acuan PIHPS).
- **Bisa lahir dari aksi** (karena itu DIGESER ke riwayat): Regional Imbalance
  Resolution (trace DETECT + status `executed`), Safe Delivered Cost (PO mock),
  Decision Time (trace DETECT..ACT + PO committed), Evidence Completeness
  (`decisions.created_at` + `approvals` + `decision_evidence` di jendela).

Yang dilakukan fungsi ini hanya MEMINDAHKAN tanggal baris yang sudah ada:
tidak ada nilai yang dikarang, tidak ada baris yang dihapus, dan status tidak
diubah. `expires_at` sengaja tidak ikut bergeser supaya keputusan yang menunggu
tindakan tetap punya tenggat berjalan.

Semua kolom digeser dengan DELTA yang SAMA, dihitung dari timestamp terbaru di
jendela, sehingga urutan rantai (keputusan → bukti → approval → PO) tidak
berubah dan baris terbaru mendarat `margin_jam` di luar jendela.

Dipanggil oleh dua jalur penyemai demo:
- `app/seed/demo_template.build_into` (tombol "Siapkan data demo"),
- `POST /demo/refresh` (tombol "Segarkan ke hari ini").
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Satu saklar untuk mematikan perilaku ini (mis. demo yang memang ingin KPI
#: 24 jam langsung terisi). Default: mulai dari keadaan "belum ada aksi".
AKTIF = True

#: Lokasi yang ceritanya dipakai saat demo (akun SPPG Head Jakarta). Hanya
#: baris aksi lokasi ini yang digeser; kota lain tetap seperti disemai supaya
#: pandangan global BGN Monitor tidak ikut kosong. `None` = semua lokasi.
LOKASI_DEMO = "Jakarta"

#: Tabel + kolom waktu yang menentukan empat metrik berbasis aksi. Nama tabel
#: dan kolom adalah konstanta modul (bukan input pengguna), jadi aman
#: diinterpolasi ke SQL; nilainya tetap lewat parameter binding.
KOLOM_AKSI: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "decisions",
        ("created_at", "generated_at"),
        "(source_location_id = :loc OR target_location_id = :loc)",
    ),
    (
        "agent_traces",
        ("step_at",),
        "decision_id IN (SELECT id FROM decisions WHERE "
        "source_location_id = :loc OR target_location_id = :loc)",
    ),
    (
        "approvals",
        ("approved_at",),
        "decision_id IN (SELECT id FROM decisions WHERE "
        "source_location_id = :loc OR target_location_id = :loc)",
    ),
    (
        "decision_evidence",
        ("recorded_at",),
        "decision_id IN (SELECT id FROM decisions WHERE "
        "source_location_id = :loc OR target_location_id = :loc)",
    ),
    (
        "sap_mock_purchase_orders",
        ("created_at",),
        "decision_id IN (SELECT id FROM decisions WHERE "
        "source_location_id = :loc OR target_location_id = :loc)",
    ),
)

JENDELA_JAM = 24
#: Baris terbaru diletakkan `JENDELA_JAM + MARGIN_JAM` ke belakang, bukan tepat
#: di batas: permintaan KPI berikutnya bergerak maju beberapa detik, dan baris
#: yang menempel di batas bisa masuk lagi ke jendela.
MARGIN_JAM = 1


async def geser_aksi_ke_riwayat(
    db: AsyncSession,
    now: datetime,
    *,
    nama_lokasi: str | None = LOKASI_DEMO,
    jendela_jam: int = JENDELA_JAM,
    margin_jam: int = MARGIN_JAM,
) -> dict:
    """Geser baris aksi lokasi demo di jendela `(now - jendela_jam, now]`.

    `nama_lokasi=None` menggeser semua lokasi (perilaku lama). Default Jakarta:
    hanya akun yang dipakai mendemokan yang mulai dari "belum ada aksi".

    Mengembalikan laporan `{aktif, digeser, detik_geser, batas}` agar penyemai
    bisa menampilkannya (bukan menyembunyikan bahwa tanggal dipindahkan).
    """
    if not AKTIF:
        return {"aktif": False, "digeser": {}, "keterangan": "saklar AKTIF mati"}

    # Baris yang masih tertahan di unit-of-work TIDAK terlihat oleh UPDATE di
    # bawah (raw SQL). Tanpa flush, keputusan yang baru di-`add` penyemai ikut
    # ter-commit dengan tanggal aslinya dan tetap berada di jendela 24 jam
    # (terukur 23 Okt 2026: 7 keputusan Jakarta lolos tanpa jejak/PO).
    await db.flush()

    # Jam acuan tidak boleh lebih tua daripada kenyataan: penyemai mencatat
    # `now` di awal build, sedangkan build-nya sendiri bisa berjalan puluhan
    # detik. Baris yang lahir sesudah `now` (terukur 23 Okt 2026: 4 kasus skrip
    # Jakarta, created_at 57 detik setelah `now`) akan lolos dari jendela dan
    # tetap tinggal di 24 jam. Karena itu batas atas memakai jam nyata.
    sekarang = max(now, datetime.now(timezone.utc))

    batas = sekarang - timedelta(hours=jendela_jam)
    params: dict = {"batas": batas, "now": sekarang}

    if nama_lokasi is None:
        # Tanpa filter lokasi: semua baris aksi di jendela ikut digeser.
        saringan = {tabel: "TRUE" for tabel, _kolom, _filter in KOLOM_AKSI}
    else:
        loc_id = (
            await db.execute(
                text("SELECT id FROM locations WHERE name = :nama"),
                {"nama": nama_lokasi},
            )
        ).scalar_one_or_none()
        if loc_id is None:
            return {
                "aktif": True,
                "digeser": {},
                "keterangan": f"lokasi '{nama_lokasi}' tidak ditemukan — tidak ada yang digeser",
                "batas": batas.isoformat(),
            }
        params["loc"] = loc_id
        saringan = {tabel: f"({filter_})" for tabel, _kolom, filter_ in KOLOM_AKSI}

    terbaru: datetime | None = None
    for tabel, kolom, _filter in KOLOM_AKSI:
        for nama_kolom in kolom:
            nilai = (
                await db.execute(
                    text(
                        f"SELECT max({nama_kolom}) FROM {tabel} "
                        f"WHERE {nama_kolom} >= :batas AND {nama_kolom} <= :now "
                        f"AND {saringan[tabel]}"
                    ),
                    params,
                )
            ).scalar_one_or_none()
            if nilai is not None and (terbaru is None or nilai > terbaru):
                terbaru = nilai

    if terbaru is None:
        return {
            "aktif": True,
            "digeser": {},
            "keterangan": "tidak ada baris aksi di dalam jendela",
            "batas": batas.isoformat(),
        }

    target = now - timedelta(hours=jendela_jam + margin_jam)
    detik_geser = (target - terbaru).total_seconds()
    if detik_geser >= 0:
        return {
            "aktif": True,
            "digeser": {},
            "keterangan": "seluruh baris aksi sudah di luar jendela",
            "batas": batas.isoformat(),
        }

    digeser: dict[str, int] = {}
    for tabel, kolom, _filter in KOLOM_AKSI:
        for nama_kolom in kolom:
            hasil = await db.execute(
                text(
                    f"UPDATE {tabel} SET {nama_kolom} = "
                    f"{nama_kolom} + make_interval(secs => :detik) "
                    f"WHERE {nama_kolom} >= :batas AND {nama_kolom} <= :now "
                    f"AND {saringan[tabel]}"
                ),
                {**params, "detik": detik_geser},
            )
            jumlah = getattr(hasil, "rowcount", 0) or 0
            if jumlah:
                digeser[f"{tabel}.{nama_kolom}"] = int(jumlah)

    return {
        "aktif": True,
        "lokasi": nama_lokasi,
        "digeser": digeser,
        "detik_geser": round(detik_geser, 1),
        "batas": batas.isoformat(),
    }
