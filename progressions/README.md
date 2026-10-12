# progressions

Moves a natal chart forward in time with the two techniques astrologers use most: secondary progressions, where one day after birth stands for one year of life, and solar arc directions, where every natal point moves forward by the arc the progressed Sun has travelled. Writes a progressed or directed chart for any date as an ordinary `chart.json` with its aspect grid, and a dated CSV timeline of both techniques' events. Takes the `chart.json` produced by `natal-chart`.

**Charts:** `--date` for a secondary progressed chart, `--method solar-arc` for a solar arc directed chart; progressed angles by solar arc (default) or Naibod (`--angles naibod`)
**Timeline:** `--timeline --start --end` lists progressed and directed aspects to the natal chart, sign ingresses, the progressed Moon's natal house ingresses and stations, each aspect with the dates it enters and leaves a 1° orb
**Output:** `secondary_progressed_<date>.json` or `solar_arc_directed_<date>.json` with a `_aspects.md` grid, or `progressions_timeline.csv`
**Extra:** an untimed birth is accepted, with secondary dates marked uncertain (about six months either way) and no angles or houses

## Example output

All three examples progress the natal-chart example chart (1990-06-15 at 12:00, New York City, Virgo rising).

[`examples/secondary_progressed_2027-06-15.json`](examples/secondary_progressed_2027-06-15.json), with its grid in [`examples/secondary_progressed_2027-06-15_aspects.md`](examples/secondary_progressed_2027-06-15_aspects.md), is the secondary progressed chart for 2027-06-15: age 37.0001, solar arc 35°18' (35.2991°). The progressed Sun is at 29°35' Cancer, a few months from entering Leo, and the progressed Moon at 6°48' Leo, in the progressed 10th house and the natal 11th. With the default solar-arc angles the progressed MC is 16°31' Cancer (natal MC plus the arc) and the Ascendant 14°12' Libra; progressed Saturn, Uranus, Neptune and Pluto are retrograde. The file carries `chart_type: secondary_progressed`, `derived_from: ["Example"]` and `meta.progression` `{target_date: "2027-06-15", age_years: 37.0001, solar_arc: 35.2991, angles_method: "solar-arc"}`; its birth timestamps are the natal ones.

[`examples/solar_arc_directed_2027-06-15.json`](examples/solar_arc_directed_2027-06-15.json), with [`examples/solar_arc_directed_2027-06-15_aspects.md`](examples/solar_arc_directed_2027-06-15_aspects.md), is the solar arc directed chart for the same date: every natal body, angle and cusp moved 35°18', so the natal pattern and houses are unchanged. The directed MC is the same 16°31' Cancer, the directed Ascendant 19°11' Libra, the directed Moon 22°53' Aries; speeds are `null` and `angles_method` is `null`.

[`examples/progressions_timeline_2027-2036.csv`](examples/progressions_timeline_2027-2036.csv) is the timeline for 2027 to 2036: 132 events, 73 secondary aspects, 48 solar arc aspects, 6 sign ingresses, 4 natal house ingresses of the progressed Moon and 1 station, none marked uncertain since the birth time is known. A few of its rows:

| Technique | Event | Moving | Aspect | Target | Exact | Orb from | Orb to | Detail |
|---|---|---|---|---|---|---|---|---|
| solar arc | aspect | Venus | Conjunction | Sun | 2027-06-21 | 2026-06-04 | 2028-07-07 | |
| secondary | aspect | Moon | Opposition | Node | 2027-07-19 | 2027-06-23 | 2027-08-14 | |
| secondary | ingress | Sun | | | 2027-11-20 | | | enters Leo |
| secondary | house | Moon | | | 2028-02-27 | | | enters natal house 12 |
| secondary | ingress | Moon | | | 2029-02-17 | | | enters Virgo |
| secondary | aspect | Moon | Conjunction | Ascendant | 2030-03-05 | 2030-02-05 | 2030-04-02 | |
| secondary | station | Pluto | | | 2030-11-05 | | | turns direct at 14°58' Scorpio |

The progressed Moon enters Virgo, Libra, Scorpio and Sagittarius about two and a half years apart, and nine rows have their exact date outside the range (in 2026, 2037 and 2038) because their 1° windows overlap it. The progressed Sun's aspects are listed once, under `secondary`: the directed Sun is the progressed Sun.

Examples are produced by:

```bash
python progressions/scripts/progressions.py natal-chart/examples/chart.json --date 2027-06-15 --out progressions/examples/secondary_progressed_2027-06-15.json
python progressions/scripts/progressions.py natal-chart/examples/chart.json --date 2027-06-15 --method solar-arc --out progressions/examples/solar_arc_directed_2027-06-15.json
python progressions/scripts/progressions.py natal-chart/examples/chart.json --timeline --start 2027-01-01 --end 2036-12-31 --out progressions/examples/progressions_timeline_2027-2036.csv
```

