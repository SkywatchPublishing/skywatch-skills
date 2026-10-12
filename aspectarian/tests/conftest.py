import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

EPHEMERIS = SKILL / "ephe" / "de440s.bsp"


@pytest.fixture(scope="session")
def sky():
    if not EPHEMERIS.exists():
        pytest.skip(f"{EPHEMERIS} absent; run python aspectarian/scripts/fetch_ephemeris.py")
    import aspectarian
    return aspectarian.Sky(EPHEMERIS)
