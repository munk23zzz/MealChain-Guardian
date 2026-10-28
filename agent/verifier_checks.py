"""Cek deterministik + guard verdict Verifier Agent (AUD-9A-03).

Dua lapis di sini, keduanya **tanpa model**:

1. `periksa_klaim` membandingkan KLAIM supervisor dengan FAKTA yang dihitung
   kode (`/decisions/{id}/audit-facts`). Ia tidak menghitung ulang angka
   bisnis: yang dibandingkan adalah angka yang sudah ada di fakta.
2. `jaga_verdict` menahan jawaban model: model hanya boleh menurunkan atau
   menandai, tidak pernah menaikkan `flagged`/`unavailable` menjadi
   `consistent`, dan `consistent` tanpa sitasi selalu diturunkan.

Karena guard bekerja pada `checks` deterministik (bukan pada `checks` model),
model yang "yakin semua baik" tidak bisa menutupi cek yang gagal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .contracts import AgentRun
from .verifier_contracts import VERDICTS, VerifierCheck

#: Angka kecil yang bersifat struktural (jumlah worker, jumlah lane, horizon
#: hari) boleh muncul di narasi tanpa dianggap klaim data.
ANGKA_STRUKTURAL = frozenset(float(n) for n in range(0, 13))
#: Ambang bisnis yang boleh disebut sebagai aturan, bukan sebagai pengukuran.
ANGKA_AMBANG = frozenset({0.85, 0.6, 1.0, 100.0})

_ANGKA_RE = re.compile(r"\d+(?:[.,]\d+)+|\d+")
_ID_PANJANG = re.compile(r"^\d{6,}$")


KATA_JUJUR = (
    "degraded",
    "sebagian",
    "gagal",
    "tidak tersedia",
    "tidak lengkap",
    "partial",
    "flag",
    "needs_verification",
    "tidak aman",
    "tidak dinilai",
    "belum",
    "tidak dapat",
    "tanpa bukti",
    "memblokir",
    "blokir",
    "jangan eksekusi",
    "jangan dieksekusi",
    "menunggu review",
    "menunggu persetujuan",
)


def _ke_float(raw: str) -> float | None:
    """Baca angka Indonesia maupun Inggris sebagai satu nilai.

    Kenapa (28 Okt 2026): narasi demo ditulis dengan format Indonesia
    (`3.057,65`), sedangkan regex lama memotongnya menjadi `3.057` + `65`.
    Akibatnya cek `angka_bersitasi` menuduh angka yang sebenarnya ada di fakta
    (3057.65), verdict jatuh ke `unavailable`, dan keputusan berhenti di
    `proposed` sehingga tidak bisa disetujui. Titik ribuan dibuang, koma
    desimal dibaca sebagai titik desimal.
    """
    teks = raw.strip()
    if not teks:
        return None
    if "," in teks and "." in teks:
        # Pemisah terakhir = desimal; sisanya pemisah ribuan.
        if teks.rfind(",") > teks.rfind("."):
            teks = teks.replace(".", "").replace(",", ".")
        else:
            teks = teks.replace(",", "")
    elif "," in teks:
        teks = teks.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", teks):
        teks = teks.replace(".", "")
    try:
        return float(teks)
    except ValueError:
        return None


def angka_dalam_teks(teks: str) -> list[tuple[str, float]]:
    """Angka yang muncul di teks klaim (id panjang dilewati)."""
    hasil: list[tuple[str, float]] = []
    isi = teks or ""
    for match in _ANGKA_RE.finditer(isi):
        raw = match.group(0)
        if _ID_PANJANG.match(raw):
            continue
        nilai = _ke_float(raw)
        if nilai is None:
            continue
        # Tanda minus HARUS ikut dibaca. Narasi demo memakai minus tipografis
        # (U+2212 "−"), dan regex angka tidak memuat tanda; akibatnya
        # "-1,197654" dibaca 1,197654 dan cek `angka_bersitasi` menolak deviasi
        # harga yang sebenarnya benar (terukur 28 Okt 2026 pada `f52941d5`).
        awal = match.start()
        if awal > 0 and isi[awal - 1] in "-−–":
            sebelum = isi[awal - 2] if awal >= 2 else ""
            # Hanya tanda yang berdiri sendiri (" −1,2"), bukan bagian kata
            # atau kode seperti "PO-123".
            if awal == 1 or sebelum in " 	(:=~>≥≤":
                nilai = -nilai
        hasil.append((raw, nilai))
    return hasil


@dataclass(frozen=True)
class KlaimTemuan:
    agent: str
    status: str
    summary: str
    blocking: bool = False


@dataclass(frozen=True)
class KlaimSupervisor:
    """Objek yang DIAUDIT — bukan sumber data."""

    decision_id: str
    narrative: str | None
    status: str
    safety_veto: bool
    gate_verdict: str | None
    gate_reasons: tuple[str, ...] = ()
    findings: tuple[KlaimTemuan, ...] = ()

    @property
    def teks(self) -> str:
        """NARASI supervisor — satu-satunya klaim yang diaudit.

        Ringkasan worker sengaja tidak ikut: itu bahan masukan supervisor, bukan
        klaim yang harus dibuktikan. Kalau ikut, auditor akan menuntut sitasi
        untuk angka turunan yang ditulis worker dan berhenti mengaudit narasi.
        """
        return (self.narrative or "").strip()

    @property
    def teks_lower(self) -> str:
        return self.teks.lower()

    def jujur_tentang_penurunan(self) -> bool:
        return any(kata in self.teks_lower for kata in KATA_JUJUR)

    def menyebut(self, *kata: str) -> bool:
        return any(item in self.teks_lower for item in kata)

    def menyatakan_aman(self) -> bool:
        """Klaim bahwa putaran ini baik-baik saja, tanpa kualifikasi jujur."""
        if self.safety_veto:
            return False
        if self.status not in {"completed", "partial"}:
            return False
        return self.menyebut("aman", "pass", "layak", "konsisten", "tanpa kontradiksi")

    @property
    def ringkas_temuan(self) -> str:
        """Ringkasan tujuh worker — konteks untuk model, BUKAN klaim yang diaudit."""
        return " | ".join(f"{f.agent}: {f.summary}" for f in self.findings)


def klaim_dari_run(run: AgentRun) -> KlaimSupervisor:
    """Ambil klaim supervisor APA ADANYA dari satu putaran review."""
    return KlaimSupervisor(
        decision_id=run.decision_id,
        narrative=run.narrative,
        status=run.status.value,
        safety_veto=run.safety_veto,
        gate_verdict=run.verification.verdict if run.verification else None,
        gate_reasons=tuple(run.verification.reasons) if run.verification else (),
        findings=tuple(
            KlaimTemuan(
                agent=finding.agent.value,
                status=finding.status.value,
                summary=finding.summary,
                blocking=finding.blocking,
            )
            for finding in run.findings
        ),
    )


def _aktual(nilai: Any) -> str:
    if nilai is None:
        return "tidak tersedia"
    if isinstance(nilai, bool):
        return "true" if nilai else "false"
    return str(nilai)


def _cek(
    nama: str, klaim: str, aktual: Any, lulus: bool
) -> VerifierCheck:
    return VerifierCheck(nama=nama, klaim=klaim, aktual=_aktual(aktual), lulus=lulus)


def _fakta_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _presisi_teks(raw: str) -> int:
    """Jumlah digit desimal yang benar-benar ditulis narasi.

    Narasi wajar membulatkan (`-1,2%` dari `-1,197654`, `1.514,0` dari
    `1514.0159999999998`). Dengan membaca presisi yang ditulis, verifier bisa
    memakai toleransi pembulatan yang tepat alih-alih menuntut kesamaan 1e-9 —
    tuntutan itu menandai SEMUA review sebagai `verifier_flagged` (terukur
    28 Okt 2026: keputusan `9dbd0835` gagal di `angka_bersitasi` hanya karena
    pembulatan, lalu tidak bisa di-approve saat demo).
    """
    teks = raw.strip().rstrip("%").replace(" ", "")
    for sep in (",", "."):
        idx = teks.rfind(sep)
        if idx < 0:
            continue
        ekor = teks[idx + 1 :]
        if not ekor.isdigit():
            continue
        lain = "," if sep == "." else "."
        if len(ekor) == 3 and lain not in teks and teks.count(sep) >= 1:
            # "1.514" / "1,514" tanpa pemisah lain = pemisah ribuan
            continue
        return len(ekor)
    return 0


def cek_angka_bersitasi(
    klaim: KlaimSupervisor, fakta: dict[str, Any], angka_dikenal: Iterable[float]
) -> VerifierCheck:
    """Setiap angka di klaim wajib ada di fakta (atau ambang/struktural)."""
    dikenal = list(angka_dikenal)
    tanpa_sumber: list[str] = []
    for raw, nilai in angka_dalam_teks(klaim.teks):
        if nilai in ANGKA_STRUKTURAL or nilai in ANGKA_AMBANG:
            continue
        # Toleransi = setengah satuan digit terakhir yang ditulis narasi.
        toleransi = 0.5 * 10 ** (-_presisi_teks(raw))
        if any(abs(nilai - item) <= max(toleransi, 1e-9) for item in dikenal):
            continue
        tanpa_sumber.append(raw)
    if tanpa_sumber:
        return _cek(
            "angka_bersitasi",
            "setiap angka di klaim punya nilai sumber di fakta",
            f"tanpa sumber: {', '.join(sorted(set(tanpa_sumber)))}",
            False,
        )
    return _cek(
        "angka_bersitasi",
        "setiap angka di klaim punya nilai sumber di fakta",
        "semua angka klaim ditemukan di fakta",
        True,
    )


def cek_sdc_rincian(
    klaim: KlaimSupervisor, fakta: dict[str, Any]
) -> VerifierCheck:
    """SDC vs total rincian — hasil hitung kode, bukan hitung ulang verifier."""
    sdc = _fakta_dict(fakta.get("sdc_check"))
    if not klaim.menyebut("sdc", "safe delivered", "rincian", "breakdown", "biaya"):
        return _cek(
            "sdc_vs_cost_breakdown",
            "SDC sama dengan total rincian",
            "tidak diklaim",
            True,
        )
    cocok = sdc.get("cocok")
    aktual = (
        f"sdc={_aktual(sdc.get('safe_delivered_cost'))} "
        f"total={_aktual(sdc.get('breakdown_total'))} "
        f"selisih={_aktual(sdc.get('selisih'))} cocok={_aktual(cocok)}"
    )
    if cocok is None:
        return _cek(
            "sdc_vs_cost_breakdown",
            "SDC sama dengan total rincian",
            f"{aktual} ({sdc.get('alasan') or 'tidak dapat dinilai'})",
            False,
        )
    return _cek("sdc_vs_cost_breakdown", "SDC sama dengan total rincian", aktual, bool(cocok))


def cek_safety_sumber(
    klaim: KlaimSupervisor, fakta: dict[str, Any]
) -> VerifierCheck:
    batch = _fakta_dict(fakta.get("batch_sumber"))
    if not klaim.menyebut("batch", "safety", "keamanan", "aman"):
        return _cek(
            "safety_batch_sumber",
            "semua batch sumber aman (tidak fail/karantina)",
            "tidak diklaim",
            True,
        )
    worst = batch.get("worst_status")
    penghalang = batch.get("penghalang")
    failed = batch.get("failed_batch_ids") or []
    aktual = (
        f"worst_status={_aktual(worst)} fail={len(failed)} penghalang={_aktual(penghalang)}"
    )
    if worst is None:
        # Fakta tidak dapat dinilai. Narasi yang MENGAKU aman = klaim palsu;
        # narasi yang jujur menyebut ketidakpastian tidak boleh dihukum.
        return _cek(
            "safety_batch_sumber",
            "semua batch sumber aman",
            aktual,
            klaim.jujur_tentang_penurunan(),
        )
    lulus = worst != "fail" and not penghalang
    return _cek(
        "safety_batch_sumber",
        "semua batch sumber aman (tidak fail/karantina)",
        aktual,
        lulus,
    )


def cek_kesegaran(
    klaim: KlaimSupervisor, fakta: dict[str, Any]
) -> VerifierCheck:
    batch = _fakta_dict(fakta.get("batch_sumber"))
    if not klaim.menyebut("freshness", "kesegaran", "segar", "aman", "layak"):
        return _cek(
            "kesegaran_certified",
            "kesegaran memenuhi ambang certified (PASS >= 0,85)",
            "tidak diklaim",
            True,
        )
    skor = batch.get("worst_freshness_score")
    status = batch.get("freshness_status")
    ambang = _fakta_dict(batch.get("freshness_ambang"))
    aktual = (
        f"skor={_aktual(skor)} status={_aktual(status)} "
        f"ambang_pass={_aktual(ambang.get('pass'))}"
    )
    if status is None:
        return _cek(
            "kesegaran_certified",
            "kesegaran PASS",
            aktual,
            klaim.jujur_tentang_penurunan(),
        )
    # Cek ini mengaudit KLAIM "kesegaran PASS". Narasi yang menyebut status
    # non-pass secara jujur (mis. `needs_verification`) tidak mengklaim PASS,
    # jadi tidak boleh ditandai — yang ditandai adalah klaim yang melampaui fakta.
    return _cek(
        "kesegaran_certified",
        "kesegaran memenuhi ambang certified (PASS >= 0,85)",
        aktual,
        status == "pass" or klaim.jujur_tentang_penurunan(),
    )


def cek_bukti(
    klaim: KlaimSupervisor, fakta: dict[str, Any]
) -> VerifierCheck:
    evidence = _fakta_dict(fakta.get("evidence"))
    jumlah = evidence.get("count")
    tegas = klaim.status == "completed" or klaim.menyebut(
        "bukti", "evidence", "terbukti", "lengkap", "selesai"
    )
    if not tegas:
        return _cek(
            "bukti_keputusan",
            "keputusan punya baris bukti (decision_evidence)",
            "tidak diklaim",
            True,
        )
    aktual = f"evidence_count={_aktual(jumlah)} types={_aktual(evidence.get('types'))}"
    if jumlah is None:
        return _cek("bukti_keputusan", "keputusan punya bukti", aktual, False)
    if jumlah == 0:
        # Klaim "selesai" tanpa satu pun baris bukti: jujur hanya bila klaim
        # menyebut ketiadaan bukti (diperiksa oleh `jujur_tentang_penurunan`).
        lulus = klaim.jujur_tentang_penurunan()
        return _cek(
            "bukti_keputusan",
            "keputusan punya baris bukti (decision_evidence)",
            aktual + " (tidak ada bukti)",
            lulus,
        )
    return _cek("bukti_keputusan", "keputusan punya bukti", aktual, True)


def cek_exclusion(
    klaim: KlaimSupervisor, fakta: dict[str, Any]
) -> VerifierCheck:
    exclusion = _fakta_dict(fakta.get("exclusion"))
    if not klaim.menyebut("exclusion", "eksklusi", "pemasok", "supplier"):
        return _cek(
            "exclusion_berlaku",
            "tidak ada exclusion aktif yang berlaku",
            "tidak diklaim",
            True,
        )
    aktif = exclusion.get("aktif")
    aktual = f"aktif={_aktual(aktif)} ids={_aktual(exclusion.get('ids'))}"
    if aktif is None:
        return _cek(
            "exclusion_berlaku",
            "tidak ada exclusion aktif yang berlaku",
            aktual + f" ({exclusion.get('alasan') or 'tidak dapat dinilai'})",
            False,
        )
    return _cek(
        "exclusion_berlaku",
        "tidak ada exclusion aktif yang berlaku",
        aktual,
        not aktif,
    )


def cek_ledger(
    klaim: KlaimSupervisor, fakta: dict[str, Any]
) -> VerifierCheck:
    ledger = _fakta_dict(fakta.get("ledger"))
    jumlah = ledger.get("count")
    aktual = f"ledger_blocks={_aktual(jumlah)} actions={_aktual(ledger.get('actions'))}"
    if not klaim.menyebut("ledger", "hash", "tercatat"):
        return _cek("ledger_tercatat", "ada blok ledger untuk keputusan", aktual, True)
    if jumlah is None:
        return _cek("ledger_tercatat", "ada blok ledger untuk keputusan", aktual, False)
    # Keputusan yang belum dieksekusi memang belum punya blok aksi; menuntutnya
    # akan menandai setiap review dini. Yang diaudit: klaim "sudah tercatat"
    # pada keputusan yang sudah punya aksi.
    status = str(fakta.get("status") or "").lower()
    # Blok ledger lahir saat eksekusi. `pending_approval` juga belum punya
    # aksi — dulu status itu tidak ada di daftar, sehingga SETIAP review yang
    # lahir dari Demo Control ditandai gagal `ledger_tercatat` dan keputusan
    # berakhir `verifier_flagged` (terukur 28 Okt 2026: `9dbd0835`).
    if jumlah == 0 and status in {"proposed", "pending", "menunggu", "pending_approval"}:
        return _cek(
            "ledger_tercatat",
            "ada blok ledger untuk keputusan",
            aktual + " (belum ada aksi)",
            True,
        )
    return _cek(
        "ledger_tercatat", "ada blok ledger untuk keputusan", aktual, jumlah > 0
    )


def cek_gerbang(
    klaim: KlaimSupervisor, fakta: dict[str, Any]
) -> VerifierCheck:
    """Klaim "semua baik" tidak boleh bertahan saat gerbang menandai flag."""
    flaged = klaim.gate_verdict == "flag"
    if not flaged:
        return _cek(
            "gerbang_verifikasi",
            "klaim konsisten dengan verdict gerbang deterministik",
            "gerbang: pass",
            True,
        )
    jujur = klaim.jujur_tentang_penurunan()
    return _cek(
        "gerbang_verifikasi",
        "klaim konsisten dengan verdict gerbang deterministik",
        f"gerbang: flag ({', '.join(klaim.gate_reasons) or 'tanpa alasan'})",
        jujur,
    )


def periksa_klaim(
    klaim: KlaimSupervisor,
    fakta: dict[str, Any] | None,
    *,
    angka_dikenal: Iterable[float] = (),
) -> list[VerifierCheck]:
    """Semua cek deterministik; fakta kosong → semua cek gagal (fail-closed)."""
    if not isinstance(fakta, dict) or not fakta:
        return [
            _cek(
                "fakta_tersedia",
                "fakta audit dapat dibaca",
                "fakta tidak tersedia",
                False,
            )
        ]
    return [
        cek_angka_bersitasi(klaim, fakta, angka_dikenal),
        cek_sdc_rincian(klaim, fakta),
        cek_safety_sumber(klaim, fakta),
        cek_kesegaran(klaim, fakta),
        cek_bukti(klaim, fakta),
        cek_exclusion(klaim, fakta),
        cek_ledger(klaim, fakta),
        cek_gerbang(klaim, fakta),
    ]


#: Token umum yang tidak menunjuk field/nilai fakta tertentu. Dipakai guard
#: `flagged`: cek model harus menyebut sesuatu yang bisa dicocokkan ke fakta.
KATA_UMUM = frozenset(
    {
        "status",
        "count",
        "ids",
        "types",
        "name",
        "data",
        "true",
        "false",
        "none",
        "null",
        "klaim",
        "aktual",
        "tidak",
        "semua",
    }
)


def token_fakta(fakta: Any) -> set[str]:
    """Nama field + nilai (string/angka) yang benar-benar ada di fakta."""
    tokens: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for kunci, isi in value.items():
                teks = str(kunci).strip().lower()
                if len(teks) >= 4 and teks not in KATA_UMUM:
                    tokens.add(teks)
                walk(isi)
        elif isinstance(value, (list, tuple)):
            for isi in value:
                walk(isi)
        elif isinstance(value, bool) or value is None:
            return
        else:
            teks = str(value).strip().lower()
            if len(teks) >= 4 and teks not in KATA_UMUM:
                tokens.add(teks)

    walk(fakta or {})
    return tokens


def flagged_punya_bukti(
    checks: Sequence[VerifierCheck], fakta: Any
) -> tuple[bool, list[str]]:
    """`FLAGGED` model hanya sah bila satu cek gagal menunjuk fakta NYATA.

    Prosa `catatan` ("empat klaim kritis gagal …") bukan bukti: ia tidak bisa
    dicocokkan ke fakta. Yang dihitung sebagai bukti hanya cek model dengan
    `lulus=false` yang menyebut nama field atau nilai yang ada di fakta.
    """
    gagal = [cek for cek in checks if not cek.lulus]
    if not gagal:
        return False, ["tidak ada cek model yang gagal"]
    tokens = token_fakta(fakta)
    if not tokens:
        return False, ["fakta tidak memuat nilai yang bisa dicocokkan"]
    for cek in gagal:
        bagian = (
            getattr(cek, "nama", ""),
            getattr(cek, "klaim", ""),
            getattr(cek, "aktual", ""),
        )
        teks = " ".join(str(item).lower() for item in bagian)
        if any(token in teks for token in tokens):
            return True, []
    return False, ["tidak ada cek gagal yang menunjuk field/nilai fakta"]


def jaga_verdict(
    model_verdict: str | None,
    *,
    checks: Sequence[VerifierCheck],
    citations: Sequence[Any],
    fakta_tersedia: bool,
    gate_verdict: str | None = None,
    model_checks: Sequence[VerifierCheck] = (),
    fakta: Any = None,
) -> tuple[str, list[str]]:
    """Guard pasca-LLM: verdict hanya boleh turun, dan `consistent` butuh bukti.

    Mengembalikan `(verdict_final, alasan_penurunan)`. Aturan:

    - model tidak menjawab / verdict di luar kosakata → `unavailable`, KECUALI
      ada cek deterministik yang gagal: itu tetap `flagged` (menandai boleh,
      menyatakan konsisten tidak);
    - fakta tidak terbaca → `unavailable` (fail-closed, bukan lulus);
    - `consistent` + ada cek gagal → `flagged`;
    - `consistent` + tanpa sitasi → `flagged`;
    - `consistent` + gerbang `flag` → `flagged`;
    - `flagged`/`unavailable` dari model TIDAK pernah dinaikkan;
    - `flagged` model TANPA cek yang menunjuk ketidaksesuaian nyata → `unavailable`
      (prosa saja bukan veto; `unavailable` juga bukan `consistent`).
    """
    alasan: list[str] = []
    verdict = (model_verdict or "").strip().lower()
    gagal = [cek.nama for cek in checks if not cek.lulus]
    if verdict not in VERDICTS:
        # Tidak ada jawaban model yang sah. Cek deterministik tetap boleh
        # MENANDAI (arah konservatif), tetapi tidak boleh menyatakan konsisten:
        # "tidak ada auditor" bukan "tidak ada masalah".
        if gagal:
            alasan.append(
                "guard: model tidak menjawab sahih, tetapi cek deterministik gagal: "
                f"{', '.join(gagal)} → FLAGGED"
            )
            return ("flagged" if fakta_tersedia else "unavailable"), alasan
        alasan.append(
            f"output model tidak sah ({(model_verdict or 'kosong')!r}); verdict unavailable"
        )
        return "unavailable", alasan
    if not fakta_tersedia:
        alasan.append("fakta audit tidak terbaca; verdict unavailable (fail-closed)")
        return "unavailable", alasan
    if verdict != "consistent":
        if verdict == "flagged" and not gagal:
            didukung, catatan = flagged_punya_bukti(model_checks, fakta)
            if not didukung:
                alasan.append(
                    "guard: FLAGGED model tanpa cek yang menunjuk ketidaksesuaian "
                    f"nyata ({'; '.join(catatan)}) → unavailable"
                )
                return "unavailable", alasan
        return verdict, alasan

    if gagal:
        alasan.append(
            "guard: CONSISTENT diturunkan ke FLAGGED — cek deterministik gagal: "
            f"{', '.join(gagal)}"
        )
    if not citations:
        alasan.append(
            "guard: CONSISTENT diturunkan ke FLAGGED — tidak ada sitasi id"
        )
    if gate_verdict == "flag":
        alasan.append(
            "guard: CONSISTENT diturunkan ke FLAGGED — gerbang deterministik flag"
        )
    final = "flagged" if alasan else "consistent"
    return final, alasan


__all__ = [
    "KlaimSupervisor",
    "KlaimTemuan",
    "angka_dalam_teks",
    "cek_angka_bersitasi",
    "cek_bukti",
    "cek_exclusion",
    "cek_gerbang",
    "cek_kesegaran",
    "cek_ledger",
    "cek_safety_sumber",
    "cek_sdc_rincian",
    "flagged_punya_bukti",
    "jaga_verdict",
    "klaim_dari_run",
    "periksa_klaim",
    "token_fakta",
]
