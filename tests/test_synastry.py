"""Synastry: cross-chart aspects between two people.

The tool advertised "aspects from Person A's planets to Person B's planets"
and returned a sentence saying so, with no aspects. Separately, the aspects
it did return were composite-to-B presented as the composite's own -- hence
impossible rows like "Asc conjunct Asc".
"""
import json

import pytest
from unittest.mock import MagicMock

from astro_mcp.tools import synastry

A = dict(date_time_a="1984-05-10 20:44", latitude_a="34.02", longitude_a="-118.40")
B = dict(date_time_b="1990-11-03 09:15", latitude_b="40.71", longitude_b="-74.01")


@pytest.fixture(scope="module")
def tool():
    captured = {}
    mcp = MagicMock()
    mcp.add_tool.side_effect = lambda fn, **kw: captured.update(fn=fn)
    synastry.register(mcp)
    return captured["fn"]


@pytest.fixture(scope="module")
def result(tool):
    return json.loads(tool(**A, **B))


class TestCrossAspects:
    def test_they_exist_at_all(self, result):
        assert isinstance(result["cross_aspects"], list)
        assert result["cross_aspects"], "no cross-aspects returned"

    def test_each_names_the_chart_on_both_sides(self, result):
        for aspect in result["cross_aspects"]:
            assert aspect["from_chart"] == "person_a"
            assert aspect["to_chart"] == "person_b"

    def test_they_really_are_a_to_b(self, result):
        # Check one against the raw positions rather than trusting the label.
        objects_a = result["person_a"]["objects"]
        objects_b = result["person_b"]["objects"]
        for aspect in result["cross_aspects"]:
            a = objects_a.get(aspect["from_object"])
            b = objects_b.get(aspect["to_object"])
            if not a or not b:
                continue
            separation = abs(a["longitude"] - b["longitude"]) % 360
            if separation > 180:
                separation = 360 - separation
            expected = {"Conjunction": 0, "Sextile": 60, "Square": 90,
                        "Trine": 120, "Opposition": 180}[aspect["type"]]
            assert abs(separation - expected) == pytest.approx(aspect["orb"], abs=0.02)

    def test_they_are_ordered_tightest_first(self, result):
        orbs = [a["orb"] for a in result["cross_aspects"]]
        assert orbs == sorted(orbs)


class TestCompositeAspectsAreInternal:
    def test_no_object_aspects_itself(self, result):
        # "Asc conjunct Asc" is impossible within one chart and was the
        # symptom of composite-to-B aspects being mislabelled.
        for aspect in result["composite_chart"]["aspects"]:
            assert aspect["from_object"] != aspect["to_object"], aspect

    def test_the_composite_claims_no_moment(self, result):
        # A midpoint construct is not cast for person A's birth time.
        assert not result["composite_chart"].get("date_time")


class TestBothChartsAreReturned:
    def test_each_person_carries_their_positions(self, result):
        for person in ("person_a", "person_b"):
            assert result[person]["objects"]["Sun"]["longitude"]
            assert result[person]["date_time"]


class TestPayload:
    def test_it_is_compact(self, tool):
        out = tool(**A, **B)
        assert "\n" not in out
        assert "\\u00b0" not in out
