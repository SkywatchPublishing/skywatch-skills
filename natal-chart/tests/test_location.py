import pytest
import location as loc

CSV = """geonameid,name,asciiname,country,admin1,latitude,longitude,timezone,population
2988507,Paris,Paris,FR,11,48.85341,2.3488,Europe/Paris,2138551
4717560,Paris,Paris,US,TX,33.66094,-95.55551,America/Chicago,24000
5128581,New York City,New York City,US,NY,40.71427,-74.00597,America/New_York,8804190
"""


@pytest.fixture
def table(tmp_path):
    p = tmp_path / "cities.csv"
    p.write_text(CSV, encoding="utf-8")
    return loc.load_table(p)


def test_unique_match(table):
    city = loc.lookup("new york city", table)
    assert city.geonameid == 5128581
    assert city.timezone == "America/New_York"
    assert city.label == "New York City, NY, US"


def test_ambiguous_raises_with_candidates(table):
    with pytest.raises(loc.AmbiguousLocation) as info:
        loc.lookup("Paris", table)
    assert [c.geonameid for c in info.value.candidates] == [2988507, 4717560]


def test_suffix_disambiguates(table):
    assert loc.lookup("Paris, TX", table).geonameid == 4717560
    assert loc.lookup("Paris, FR", table).geonameid == 2988507


def test_by_geonameid(table):
    assert loc.lookup_id(4717560, table).label == "Paris, TX, US"


def test_unknown(table):
    with pytest.raises(loc.UnknownLocation):
        loc.lookup("Atlantis", table)
