"""Tests for the timing tools: planetary hours, void-of-course Moon, and
lunations and eclipses.

Where a published reference exists (2026's eclipses) results are checked
against it. The void-of-course calculation, which rests on immanuel's
iterative aspect search, is checked against an independent brute-force scan
of the Moon's aspects.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from astro_mcp.tools.timing import (
    CHALDEAN,
    PTOLEMAIC,
    TRADITIONAL_PLANETS,
    _jd,
    _moon_sign_stays,
    lunations_and_eclipses,
    moon_void_periods,
    planetary_hours,
    void_periods,
)

LA = {"latitude": "34.02", "longitude": "-118.40"}
NYC = {"latitude": "40.74", "longitude": "-73.99"}
TROMSO = {"latitude": "69.65", "longitude": "18.96"}


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


class TestPlanetaryHours:
    def test_a_day_of_24_hours_in_chaldean_order_from_the_day_ruler(self):
        r = json.loads(planetary_hours(date="2026-09-27", **LA))  # a Sunday
        assert r["day_ruler"] == "Sun"
        assert r["timezone"] == "America/Los_Angeles"
        rulers = [h["ruler"] for h in r["hours"]]
        assert len(rulers) == 24
        start = CHALDEAN.index("Sun")
        assert rulers == [CHALDEAN[(start + i) % 7] for i in range(24)]
        # The next day's first hour would continue the sequence onto Monday's ruler.
        assert CHALDEAN[(start + 24) % 7] == "Moon"

    def test_hours_run_sunrise_to_sunset_then_through_the_night(self):
        r = json.loads(planetary_hours(date="2026-09-27", **LA))
        hours = r["hours"]
        assert hours[0]["start"] == r["sunrise"]
        assert hours[12]["start"] == r["sunset"]
        assert hours[23]["end"] == r["next_sunrise"][11:]
        for a, b in zip(hours, hours[1:]):
            assert a["end"] == b["start"]
        # Near the equinox, day and night hours are close to an hour each.
        assert 58 < r["day_hour_minutes"] < 62
        assert 58 < r["night_hour_minutes"] < 62
        # Los Angeles, late September: sunrise about 6:45, sunset about 6:43 pm.
        assert abs(_minutes(r["sunrise"]) - _minutes("06:45")) <= 3
        assert abs(_minutes(r["sunset"]) - _minutes("18:43")) <= 3

    def test_summer_day_hours_are_longer_than_night_hours(self):
        r = json.loads(planetary_hours(date="2026-06-21", **NYC))
        assert r["day_hour_minutes"] > 70 > 50 > r["night_hour_minutes"]

    @pytest.mark.parametrize("day,ruler", [
        ("2026-09-28", "Moon"), ("2026-09-29", "Mars"), ("2026-09-30", "Mercury"),
        ("2026-10-01", "Jupiter"), ("2026-10-02", "Venus"), ("2026-10-03", "Saturn"),
    ])
    def test_each_weekday_has_its_ruler(self, day, ruler):
        assert json.loads(planetary_hours(date=day, **LA))["day_ruler"] == ruler

    def test_polar_day_is_explained_not_miscomputed(self):
        r = json.loads(planetary_hours(date="2026-06-21", **TROMSO))
        assert r["error"] == "No planetary hours for this day"
        assert "polar" in r["detail"]

    def test_needs_a_place(self):
        assert "place is required" in json.loads(planetary_hours(date="2026-09-27"))["detail"]

    def test_rejects_a_bad_date(self):
        assert json.loads(planetary_hours(date="Sept 27", **LA))["error"] == "Invalid input"


def _brute_last_aspect(entry: float, exit_: float) -> float | None:
    """Independent check: the Moon's last exact Ptolemaic aspect to the
    traditional planets in [entry, exit).

    Uses the Moon's signed elongation from each planet (0-360), where every
    aspect -- oppositions included -- is a genuine crossing of a target angle
    (A or 360 - A), found by 20-minute scanning then bisection. (The folded
    0-180 separation only *touches* 0 and 180, which a coarse scan misses.)
    """
    from immanuel.const import chart
    from immanuel.tools import sweph

    def offset(pid: int, target: float, jd: float) -> float:
        elong = (sweph.planet(chart.MOON, jd)["lon"] - sweph.planet(pid, jd)["lon"]) % 360
        return (elong - target + 180) % 360 - 180

    step = 20 / 1440
    last = None
    for name in TRADITIONAL_PLANETS:
        pid = getattr(chart, name.upper())
        for angle in PTOLEMAIC.values():
            for target in {angle % 360, (360 - angle) % 360}:
                jd = entry
                while jd < exit_:
                    b = min(jd + step, exit_)
                    fa, fb = offset(pid, target, jd), offset(pid, target, b)
                    if fa * fb <= 0 and abs(fa) < 90 and abs(fb) < 90:
                        lo, hi = jd, b
                        for _ in range(40):
                            mid = (lo + hi) / 2
                            if offset(pid, target, lo) * offset(pid, target, mid) <= 0:
                                hi = mid
                            else:
                                lo = mid
                        t = (lo + hi) / 2
                        if entry <= t < exit_ and (last is None or t > last):
                            last = t
                    jd = b
    return last


class TestVoidOfCourse:
    def test_matches_an_independent_scan_for_a_month_of_moon_signs(self):
        start = _jd(datetime(2026, 9, 1, tzinfo=timezone.utc))
        end = start + 30
        periods = void_periods(start, end)
        assert len(periods) >= 12  # a sign change every ~2.5 days
        for p in periods:
            expected = _brute_last_aspect(p["entry"], p["end"])
            got = p["last_aspect"][2] if p["last_aspect"] else None
            if expected is None:
                assert got is None, p
            else:
                assert got is not None, p
                assert abs(got - expected) * 1440 < 2, (p["sign"], got, expected)

    def test_each_period_ends_as_the_moon_changes_sign(self):
        start = _jd(datetime(2026, 9, 1, tzinfo=timezone.utc))
        stays = _moon_sign_stays(start, start + 10)
        for (_, _, exit_a), (_, entry_b, _) in zip(stays, stays[1:]):
            assert abs(exit_a - entry_b) * 1440 < 1

    def test_reports_local_times_and_what_began_each_period(self):
        r = json.loads(moon_void_periods(start_date="2026-09-27", end_date="2026-10-04", **LA))
        assert r["timezone"] == "America/Los_Angeles"
        first = r["periods"][0]
        assert set(first) == {"moon_in", "void_from", "void_until", "enters", "hours", "began_with"}
        assert first["began_with"].startswith("Moon ") or "void for the whole sign" in first["began_with"]
        for p in r["periods"]:
            assert p["void_from"] <= p["void_until"]
            assert p["hours"] >= 0

    def test_outer_planets_can_only_shorten_a_void_period(self):
        trad = json.loads(moon_void_periods(start_date="2026-09-01", end_date="2026-09-30", **LA))["periods"]
        modern = json.loads(moon_void_periods(start_date="2026-09-01", end_date="2026-09-30",
                                              include_outer_planets=True, **LA))["periods"]
        by_end = {p["void_until"]: p for p in trad}
        for p in modern:
            if p["void_until"] in by_end:
                assert p["void_from"] >= by_end[p["void_until"]]["void_from"]

    def test_void_now_is_null_or_a_listed_period(self):
        r = json.loads(moon_void_periods(**LA))
        assert r["void_now"] is None or r["void_now"] in r["periods"]

    def test_limits_the_range(self):
        r = json.loads(moon_void_periods(start_date="2026-01-01", end_date="2026-12-31"))
        assert r["error"] == "Range too long"


# Published 2026 eclipses: greatest eclipse (UTC) and zodiac degree.
ECLIPSES_2026 = [
    ("annular solar eclipse", "2026-02-17 12:12", "28°50' Aquarius"),
    ("total lunar eclipse", "2026-03-03 11:34", "12°51' Virgo"),
    ("total solar eclipse", "2026-08-12 17:46", "20°02' Leo"),
    ("partial lunar eclipse", "2026-08-28 04:13", "4°51' Pisces"),
]


class TestLunationsAndEclipses:
    def test_finds_2026s_eclipses_at_their_published_times_and_degrees(self):
        r = json.loads(lunations_and_eclipses(start_date="2026-01-01", end_date="2026-12-31", **NYC))
        eclipses = [e for e in r["events"] if "eclipse" in e["event"]]
        assert [e["event"] for e in eclipses] == [kind for kind, _, _ in ECLIPSES_2026]
        tz = __import__("zoneinfo").ZoneInfo("America/New_York")
        for e, (_, utc, position) in zip(eclipses, ECLIPSES_2026):
            local = datetime.strptime(e["exact"], "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            published = datetime.strptime(utc, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            assert abs(local - published) <= timedelta(minutes=2), e
            assert e["position"] == position

    def test_a_year_has_twelve_or_thirteen_of_each_lunation(self):
        r = json.loads(lunations_and_eclipses(start_date="2026-01-01", end_date="2026-12-31", **NYC))
        kinds = [e["event"] for e in r["events"]]
        assert 12 <= kinds.count("new moon") <= 13
        assert 12 <= kinds.count("full moon") <= 13
        assert [e["exact"] for e in r["events"]] == sorted(e["exact"] for e in r["events"])

    def test_relates_each_event_to_a_birth_chart(self):
        r = json.loads(lunations_and_eclipses(
            start_date="2026-08-01", end_date="2026-08-31", date_time="1990-06-15 14:30", **NYC))
        assert r["house_system"] == "whole_sign"
        solar = next(e for e in r["events"] if e["event"] == "total solar eclipse")
        assert 1 <= solar["natal_house"] <= 12
        assert all(" natal " in c for c in solar["contacts"])

    def test_needs_a_birthplace_with_a_birth_time(self):
        r = json.loads(lunations_and_eclipses(date_time="1990-06-15 14:30"))
        assert r["error"] == "Invalid input"

    def test_without_a_place_reports_in_the_servers_timezone(self):
        r = json.loads(lunations_and_eclipses(start_date="2026-01-01", end_date="2026-01-31"))
        assert r["timezone"]
        assert "natal_house" not in r["events"][0]


def test_tools_are_registered_with_directive_descriptions():
    from astro_mcp.server import mcp
    import asyncio
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    for name in ("planetary_hours", "moon_void_periods", "lunations_and_eclipses"):
        assert name in tools
        assert "never" in tools[name].description.lower()
