"""Aspect detection shared in spirit (copied, not imported) by synastry."""
import itertools

# Config block from the design document. synastry copies these and subtracts 2.
ASPECTS = {"Conjunction": 0, "Sextile": 60, "Square": 90, "Trine": 120, "Quincunx": 150, "Opposition": 180}
ORBS = {"Conjunction": 8.0, "Opposition": 8.0, "Square": 8.0, "Trine": 8.0, "Sextile": 6.0, "Quincunx": 3.0}
LUMINARY_BONUS = 2.0
LUMINARIES = {"Sun", "Moon"}


def max_orb(aspect: str, b1: str, b2: str, reduction: float = 0.0) -> float:
    bonus = LUMINARY_BONUS if (b1 in LUMINARIES or b2 in LUMINARIES) else 0.0
    return ORBS[aspect] + bonus - reduction


def separation(lon1: float, lon2: float) -> float:
    d = abs(lon1 - lon2) % 360
    return min(d, 360 - d)


def applying(p1: dict, p2: dict, angle: float) -> bool | None:
    """True when the pair is closing on the exact aspect, False when moving away from it,
    None when a speed is missing or the bodies move at the same rate.
    Uses the signed separation and relative speed analytically, so a fast body that reaches
    exact within the hour (the Moon, say) is still reported as applying."""
    if p1.get("speed") is None or p2.get("speed") is None:
        return None
    rel = p1["speed"] - p2["speed"]
    if abs(rel) < 1e-9:
        return None
    delta = ((p1["longitude"] - p2["longitude"] + 180) % 360) - 180  # signed, in (-180, 180]
    target = angle if delta >= 0 else -angle  # nearest exact aspect on delta's side (0 stays 0)
    return (delta - target) * rel < 0


def find_aspects(bodies: dict[str, dict], reduction: float = 0.0, pairs=None) -> list[dict]:
    """bodies: name -> {longitude, speed?}. pairs: optional iterable of (name1, name2); default all combinations."""
    pairs = pairs if pairs is not None else itertools.combinations(bodies, 2)
    found = []
    for n1, n2 in pairs:
        p1, p2 = bodies[n1], bodies[n2]
        sep = separation(p1["longitude"], p2["longitude"])
        for aspect, angle in ASPECTS.items():
            limit = max_orb(aspect, n1, n2, reduction)
            orb = abs(sep - angle)
            if orb <= limit:
                found.append({"body1": n1, "body2": n2, "aspect": aspect, "angle": angle,
                              "orb": round(orb, 3), "max_orb": limit, "applying": applying(p1, p2, angle)})
                break
    return found
