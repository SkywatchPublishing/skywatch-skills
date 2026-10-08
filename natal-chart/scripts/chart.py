"""Assemble chart.json (schema version 1) from birth data."""
import datetime as dt
from zoneinfo import ZoneInfo

import swisseph as swe

import aspects as asp
import ephemeris as eph

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
BODY_ORDER = list(eph.BODIES)


def sign_of(lon: float) -> tuple[str, float]:
    lon %= 360
    return SIGNS[int(lon // 30)], lon % 30


def format_degree(lon: float) -> str:
    # Round the whole longitude to the nearest arc-minute first so a value a
    # hair under a sign boundary rolls over into the next sign (never "30°00'").
    total_minutes = round(lon % 360 * 60) % (360 * 60)
    sign = SIGNS[total_minutes // (30 * 60)]
    whole, minutes = divmod(total_minutes % (30 * 60), 60)
    return f"{whole}°{minutes:02d}' {sign}"


def house_of(lon: float, cusps: list[float]) -> int:
    lon %= 360
    for i in range(12):
        start, end = cusps[i], cusps[(i + 1) % 12]
        inside = start <= lon < end if start < end else (lon >= start or lon < end)
        if inside:
            return i + 1
    return 12


def moon_range(date: dt.date, tz: ZoneInfo, zodiac: str) -> dict:
    """Moon longitude at the first and last minute of the local day; used when the time is unknown."""
    first = dt.datetime.combine(date, dt.time(0, 0), tzinfo=tz)
    last = dt.datetime.combine(date, dt.time(23, 59), tzinfo=tz)
    return {"start": round(eph.body_positions(eph.julian_day(first), zodiac)["Moon"]["longitude"], 4),
            "end": round(eph.body_positions(eph.julian_day(last), zodiac)["Moon"]["longitude"], 4)}


def build_chart(name: str, date: dt.date, time: dt.time | None, timezone: str, location: dict, house_system: str,
                zodiac: str = "tropical", node: str = "true") -> dict:
    flags = []
    tz = ZoneInfo(timezone)
    moon = None
    if time is None:
        time = dt.time(12, 0)
        flags += ["time_unknown", "moon_uncertain"]
        moon = moon_range(date, tz, zodiac)
    local = dt.datetime.combine(date, time, tzinfo=tz)
    jd = eph.julian_day(local)
    positions = eph.body_positions(jd, zodiac, node)
    if "Chiron" not in positions:
        flags.append("chiron_unavailable")

    houses = angles = None
    if "time_unknown" not in flags:
        houses, house_flags = eph.houses(jd, location["latitude"], location["longitude"], house_system, zodiac)
        flags += house_flags
        angles = houses.pop("angles")

    bodies = {}
    for n in BODY_ORDER:
        if n not in positions:
            continue
        p = positions[n]
        sign, deg = sign_of(p["longitude"])
        bodies[n] = {
            "longitude": round(p["longitude"], 4), "sign": sign, "sign_degree": round(deg, 4),
            "formatted": format_degree(p["longitude"]), "speed": round(p["speed"], 4),
            "retrograde": p["speed"] < 0, "house": house_of(p["longitude"], houses["cusps"]) if houses else None,
            "latitude": round(p["latitude"], 4),
        }

    aspect_input = {n: {"longitude": b["longitude"], "speed": b["speed"]} for n, b in bodies.items()}
    if angles:
        aspect_input["Ascendant"] = {"longitude": angles["ascendant"]}
        aspect_input["MC"] = {"longitude": angles["mc"]}
    pairs = [(a, b) for i, a in enumerate(aspect_input) for b in list(aspect_input)[i + 1:]
             if not (a in ("Ascendant", "MC") and b in ("Ascendant", "MC"))]

    return {
        "schema_version": 1,
        "meta": {
            "name": name,
            "datetime_local": local.replace(tzinfo=None).isoformat(),
            "timezone": timezone,
            "datetime_utc": local.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "utc_offset": local.isoformat()[-6:],
            "julian_day_ut": round(jd, 7),
            "time_unknown": "time_unknown" in flags,
            "moon_range": moon,
            "location": location,
            "zodiac": "sidereal_lahiri" if zodiac == "sidereal" else "tropical",
            "house_system": houses["system"] if houses else None,
            "node": node,
            "flags": flags,
            "source": {"library": "pyswisseph", "version": swe.version, "ephemeris_files": eph.ephemeris_files_present()},
        },
        "angles": {k: round(v, 4) for k, v in angles.items()} if angles else None,
        "houses": {"system": houses["system"], "cusps": [round(c, 4) for c in houses["cusps"]]} if houses else None,
        "bodies": bodies,
        "aspects": asp.find_aspects(aspect_input, pairs=pairs),
    }
