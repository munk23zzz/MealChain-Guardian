"""Router sesi demo — "Siapkan data demo" (migrasi 024, 20 Okt 2026).

Lima endpoint, semuanya tipis: status, mulai, perpanjang, akhiri, dan bangun
ulang template (21 Okt 2026) untuk geladi berulang tanpa menutup sesi. Logika
(validasi durasi, kedaluwarsa malas, pembersihan ber-stempel) ada di
`app/services/demo_session.py` supaya bisa diuji tanpa HTTP.

Kenapa `POST /demo/session/start` juga menyemai: tombol "Siapkan data demo"
memang berarti "isi data lalu jalankan jam". Penyemai yang dipakai adalah yang
sudah ada (`app.api.demo._seed_demo_cases`), bukan salinan kedua — satu jalur
data, satu set tes.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import MUTATING_ROLES, get_current_user, require_roles
from app.api.dependencies import get_db
from app.core.config import settings
from app.models import User
from app.services import decision_time
from app.services import demo_session as sesi

router = APIRouter()


async def butuh_sesi_aktif(db: AsyncSession = Depends(get_db)):
    """Penjaga endpoint MUTASI saat sesi demo diberlakukan.

    Aturan pemilik: data hanya bisa diubah selama sesi berlangsung. Dengan
    `DEMO_SESSION_ENFORCE=false` (bawaan dev/tes) fungsi ini tidak melakukan
    apa pun — 1.200+ tes lama tetap sah.
    """
    if not settings.demo_session_enforce:
        return None
    aktif = await sesi.aktif(db)
    if aktif is None:
        raise HTTPException(
            status_code=409,
            detail="sesi demo belum aktif — tekan \"Siapkan data demo\" lebih dulu",
        )
    return aktif


class MulaiRequest(BaseModel):
    menit: int | None = Field(
        default=None,
        ge=1,
        le=1440,
        description="Durasi sesi dalam menit; kosong = nilai bawaan server.",
    )
    #: Fase 10 MG: dua tombol Demo Control mengirim mode EKSPLISIT. `Literal`
    #: dipakai supaya nilai asing ditolak 422 oleh kontrak request — bukan
    #: diabaikan lalu jatuh ke mode bawaan tanpa ada yang tahu.
    mode: Literal["replay", "realtime"] | None = Field(
        default=None,
        description="Mode dataset: `replay` (jangkar kanon) atau `realtime` (waktu sesi).",
    )
    #: Hanya tombol "Muat Demo …" yang boleh MENGGANTI sesi bermode lain.
    #: Tanpa ini, tombol lama ("Siapkan data demo") yang mengirim
    #: `mode=replay` akan diam-diam menutup sesi realtime yang sedang berjalan.
    replace: bool = Field(
        default=False,
        description="Tutup sesi berjalan dan buka sesi baru dengan mode yang diminta.",
    )


class PerpanjangRequest(BaseModel):
    menit: int = Field(default=30, ge=1, le=240)


@router.get("/demo/session")
async def status_sesi(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Status sesi + hitungan mundur. Aman dipanggil berkali-kali (poling UI).

    Sejak Fase 7 MG payload juga membawa `cases`: jumlah KASUS demo yang
    dimiliki sesi ini, dibaca dari DB (bukan dari ingatan klien). Panel Demo
    Control perlu menyebut "berapa kasus termuat" sesudah halaman di-reload —
    tanpa angka dari server, klien hanya bisa mengarang atau kosong.
    """
    aktif = await sesi.aktif(db)
    payload = sesi.status_payload(aktif)
    payload["cases"] = await jumlah_kasus_sesi(db, aktif) if aktif is not None else None
    return payload


async def jumlah_kasus_sesi(db: AsyncSession, sesi_row) -> int:
    """Jumlah `demo_case` berbeda yang dimiliki satu sesi (bukan jumlah baris).

    Satu kasus bisa punya beberapa baris keputusan (siklus penolakan), jadi
    menghitung baris akan melebih-lebihkan "jumlah kasus" di layar.
    """
    from sqlalchemy import func, select

    from app.models import Decision

    hasil = (
        await db.execute(
            select(func.count(func.distinct(Decision.demo_case))).where(
                Decision.demo_session_id == sesi_row.id,
                Decision.demo_case.is_not(None),
            )
        )
    ).scalar()
    return int(hasil or 0)


