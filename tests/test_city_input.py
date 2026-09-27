"""A place name works on every chart tool, not only natal.

create_natal_chart accepted a city; the other four required coordinates, so
a caller that learned "city works" from one tool failed on the rest.
Geocoding is stubbed here so the suite never depends on the network.
"""
import json

import pytest

import astro_mcp.geocode as geocode
from astro_mcp.tools.natal import create_natal_chart
from astro_mcp.tools.progressed import create_progressed_chart
from astro_mcp.tools.solar_return import create_solar_return
from astro_mcp.tools.transit import create_transit_chart, list_upcoming_transits

LA = (34.0522, -118.2437, "Los Angeles, California, United States")


@pytest.fixture(autouse=True)
def offline_geocoder(monkeypatch):
    calls = []

    def fake(city, state=None, country=None):
        calls.append((city, state, country))
        return LA

    monkeypatch.setattr(geocode, "resolve_location", fake)
    return calls


BIRTH = "1984-05-10 20:44"

TOOLS = {
    "natal": lambda **kw: create_natal_chart(date_time=BIRTH, **kw),
    "progressed": lambda **kw: create_progressed_chart(date_time=BIRTH, target_date="2026-09-26 12:00", **kw),
    "solar_return": lambda **kw: create_solar_return(date_time=BIRTH, year=2026, **kw),
    "transit_chart": lambda **kw: create_transit_chart(date_time=BIRTH, **kw),
    "upcoming": lambda **kw: list_upcoming_transits(date_time=BIRTH, **kw),
}


@pytest.mark.parametrize("name", TOOLS)
def test_every_tool_accepts_a_city(name, offline_geocoder):
    data = json.loads(TOOLS[name](city="Los Angeles", state="CA"))
    assert "error" not in data, data
    assert offline_geocoder == [("Los Angeles", "CA", None)]


@pytest.mark.parametrize("name", TOOLS)
def test_coordinates_still_win_and_skip_the_geocoder(name, offline_geocoder):
    data = json.loads(TOOLS[name](latitude="34.02", longitude="-118.40"))
    assert "error" not in data, data
    assert offline_geocoder == []


def test_a_chart_with_no_location_explains_what_it_needs():
    data = json.loads(create_transit_chart(date_time=BIRTH))
    assert data["error"] == "Invalid location"
    assert "city" in data["detail"]


def test_natal_reports_what_the_place_name_resolved_to():
    data = json.loads(create_natal_chart(date_time=BIRTH, city="Los Angeles"))
    assert data["matched_location"] == LA[2]
    assert data["latitude"] == pytest.approx(LA[0], abs=1e-3)
