"""Pure geometry for the wheel. No SVG here."""
import math


def point(asc: float, lon: float, cx: float, cy: float, r: float) -> tuple[float, float]:
    theta = math.radians(180.0 + (lon - asc))
    return cx + r * math.cos(theta), cy - r * math.sin(theta)


def spread(longitudes: list[float], min_gap: float) -> list[float]:
    """Nudge display longitudes apart so glyphs do not overlap. Order is preserved; clusters stay centred."""
    order = sorted(range(len(longitudes)), key=lambda i: longitudes[i])
    vals = [longitudes[i] for i in order]
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] - vals[j] < min_gap:
            j += 1
        if j > i:
            centre = sum(longitudes[order[k]] for k in range(i, j + 1)) / (j - i + 1)
            start = centre - min_gap * (j - i) / 2
            for k in range(i, j + 1):
                vals[k] = start + min_gap * (k - i)
        i = j + 1
    out = [0.0] * len(longitudes)
    for pos, idx in enumerate(order):
        out[idx] = vals[pos]
    return out
