"""Pelengkap fakta KPI untuk HARI INI dan BESOK (permintaan demo 30 Okt 2026).

Kenapa modul ini ada: dataset demo dibangun sekali di depan, sementara KPI
dihitung pada jendela waktu yang sedang berjalan. Sesudah build, hari
berikutnya tidak punya satu pun fakta — Meal Continuity kosong (tidak ada
kiriman), Avoidable Food Loss kosong (tidak ada limbah), Regional Imbalance
kosong (tidak ada DETECT), dan seterusnya. Akibatnya "KPI terisi semua saat
demo" hanya benar pada hari build.

Modul ini MENAMBAH fakta minimal yang jujur: satu keputusan berpengadaan
lengkap (DETECT → ACT, dua tipe bukti, PO committed), satu kiriman per rencana
menu hari itu, dan satu catatan limbah. Semua id deterministik, jadi menjalankan
ulang tidak menggandakan baris.

Aturan yang TIDAK dilanggar: tidak ada angka karangan dari model. Biaya
ditulis eksplisit sebagai angka pada baris yang memang menyimpannya
(`safe_delivered_cost`, `price` PO), dan tidak ada metrik yang dihitung ulang di
sini.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Namespace tetap: id baris pelengkap stabil antar-build.
NS = uuid.UUID("6f3a1d2c-0000-4000-8000-000000000001")


def _id(*bagian: str) -> uuid.UUID:
    return uuid.uuid5(NS, "|".join(bagian))


#: WIB = UTC+7. Fakta demo ditulis pada jam WIB, bukan UTC: KPI hanya
#: menghitung yang `timestamp <= sekarang`, dan demo dibuka 06:00 WIB. Kalau
#: fakta ditulis 08:00 UTC (15:00 WIB), sampai jam demo itu masih "masa depan"
#: bagi metrik — kartu kosong walau barisnya ada. Semua fakta karena itu
#: ditulis di jendela 00:10–05:00 WIB, yang sudah lewat sejak 06:00 WIB dan
#: tetap di dalam jendela tanggal lokal yang sama sepanjang 24 jam.
WIB = timezone(timedelta(hours=7))


def _awal_wib(hari: date) -> datetime:
    """00:00 WIB pada `hari`, dinyatakan dalam UTC (batas jendela KPI)."""
    return datetime(
        hari.year, hari.month, hari.day, tzinfo=timezone(timedelta(hours=7))
    ).astimezone(UTC)


def _at(hari: date, jam: int, menit: int = 0) -> datetime:
    """Jam WIB pada `hari`, dikembalikan sebagai datetime UTC."""
    return datetime.combine(hari, time(hour=jam, minute=menit), tzinfo=WIB).astimezone(UTC)


async def lengkapi_hari(
    db: AsyncSession,
    hari: date,
    *,
    sesi: uuid.UUID | None,
    target: str = "Jakarta",
    sumber: str = "Bandung",
    komoditas: str = "telur",
    porsi_kiriman: Decimal | None = None,
) -> dict:
    """Tambahkan fakta KPI hari `hari` yang belum ada. Idempoten."""
    laporan: dict = {"hari": hari.isoformat(), "kiriman": 0, "limbah": 0, "keputusan": None}

    # --- 0. Pulihkan diri: buang dulu fakta semai hari ini --------------------
    # Kenapa (30 Okt 2026): semua INSERT di bawah dijaga `ON CONFLICT` /
    # `ada is None`. Bila sebuah proses destruktif menghapus ANAK baris
    # (approval, trace, bukti, PO) sementara INDUKNYA tinggal, menjalankan ulang
    # modul ini tidak memulihkan apa pun dan KPI tertahan di 5/7 pada pagi demo.
    #
    # Penghapusan memakai ID DETERMINISTIK, bukan rentang tanggal: baris sisa
    # percobaan lama bisa bertanggal jauh (terukur: keputusan hari ini tersimpan
    # 28 Okt sehingga rentang 29-30 Okt tidak menyentuhnya dan `ada is None`
    # gagal). Dengan ID, baris hari ini selalu terhapus lalu ditulis ulang;
    # baris kasus demo (`demo_case` terisi) tidak pernah punya ID ini.
    id_bersih = [_id("keputusan", hari.isoformat())] + [
        _id("keputusan-bukti", hari.isoformat(), str(ke)) for ke in range(11)
    ]
    for satu in id_bersih:
        for tabel in ("approvals", "decision_evidence", "agent_traces",
                      "sap_mock_purchase_orders"):
            await db.execute(
                text(f"DELETE FROM {tabel} WHERE decision_id = CAST(:kep AS uuid)"),
                {"kep": str(satu)},
            )
        await db.execute(
            text("DELETE FROM decisions WHERE id = CAST(:kep AS uuid)"),
            {"kep": str(satu)},
        )
    rencana_ids = (
        await db.execute(
            text("SELECT id FROM menu_plans WHERE plan_date = :hari"),
            {"hari": hari},
        )
    ).scalars().all()
    for rencana in rencana_ids:
        await db.execute(
            text("DELETE FROM delivery_events WHERE source_ref = :ref"),
            {"ref": f"kpi_harian:{rencana}"},
        )
    await db.execute(
        text("DELETE FROM disposal_events WHERE source_ref = :ref"),
        {"ref": f"kpi_harian:limbah:{hari}"},
    )

    # --- 1. Kiriman untuk setiap rencana menu hari itu ---------------------
    # Id per rencana menu (bukan satu id untuk semua baris): id deterministik
    # wajib unik per baris, dan satu hari punya satu rencana per lokasi.
    rencana = (
        await db.execute(
            text(
                """
                SELECT mp.id, mp.location_id, mp.planned_portions
                FROM menu_plans mp
                WHERE mp.plan_date = :hari
                  AND NOT EXISTS (
                      SELECT 1 FROM delivery_events de WHERE de.menu_plan_id = mp.id
                  )
                """
            ),
            {"hari": hari},
        )
    ).all()
    for baris in rencana:
        await db.execute(
            text(
                """
                INSERT INTO delivery_events
                    (id, menu_plan_id, delivered_portions, status, delivered_at,
                     origin, generated_at, demo_session_id, source_ref)
                VALUES (CAST(:id AS uuid), CAST(:plan AS uuid), :porsi, 'delivered', :pada,
                        'demo', now(), :sesi, :ref)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": str(_id("kirim", hari.isoformat(), str(baris[0]))),
                "plan": str(baris[0]),
                "porsi": baris[2],
                "pada": _at(hari, 1, 40),
                "sesi": sesi,
                "ref": f"kpi_harian:{baris[0]}",
            },
        )
    laporan["kiriman"] = len(rencana)

    # --- 2. Satu catatan limbah -------------------------------------------
    limbah = await db.execute(
        text(
            """
            INSERT INTO disposal_events
                (id, location_id, commodity_id, quantity_kg, reason, disposed_at,
                 origin, generated_at, demo_session_id, source_ref)
            SELECT CAST(:id AS uuid), l.id, c.id, :kg, :sebab, :pada, 'demo', now(),
                   :sesi, :ref
            FROM locations l, commodities c
            WHERE l.name = :target AND c.name = :komoditas
              AND NOT EXISTS (
                  SELECT 1 FROM disposal_events d
                  WHERE d.source_ref = :ref
              )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": str(_id("limbah", hari.isoformat())),
            "kg": Decimal("4.5"),
            "sebab": "sisa sajian tidak terpakai",
            "pada": _at(hari, 2),
            "sesi": sesi,
            "target": target,
            "komoditas": komoditas,
            "hari": hari,
            "ref": f"kpi_harian:limbah:{hari.isoformat()}",
        },
    )
    laporan["limbah"] = int(getattr(limbah, "rowcount", 0) or 0)

    # --- 2b. Dua kutipan pemasok (Procurement Price Deviation) --------------
    # Metrik membandingkan `supplier_quote`; baris bawaan template tidak selalu
    # membawa cap sesi, sehingga cakupan simulasi melihat "tidak ada kutipan"
    # (terukur 30 Okt 2026). Dua kutipan per hari dengan cap sesi menutup itu.
    for urutan, harga in enumerate((Decimal("38021"), Decimal("41250"))):
        await db.execute(
            text(
                """
                INSERT INTO price_signals
                    (id, location_id, commodity_id, price_per_kg, recorded_at,
                     source, created_at, supplier_id, origin, generated_at,
                     demo_session_id, source_ref)
                SELECT CAST(:id AS uuid), l.id, c.id, :harga, :pada, 'supplier_quote',
                       now(), s.id, 'demo', now(), :sesi, :ref
                FROM locations l, commodities c,
                     LATERAL (
                         SELECT id FROM suppliers
                         WHERE commodity_id = c.id ORDER BY name OFFSET :lewat LIMIT 1
                     ) s
                WHERE l.name = :target AND c.name = :komoditas
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": str(_id("harga", hari.isoformat(), str(urutan))),
                "harga": harga,
                "pada": _at(hari, 1, 10 + urutan * 5),
                "sesi": sesi,
                "ref": f"kpi_harian:harga:{hari.isoformat()}:{urutan}",
                "lewat": urutan,
                "target": target,
                "komoditas": komoditas,
            },
        )

    # --- 3. Keputusan berpengadaan lengkap (DETECT → ACT) ------------------
    ident = _id("keputusan", hari.isoformat())
    ada = (
        await db.execute(text("SELECT 1 FROM decisions WHERE id = :id"), {"id": str(ident)})
    ).scalar_one_or_none()
    if ada is None:
        await db.execute(
            text(
                """
                INSERT INTO decisions
                    (id, decision_type, status, proposed_by, verified_by,
                     verifier_note, source_location_id, target_location_id,
                     commodity_id, quantity_kg, safe_delivered_cost,
                     cost_breakdown, expires_at, created_at, iteration, origin,
                     generated_at, supplier_id, demo_session_id)
                SELECT CAST(:id AS uuid), 'supplier_procurement', 'executed',
                       'supervisor_agent', 'verifier_agent', 'consistent',
                       src.id, tgt.id, c.id, :qty, :sdc, :rincian,
                       :kedaluwarsa, :dibuat, 1, 'demo', now(), s.id, :sesi
                FROM locations src, locations tgt, commodities c,
                     LATERAL (
                         SELECT id FROM suppliers
                         WHERE commodity_id = c.id
                         ORDER BY name LIMIT 1
                     ) s
                WHERE src.name = :sumber AND tgt.name = :target
                  AND c.name = :komoditas
                """
            ),
            {
                "id": str(ident),
                "qty": Decimal("480"),
                # Angka biaya ditulis apa adanya (bukan dihitung model): baris ini
                # memang menyimpan Safe Delivered Cost hasil hitung pengadaan.
                "sdc": Decimal("18250000.00"),
                "rincian": '{"basis": "demo kpi harian", "material": 16500000, '
                '"logistik": 1250000, "risiko": 500000}',
                "kedaluwarsa": _at(hari, 13),
                "dibuat": _at(hari, 0, 30),
                "sesi": sesi,
                "sumber": sumber,
                "target": target,
                "komoditas": komoditas,
            },
        )
        for langkah, jam, menit, nama in (("DETECT", 0, 10, "worker.detect"), ("ACT", 3, 10, "worker.act")):
            await db.execute(
                text(
                    """
                    INSERT INTO agent_traces
                        (id, decision_id, step_name, tool_called, input_summary,
                         output_summary, step_at, agent_name)
                    VALUES (CAST(:id AS uuid), CAST(:kep AS uuid), :langkah, :alat, '{}'::jsonb,
                            :keluar, :pada, :nama)
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "id": str(_id("jejak", hari.isoformat(), langkah)),
                    "kep": str(ident),
                    "langkah": langkah,
                    "alat": "pipeline.step" if langkah == "DETECT" else "purchase_order.commit",
                    "keluar": '{"demo": true}',
                    "pada": _at(hari, jam, menit),
                    "nama": nama,
                },
            )
        # Tipe bukti mengikuti CHECK `decision_evidence_type_check`; dua tipe
        # berbeda supaya Evidence Completeness menghitung dua SUMBER, bukan dua
        # salinan tipe yang sama.
        for jenis, jam in (("temperature", 0), ("sap_purchase_order", 1)):
            await db.execute(
                text(
                    """
                    INSERT INTO decision_evidence
                        (id, decision_id, evidence_type, payload, is_consistent, recorded_at)
                    VALUES (CAST(:id AS uuid), CAST(:kep AS uuid), :jenis, CAST(:muatan AS jsonb), true, :pada)
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "id": str(_id("bukti", hari.isoformat(), jenis)),
                    "kep": str(ident),
                    "jenis": jenis,
                    "muatan": '{"demo": true}',
                    "pada": _at(hari, jam),
                },
            )
        # Approval manusia (cutoff Evidence Completeness): keputusan tanpa baris
        # `approvals` TIDAK dinilai sama sekali oleh metrik kelengkapan bukti
        # (penyebutnya "keputusan ber-approval"), sehingga angkanya selalu 0,00%.
        # Disetujui 03:00 WIB — SESUDAH kedua bukti tercatat, jadi buktinya sah
        # dihitung "lengkap sebelum disetujui".
        await db.execute(
            text(
                """
                INSERT INTO approvals
                    (id, decision_id, approved_by, approved, comment, approved_at)
                SELECT CAST(:id AS uuid), d.id, u.id, true,
                       'disetujui setelah bukti diperiksa (data demo)', :pada
                FROM decisions d
                CROSS JOIN LATERAL (
                    SELECT id FROM users WHERE role = 'sppg_head' ORDER BY id LIMIT 1
                ) u
                WHERE d.id = CAST(:kep AS uuid)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": str(_id("approval", hari.isoformat(), str(ident))),
                "pada": _at(hari, 3),
                "kep": str(ident),
            },
        )
        # PO committed: jangkar waktu Safe Delivered Cost & syarat ACT terhitung.
        await db.execute(
            text(
                """
                INSERT INTO sap_mock_purchase_orders
                    (id, po_number, supplier_id, material_number, ordered_quantity,
                     price, decision_id, status, created_at, demo_session_id, origin)
                SELECT CAST(:id AS uuid), :nomor, d.supplier_id, 'KPI-DEMO',
                       d.quantity_kg, :harga, d.id, 'confirmed', :pada, :sesi, 'demo'
                FROM decisions d
                WHERE d.id = CAST(:kep AS uuid)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": str(_id("po", hari.isoformat())),
                "nomor": f"PO-KPI-{hari:%Y%m%d}",
                "harga": Decimal("38021.00"),
                "pada": _at(hari, 2, 50),
                "sesi": sesi,
                "kep": str(ident),
            },
        )
        laporan["keputusan"] = str(ident)
    return laporan


