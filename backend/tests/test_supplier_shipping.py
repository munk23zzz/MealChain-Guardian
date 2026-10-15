"""Aturan `sedang mengirim`: hanya batch yang MASIH LAYAK hari ini
(`usable_until >= sekarang`) - keputusan pemilik 2026-10-16.

Tes ini yang mengunci batasnya, termasuk dua hal yang mudah salah:
- batch yang sudah lewat masa layak TIDAK boleh dihitung sebagai kiriman aktif;
- kiriman layak yang status keamanannya `fail` tetap dihitung, tapi jumlahnya
  dilaporkan terpisah supaya UI tidak bisa menyembunyikannya.
"""

from datetime import UTC, datetime, timedelta

from app.core.supplier_shipping import shipping_for, shipping_summary

NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=UTC)


def _row(supplier_id, commodity, quantity_kg, usable_until, safety_status="pass"):
    return {
        "supplier_id": supplier_id,
        "commodity": commodity,
        "quantity_kg": quantity_kg,
        "usable_until": usable_until,
        "safety_status": safety_status,
    }


def test_batch_kedaluwarsa_tidak_dihitung() -> None:
    """Cianjur→Palembang layak sampai 10 Sep: bukan kiriman aktif pada 16 Okt."""
    summary = shipping_summary(
        [_row("sup-c", "telur", 250, datetime(2026, 9, 10, tzinfo=UTC))], NOW
    )

    assert summary == {}


def test_batas_tepat_sekarang_dihitung() -> None:
    """Batasnya inklusif: `usable_until == now` masih layak (bukan lewat)."""
    summary = shipping_summary([_row("sup-a", "telur", 500, NOW)], NOW)

    assert summary["sup-a"]["count"] == 1


def test_total_berat_dan_batas_terjauh() -> None:
    """Dua kiriman layak -> total kg dijumlah, `until` = batas paling jauh."""
    summary = shipping_summary(
        [
            _row("sup-a", "telur", 500, NOW + timedelta(days=17)),
            _row("sup-a", "telur", 400, NOW + timedelta(days=3)),
            _row("sup-a", "telur", 900, NOW - timedelta(days=1)),  # kedaluwarsa
        ],
        NOW,
    )

    assert summary["sup-a"]["count"] == 2
    assert summary["sup-a"]["total_kg"] == 900.0
    assert summary["sup-a"]["until"] == NOW + timedelta(days=17)


def test_gagal_uji_dihitung_terpisah() -> None:
    """Kiriman layak yang safety-nya fail tetap dihitung, tapi dilaporkan."""
    summary = shipping_summary(
        [
            _row("sup-b", "telur", 600, NOW + timedelta(days=10), safety_status="fail"),
            _row("sup-b", "telur", 200, NOW + timedelta(days=10)),
        ],
        NOW,
    )

    assert summary["sup-b"]["count"] == 2
    assert summary["sup-b"]["safety_fail_count"] == 1


def test_komoditas_unik_dan_terurut() -> None:
    """Komoditas unik (bukan daftar berulang), urut alfabetis."""
    summary = shipping_summary(
        [
            _row("sup-b", "telur", 600, NOW + timedelta(days=1)),
            _row("sup-b", "ayam", 200, NOW + timedelta(days=1)),
            _row("sup-b", "telur", 100, NOW + timedelta(days=1)),
        ],
        NOW,
    )

    assert summary["sup-b"]["commodities"] == ["ayam", "telur"]


def test_pemasok_tanpa_kiriman_layak_tidak_muncul() -> None:
    """Tidak ada entri 0 kg untuk pemasok yang tidak sedang mengirim."""
    summary = shipping_summary(
        [_row("sup-c", "telur", 250, NOW - timedelta(days=30))], NOW
    )

    assert shipping_for(summary, "sup-c") is None
    assert summary == {}


def test_baris_tanpa_pemasok_atau_batas_layak_diabaikan() -> None:
    """Batch tanpa pemasok / tanpa `usable_until` tidak bisa diklaim sedang berjalan."""
    summary = shipping_summary(
        [
            _row(None, "telur", 500, NOW + timedelta(days=1)),
            _row("sup-a", "telur", 500, None),
        ],
        NOW,
    )

    assert summary == {}


def test_kirim_dua_pemasok_terpisah() -> None:
    """Ringkasan dipisah per pemasok; `shipping_for` menerima id sebagai apa pun."""
    summary = shipping_summary(
        [
            _row("sup-a", "telur", 500, NOW + timedelta(days=17)),
            _row("sup-b", "telur", 600, NOW + timedelta(days=10)),
        ],
        NOW,
    )

    assert set(summary) == {"sup-a", "sup-b"}
    assert shipping_for(summary, "sup-b")["total_kg"] == 600.0
    assert shipping_for(summary, None) is None