async def _semai_riwayat(hari: int) -> dict:
    """Semai fakta harian `hari` hari terakhir (best-effort).

    Kenapa ada: penyemai "hari ini" menaruh (hampir) semua fakta di satu hari,
    sehingga pemilih periode KPI 24 jam / 7 hari / 30 hari memuat himpunan baris
    yang sama dan angkanya identik. Generator ini yang sama dengan tombol deret
    waktu (origin='demo'); stempel massal sesudahnya menandai baris-baris itu
    milik sesi yang sedang dimulai.

    Kegagalan generator TIDAK membatalkan sesi: sesi tetap berguna tanpa riwayat,
    dan alasannya dilaporkan di respons supaya terlihat — bukan disembunyikan.
    """
    if hari <= 0:
        return {"hari": 0, "rows": None, "error": None}

    import asyncio
    from datetime import datetime, timedelta, timezone

    from app.seed.timeseries import EVENT_DEMO_START, generate_timeseries

    sekarang = datetime.now(timezone.utc)
    try:
        # `generate_timeseries` adalah async def yang memakai engine SINKRON di
        # dalamnya. `run_in_threadpool` hanya memanggil fungsi biasa — dengan
        # coroutine ia mengembalikan objek coroutine (AttributeError .get) dan
        # baris tidak pernah ditulis. Jalankan loop sendiri di thread supaya
        # event loop utama tidak berhenti 2-3 detik saat menyemai.
        hasil = await asyncio.to_thread(
            lambda: asyncio.run(
                generate_timeseries(
                    sekarang - timedelta(days=hari),
                    sekarang,
                    interval_hours=24,
                    # Rencana/kiriman/limbah tetap mulai EVENT_DEMO_START:
                    # rencana tanpa kiriman di hari lama akan menjatuhkan
                    # Meal Continuity hanya karena bentuk data, bukan operasi.
                    menu_start=EVENT_DEMO_START,
                )
            )
        )
    except Exception as exc:  # jaringan/OSRM atau DB: laporkan, jangan gagalkan
        return {"hari": hari, "rows": None, "error": f"{type(exc).__name__}: {exc}"}
    return {"hari": hari, "rows": (hasil or {}).get("counts"), "error": None}


