#!/usr/bin/env python3
"""Script to capture reference fixtures from immanuel for testing.

This script generates verified JSON output from immanuel that can be used
as fixtures for MCP tool testing. Each fixture should be manually verified
against astro.com before committing.

Fixtures are written in the compact tool-output format (see
astro_mcp.utils.compact_chart_json).
"""

import json

from immanuel import charts

from astro_mcp.config import get_config
from astro_mcp.tools.transit import _transits_for_date
from astro_mcp.utils import (
    assign_natal_houses_to_transit_objects,
    calculate_transit_to_natal_aspects,
    compact_chart_json,
    extract_aspect_details,
)

FIXTURES_DIR = "tests/fixtures"

# Reference test data points
REFERENCE_DATA = [
    {
        "label": "reference_a_nyc",
        "date_time": "1990-06-15 14:30",
        "latitude": 40.74,
        "longitude": -73.99,
    },
    {
        "label": "reference_b_sydney",
        "date_time": "1985-01-28 03:15",
        "latitude": -33.87,
        "longitude": 151.21,
    },
    {
        "label": "reference_c_london",
        "date_time": "2000-03-20 09:00",
        "latitude": 51.51,
        "longitude": -0.13,
    },
]

MAJOR_OBJECTS = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                 "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Chiron"]

# The transit fixture uses the chart from tests/test_transit.py's
# reference_a (kept under its historical "reference_a_nyc" filename).
TRANSIT_REFERENCE = {
    "label": "reference_a_nyc",
    "date_time": "1984-05-10 20:44",
    "latitude": 34.02,
    "longitude": -118.40,
}


def save_fixture(filename: str, content: str) -> None:
    """Write a fixture file and print a summary."""
    with open(f"{FIXTURES_DIR}/{filename}", "w") as f:
        f.write(content)

    data = json.loads(content)
    print(f"Saved: {FIXTURES_DIR}/{filename} ({len(content)} chars)")
    print(f"  Objects: {len(data.get('objects', {}))}")
    print(f"  Houses: {len(data.get('houses', {}))}")
    print(f"  Aspects: {len(data.get('aspects', []))}")


def capture_natal_fixture(data: dict, house_system: str = "whole_sign") -> str:
    """Capture a natal chart fixture in compact format."""
    native = charts.Subject(
        date_time=data["date_time"].replace("T", " "),
        latitude=data["latitude"],
        longitude=data["longitude"],
    )

    config = get_config(house_system)
    natal = charts.Natal(native, config=config)

    return compact_chart_json(
        natal,
        chart_type="natal",
        date_time=data["date_time"].replace("T", " "),
        house_system=house_system,
        aspects=extract_aspect_details(natal),
    )


def capture_solar_return_fixture(data: dict, year: int) -> str:
    """Capture a solar return chart fixture in compact format."""
    native = charts.Subject(
        date_time=data["date_time"].replace("T", " "),
        latitude=data["latitude"],
        longitude=data["longitude"],
    )

    config = get_config("whole_sign")
    solar_return_chart = charts.SolarReturn(native=native, year=year, config=config)

    return compact_chart_json(
        solar_return_chart,
        chart_type="solar_return",
        date_time=data["date_time"].replace("T", " "),
        house_system="whole_sign",
        aspects=extract_aspect_details(solar_return_chart),
        extra={
            "solar_return_year": year,
            "solar_return_date_time": solar_return_chart.solar_return_date_time.datetime.isoformat(),
        },
    )


def capture_progressed_fixture(data: dict, target_date: str) -> str:
    """Capture a progressed chart fixture in compact format."""
    native = charts.Subject(
        date_time=data["date_time"].replace("T", " "),
        latitude=data["latitude"],
        longitude=data["longitude"],
    )

    config = get_config("whole_sign")
    natal = charts.Natal(native, config=config)
    progressed = charts.Progressed(
        native=native,
        date_time=target_date,
        aspects_to=natal,
        config=config,
    )

    return compact_chart_json(
        progressed,
        chart_type="progressed",
        date_time=data["date_time"].replace("T", " "),
        house_system="whole_sign",
        aspects=extract_aspect_details(progressed),
        extra={
            "target_date": target_date,
            "progressed_date_time": progressed.progressed_date_time.datetime.isoformat(),
        },
    )


def capture_transit_fixture(data: dict, transit_date_time: str) -> str:
    """Capture a transit chart fixture in compact format."""
    native = charts.Subject(
        date_time=data["date_time"].replace("T", " "),
        latitude=data["latitude"],
        longitude=data["longitude"],
    )

    config = get_config("whole_sign")
    natal = charts.Natal(native, config=config)
    transit = _transits_for_date(
        transit_date_time, data["latitude"], data["longitude"], natal, config
    )

    natal_positions = {
        o.name: o.longitude.raw % 360
        for o in natal.objects.values()
        if o.name in MAJOR_OBJECTS
    }

    return compact_chart_json(
        transit,
        chart_type="transit",
        date_time=transit_date_time,
        house_system="whole_sign",
        house_overrides=assign_natal_houses_to_transit_objects(transit, natal, "whole_sign"),
        houses_chart=natal,
        aspects=calculate_transit_to_natal_aspects(transit, natal_positions),
    )


def main() -> None:
    """Generate all fixtures."""
    print("Generating reference fixtures...")

    by_label = {ref["label"]: ref for ref in REFERENCE_DATA}

    for ref in REFERENCE_DATA:
        print(f"\n{'=' * 60}")
        print(f"Capturing natal: {ref['label']}")
        print(f"{'=' * 60}")
        save_fixture(
            f"{ref['label']}_whole_sign.json",
            capture_natal_fixture(ref),
        )

    print(f"\n{'=' * 60}")
    print("Capturing solar return / progressed / transit (reference A)")
    print(f"{'=' * 60}")
    ref_a = by_label["reference_a_nyc"]

    save_fixture(
        "reference_a_nyc_solar_return_2025.json",
        capture_solar_return_fixture(ref_a, 2025),
    )
    save_fixture(
        "reference_a_nyc_progressed_2025.json",
        capture_progressed_fixture(ref_a, "2025-06-15 14:30"),
    )
    save_fixture(
        "reference_a_nyc_transit_2025.json",
        capture_transit_fixture(TRANSIT_REFERENCE, "2025-06-15 14:30"),
    )


if __name__ == "__main__":
    main()
