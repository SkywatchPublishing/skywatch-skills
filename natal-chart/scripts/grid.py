"""Markdown aspect grid from chart.json."""
SYMBOLS = {"Conjunction": "☌", "Sextile": "⚹", "Square": "□", "Trine": "△", "Quincunx": "⚻", "Opposition": "☍"}


def _cell(a: dict) -> str:
    suffix = {True: "a", False: "s", None: ""}[a["applying"]]
    return f"{SYMBOLS[a['aspect']]} {a['orb']:.1f}{suffix}"


def render(chart: dict) -> str:
    names = list(chart["bodies"])
    if chart.get("angles"):
        names += ["Ascendant", "MC"]
    lookup = {}
    for a in chart["aspects"]:
        lookup[(a["body1"], a["body2"])] = lookup[(a["body2"], a["body1"])] = _cell(a)
    lines = ["| | " + " | ".join(names) + " |", "|" + "---|" * (len(names) + 1)]
    for row in names:
        cells = [lookup.get((row, col), "") for col in names]
        lines.append(f"| {row} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
