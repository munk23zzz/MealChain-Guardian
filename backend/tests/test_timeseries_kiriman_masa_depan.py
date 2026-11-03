"""Kontrak: penyemai deret waktu tidak boleh menulis kiriman yang belum terjadi.

Regresi yang dikunci (audit ulang 24 Okt 2026, temuan N1):
`plan_delivery_rows()` membuat satu `delivery_events` berstatus `delivered` untuk
SETIAP rencana menu sejak `EVENT_DEMO_START` — termasuk rencana besok dan bulan
depan — dengan `delivered_at` selalu 21:00 WIB pada tanggal rencana. Akibatnya
KPI Meal Continuity 24 jam menampilkan 100% padahal belum ada barang berangkat.

Aturan yang harus berlaku:
1. Rencana bertanggal SETELAH hari ini (WIB) tidak mendapat baris kiriman.
2. Rencana hari ini hanya mendapat kiriman bila jam kirimnya (21:00 WIB) sudah lewat.
3. Rencana hari-hari sebelumnya tetap mendapat kiriman seperti biasa.
4. Batas "hari ini" memakai WIB, bukan UTC.
5. Id kiriman tetap deterministik (idempoten saat penyemaian diulang).
"""

from datetime import UTC, date, datetime, timedelta, timezone

from app.seed.timeseries import plan_delivery_rows

WIB = timezone(timedelta(hours=7))


def _wib(hari: date, jam: int, menit: int = 0) -> datetime:
    """Pukul `jam` WIB pada tanggal tertentu, dikembalikan sebagai UTC."""
    return datetime(hari.year, hari.month, hari.day, jam, menit, tzinfo=WIB).astimezone(UTC)


def _rencana(*tanggal: date) -> list[dict]:
    return [
        {
            "menu_plan_id": f"plan-{t.isoformat()}",
            "location_id": "loc-jakarta",
            "plan_date": t,
            "planned_portions": 1000,
        }
        for t in tanggal
    ]


HARI = date(2026, 10, 24)


def test_rencana_besok_dan_bulan_depan_tidak_dapat_kiriman():
    # 22:00 WIB: kiriman hari ini sudah lewat, besok & 12 hari lagi belum.
    rows = plan_delivery_rows(
        _rencana(HARI, HARI + timedelta(days=1), HARI + timedelta(days=12)),
        now=_wib(HARI, 22, 0),
    )
    tanggal = sorted(r["menu_plan_id"] for r in rows)
    assert tanggal == [f"plan-{HARI.isoformat()}"], (
        "rencana setelah hari ini tidak boleh punya kiriman 'delivered'"
    )


def test_hari_ini_belum_ada_kiriman_sebelum_jam_kirim():
    rows = plan_delivery_rows(_rencana(HARI), now=_wib(HARI, 8, 0))
    assert rows == [], "pukul 08:00 WIB kiriman 21:00 WIB belum terjadi"


def test_hari_ini_dapat_kiriman_setelah_jam_kirim():
    rows = plan_delivery_rows(_rencana(HARI), now=_wib(HARI, 22, 0))
    assert len(rows) == 1
    kiriman = rows[0]
    assert kiriman["status"] == "delivered"
    assert kiriman["delivered_at"] <= _wib(HARI, 22, 0)
    assert kiriman["delivered_at"] == datetime(2026, 10, 24, 14, tzinfo=UTC)


def test_hari_lalu_tetap_dapat_kiriman():
    kemarin = HARI - timedelta(days=1)
    rows = plan_delivery_rows(_rencana(kemarin, HARI), now=_wib(HARI, 9, 0))
    ids = {r["menu_plan_id"] for r in rows}
    assert f"plan-{kemarin.isoformat()}" in ids
    assert f"plan-{HARI.isoformat()}" not in ids


def test_batas_hari_memakai_wib_bukan_utc():
    """00:30 WIB tanggal 25 = 17:30 UTC tanggal 24; rencana 25 belum boleh dikirim."""
    sekarang = _wib(date(2026, 10, 25), 0, 30)
    rows = plan_delivery_rows(
        _rencana(date(2026, 10, 24), date(2026, 10, 25)), now=sekarang
    )
    ids = {r["menu_plan_id"] for r in rows}
    assert "plan-2026-10-25" not in ids, "hari ini (WIB) belum lewat 21:00, jangan dikirim"
    assert "plan-2026-10-24" in ids


def test_kiriman_tetap_deterministik():
    once = plan_delivery_rows(_rencana(HARI - timedelta(days=2)), now=_wib(HARI, 9, 0))
    twice = plan_delivery_rows(_rencana(HARI - timedelta(days=2)), now=_wib(HARI, 9, 0))
    assert [r["id"] for r in once] == [r["id"] for r in twice]
