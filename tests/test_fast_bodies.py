"""Sampling and scope for fast-moving bodies.

The Moon travels ~13 degrees a day, so at the default 1.5 degree orb a lunar
aspect lasts about five hours. Once-a-day sampling missed most of them and
reported the survivors as day-long spans -- a short list that looked like a
filter but was an artefact.
"""
import json

import pytest

from astro_mcp.tools.transit import (
    FAST_BODIES, FAST_BODY_HORIZON_DAYS, list_upcoming_transits,
)

BIRTH = dict(date_time="1984-05-10T20:44:00", latitude=37.77, longitude=-122.42)


def rows(data):
    """Spans as dicts, whichever encoding was used."""
    if "span_fields" in data:
        return [dict(zip(data["span_fields"], r)) for r in data["transits"]]
    return data["transits"]


def moon_spans(data):
    return [r for r in rows(data) if r["from_object"] == "Moon"]


@pytest.fixture(scope="module")
def week():
    return json.loads(list_upcoming_transits(
        start_date="2026-09-25", end_date="2026-10-02", **BIRTH))


@pytest.fixture(scope="module")
def two_months():
    return json.loads(list_upcoming_transits(**BIRTH))


class TestShortRangeSamplesTheMoonProperly:

    def test_the_moon_is_included_within_the_horizon(self, week):
        assert moon_spans(week), "no lunar contacts in a one-week scan"
        assert "excluded" not in week

    def test_it_finds_contacts_a_daily_sample_would_miss(self, week):
        # At ~13 deg/day and a 1.5 deg orb, a week holds far more than the
        # handful that happen to straddle midnight.
        assert len(moon_spans(week)) > 7, (
            f"only {len(moon_spans(week))} lunar spans in a week; "
            "sub-daily sampling is not running"
        )

    def test_lunar_spans_carry_exact_moments(self, week):
        assert any(s.get("exact") for s in moon_spans(week))


class TestLongRangeExcludesTheMoon:
    def test_the_moon_is_left_out_beyond_the_horizon(self, two_months):
        assert not moon_spans(two_months)

    def test_and_says_so_rather_than_silently_dropping_her(self, two_months):
        # Silence here would look identical to "no lunar transits", which is
        # never true over two months.
        assert "Moon" in two_months["excluded"]["objects"]
        assert "object_filter" in two_months["excluded"]["hint"]

    def test_slower_bodies_are_untouched(self, two_months):
        movers = {r["from_object"] for r in rows(two_months)}
        assert {"Sun", "Saturn"} <= movers


class TestAskingForTheMoonOverrides:
    def test_an_explicit_filter_brings_her_back(self):
        data = json.loads(list_upcoming_transits(object_filter="Moon", **BIRTH))
        assert moon_spans(data), "explicit request for the Moon returned none"
        assert "excluded" not in data

    def test_the_horizon_is_a_documented_constant(self):
        assert "Moon" in FAST_BODIES
        assert FAST_BODY_HORIZON_DAYS > 0


class TestOversizeIsReported:
    def test_a_filter_that_defeats_omission_still_warns(self):
        # object_filter disables the omission tier by design; the caller must
        # still learn the client may truncate the result.
        data = json.loads(list_upcoming_transits(
            start_date="2026-09-25", end_date="2027-09-25",
            object_filter="Sun,Moon,Mercury,Venus,Mars,Jupiter,Saturn,Uranus,Neptune,Pluto,Chiron",
            **BIRTH))
        assert "warning" in data
        assert "truncated" in data["warning"]