@router.post("/demo/session/start", status_code=200)
async def mulai_sesi(
    payload: MulaiRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*MUTATING_ROLES)),
):
    """Siapkan data demo: buat sesi, semai data, aktifkan satu jendela waktu.

    Idempoten terhadap klik ganda: kalau sesi masih berjalan, sesi itu yang
    dikembalikan (`created=false`) — data dan jam tidak di-reset diam-diam.

    Fase 10 MG — dua tombol Demo Control:

    - `mode` diminta eksplisit (`replay`/`realtime`); mode asing 422.
    - `replace=true` = tombol "Muat Demo …": sesi bermode LAIN ditutup lalu
      sesi baru dibangun dengan mode yang diminta.
    - Tanpa `replace`, permintaan bermode lain TIDAK menutup apa pun; balasannya
      membawa `conflict` (mode diminta vs mode berjalan) supaya panel bisa
      mengatakan yang sebenarnya alih-alih mengganti pilihan operator.
    """
    berjalan = await sesi.aktif(db)
    mode_diminta = decision_time.mode_sah(payload.mode) if payload and payload.mode else None
    if berjalan is not None:
        ganti = bool(payload and payload.replace)
        if mode_diminta is None or mode_diminta == berjalan.mode or not ganti:
            hasil = {**sesi.status_payload(berjalan), "created": False}
            if mode_diminta is not None and mode_diminta != berjalan.mode:
                hasil["conflict"] = {
                    "requested_mode": mode_diminta,
                    "active_mode": berjalan.mode,
                }
            return hasil

    durasi = payload.menit if payload else None
    mode_baru = mode_diminta or "replay"
    # Kunci: penyemaian di bawah ini bisa puluhan detik; "Akhiri sesi" harus
    # menunggu, bukan berjalan bersamaan lalu meninggalkan baris sisa.
    async with sesi.kunci_sesi():
        # Sejak 21 Okt 2026 tombol ini membangun TEMPLATE lengkap, bukan hanya
        # `refresh_to_today`: template memuat kasus skrip untuk tiga kota,
        # karantina/uji gagal, penerimaan menunggu, eksklusi pemasok, approval +
        # bukti, dan rantai ledger yang menunjuk entitas nyata. Baris template
        # sengaja TIDAK ber-stempel (= cetakan), sehingga "Akhiri sesi" tidak
        # menghapus apa pun; sesi berikutnya membangun ulang dari nol.
        #
        # Urutan build-dulu-baru-sesi (audit 21 Okt 2026): kalau build gagal,
        # tidak boleh ada sesi aktif yang tertinggal — sebelumnya kegagalan
        # meninggalkan sesi aktif + tabel kosong, dan klik ulang dibalas
        # created=false sehingga sistem tidak pulih tanpa "Akhiri sesi".
        try:
            baru, laporan = await sesi.mulai_dengan_template(
                db, menit=durasi, created_by=user.id, mode=mode_baru
            )
        except Exception as exc:  # noqa: BLE001 — dilaporkan, bukan ditelan
            await db.rollback()
            raise HTTPException(
                status_code=503,
                detail=(
                    "template demo gagal dibangun; TIDAK ada sesi aktif yang dibuka, "
                    "jadi klik ulang akan mencoba lagi. "
                    f"Penyebab: {type(exc).__name__}: {exc}"
                ),
            ) from exc
        disiapkan = {
            "mode": "template",
            "message": (
                "Template demo dibangun: kasus 3 kota, karantina, penerimaan, eksklusi, bukti."
            ),
            "kasus": laporan.get("kasus"),
            "karantina": laporan.get("karantina"),
            "penerimaan": laporan.get("penerimaan"),
            "eksklusi": laporan.get("eksklusi"),
            "bukti": laporan.get("bukti"),
        }
        riwayat = laporan.get("inti", {}).get("seed")
        ditandai = 0
        await db.refresh(baru)
    return {
        **sesi.status_payload(baru),
        "created": True,
        "prepared": disiapkan,
        "riwayat": riwayat,
        "stamped": ditandai,
    }


@router.post("/demo/session/extend", status_code=200)
async def perpanjang_sesi(
    payload: PerpanjangRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*MUTATING_ROLES)),
):
    """Tambah waktu sesi berjalan tanpa mengganti sesi atau menyentuh data."""
    sesi_baru = await sesi.perpanjang(db, menit=(payload.menit if payload else 30))
    if sesi_baru is None:
        raise HTTPException(status_code=409, detail="tidak ada sesi demo yang aktif")
    return sesi.status_payload(sesi_baru)


@router.post("/demo/session/end", status_code=200)
async def akhiri_sesi(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*MUTATING_ROLES)),
):
    """Tutup sesi sekarang juga (tombol Darurat): data sesi dibersihkan."""
    async with sesi.kunci_sesi():
        ditutup = await sesi.akhiri(db)
    if ditutup is None:
        return sesi.status_payload(None)
    return sesi.status_payload(None)


@router.post("/demo/template/rebuild", status_code=200)
async def bangun_ulang_template(
    _sesi: object = Depends(butuh_sesi_aktif),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("sppg_head")),
):
    """Bangun ulang seluruh data demo ke keadaan awal, tanpa menutup sesi.

    Dipakai saat geladi berulang: setelah beberapa aksi dicoba, angka tidak
    kembali ke awal dengan sendirinya (memang begitu desainnya — data tidak
    dihapus saat sesi ditutup). Endpoint ini mem-purge baris operasional lalu
    menyemai template lagi, dan **tidak** menyentuh jendela waktu sesi.

    Hanya kepala SPPG: ini operasi destruktif. Permintaan kedua saat proses
    masih berjalan ditolak 409, bukan diantrikan sampai klien kehabisan waktu.
    """
    from app.services import demo_template_reset as reset

    try:
        hasil = await reset.bangun_ulang(db)
    except reset.SibukError:
        raise HTTPException(
            status_code=409,
            detail="bangun ulang sedang berjalan — tunggu sampai selesai",
        ) from None
    return {"ok": True, **hasil}
