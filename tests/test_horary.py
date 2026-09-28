"""Tests for the horary tools.

The rules of judgment are checked with invented planetary motion, one
scenario per rule, so each can be set up exactly. Every Ptolemaic aspect is a
multiple of 30 degrees, so an exact aspect needs the same degree within the
sign. Planets not in a scenario are parked at 2 degrees of a sign, which
significators starting at 5 degrees or later never pass: they stay out of
the way.

The chart itself, and the tools end to end, run on immanuel's real ephemeris.
"""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from astro_mcp.tools.horary import (
    PLANETS,
    Contact,
    cast,
    cast_horary_chart,
    considerations,
    essential_dignity,
    judge,
    judge_question,
    last_perfection,
    next_perfection,
    next_sign_change,
    receptions,
    traditional_timing,
    ImmanuelEphemeris,
)

LA = {"latitude": "34.02", "longitude": "-118.40"}


class FakeEphemeris:
    """Planets on given paths: {name: lon(t)}, t in days. Speed by differencing."""

    def __init__(self, paths: dict):
        # Parked at 2° of a sign: significators start at 5° or later and move
        # forward, so they reach their sign's end before ever meeting these.
        idle = {p: (lambda t, p=p: 2.0 + 30 * PLANETS.index(p)) for p in PLANETS}
        self.paths = {**idle, **paths}

    def lon(self, planet, jd):
        return self.paths[planet](jd) % 360

    def speed(self, planet, jd):
        h = 1e-4
        return (self.paths[planet](jd + h) - self.paths[planet](jd - h)) / (2 * h)


def when(jd):
    return f"at t={jd:.2f}"


class TestPerfectionSearch:
    def test_finds_an_applying_trine(self):
        eph = FakeEphemeris({"Mars": lambda t: 10 + 0.5 * t, "Jupiter": lambda t: 135.0})
        hit = next_perfection(eph, "Mars", "Jupiter", 0, 30)
        assert hit.aspect == "trine"
        assert hit.jd == pytest.approx(10, abs=1e-3)

    def test_finds_an_opposition_and_a_conjunction(self):
        eph = FakeEphemeris({"Moon": lambda t: 5 + 13 * t, "Saturn": lambda t: 190.0})
        assert next_perfection(eph, "Moon", "Saturn", 0, 1).aspect == "opposition"
        eph = FakeEphemeris({"Moon": lambda t: 5 + 13 * t, "Saturn": lambda t: 10.0})
        assert next_perfection(eph, "Moon", "Saturn", 0, 1).aspect == "conjunction"

    def test_looks_back_for_a_separation(self):
        eph = FakeEphemeris({"Moon": lambda t: 12 + 13 * t, "Saturn": lambda t: 10.0})
        hit = last_perfection(eph, "Moon", "Saturn", -2, 0)
        assert hit.aspect == "conjunction"
        assert hit.jd == pytest.approx(-2 / 13, abs=1e-3)

    def test_sign_change(self):
        eph = FakeEphemeris({"Mars": lambda t: 25 + 1.0 * t})
        assert next_sign_change(eph, "Mars", 0) == pytest.approx(5, abs=1e-3)


