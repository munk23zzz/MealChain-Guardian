"""Analysis client — hipotesis sebab + rekomendasi dari FAKTA deterministik.

Posisi dalam pipeline: sesudah DETECT/OPTIMIZE/PREDICT, sebelum DECIDE. Fungsinya
menjawab pertanyaan yang tidak bisa dijawab angka saja: *kenapa* ada kekurangan dan
*apa* tindakan yang masuk akal — tanpa memindahkan angka ke model.

Batas yang dijaga (sama semangatnya dengan verifier):

- **Angka tetap milik kode.** Prompt hanya membawa fakta yang sudah dihitung
  `supply/demand/supplier.evaluate/forecast`. Model tidak diminta menghitung apa pun.
- **Angka baru dijawab model ditandai, bukan diterima.** Setiap token numerik yang
  tidak ada di fakta dikumpulkan di `ungrounded_numbers`; status menjadi `ungrounded`
  walau teksnya tetap disimpan untuk dibaca manusia. Ini menjaga "penyebab: deviasi
  harga -3,7%" tidak lolos saat angka itu tidak pernah ada di fakta.
- **Tanpa model = jujur.** Chain kosong/gagal → `unavailable`; output tak terbaca →
  `error`. Langkah DECIDE tetap berjalan; hipotesis bukan syarat keputusan.
- Prompt tidak memuat kredensial; hanya fakta operasional.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

#: Kunci JSON yang diminta dari model. Nama Indonesia supaya selaras laporan chat.
ANALYSIS_KEYS = ("penyebab", "rekomendasi", "keyakinan")

#: Status yang boleh muncul di trace. `ungrounded` tetap dianggap berhasil diproses,
#: tetapi pembaca harus tahu angkanya tidak berasal dari fakta.
VALID_STATUSES = ("analyzed", "ungrounded", "unavailable", "error")

_NUM = re.compile(r"-?\d+(?:[.,]\d+)*")

#: ID yang tidak boleh muncul dari model: UUID utuh atau potongan 8 karakter hex.
#: Fakta tidak pernah membawa ID batch/keputusan (sengaja), jadi ID yang muncul di
#: jawaban model PASTI karangan — dan ID palsu di layar lebih berbahaya daripada
#: kalimat yang tidak lengkap.
_ID_KARANGAN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


@dataclass
class HypothesisResult:
    """Hipotesis + jejak provider eksplisit."""

    status: str  # analyzed | ungrounded | unavailable | error
    hypothesis: str | None = None
    recommendation: str | None = None
    confidence: str | None = None
    provider: str | None = None
    fallback_used: bool = False
    attempts: list = field(default_factory=list)
    ungrounded_numbers: list = field(default_factory=list)


def _facts_json(ctx: Mapping[str, Any]) -> str:
    return json.dumps(ctx, ensure_ascii=False, default=str)


def build_prompt(ctx: Mapping[str, Any]) -> str:
    """Prompt analisis: fakta masuk apa adanya, keluaran JSON tiga kunci.

    Instruksi eksplisit "jangan menghitung" penting: tanpa itu model cenderung
    menurunkan angka baru (mis. persentase deviasi) yang tidak ada di fakta dan
    membuat laporan terbaca lebih pasti daripada datanya.
    """
    return json.dumps(
        {
            "task": (
                "jelaskan sebab paling mungkin dari kekurangan pasokan pada fakta ini dan "
                "rekomendasikan satu tindakan operasional. JANGAN menghitung atau mengarang "
                "angka baru: kutip hanya angka yang tertulis di fakta. Jawab JSON dengan kunci "
                "penyebab, rekomendasi, keyakinan (tinggi|sedang|rendah). Jangan menyebut "
                "ID batch/keputusan, nomor dokumen, atau nama pemasok yang tidak tertulis di fakta."
            ),
            "facts": json.loads(_facts_json(ctx)),
        },
        ensure_ascii=False,
    )


def _angka_dalam(teks: str) -> set[str]:
    """Token numerik pada teks, dinormalkan (koma desimal → titik)."""
    hasil: set[str] = set()
    for tok in _NUM.findall(teks or ""):
        hasil.add(tok.replace(",", "."))
    return hasil


def _nilai(token: str) -> float | None:
    """Nilai numerik dari token gaya Indonesia maupun gaya mesin.

    `2.110` (ribuan Indonesia) dan `2110` harus bertemu sebagai nilai yang sama;
    `1.500,5` juga. Tanpa ini, model yang menulis angka dengan format Indonesia
    selalu ditandai "tidak berdasar" — peringatan palsu yang membuat pembaca
    mengabaikan peringatan yang benar.
    """
    teks = token.strip()
    if not teks:
        return None
    if "," in teks:
        # Gaya Indonesia: titik = ribuan, koma = desimal.
        teks = teks.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", teks):
        # Hanya titik berkelompok tiga = pemisah ribuan.
        teks = teks.replace(".", "")
    try:
        return float(teks)
    except (TypeError, ValueError):
        return None


def _angka_fakta(ctx: Mapping[str, Any]) -> list[float]:
    """Nilai numerik yang benar-benar ada di fakta (termasuk di dalam string).

    Dibandingkan sebagai NILAI, bukan sebagai teks: fakta JSON menulis `1500.0`
    sedangkan manusia (dan model) menulis `1500` — keduanya angka yang sama.
    """
    nilai: list[float] = []
    for token in _angka_dalam(_facts_json(ctx)):
        angka = _nilai(token)
        if angka is not None:
            nilai.append(angka)
    return nilai


def _liar(dijawab: set[str], fakta: list[float]) -> list[str]:
    """Angka di jawaban model yang tidak cocok dengan satu pun nilai fakta."""
    liar: list[str] = []
    for token in sorted(dijawab):
        angka = _nilai(token)
        if angka is None:
            continue
        cocok = any(abs(angka - f) <= max(1e-9, abs(f) * 1e-9) for f in fakta)
        if not cocok:
            liar.append(token)
    return liar


def _bersihkan_id(teks: str | None) -> str | None:
    """Buang ID karangan dari teks model, ganti penanda yang jujur.

    Fakta yang dikirim ke model tidak memuat ID batch/keputusan, jadi ID yang muncul
    di jawabannya pasti bukan dari data. Menampilkannya di layar membuat pembaca
    menyalin rujukan yang tidak ada — lebih buruk daripada kalimat tanpa rujukan.
    """
    if not teks:
        return teks
    bersih = _ID_KARANGAN.sub("(id tidak ada di fakta)", teks)
    return bersih.strip() or None


def _parse(raw: str) -> dict | None:
    """Ambil objek JSON dari output model; toleran noise di sekitarnya."""
    if not raw:
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _teks(data: dict, key: str, *, batas: int = 400) -> str | None:
    value = data.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()[:batas]
    return None


def run_hypothesis(
    ctx: Mapping[str, Any],
    *,
    chain: list | None = None,
    timeout_seconds: float | None = 30.0,
) -> HypothesisResult:
    """Jalankan langkah analisis lewat chain fallback yang sama dengan agent lain."""
    return _jalankan(
        ctx,
        prompt=build_prompt(ctx),
        kunci=("penyebab", "rekomendasi"),
        chain=chain,
        timeout_seconds=timeout_seconds,
    )


#: Instruksi narasi per tahap. Semua tahap pipeline mendapat giliran model;
#: angkanya tetap milik kode, model hanya menarasikan fakta yang sudah dihitung.
INSTRUKSI_TAHAP: dict[str, str] = {
    "DETECT": "sebut kondisi pasokan dan permintaan yang terdeteksi beserta selisihnya",
    "VERIFY": "sebut hasil verifikasi independen dan alasannya",
    "TRACE": "sebut apa yang dicatat pada jejak ini dan mengapa bisa dibaca ulang",
    "PREDICT": "sebut proyeksi kebutuhan serta metode dan sumber yang menghasilkannya",
    "OPTIMIZE": "sebut usulan pemasok terpilih dan alasan kelayakannya menurut fakta",
    "DECIDE": "sebut status usulan dan apa yang masih menunggu persetujuan manusia",
    "ACT": "sebut aksi yang dijalankan dan siapa yang menyetujuinya",
    "LEARN": "sebut pelajaran dari hasil yang tercatat",
}


def build_prompt_tahap(tahap: str, ctx: Mapping[str, Any]) -> str:
    """Prompt narasi satu tahap; keluaran JSON `narasi` + `keyakinan`."""
    return json.dumps(
        {
            "task": (
                f"Anda agen tahap {tahap} pada pipeline pengadaan pangan. "
                f"{INSTRUKSI_TAHAP.get(tahap, 'sebut isi fakta tahap ini')}. "
                "JANGAN menghitung atau mengarang angka baru: kutip hanya angka yang "
                "tertulis di fakta. Jawab JSON dengan kunci narasi, keyakinan "
                "(tinggi|sedang|rendah). Jangan menyebut ID batch/keputusan, nomor "
                "dokumen, atau nama pemasok yang tidak tertulis di fakta."
            ),
            "facts": json.loads(_facts_json(ctx)),
        },
        ensure_ascii=False,
    )


def narasi_tahap(
    tahap: str,
    ctx: Mapping[str, Any],
    *,
    chain: list | None = None,
    timeout_seconds: float | None = 30.0,
) -> HypothesisResult:
    """Narasi model untuk satu tahap pipeline; penjaga sama dengan analisis."""
    return _jalankan(
        ctx,
        prompt=build_prompt_tahap(tahap, ctx),
        kunci=("narasi",),
        chain=chain,
        timeout_seconds=timeout_seconds,
    )


def _jalankan(
    ctx: Mapping[str, Any],
    *,
    prompt: str,
    kunci: tuple[str, ...],
    chain: list | None,
    timeout_seconds: float | None,
) -> HypothesisResult:
    """Satu panggilan model + penjaga angka/ID yang sama untuk semua tahap.

    `kunci` adalah kunci teks yang diminta dari model; kunci pertama jadi
    `hypothesis` (teks utama), kunci kedua bila ada jadi `recommendation`.
    """
    if chain is None:
        from app.ai_providers.ai_provider_chain import build_default_callers

        chain = build_default_callers("supervisor")
    if not chain:
        return HypothesisResult(status="unavailable")

    from app.ai_providers.resilience import ProviderUnavailableError, provider_slot_index

    try:
        result = with_fallback_chain_safe(
            chain=chain, prompt=prompt, timeout_seconds=timeout_seconds
        )
    except ProviderUnavailableError as exc:
        return HypothesisResult(status="unavailable", attempts=exc.attempts)

    data = _parse(result.text)
    if not data:
        return HypothesisResult(
            status="error",
            fallback_used=result.fallback_used,
            attempts=result.attempts,
        )

    teks = [_bersihkan_id(_teks(data, k)) for k in kunci]
    if not any(teks):
        return HypothesisResult(
            status="error",
            fallback_used=result.fallback_used,
            attempts=result.attempts,
        )

    # Angka yang tidak ada di fakta: ditandai, bukan dibuang diam-diam.
    dijawab = _angka_dalam(" ".join(t for t in teks if t))
    liar = _liar(dijawab, _angka_fakta(ctx))

    winner_index = provider_slot_index(result.provider)
    winner_label = chain[winner_index][0] if winner_index < len(chain) else result.provider

    return HypothesisResult(
        status="ungrounded" if liar else "analyzed",
        hypothesis=teks[0],
        recommendation=teks[1] if len(teks) > 1 else None,
        confidence=_teks(data, "keyakinan", batas=20),
        provider=winner_label,
        fallback_used=result.fallback_used,
        attempts=result.attempts,
        ungrounded_numbers=liar,
    )


def with_fallback_chain_safe(*, chain: list, prompt: str, timeout_seconds: float | None):
    """`with_fallback_chain` dengan chain berbentuk [(label, fn, kind), ...]."""
    from app.ai_providers.resilience import with_fallback_chain

    return with_fallback_chain(
        primary=chain[0][1],
        prompt=prompt,
        fallbacks=[fn for _label, fn, _kind in chain[1:]],
        timeout_seconds=timeout_seconds,
    )
