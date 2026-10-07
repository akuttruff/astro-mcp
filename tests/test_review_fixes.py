"""Fixes from the October 2026 review: what each one guarantees.

Coordinates are decimal degrees and say so; an unfindable place is a
structured error from every tool; filters take any case and reject unknown
names; the Moon is sampled properly without a birth chart too; a longitude
prints the same minute in every tool.
"""
import json

import pytest

import astro_mcp.geocode as geocode
from astro_mcp.tools.horary import judge_question
from astro_mcp.tools.natal import create_natal_chart
from astro_mcp.tools.timing import lunations_and_eclipses, moon_void_periods, planetary_hours
from astro_mcp.tools.transit import create_transit_chart, list_upcoming_transits
from astro_mcp.utils import sign_position, validate_latitude, validate_longitude

BIRTH = dict(date_time="1984-05-10 20:44", latitude=34.02, longitude=-118.4)
MOMENT = "2026-10-06 12:00"


class TestCoordinatesAreDecimalDegrees:
    def test_the_dms_forms_once_advertised_are_refused_with_the_format_spelled_out(self):
        for value, check in (("34n03", validate_latitude), ("118w15", validate_longitude), ("34n", validate_latitude)):
            valid, error = check(value)
            assert not valid
            assert "decimal degrees" in error and value in error and "34n03" in error

    def test_a_tool_says_the_same(self):
        r = json.loads(create_natal_chart(date_time="1984-05-10 20:44", latitude="34n03", longitude="118w15"))
        assert r["error"] in ("Invalid latitude", "Invalid location")
        assert "decimal degrees" in r["detail"] and "34n03" in r["detail"]

    def test_no_tool_still_promises_dms(self):
        from astro_mcp.server import mcp
        import inspect
        for name, fn in (
            ("create_natal_chart", create_natal_chart), ("create_transit_chart", create_transit_chart),
            ("list_upcoming_transits", list_upcoming_transits),
        ):
            assert "DMS" not in (inspect.getdoc(fn) or ""), name


class TestAnUnfindablePlaceIsAnError:
    @pytest.fixture(autouse=True)
    def nowhere(self, monkeypatch):
        def boom(city, state=None, country=None):
            raise geocode.LocationNotFoundError(f"Could not find coordinates for: {city}")
        monkeypatch.setattr(geocode, "resolve_location", boom)

    @pytest.mark.parametrize("call", [
        lambda: create_natal_chart(date_time="1984-05-10 20:44", city="Nowhereville"),
        lambda: planetary_hours(date="2026-10-06", city="Nowhereville"),
        lambda: moon_void_periods(start_date="2026-10-06", city="Nowhereville"),
        lambda: lunations_and_eclipses(start_date="2026-10-01", end_date="2026-10-31", date_time="1984-05-10 20:44", city="Nowhereville"),
        lambda: judge_question(question="will it rain?", quesited_house=4, when=MOMENT, city="Nowhereville"),
        lambda: create_transit_chart(date_time="1984-05-10 20:44", city="Nowhereville"),
    ])
    def test_every_tool_reports_it_with_the_message(self, call):
        r = json.loads(call())
        assert r["error"] == "Geocoding failed"
        assert "Nowhereville" in r["detail"]


class TestFiltersTakeAnyCaseAndRejectUnknownNames:
    def test_transit_snapshot_object_filter(self):
        upper = json.loads(create_transit_chart(transit_date_time=MOMENT, object_filter="Saturn,Jupiter", max_orb=8, **BIRTH))
        lower = json.loads(create_transit_chart(transit_date_time=MOMENT, object_filter=" saturn , JUPITER ", max_orb=8, **BIRTH))
        assert upper["aspects"] and upper["aspects"] == lower["aspects"]
        bad = json.loads(create_transit_chart(transit_date_time=MOMENT, object_filter="Saturn,Vulcan", **BIRTH))
        assert bad["error"] == "Invalid object_filter" and "Vulcan" in bad["detail"] and "Chiron" in bad["detail"]

    def test_transit_snapshot_aspect_type(self):
        r = json.loads(create_transit_chart(transit_date_time=MOMENT, aspect_type="square,TRINE", max_orb=8, **BIRTH))
        assert r["aspects"] and {a["type"] for a in r["aspects"]} <= {"Square", "Trine"}
        bad = json.loads(create_transit_chart(transit_date_time=MOMENT, aspect_type="quintile", **BIRTH))
        assert bad["error"] == "Invalid aspect_type" and "quintile" in bad["detail"]

    def test_transit_scan_aspect_filter(self):
        r = json.loads(list_upcoming_transits(start_date="2026-10-06", end_date="2026-10-20", aspect_filter="square", **BIRTH))
        assert r["total_transits"] and {t["type"] for t in r["transits"]} == {"Square"}
        bad = json.loads(list_upcoming_transits(start_date="2026-10-06", end_date="2026-10-20", aspect_filter="Square,Quintile"))
        assert bad["error"] == "Invalid aspect_filter"


class TestTheMoonIsSampledProperlyWithoutABirthChart:
    @pytest.fixture(scope="class")
    def general(self):
        return json.loads(list_upcoming_transits(start_date="2026-10-06", end_date="2026-10-10", object_filter="Moon"))

    def test_it_finds_the_contacts_a_daily_sample_missed(self, general):
        # ~13 degrees a day at a 1.5 degree orb, against ten other bodies: a
        # dozen contacts in five days. The once-a-day sample found two.
        assert general["total_transits"] > 7, general["total_transits"]

    def test_the_moon_is_the_first_named_body_of_every_pair(self, general):
        assert {t["from_object"] for t in general["transits"]} == {"Moon"}

    def test_each_contact_is_one_span_with_an_exact_moment(self, general):
        keys = [(t["from_object"], t["to_object"], t["type"], t["start"]) for t in general["transits"]]
        assert len(keys) == len(set(keys))
        assert sum(1 for t in general["transits"] if t["exact"]) > len(general["transits"]) * 0.8

    def test_without_a_birth_chart_the_filter_keeps_either_end(self):
        r = json.loads(list_upcoming_transits(start_date="2026-10-06", end_date="2026-10-20", object_filter="Saturn"))
        assert r["transits"]
        assert all("Saturn" in (t["from_object"], t["to_object"]) for t in r["transits"])
        # The faster body leads each pair: a Sun-Saturn contact is Sun to Saturn, never the reverse.
        assert not any(t["from_object"] == "Saturn" and t["to_object"] == "Sun" for t in r["transits"])


class TestOneLongitudePrintsTheSameEverywhere:
    def test_lunation_degrees_round_like_every_other_tool(self):
        r = json.loads(lunations_and_eclipses(start_date="2026-03-01", end_date="2026-03-05", latitude=40.7128, longitude=-74.006))
        eclipse = next(e for e in r["events"] if e["event"] == "total lunar eclipse")
        # 12°51'40" Virgo: rounded to 12°52', not truncated to 12°51'.
        assert eclipse["position"] == "12°52' Virgo"
        assert eclipse["position"] == sign_position(162.8612)["position"]
