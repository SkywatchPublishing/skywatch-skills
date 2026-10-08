"""Synastry: inter-aspects and house overlays between two chart.json files.

The aspect config and helpers are copied from natal-chart/scripts (never imported across
skill folders). Synastry orbs are the natal table minus 2 degrees (``REDUCTION``).
"""

SCHEMA_VERSION = 1
REDUCTION = 2.0

# Config block from the design document; identical to natal-chart's, reduced by REDUCTION here.
ASPECTS = {"Conjunction": 0, "Sextile": 60, "Square": 90, "Trine": 120, "Quincunx": 150, "Opposition": 180}
ORBS = {"Conjunction": 8.0, "Opposition": 8.0, "Square": 8.0, "Trine": 8.0, "Sextile": 6.0, "Quincunx": 3.0}
LUMINARY_BONUS = 2.0
LUMINARIES = {"Sun", "Moon"}
SYMBOLS = {"Conjunction": "☌", "Sextile": "⚹", "Square": "□", "Trine": "△", "Quincunx": "⚻", "Opposition": "☍"}
ANGLE_NAMES = ("Ascendant", "MC")


def max_orb(aspect: str, b1: str, b2: str, reduction: float = 0.0) -> float:
    bonus = LUMINARY_BONUS if (b1 in LUMINARIES or b2 in LUMINARIES) else 0.0
    return ORBS[aspect] + bonus - reduction


def separation(lon1: float, lon2: float) -> float:
    d = abs(lon1 - lon2) % 360
    return min(d, 360 - d)


def house_of(lon: float, cusps: list[float]) -> int:
    lon %= 360
    for i in range(12):
        start, end = cusps[i], cusps[(i + 1) % 12]
        inside = start <= lon < end if start < end else (lon >= start or lon < end)
        if inside:
            return i + 1
    return 12


def _points(chart: dict) -> dict[str, float]:
    """name -> longitude for every body, plus Ascendant and MC when the chart has angles."""
    points = {name: body["longitude"] for name, body in chart["bodies"].items()}
    angles = chart.get("angles")
    if angles:
        points["Ascendant"] = angles["ascendant"]
        points["MC"] = angles["mc"]
    return points


def _time_unknown(chart: dict) -> bool:
    meta = chart.get("meta") or {}
    return bool(meta.get("time_unknown")) or "time_unknown" in (meta.get("flags") or [])


def _overlay(guest: dict, host: dict) -> dict[str, int] | None:
    """Each guest body placed in the host's houses; None when the host has no houses."""
    houses = host.get("houses")
    if not houses or not houses.get("cusps"):
        return None
    cusps = houses["cusps"]
    return {name: house_of(body["longitude"], cusps) for name, body in guest["bodies"].items()}


def compare(a: dict, b: dict) -> dict:
    a_untimed, b_untimed = _time_unknown(a), _time_unknown(b)
    flags = []
    if a_untimed:
        flags.append("a_time_unknown")
    if b_untimed:
        flags.append("b_time_unknown")

    inter = []
    for name_a, lon_a in _points(a).items():
        for name_b, lon_b in _points(b).items():
            sep = separation(lon_a, lon_b)
            for aspect, angle in ASPECTS.items():
                limit = max_orb(aspect, name_a, name_b, REDUCTION)
                orb = abs(sep - angle)
                if orb <= limit:
                    uncertain = (a_untimed and name_a == "Moon") or (b_untimed and name_b == "Moon")
                    inter.append({"a": name_a, "b": name_b, "aspect": aspect, "angle": angle,
                                  "orb": round(orb, 3), "max_orb": limit, "applying": None,
                                  "uncertain": uncertain})
                    break

    return {
        "schema_version": SCHEMA_VERSION,
        "a": a["meta"]["name"],
        "b": b["meta"]["name"],
        "flags": flags,
        "inter_aspects": inter,
        "overlays": {"a_in_b_houses": _overlay(a, b), "b_in_a_houses": _overlay(b, a)},
    }


def _cell(hit: dict) -> str:
    return f"{SYMBOLS[hit['aspect']]} {hit['orb']:.1f}"


def render_grid(result: dict, a: dict, b: dict) -> str:
    """Markdown grid: A's bodies (and angles) down the left, B's across the top."""
    rows, cols = list(_points(a)), list(_points(b))
    lookup = {(h["a"], h["b"]): _cell(h) for h in result["inter_aspects"]}
    lines = ["| A \\ B | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for row in rows:
        lines.append(f"| {row} | " + " | ".join(lookup.get((row, col), "") for col in cols) + " |")
    return "\n".join(lines) + "\n"
