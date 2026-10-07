"""Signs, houses and retrograde state on every transit span.

"Mars square Pluto" made the reader work out which signs the two are in;
each span now says so. The signs are checked against immanuel's own chart at
the aspect's exact moment, a different code path from the raw ephemeris
lookup that produces them.
"""
import json

import pytest

from astro_mcp.config import get_config
from astro_mcp.tools.transit import ZODIAC, _transits_for_date, list_upcoming_transits

BIRTH = dict(date_time="1984-05-10T20:44:00", latitude=37.77, longitude=-122.42)


def rows(data):
    if "span_fields" in data:
        return [dict(zip(data["span_fields"], r)) for r in data["transits"]]
    return data["transits"]


def sign_of(chart, name):
    return next(o.sign.name for o in chart.objects.values() if o.name == name)


def natal_sign_of(name):
    from immanuel import charts
    subject = charts.Subject(date_time="1984-05-10 20:44", latitude=BIRTH["latitude"], longitude=BIRTH["longitude"])
    return sign_of(charts.Natal(subject, config=get_config()), name)


@pytest.fixture(scope="module")
def week():
    return rows(json.loads(list_upcoming_transits(start_date="2026-09-25", end_date="2026-10-02", **BIRTH)))


def test_every_span_names_the_sign_of_both_bodies(week):
    assert week
    for r in week:
        assert r["from_sign"] in ZODIAC and r["to_sign"] in ZODIAC


def test_mars_square_natal_pluto_reads_as_leo_and_scorpio():
    data = json.loads(list_upcoming_transits(
        start_date="2026-09-27", end_date="2026-09-29", object_filter="Mars", **BIRTH))
    span = next(r for r in rows(data) if r["to_object"] == "Pluto" and r["type"] == "Square")
    assert (span["from_sign"], span["to_sign"]) == ("Leo", "Scorpio")


def test_the_transiting_sign_matches_a_chart_drawn_at_the_exact_moment(week):
    config = get_config()
    checked = 0
    for r in week:
        if not r["exact"] or r["from_object"] == "Moon":
            continue
        chart = _transits_for_date(r["exact"], BIRTH["latitude"], BIRTH["longitude"], None, config)
        assert r["from_sign"] == sign_of(chart, r["from_object"]), r
        checked += 1
    assert checked


def test_the_natal_sign_matches_the_natal_chart(week):
    for r in week[:15]:
        assert r["to_sign"] == natal_sign_of(r["to_object"]), r


def test_without_birth_data_both_signs_are_transiting_positions():
    data = json.loads(list_upcoming_transits(start_date="2026-09-25", end_date="2026-10-25", object_filter="Sun,Mars,Venus"))
    config = get_config()
    checked = 0
    for r in rows(data):
        if not r["exact"]:
            continue
        chart = _transits_for_date(r["exact"], None, None, None, config)
        assert (r["from_sign"], r["to_sign"]) == (sign_of(chart, r["from_object"]), sign_of(chart, r["to_object"])), r
        checked += 1
    assert checked


# -- houses and retrograde --------------------------------------------------

def natal_chart(house_system=None):
    """The server's chart (whole sign), or one in another system straight from immanuel:
    _house_of is written for any system's cusps, and is still checked against them."""
    from immanuel import charts
    from immanuel.const import chart
    subject = charts.Subject(date_time="1984-05-10 20:44", latitude=BIRTH["latitude"], longitude=BIRTH["longitude"])
    config = get_config()
    if house_system:
        config.house_system = getattr(chart, house_system.upper())
    return charts.Natal(subject, config=config)


def test_natal_mode_spans_carry_houses_and_retrograde(week):
    for r in week:
        assert 1 <= r["from_house"] <= 12 and 1 <= r["to_house"] <= 12
        assert isinstance(r["from_retrograde"], bool)
        assert "to_retrograde" not in r


def test_the_natal_house_is_the_one_immanuel_gives_that_natal_object(week):
    chart = natal_chart()
    houses = {o.name: o.house.number for o in chart.objects.values() if o.house}
    for r in week[:20]:
        assert r["to_house"] == houses[r["to_object"]], r


def test_the_transiting_house_matches_immanuels_own_assignment(week):
    from astro_mcp.utils import assign_natal_houses_to_transit_objects
    natal = natal_chart()
    config = get_config()
    checked = 0
    for r in week:
        if not r["exact"] or r["from_object"] == "Moon":
            continue
        chart = _transits_for_date(r["exact"], BIRTH["latitude"], BIRTH["longitude"], None, config)
        expected = assign_natal_houses_to_transit_objects(chart, natal)[r["from_object"]]
        assert r["from_house"] == expected, r
        checked += 1
    assert checked


def test_retrograde_matches_immanuels_movement_at_the_exact_moment(week):
    config = get_config()
    seen = set()
    for r in week:
        if not r["exact"] or r["from_object"] == "Moon":
            continue
        chart = _transits_for_date(r["exact"], BIRTH["latitude"], BIRTH["longitude"], None, config)
        obj = next(o for o in chart.objects.values() if o.name == r["from_object"])
        assert r["from_retrograde"] == obj.movement.retrograde, r
        seen.add(r["from_retrograde"])
    assert seen


@pytest.mark.parametrize("system", ["whole_sign", "placidus", "koch", "equal"])
def test_house_lookup_agrees_with_immanuel_in_any_house_system(system):
    from astro_mcp.tools.transit import _house_of
    chart = natal_chart(system)
    cusps = sorted((h.number, h.longitude.raw % 360) for h in chart.houses.values())
    for o in chart.objects.values():
        if o.house and o.name in {"Sun", "Moon", "Mars", "Saturn", "Pluto", "Chiron"}:
            assert _house_of(o.longitude.raw % 360, cusps) == o.house.number, (system, o.name)


def test_without_birth_data_it_reports_retrograde_for_both_and_no_houses():
    data = json.loads(list_upcoming_transits(start_date="2026-09-25", end_date="2026-10-25", object_filter="Sun,Mars,Venus"))
    for r in rows(data):
        assert isinstance(r["from_retrograde"], bool) and isinstance(r["to_retrograde"], bool)
        assert "from_house" not in r and "to_house" not in r