class TestJudgment:
    def test_direct_perfection(self):
        eph = FakeEphemeris({"Mars": lambda t: 10 + 0.5 * t, "Jupiter": lambda t: 135.0})
        j = judge(eph, "Mars", "Jupiter", 0, when)
        assert j.verdict == "perfects"
        assert "easily" in j.summary
        assert j.perfection.aspect == "trine"

    def test_a_square_perfects_with_difficulty(self):
        eph = FakeEphemeris({"Mars": lambda t: 10 + 0.5 * t, "Jupiter": lambda t: 105.0})
        j = judge(eph, "Mars", "Jupiter", 0, when)
        assert j.verdict == "perfects" and "difficulty" in j.summary

    def test_prohibition(self):
        eph = FakeEphemeris({
            "Mars": lambda t: 10 + 0.5 * t,       # trines Jupiter at 15° Aries, t=10
            "Jupiter": lambda t: 135.0,           # 15° Leo
            "Venus": lambda t: 72.0,              # 12° Gemini: Mars sextiles her first, t=4
        })
        j = judge(eph, "Mars", "Jupiter", 0, when)
        assert j.verdict == "prohibited"
        assert j.via == "Venus"
        assert "prohibition" in j.testimonies[0]

    def test_the_moon_passing_a_significator_does_not_prohibit(self):
        eph = FakeEphemeris({
            "Mars": lambda t: 10 + 0.5 * t,       # trines Jupiter at t=10
            "Jupiter": lambda t: 135.0,
            "Moon": lambda t: 6 + 13 * t,         # conjoins Mars within hours
        })
        assert judge(eph, "Mars", "Jupiter", 0, when).verdict == "perfects"

    def test_translation_of_light(self):
        eph = FakeEphemeris({
            "Saturn": lambda t: 10.0,             # 10° Aries
            "Jupiter": lambda t: 110.0,           # 20° Cancer: never meets Saturn
            "Moon": lambda t: 12 + 13 * t,        # just left Saturn, squares Jupiter at 20° Aries
        })
        j = judge(eph, "Saturn", "Jupiter", 0, when)
        assert j.verdict == "perfects by translation"
        assert j.via == "Moon"

    def test_collection_of_light(self):
        eph = FakeEphemeris({
            "Mars": lambda t: 10 + 0.6 * t,       # 10° Aries
            "Venus": lambda t: 72 + 1.2 * t,      # 12° Gemini, pulling away from Mars
            "Saturn": lambda t: 140.0,            # 20° Leo, slower than both
        })
        j = judge(eph, "Mars", "Venus", 0, when)
        assert j.verdict == "perfects by collection"
        assert j.via == "Saturn"

    def test_refranation(self):
        eph = FakeEphemeris({
            "Mercury": lambda t: 10 + t - t * t / 6,   # stations at t=3, 11.5° Aries
            "Jupiter": lambda t: 133.0,                # trine needs 13° Aries
        })
        j = judge(eph, "Mercury", "Jupiter", 0, when)
        assert j.verdict == "refranation"
        assert j.via == "Mercury"
        assert "retrograde" in j.testimonies[0]

    def test_no_perfection_when_already_separating(self):
        eph = FakeEphemeris({"Mars": lambda t: 10 + 0.5 * t, "Jupiter": lambda t: 125.0})
        j = judge(eph, "Mars", "Jupiter", 0, when)
        assert j.verdict == "no perfection"

    def test_traditional_timing_counts_degrees_in_the_units_of_sign_and_house(self):
        eph = FakeEphemeris({"Mars": lambda t: 10 + 0.5 * t, "Jupiter": lambda t: 135.0})
        contact = Contact("Mars", "Jupiter", "trine", 10)
        timing = traditional_timing(eph, contact, 0, {"Mars": 1})
        assert timing["degrees_to_perfection"] == 5
        assert timing["moving_planet"] == "Mars"
        assert timing["sign_quality"] == "cardinal" and timing["house_place"] == "angular"
        assert timing["reading"] == "about 5 days"
        mixed = traditional_timing(eph, contact, 0, {"Mars": 12})
        assert mixed["reading"] == "about 5 days or months"


