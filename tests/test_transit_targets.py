"""Which natal points a transit can be reported against.

Transits to the natal angles are among the most significant contacts in
practice -- transiting Saturn crossing the Ascendant or MC is a textbook
life-stage marker -- but the natal side used to be filtered to planets, so
those were silently never reported.
"""
import json

import pytest

from astro_mcp.tools.transit import create_transit_chart, list_upcoming_transits
from astro_mcp.utils import MAJOR_OBJECTS, NATAL_TRANSIT_TARGETS

BIRTH = dict(date_time="1984-05-10T20:44:00", latitude=37.77, longitude=-122.42)


@pytest.fixture(scope="module")
def upcoming():
    return json.loads(list_upcoming_transits(**BIRTH))


def test_the_angles_are_targets(upcoming):
    targets = {t["to_object"] for t in upcoming["transits"]}
    assert "Asc" in targets or "MC" in targets, "no angular contacts reported"


def test_opposite_angles_are_not_double_counted():
    # Desc and IC sit exactly opposite Asc and MC, so every contact would be
    # reported twice if both were included.
    assert "Desc" not in NATAL_TRANSIT_TARGETS
    assert "IC" not in NATAL_TRANSIT_TARGETS


def test_the_transiting_side_stays_planetary():
    # An angle does not transit anything; it sweeps the zodiac daily.
    assert "Asc" not in MAJOR_OBJECTS
    assert "MC" not in MAJOR_OBJECTS


def test_angles_still_get_exact_moments(upcoming):
    # The natal side is a fixed longitude, so exactness needs an ephemeris
    # body only for the transiting planet.
    angular = [t for t in upcoming["transits"] if t["to_object"] in ("Asc", "MC")]
    assert angular, "no angular contacts to check"
    assert any(t["exact"] for t in angular), "no exact moment computed for an angle"


def test_a_snapshot_chart_reports_angular_contacts():
    # A fixed moment and a wide orb: whether an angle happens to be aspected
    # "now" changes from day to day, which made this fail on quiet days.
    chart = json.loads(create_transit_chart(transit_date_time="2026-10-01 12:00", max_orb=10, **BIRTH))
    targets = {a["to_object"] for a in chart["aspects"]}
    assert targets & {"Asc", "MC"}, "snapshot chart omits the angles"


def test_planets_are_still_covered(upcoming):
    targets = {t["to_object"] for t in upcoming["transits"]}
    assert {"Sun", "Moon", "Saturn"} <= targets