run from the repository root. The two `_aspects.md` grids are written beside the charts by default.

## Install

```bash
# Claude Code, project scope
cp -r progressions .claude/skills/

# Claude Code, user scope
cp -r progressions ~/.claude/skills/
```

Install `natal-chart` alongside it: this skill reads the `chart.json` that one writes, and it borrows that skill's Swiss Ephemeris files from `natal-chart/ephe/` when its own `ephe/` folder is empty. Without the files it falls back to pyswisseph's built-in Moshier ephemeris, as `natal-chart` does: a progressed chart leaves Chiron out and flags `chiron_unavailable`, and a timeline leaves out progressed Chiron's ingresses and stations; both print `Note: chiron_unavailable`. Nothing is delegated to `natal-chart` at run time.

Then ask Claude "what's my progressed Moon doing", "when does my progressed Sun change sign", "what are my solar arcs this year", or "what's coming up for me this decade".

## Run the script directly

```bash
pip install pyswisseph
python scripts/progressions.py chart.json --date 2027-06-15
python scripts/progressions.py chart.json --date 2027-06-15 --angles naibod
python scripts/progressions.py chart.json --date 2027-06-15 --method solar-arc
python scripts/progressions.py chart.json --timeline --start 2027-01-01 --end 2036-12-31
```

Options: `--date` writes a chart and `--timeline --start --end` writes the event list (exactly one of the two); `--method secondary|solar-arc` picks the chart technique; `--angles solar-arc|naibod` sets how progressed angles move, for secondary charts and the timeline (refused with `--method solar-arc`); `--out` names the output (default `secondary_progressed_<date>.json`, `solar_arc_directed_<date>.json` or `progressions_timeline.csv`) and `--grid` a chart's aspect grid (default `<out stem>_aspects.md`, never the same file as `--out`). Neither may name the input chart, and both must be in a folder that exists; they are checked before anything is written. A chart prints `Wrote <out> and <grid>` and a `Note:` line per chart flag; a timeline prints `Wrote N events to <out>`. Exit code `1` means bad arguments or input, with the reason on stderr: a chart that is not natal (returns, composites, Davison charts and progressed or directed charts are refused), a `--date` or timeline `--end` before the birth date, a range over 120 years, or a malformed chart. A timeline `--start` before the birth date is moved to the birth date with a `Note:`.

Requires Python 3.11 or newer.

## How it works

- The age at the target date (local noon in the natal timezone, never before the birth moment) is the elapsed time divided by the tropical year of 365.24219 days, and the progressed instant is the birth moment plus that many days. The progressed bodies are computed with pyswisseph at that instant, in the natal zodiac and node setting.
- The true solar arc is the progressed Sun minus the natal Sun. A directed chart adds it to every natal body, angle and cusp. A progressed chart's MC is the natal MC plus the arc by default, or the natal right ascension of the MC plus 0°59'08" a year with Naibod; the Ascendant and cusps then come from that MC at the birth latitude in the natal house system, through the same house-from-ARMC routine the composite skill uses.
- The timeline samples the range every 15 days, finds where each moving point crosses an exact aspect, and bisects the crossing and the two 1° window edges to the minute, so a date does not shift with the range asked for. Progressed Mercury, Venus and Mars can stall near a station, so their windows can last decades; they are scanned 40 years either side of the range, and any window that overlaps it is listed. Dates are local dates at the birthplace with no clock times.
- An untimed natal chart gives charts without angles or houses and a timeline without angle or house events; every secondary event and every solar arc event touching the Moon, Sun, Mercury, Venus or Mars is marked `Uncertain`: a 12-hour error in the birth moment is half a progressed day, about six months, and it moves those five natal positions by months of arc (years for the Moon).
- Because each chart is a complete `chart.json`, `chart-wheel` draws it with the target date in the caption, and `synastry` against the natal chart gives the progressed-to-natal aspects and house overlays. `returns` and `composite` refuse progressed and directed charts, and this skill refuses every chart that is not natal.
- The script imports nothing from the other skill folders; the helpers it needs are copied from `natal-chart` and `composite`.

## Why it exists

After transits, progressions are what astrologers reach for when the question is "what chapter am I in, and what is coming next". They are slow, so the useful answer is a set of dates years apart, and the two techniques are easy to confuse or to compute by hand with the wrong arc. This casts both on the `chart.json` contract, so the wheel and synastry read the charts unchanged, and turns the next decade into a dated list.
