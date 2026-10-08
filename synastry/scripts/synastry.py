"""Synastry: inter-aspects and house overlays between two chart.json files.

The aspect config and helpers are copied from natal-chart/scripts (never imported across
skill folders). Synastry orbs are the natal table minus 2 degrees (``REDUCTION``).

Usage:
    python synastry.py --a chartA.json --b chartB.json [--out synastry.json] [--grid synastry.md]
    python synastry.py --a-birth '--name Ada --date 1990-06-15 --time 14:30 --geonameid 2643743' \
                       --b-birth '--name Bob --date 1988-02-02 --geonameid 5128581'

``--a-birth``/``--b-birth`` are shell-style strings handed verbatim to the natal-chart script.
"""

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

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


def _side_flags(side: str, chart: dict, untimed: bool) -> list[str]:
    """The chart's natal flags prefixed with its side, with ``time_unknown`` added, deduplicated."""
    names = list((chart.get("meta") or {}).get("flags") or [])
    if untimed:
        names.insert(0, "time_unknown")
    out = []
    for name in names:
        flag = f"{side}_{name}"
        if flag not in out:
            out.append(flag)
    return out


def compare(a: dict, b: dict, sources: dict[str, str] | None = None) -> dict:
    """Inter-aspects and overlays; ``sources`` names where each chart came from (file path or "birth data")."""
    a_untimed, b_untimed = _time_unknown(a), _time_unknown(b)
    flags = _side_flags("a", a, a_untimed) + _side_flags("b", b, b_untimed)
    sources = sources or {}
    config = {"orb_reduction": REDUCTION}
    for side, chart in (("a", a), ("b", b)):
        config[side] = {"source": sources.get(side), "house_system": chart["meta"].get("house_system")}

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
        "config": config,
        "inter_aspects": inter,
        "overlays": {"a_in_b_houses": _overlay(a, b), "b_in_a_houses": _overlay(b, a)},
    }


def _cell(hit: dict) -> str:
    return f"{SYMBOLS[hit['aspect']]} {hit['orb']:.1f}" + ("?" if hit["uncertain"] else "")


def render_grid(result: dict, a: dict, b: dict) -> str:
    """Markdown grid: A's bodies (and angles) down the left, B's across the top; uncertain cells end in ``?``."""
    rows, cols = list(_points(a)), list(_points(b))
    lookup = {(h["a"], h["b"]): _cell(h) for h in result["inter_aspects"]}
    lines = ["| A \\ B | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for row in rows:
        lines.append(f"| {row} | " + " | ".join(lookup.get((row, col), "") for col in cols) + " |")
    return "\n".join(lines) + "\n"


# --- command line ---------------------------------------------------------------------

NATAL_MISSING = ("synastry needs the natal-chart skill installed beside it to accept raw birth data; "
                 "pass chart files instead")


def find_natal_script() -> Path | None:
    """The sibling natal-chart script: beside this skill, then the user and project skill folders."""
    rel = Path("natal-chart") / "scripts" / "natal_chart.py"
    candidates = [
        Path(__file__).resolve().parents[2] / rel,
        Path.home() / ".claude" / "skills" / rel,
        Path.cwd() / ".claude" / "skills" / rel,
    ]
    return next((c for c in candidates if c.is_file()), None)


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on usage errors; that code is passed through from natal-chart, so exit 1."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    p = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--a", type=Path, help="chart.json for person A")
    p.add_argument("--b", type=Path, help="chart.json for person B")
    p.add_argument("--a-birth", help="raw birth arguments for A, as one shell-style string for natal_chart.py")
    p.add_argument("--b-birth", help="raw birth arguments for B, as one shell-style string for natal_chart.py")
    p.add_argument("--out", type=Path, default=Path("synastry.json"))
    p.add_argument("--grid", type=Path, help="markdown grid path (default: <out stem>.md)")
    return p


class DelegationFailed(Exception):
    def __init__(self, code: int, stdout: str, stderr: str):
        super().__init__(f"natal_chart.py exited {code}")
        self.code, self.stdout, self.stderr = code, stdout, stderr


def cast_chart(natal_script: Path, birth: str, out: Path) -> dict:
    """Run the natal script with the user's raw arguments, writing to ``out``, and load the result.

    ``--out`` and ``--grid`` come last so a user-supplied path in ``birth`` cannot write outside the
    temporary directory. The natal script's "Note:" lines and stderr are forwarded to the user.
    """
    try:
        words = shlex.split(birth)
    except ValueError as exc:
        raise ValueError(f"cannot parse birth arguments {birth!r}: {exc}") from exc
    cmd = [sys.executable, "-I", str(natal_script), *words,
           "--out", str(out), "--grid", str(out.with_suffix(".md"))]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise DelegationFailed(proc.returncode, proc.stdout, proc.stderr)
    for line in proc.stdout.splitlines():
        if line.startswith("Note:"):
            print(line)
    sys.stderr.write(proc.stderr)
    return load_chart(out)


def load_chart(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        try:
            chart = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(chart, dict):
        raise ValueError(f"{path}: expected a chart object")
    if chart.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{path}: expected schema_version {SCHEMA_VERSION}, got {chart.get('schema_version')!r}")
    if not isinstance(chart.get("meta"), dict) or not chart["meta"].get("name"):
        raise ValueError(f"{path}: missing meta.name")
    if not isinstance(chart.get("bodies"), dict) or not chart["bodies"]:
        raise ValueError(f"{path}: missing bodies")
    return chart


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    for side in "ab":
        file_arg, birth_arg = getattr(args, side), getattr(args, f"{side}_birth")
        if file_arg and birth_arg:
            parser.error(f"give --{side} or --{side}-birth, not both")
        if not file_arg and not birth_arg:
            parser.error(f"give --{side} or --{side}-birth")

    grid_path = args.grid or args.out.with_suffix(".md")
    if grid_path.resolve() == args.out.resolve():
        print(f"--grid and --out are the same file ({args.out}); choose a different --grid", file=sys.stderr)
        return 1

    natal_script = None
    if args.a_birth or args.b_birth:
        natal_script = find_natal_script()
        if natal_script is None:
            print(NATAL_MISSING, file=sys.stderr)
            return 1

    charts, sources = {}, {}
    try:
        with tempfile.TemporaryDirectory(prefix="synastry-") as tmp:
            for side in "ab":
                birth = getattr(args, f"{side}_birth")
                if birth:
                    charts[side] = cast_chart(natal_script, birth, Path(tmp) / f"{side}.json")
                    sources[side] = "birth data"
                else:
                    charts[side] = load_chart(getattr(args, side))
                    sources[side] = str(getattr(args, side))
    except DelegationFailed as exc:
        # Exit 2 (ambiguous city) carries the candidate table on stdout; pass both through.
        sys.stdout.write(exc.stdout)
        sys.stderr.write(exc.stderr)
        return exc.code
    except subprocess.TimeoutExpired:
        print("natal_chart.py did not finish within 120 seconds", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1

    result = compare(charts["a"], charts["b"], sources)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    grid_path.write_text(render_grid(result, charts["a"], charts["b"]), encoding="utf-8")
    print(f"Wrote {args.out} and {grid_path}")
    for flag in result["flags"]:
        print(f"Note: {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
