"""Pure geometry for the wheel. No SVG here."""
import math


def point(asc: float, lon: float, cx: float, cy: float, r: float) -> tuple[float, float]:
    theta = math.radians(180.0 + (lon - asc))
    return cx + r * math.cos(theta), cy - r * math.sin(theta)


def spread(longitudes: list[float], min_gap: float) -> list[float]:
    """Nudge display longitudes apart so glyphs do not overlap.

    Works on the circle: the 0/360 seam is just another place on the wheel, so a
    cluster straddling 0 Aries is spread like any other. Cyclic order is
    preserved, clusters stay centred, and results are in [0, 360).
    """
    n = len(longitudes)
    if n == 0:
        return []
    if n == 1:
        return [longitudes[0] % 360.0]

    order = sorted(range(n), key=lambda i: longitudes[i] % 360.0)
    vals = [longitudes[i] % 360.0 for i in order]

    out = [0.0] * n
    if n * min_gap >= 360.0:
        # Not enough room to honour min_gap: share the circle evenly instead.
        for pos, idx in enumerate(order):
            out[idx] = (vals[0] + 360.0 * pos / n) % 360.0
        return out

    # Unroll the circle starting just after the widest gap, so no cluster is cut by the seam.
    gaps = [(vals[(k + 1) % n] - vals[k]) % 360.0 for k in range(n)]
    if gaps[-1] == 0.0:
        gaps[-1] = 360.0   # all values identical: the wrap gap is the whole circle
    start = (max(range(n), key=lambda k: gaps[k]) + 1) % n
    offset = vals[start]
    unrolled = [(vals[(start + k) % n] - offset) % 360.0 for k in range(n)]
    unrolled[0] = 0.0

    # Cluster pass; repeat because a centred cluster can be pushed into its neighbour.
    for _ in range(n):
        moved = False
        i = 0
        while i < n:
            j = i
            while j + 1 < n and unrolled[j + 1] - unrolled[j] < min_gap - 1e-12:
                j += 1
            if j > i:
                centre = sum(unrolled[i:j + 1]) / (j - i + 1)
                first = centre - min_gap * (j - i) / 2
                for k in range(i, j + 1):
                    unrolled[k] = first + min_gap * (k - i)
                moved = True
            i = j + 1
        if not moved:
            break

    # The ends can still meet across the seam; then the whole ring is one cluster.
    if unrolled[-1] - unrolled[0] > 360.0 - min_gap + 1e-12:
        centre = sum(unrolled) / n
        first = centre - min_gap * (n - 1) / 2
        unrolled = [first + min_gap * k for k in range(n)]

    for k in range(n):
        out[order[(start + k) % n]] = (unrolled[k] + offset) % 360.0
    return out
