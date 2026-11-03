"""Logistics matrix dan feasibility (Task 5) — deterministik, seluruh pasangan seed.

Matriks jarak setara darat/laut (km) antar 10 lokasi seed. Nilai Cianjur–Jakarta
120 km terkunci dari demo docs/Skill.md §8. Pasangan lain adalah nilai sintetis
deterministik untuk seed — bukan data survei. Makassar (Sulawesi Selatan)
memakai perkiraan rute laut, sehingga jaraknya lebih jauh daripada kota Jawa.
"""

LOCATIONS: tuple[str, ...] = (
    "Jakarta", "Bogor", "Cianjur", "Bandung", "Semarang",
    "Yogyakarta", "Surabaya", "Makassar", "Palembang", "Medan",
)

_DIST = {
    ("Jakarta", "Bogor"): 50,
    ("Jakarta", "Cianjur"): 120,
    ("Jakarta", "Bandung"): 150,
    ("Jakarta", "Semarang"): 450,
    ("Jakarta", "Yogyakarta"): 560,
    ("Jakarta", "Surabaya"): 780,
    ("Jakarta", "Makassar"): 1400,
    ("Jakarta", "Palembang"): 540,
    ("Jakarta", "Medan"): 1900,
    ("Bogor", "Cianjur"): 70,
    ("Bogor", "Bandung"): 120,
    ("Bogor", "Semarang"): 430,
    ("Bogor", "Yogyakarta"): 540,
    ("Bogor", "Surabaya"): 760,
    ("Bogor", "Makassar"): 1420,
    ("Bogor", "Palembang"): 560,
    ("Bogor", "Medan"): 1920,
    ("Cianjur", "Bandung"): 65,
    ("Cianjur", "Semarang"): 480,
    ("Cianjur", "Yogyakarta"): 590,
    ("Cianjur", "Surabaya"): 810,
    ("Cianjur", "Makassar"): 1450,
    ("Cianjur", "Palembang"): 580,
    ("Cianjur", "Medan"): 1940,
    ("Bandung", "Semarang"): 420,
    ("Bandung", "Yogyakarta"): 530,
    ("Bandung", "Surabaya"): 750,
    ("Bandung", "Makassar"): 1380,
    ("Bandung", "Palembang"): 550,
    ("Bandung", "Medan"): 1910,
    ("Semarang", "Yogyakarta"): 110,
    ("Semarang", "Surabaya"): 330,
    ("Semarang", "Makassar"): 1000,
    ("Semarang", "Palembang"): 850,
    ("Semarang", "Medan"): 2100,
    ("Yogyakarta", "Surabaya"): 300,
    ("Yogyakarta", "Makassar"): 1050,
    ("Yogyakarta", "Palembang"): 900,
    ("Yogyakarta", "Medan"): 2200,
    ("Surabaya", "Makassar"): 780,
    ("Surabaya", "Palembang"): 1050,
    ("Surabaya", "Medan"): 2350,
    ("Makassar", "Palembang"): 1300,
    ("Makassar", "Medan"): 2900,
    ("Palembang", "Medan"): 1400,
}

DISTANCE_KM: dict[frozenset[str], int] = {
    frozenset(pair): km for pair, km in _DIST.items()
}


def _lookup_distance(source: str, target: str) -> int:
    if source == target:
        return 0
    try:
        return DISTANCE_KM[frozenset({source, target})]
    except KeyError as exc:
        raise ValueError(f"lokasi tidak dikenal: {source!r}/{target!r}") from exc


def estimate_logistics(
    source: str,
    target: str,
    quantity_kg: float,
    delivery_window_min: float | None = None,
    speed_kmh: float = 60.0,
    fixed_handling_min: float = 30.0,
) -> dict[str, int | float | bool]:
    if source not in LOCATIONS or target not in LOCATIONS:
        raise ValueError(f"lokasi tidak dikenal: {source!r}/{target!r}")
    if not (quantity_kg > 0) or quantity_kg == float("inf"):
        raise ValueError("quantity_kg harus positif dan finite")
    if not (speed_kmh > 0) or speed_kmh == float("inf"):
        raise ValueError("speed_kmh harus positif dan finite")
    if delivery_window_min is not None and delivery_window_min < 0:
        raise ValueError("delivery_window_min tidak boleh negatif")

    distance_km = _lookup_distance(source, target)
    travel_min = distance_km / speed_kmh * 60.0
    estimated_time_min = travel_min + fixed_handling_min
    feasible = (
        delivery_window_min is None or estimated_time_min <= delivery_window_min
    )

    return {
        "distance_km": distance_km,
        "estimated_time_min": estimated_time_min,
        "feasible": feasible,
    }