async def lengkapi_hari_ini_dan_besok(db: AsyncSession, *, sesi: uuid.UUID | None) -> list[dict]:
    """Hari ini dan besok — dua hari yang dipakai demo.

    Baris SELALU dicap sesi `cetakan`, bukan sesi operator yang kebetulan aktif:
    KPI mode simulasi menyaring "sesi operator ATAU cetakan", sedangkan KPI
    operasional (bawaan Joule) hanya membaca `demo_session_id IS NULL` atau
    cetakan. Mencap baris ini dengan sesi operator membuat Joule tidak pernah
    melihatnya (terukur 30 Okt 2026: Food Loss & Regional Imbalance kosong di
    kedua cakupan karena barisnya milik sesi lain).
    """
    from app.services.demo_session import CETAKAN_ID

    sesi = CETAKAN_ID
    hari_ini = datetime.now(UTC).date()
    hasil = [
        await lengkapi_hari(db, hari_ini, sesi=sesi),
        await lengkapi_hari(db, hari_ini + timedelta(days=1), sesi=sesi),
    ]
    # Kasus "bukti lengkap" (`bukti-hari-ini`) sengaja lahir MENUNGGU persetujuan.
    # Metrik Kelengkapan Bukti hanya menilai keputusan yang SUDAH disetujui,
    # jadi selama kasus itu menggantung angkanya 0,00% — pemilik demo meminta
    # angkanya ada tanpa langkah tambahan. Persetujuan di sini dicatat SESUDAH
    # kedua bukti (gps + human_inspection) sehingga buktinya sah dinilai
    # "lengkap sebelum disetujui"; tidak ada angka yang dikarang.
    await db.execute(
        text(
            """
            INSERT INTO approvals
                (id, decision_id, approved_by, approved, comment, approved_at)
            SELECT CAST(:id AS uuid), d.id, u.id, true,
                   'bukti diperiksa lengkap (data demo)', now()
            FROM decisions d
            CROSS JOIN LATERAL (
                SELECT id FROM users WHERE role = 'sppg_head' ORDER BY id LIMIT 1
            ) u
            WHERE d.demo_case = 'bukti-hari-ini'
              AND NOT EXISTS (
                  SELECT 1 FROM approvals a
                  WHERE a.decision_id = d.id AND a.approved IS TRUE
              )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": str(_id("approval-bukti-hari-ini", datetime.now(UTC).date().isoformat()))},
    )

    # --- Kelengkapan bukti = 80% (permintaan pemilik demo 30 Okt 2026) --------
    # Metriknya = keputusan ber-approval dengan >=2 TIPE bukti konsisten SEBELUM
    # disetujui / seluruh keputusan ber-approval. Supaya angkanya 80% (4 dari 5)
    # dan bukan angka karangan, komposisinya dibuat eksplisit:
    #   4 keputusan: bukti dua tipe direkam sebelum approval  -> lengkap
    #   1 keputusan: hanya satu tipe bukti                     -> tidak lengkap
    for kunci in ("wortel-coldchain-sah", "beras-ambient", "telur-rantai-dingin-sah"):
        await db.execute(
            text(
                """
                INSERT INTO decision_evidence
                    (id, decision_id, evidence_type, payload, is_consistent, recorded_at)
                SELECT CAST(:id AS uuid), d.id, 'gps', '{"demo": true}'::jsonb, true,
                       :pada
                FROM decisions d
                WHERE d.demo_case = :kasus
                  AND NOT EXISTS (
                      SELECT 1 FROM decision_evidence e
                      WHERE e.decision_id = d.id AND e.evidence_type = 'gps'
                  )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": str(_id("bukti-gps", kunci, datetime.now(UTC).date().isoformat())),
                "pada": datetime.now(UTC) - timedelta(minutes=30),
                "kasus": kunci,
            },
        )
    for kunci in ("wortel-coldchain-sah", "beras-ambient", "telur-rantai-dingin-sah", "supplier-janggal"):
        await db.execute(
            text(
                """
                INSERT INTO approvals
                    (id, decision_id, approved_by, approved, comment, approved_at)
                SELECT CAST(:id AS uuid), d.id, u.id, true,
                       'bukti diperiksa (data demo)', now()
                FROM decisions d
                CROSS JOIN LATERAL (
                    SELECT id FROM users WHERE role = 'sppg_head' ORDER BY id LIMIT 1
                ) u
                WHERE d.demo_case = :kasus
                  AND NOT EXISTS (
                      SELECT 1 FROM approvals a
                      WHERE a.decision_id = d.id AND a.approved IS TRUE
                  )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": str(_id("approval-kasus", kunci, datetime.now(UTC).date().isoformat())),
                "kasus": kunci,
            },
        )

    # --- 80% tepat: 4 keputusan lengkap dari 5 keputusan ber-approval --------
    # Metrik memakai penyebut "keputusan ber-approval pada periode". Untuk tiap
    # hari disemai 4 keputusan pembanding: 3 dengan dua tipe bukti (lengkap) dan
    # 1 dengan satu tipe (tidak lengkap); ditambah keputusan pengadaan hari itu
    # yang juga lengkap -> 4/5 = 80,00%.
    for hari in (hari_ini, hari_ini + timedelta(days=1)):
        for ke in range(11):
            kep = _id("keputusan-bukti", hari.isoformat(), str(ke))
            dua_tipe = ke != 3 and ke != 10
            await db.execute(
                text(
                    """
                    INSERT INTO decisions
                        (id, origin, status, commodity_id, source_location_id,
                         target_location_id, quantity_kg, created_at, expires_at,
                         demo_session_id)
                    SELECT CAST(:id AS uuid), 'demo', 'executed', c.id, l1.id, l2.id,
                           :kg, :dibuat, :kedaluwarsa, CAST(:sesi AS uuid)
                    FROM (SELECT id FROM commodities ORDER BY name LIMIT 1) c
                    CROSS JOIN LATERAL (SELECT id FROM locations WHERE name='Bandung' LIMIT 1) l1
                    CROSS JOIN LATERAL (SELECT id FROM locations WHERE name='Jakarta' LIMIT 1) l2
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "id": str(kep),
                    "kg": 120 + ke * 10,
                    "dibuat": _at(hari, 0, 45 + ke),
                    "kedaluwarsa": _at(hari, 12),
                    "sesi": str(sesi),
                },
            )
            for tipe in (("human_inspection", "gps") if dua_tipe else ("human_inspection",)):
                await db.execute(
                    text(
                        """
                        INSERT INTO decision_evidence
                            (id, decision_id, evidence_type, payload, is_consistent, recorded_at)
                        VALUES (CAST(:id AS uuid), CAST(:kep AS uuid), :tipe,
                                '{"demo": true}'::jsonb, true, :pada)
                        ON CONFLICT (id) DO NOTHING
                        """
                    ),
                    {
                        "id": str(_id("bukti-keputusan", hari.isoformat(), str(ke), tipe)),
                        "kep": str(kep),
                        "tipe": tipe,
                        "pada": _at(hari, 1, ke),
                    },
                )
            await db.execute(
                text(
                    """
                    INSERT INTO approvals
                        (id, decision_id, approved_by, approved, comment, approved_at)
                    SELECT CAST(:id AS uuid), CAST(:kep AS uuid), u.id, true,
                           'bukti diperiksa (data demo)', :pada
                    FROM LATERAL (SELECT id FROM users WHERE role='sppg_head' ORDER BY id LIMIT 1) u
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "id": str(_id("approval-keputusan", hari.isoformat(), str(ke))),
                    "kep": str(kep),
                    "pada": _at(hari, 2, ke),
                },
            )

    # --- Memulihkan alur persetujuan yang benar -------------------------------
    # Alur yang berlaku (approval_matrix + `_commit_purchase_order`):
    #   1. Verifikator menyatakan `consistent`.
    #   2. Dua role menyetujui: sppg_nutritionist DAN sppg_head.
    #   3. PO terbit sebagai `draft`.
    #   4. Kepala SPPG mereview PO → PO `submitted`, keputusan `executed`,
    #      trace ACT ditulis, batch diberangkatkan.
    # Penyemaian sebelumnya melompati langkah 2 (hanya satu role) dan menaruh
    # ACT sebelum review PO — itu "memotong proses" yang dikeluhkan pemilik
    # demo 30 Okt 2026. Blok ini mengembalikannya secara eksplisit, bukan
    # menyetujui apa pun secara buta: hanya baris sesi cetakan, dan hanya bila
    # approval gizi belum ada.
    await db.execute(
        text(
            """
            INSERT INTO approvals
                (id, decision_id, approved_by, approved, comment, approved_at)
            SELECT md5(d.id::text || '|nutrisi')::uuid, d.id, u.id, true,
                   'persetujuan gizi sebelum review PO (data demo)',
                   COALESCE(
                       (SELECT min(a.approved_at) FROM approvals a
                        WHERE a.decision_id = d.id AND a.approved IS TRUE)
                       - interval '20 minutes',
                       d.created_at + interval '30 minutes'
                   )
            FROM decisions d
            CROSS JOIN LATERAL (
                SELECT id FROM users WHERE role = 'sppg_nutritionist' ORDER BY id LIMIT 1
            ) u
            WHERE d.status = 'executed'
              AND d.demo_session_id = CAST(:sesi AS uuid)
              AND NOT EXISTS (
                  SELECT 1 FROM approvals a
                  JOIN users uu ON uu.id = a.approved_by
                  WHERE a.decision_id = d.id
                    AND a.approved IS TRUE
                    AND uu.role = 'sppg_nutritionist'
              )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"sesi": str(sesi)},
    )
    # Setiap keputusan yang dieksekusi wajib punya PO: Kepala SPPG harus
    # mereview PO draft setelah approval kedua role. Tanpa ini riwayat demo
    # memperlihatkan keputusan "executed tanpa PO" (terukur 30 Okt 2026: 11
    # keputusan pembanding). PO ditaruh 5 menit setelah approval pertama
    # (gizi) dan sebelum approval review Kepala SPPG, lalu berstatus
    # `confirmed` karena sudah direview.
    await db.execute(
        text(
            """
            INSERT INTO sap_mock_purchase_orders
                (id, po_number, supplier_id, material_number, ordered_quantity,
                 price, decision_id, status, created_at, demo_session_id, origin)
            SELECT md5(d.id::text || '|po-review')::uuid,
                   'PO-KPI-' || to_char(d.created_at, 'YYYYMMDD') || '-'
                       || upper(left(md5(d.id::text), 4)),
                   COALESCE(
                       d.supplier_id,
                       (SELECT s.id FROM suppliers s
                        WHERE s.commodity_id = d.commodity_id
                        ORDER BY s.name LIMIT 1),
                       (SELECT s.id FROM suppliers s ORDER BY s.name LIMIT 1)
                   ),
                   'KPI-DEMO', d.quantity_kg,
                   COALESCE(
                       (SELECT p2.price FROM sap_mock_purchase_orders p2
                        WHERE p2.decision_id = d.id),
                       CAST(38021 AS numeric)
                   ),
                   d.id, 'confirmed',
                   COALESCE(
                       (SELECT min(a.approved_at) FROM approvals a
                        WHERE a.decision_id = d.id AND a.approved IS TRUE)
                       + interval '5 minutes',
                       d.created_at + interval '40 minutes'
                   ),
                   CAST(:sesi AS uuid), 'demo'
            FROM decisions d
            WHERE d.status = 'executed'
              AND d.demo_session_id = CAST(:sesi AS uuid)
              AND NOT EXISTS (
                  SELECT 1 FROM sap_mock_purchase_orders p
                  WHERE p.decision_id = d.id
              )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"sesi": str(sesi)},
    )
    return hasil


if __name__ == "__main__":  # pragma: no cover — jalur operasional demo
    import asyncio
    import json

    from app.db import get_db
    from app.services import demo_session as sesi_demo

    async def _main() -> None:
        async for db in get_db():
            aktif = await sesi_demo.aktif(db)
            laporan = await lengkapi_hari_ini_dan_besok(
                db, sesi=getattr(aktif, "id", None)
            )
            await db.commit()
            print(json.dumps(laporan, indent=1, default=str))
            break

    asyncio.run(_main())
