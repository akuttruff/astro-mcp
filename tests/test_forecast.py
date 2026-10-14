"""Month and year digests: ranked, labelled, bounded, and in agreement with the transit scan."""
import json
import time

import pytest

from astro_mcp.tools.forecast import (
    ASPECT_WEIGHT, MONTH_HEADLINES, SLOWNESS, WEEK_HEADLINES, YEAR_HEADLINES, forecast_month, forecast_week, forecast_year,
)
from astro_mcp.tools.transit import list_upcoming_transits

BIRTH = dict(date_time="1984-05-10T20:44:00", latitude=37.77, longitude=-122.42)
FAST = {"Moon", "Sun", "Mercury", "Venus"}


@pytest.fixture(scope="module")
def week():
    return json.loads(forecast_week(start_date="2026-10-12", **BIRTH))


@pytest.fixture(scope="module")
def month():
    return json.loads(forecast_month(month="2026-10", **BIRTH))


@pytest.fixture(scope="module")
def year():
    started = time.perf_counter()
    data = json.loads(forecast_year(start_date="2026-10-02", **BIRTH))
    data["_seconds"] = time.perf_counter() - started
    return data


def test_a_month_is_the_calendar_month_with_the_natal_chart_attached(month):
    assert month["forecast"] == "month"
    assert month["range"] == {"start": "2026-10-01", "end": "2026-10-31"}
    assert {"Asc", "MC", "Saturn"} <= set(month["natal"]["positions"])
    assert month["natal"]["chart_ruler"] in {"Jupiter", "Mars", "Venus", "Mercury", "Moon", "Sun", "Saturn"}


def test_headlines_are_ranked_slow_first_and_fast_planets_are_left_out(month):
    heads = month["headline_transits"]
    assert 0 < len(heads) <= MONTH_HEADLINES
    weights = [h["weight"] for h in heads]
    assert weights == sorted(weights, reverse=True)
    assert not {h["transiting"] for h in heads} & FAST
    for h in heads:
        expected = SLOWNESS[h["transiting"]] * ASPECT_WEIGHT[h["aspect"]]
        assert h["weight"] in (expected, expected * 2)  # doubled for Sun/Moon/Asc/MC and the chart ruler
        assert h["label"].startswith(("exact ", "tightest "))
        assert f"transiting {h['transiting']} {h['from_position']} {h['aspect'].lower()} natal {h['natal']} {h['to_position']}" in h["label"]


def test_the_exact_dates_are_the_transit_scans_dates(month):
    # Same ephemeris, same refinement: a headline's exact moment must match what
    # list_upcoming_transits reports for that very contact.
    checked = 0
    for h in month["headline_transits"]:
        if not h["exact"]:
            continue
        scan = json.loads(list_upcoming_transits(
            start_date="2026-10-01", end_date="2026-10-31", object_filter=h["transiting"], **BIRTH,
        ))
        rows = scan["transits"] if "span_fields" not in scan else [dict(zip(scan["span_fields"], r)) for r in scan["transits"]]
        match = [r for r in rows if r["to_object"] == h["natal"] and r["type"] == h["aspect"] and r["exact"] == h["exact"]]
        assert match, h["label"]
        checked += 1
        if checked == 3:
            break
    assert checked


def test_a_month_lists_its_lunations_stations_and_ingresses_in_the_chart(month):
    assert len(month["lunations"]) >= 2
    for e in month["lunations"]:
        assert e["exact"].startswith("2026-10")
        assert "natal_house" in e and e["label"].startswith("2026-10")
    for s in month["stations"]:
        assert s["station"] in {"retrograde", "direct"} and s["exact"].startswith("2026-10")
    for i in month["ingresses"]:
        assert i["exact"].startswith("2026-10") and "enters" in i["label"]
    assert month["left_out"]["objects"] == ["Moon", "Sun", "Mercury", "Venus"]


