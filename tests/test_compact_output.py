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
from astro_mcp.tools.transit import NATAL_FIELDS, create_transit_chart, list_upcoming_transits

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


class TestSizeTiersPreferLosslessCompaction:
    """Dropping aspects must be a last resort, not a first one.

    The two size tiers used to run in the wrong order: real Moon and Mercury
    spans were discarded before the lossless positional encoding was tried,
    so data was lost to save bytes a cheaper encoding would have saved anyway.
    """

    BIRTH = dict(date_time="1984-05-10T20:44:00", latitude=37.77, longitude=-122.42)

    def test_a_small_range_stays_readable(self):
        # Under budget: keep named keys, which read better.
        data = json.loads(list_upcoming_transits(**self.BIRTH))
        assert "span_fields" not in data
        assert isinstance(data["transits"][0], dict)
        assert "omitted" not in data

    def test_an_oversized_range_compacts_before_it_drops(self):
        # Seven months: over the budget as named objects, but small enough
        # that positional encoding alone brings it back under.
        data = json.loads(list_upcoming_transits(
            start_date="2026-09-25", end_date="2027-03-25", **self.BIRTH))
        # Compaction happened...
        assert data["span_fields"] == NATAL_FIELDS
        assert isinstance(data["transits"][0], list)
        # ...and was enough, so nothing was thrown away.
        assert "omitted" not in data
        kept = {row[2] for row in data["transits"]}
        assert "Moon" in kept or "Mercury" in kept

    def test_only_a_huge_range_omits_fast_objects(self):
        data = json.loads(list_upcoming_transits(
            start_date="2026-09-25", end_date="2027-09-25", **self.BIRTH))
        assert "span_fields" in data, "should compact before omitting"
        assert "omitted" in data
        # The Moon is excluded earlier, by the fast-body horizon, so only
        # Mercury is left for the budget tier to drop.
        assert data["omitted"]["objects"] == ["Mercury"]
        assert data["omitted"]["spans"]["Mercury"] > 0
        assert "object_filter" in data["omitted"]["hint"]

    def test_an_explicit_filter_is_respected(self):
        data = json.loads(list_upcoming_transits(
            object_filter="Moon", start_date="2026-09-25", end_date="2027-09-25",
            **self.BIRTH))
        assert "omitted" not in data