class TestDignityAndReception:
    def test_peregrine_means_no_essential_dignity_whatever_the_element(self):
        # Mercury in Libra: immanuel's "in rulership element" would spare it.
        flags = SimpleNamespace(in_rulership_element=True)
        assert essential_dignity(flags) == {"held": ["peregrine"], "score": -5}

    def test_scores_dignities_and_debilities_lillys_way(self):
        flags = SimpleNamespace(term_ruler=True, face_ruler=True)
        assert essential_dignity(flags) == {"held": ["term", "face"], "score": 3}
        flags = SimpleNamespace(fall=True)
        assert essential_dignity(flags) == {"held": ["fall", "peregrine"], "score": -9}

    def test_mutual_reception_by_domicile_and_by_exaltation(self):
        positions = {"Moon": 18.0, "Mars": 119.0, "Sun": 184.0, "Saturn": 11.0}  # Moon Aries, Mars Cancer
        assert "mutual reception" in receptions(positions, "Moon", "Mars")[0]
        assert "exaltation" in receptions(positions, "Sun", "Saturn")[0]  # Sun Libra, Saturn Aries

    def test_one_way_reception(self):
        positions = {"Venus": 15.0, "Mars": 200.0}  # Venus in Aries (Mars' domicile), Mars in Libra (Venus')
        assert "mutual" in receptions(positions, "Venus", "Mars")[0]
        positions = {"Venus": 15.0, "Mars": 100.0}  # Mars in Cancer: not Venus'
        assert receptions(positions, "Venus", "Mars") == ["Mars receives Venus (Venus is in Mars's domicile)."]


class TestConsiderations:
    @pytest.fixture
    def chart(self):
        return cast("2026-09-27 12:00", 34.02, -118.40)

    def _flags(self, c):
        return {x["check"]: x["flag"] for x in considerations(c, ImmanuelEphemeris())}

    def test_early_and_late_ascendant(self, chart):
        assert self._flags(replace(chart, asc=1.5))["early ascendant"] is True
        assert self._flags(replace(chart, asc=28.0))["late ascendant"] is True
        assert self._flags(replace(chart, asc=15.0))["ascendant degree"] is False

    def test_via_combusta_and_saturn_in_the_seventh(self, chart):
        c = replace(chart, positions={**chart.positions, "Moon": 200.0}, houses={**chart.houses, "Saturn": 7})
        flags = self._flags(c)
        assert flags["via combusta"] is True
        assert flags["Saturn in the 7th"] is True

    def test_radicality_is_always_assessed(self, chart):
        assert "radicality (hour ruler)" in self._flags(chart)


class TestTools:
    def test_judges_a_real_question_end_to_end(self):
        r = json.loads(judge_question(question="Will I get the job?", quesited_house=10, when="2026-09-27 12:00", **LA))
        assert r["significators"]["querent"]["rules_house"] == 1
        assert r["significators"]["quesited"]["rules_house"] == 10
        assert r["verdict"] in {"perfects", "perfects by translation", "perfects by collection",
                                "prohibited", "refranation", "no perfection"}
        assert r["summary"] and r["testimony"] and r["considerations"]
        assert r["timezone"] == "America/Los_Angeles"

    def test_derived_houses(self):
        # A partner's money: the 2nd from the 7th is the 8th.
        r = json.loads(judge_question(question="Does my partner have money?", quesited_house=2, relative_to=7,
                                      when="2026-09-27 12:00", **LA))
        assert r["significators"]["quesited"]["rules_house"] == 8

    def test_casts_a_chart_with_conditions_and_considerations(self):
        r = json.loads(cast_horary_chart(question="Where is my ring?", when="2026-09-27 12:00", **LA))
        assert r["settings"].startswith("Regiomontanus")
        assert len(r["houses"]) == 12
        assert set(r["planets"]) == set(PLANETS)
        assert "Uranus" not in r["planets"]
        for p in r["planets"].values():
            assert {"position", "house", "essential_dignity", "dignity_score", "condition"} <= set(p)

    def test_needs_a_place(self):
        r = json.loads(judge_question(question="?", quesited_house=7))
        assert r["error"] == "Invalid input"


def test_registered_with_directive_descriptions_and_the_house_guide():
    import asyncio
    from astro_mcp.server import mcp
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    assert "never" in tools["judge_question"].description
    assert "7 partner" in tools["judge_question"].description
    assert "never" in tools["cast_horary_chart"].description