def test_a_year_has_a_skeleton_and_themes_and_stays_within_budget(year):
    assert year["forecast"] == "year"
    assert len(year["by_month"]) in (12, 13)
    assert all(len(v) <= 3 for v in year["by_month"].values())
    assert any(year["by_month"].values()), "no month got an event"
    assert 0 < len(year["headline_transits"]) <= YEAR_HEADLINES
    assert not {h["transiting"] for h in year["headline_transits"]} & (FAST | {"Mars"})
    assert all(k.startswith("natal house ") for k in year["themes"])
    assert all("eclipse" in e["event"] for e in year["eclipses"])
    assert len(json.dumps(year, separators=(",", ":"))) < 25000
    assert year["_seconds"] < 15, f"a year took {year['_seconds']:.1f}s"


def test_retrograde_passes_are_numbered(year):
    passes = [h for h in year["headline_transits"] if h["pass"]]
    if passes:  # a slow planet in orb twice across a year is the common case, not a guaranteed one
        assert all("pass " in h["label"] and " of " in h["pass"] for h in passes)


def test_a_week_is_seven_days_with_the_fast_planets_but_not_the_moon(week):
    assert week["forecast"] == "week"
    assert week["range"] == {"start": "2026-10-12", "end": "2026-10-18"}
    heads = week["headline_transits"]
    assert 0 < len(heads) <= WEEK_HEADLINES
    # The week's events first (exact within it), then the backdrop; weight ranks within each group.
    events = [h for h in heads if h["exact"]]
    backdrop = [h for h in heads if not h["exact"]]
    assert heads == events + backdrop
    for group in (events, backdrop):
        weights = [h["weight"] for h in group]
        assert weights == sorted(weights, reverse=True)
    assert events, "a week with nothing exact in it: pick another week"
    assert any(h["transiting"] in {"Sun", "Mercury", "Venus", "Mars"} for h in events)
    assert "Moon" not in {h["transiting"] for h in heads}
    assert week["left_out"]["objects"] == ["Moon"]
    for h in heads:
        expected = SLOWNESS[h["transiting"]] * ASPECT_WEIGHT[h["aspect"]]
        assert h["weight"] in (expected, expected * 2)
        assert h["start"] >= "2026-10-12" and h["end"] <= "2026-10-18"
    assert "lunations" in week and "eclipses" not in week
    assert all("2026-10-12" <= e["exact"][:10] <= "2026-10-18" for e in week["lunations"] + week["stations"] + week["ingresses"])
    # The same week, scanned contact by contact: every headline is a span the scan knows.
    scan = json.loads(list_upcoming_transits(start_date="2026-10-12", end_date="2026-10-18", max_orb=1.5, **BIRTH))
    spans = {(r["from_object"], r["to_object"], r["type"]) for r in scan["transits"]}
    assert all((h["transiting"], h["natal"], h["aspect"]) in spans for h in heads)


def test_a_contact_in_orb_without_perfecting_says_when_it_does(week, month):
    for data, first, last in ((week, "2026-10-12", "2026-10-18"), (month, "2026-10-01", "2026-10-31")):
        for h in data["headline_transits"]:
            if h["exact"]:
                assert h["nearest_exact"] == h["exact"]
            elif h["nearest_exact"]:
                assert not (first <= h["nearest_exact"][:10] <= last), h["label"]
                assert f"exact {h['nearest_exact']}" in h["label"]
            else:
                assert "not exact within" in h["label"]
            if h["exact"] or h["start"] == h["end"]:
                assert h["movement"] is None
            else:
                assert h["movement"] in {"applying", "separating"} and h["label"].endswith(h["movement"])
    assert any(h["nearest_exact"] and not h["exact"] for h in week["headline_transits"]), "no backdrop contact this week"


def test_bad_input_is_an_error_not_a_crash():
    assert "error" in json.loads(forecast_week(start_date="next monday", **BIRTH))
    assert "error" in json.loads(forecast_month(month="October", **BIRTH))
    assert "error" in json.loads(forecast_year(start_date="soon", **BIRTH))
    assert "error" in json.loads(forecast_month(month="2026-10", date_time="1984-05-10 20:44"))
