"""Payload compaction.

MCP clients carry these results in a model's context, and some truncate long
tool output outright, so wasted bytes are not merely untidy -- they can cost
the model the end of a chart. These tests pin the savings that cost nothing
in information: no indentation, no ASCII escaping, and no spurious float
precision.
"""
import json

import pytest

from astro_mcp.tools.natal import create_natal_chart
from astro_mcp.tools.transit import create_transit_chart, list_upcoming_transits

BIRTH = dict(date_time="1984-05-10T20:44:00", latitude=37.77, longitude=-122.42)


@pytest.fixture(scope="module")
def natal():
    return create_natal_chart(house_system="whole_sign", **BIRTH)


def test_output_is_not_pretty_printed(natal):
    # indent=2 added roughly 30% to every chart and told the model nothing.
    assert "\n" not in natal
    assert ", " not in natal
    json.loads(natal)  # still valid


def test_degree_symbols_are_literal(natal):
    # ensure_ascii escapes each degree sign to six bytes of °.
    assert "\\u00b0" not in natal
    assert "°" in natal


def test_orbs_carry_no_spurious_precision(natal):
    for aspect in json.loads(natal)["aspects"]:
        orb = aspect["orb"]
        if orb is None:
            continue
        assert round(orb, 2) == orb, f"unrounded orb: {orb}"


def test_chart_keeps_its_full_structure(natal):
    chart = json.loads(natal)
    assert set(chart) >= {
        "chart_type", "date_time", "house_system",
        "objects", "houses", "aspects", "aspect_patterns", "diurnal",
    }
    assert len(chart["houses"]) == 12
    assert chart["objects"]["Sun"]["position"]
    assert chart["objects"]["Sun"]["longitude"]


def test_a_natal_chart_fits_a_modest_budget(natal):
    # Was ~11KB pretty-printed, and 50KB before compact_chart_json.
    assert len(natal) < 9000, f"natal chart grew to {len(natal)} bytes"


@pytest.mark.parametrize("result", [
    create_transit_chart(**BIRTH),
    list_upcoming_transits(**BIRTH),
])
def test_transit_tools_are_compact_too(result):
    assert "\n" not in result
    assert "\\u00b0" not in result
    json.loads(result)
