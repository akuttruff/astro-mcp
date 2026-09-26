"""Applying vs separating on transit aspects.

Whether an aspect is closing or fading is the first thing a reading asks of a
transit -- an applying square is building, a separating one is spending
itself -- and it cannot be recovered from the orb alone. The natal path gets
this from immanuel; the transit paths compute it here.
"""
import json

import pytest

from astro_mcp.tools.transit import create_transit_chart
from astro_mcp.utils import aspect_movement

BIRTH = dict(date_time="1984-05-10T20:44:00", latitude=37.77, longitude=-122.42)


class TestAspectMovement:
    def test_direct_body_closing_on_the_aspect_is_applying(self):
        # Transiting body just short of a conjunction, moving forward.
        assert aspect_movement(99.0, 100.0, 0.0, +1.0) == "Applicative"

    def test_direct_body_past_the_aspect_is_separating(self):
        assert aspect_movement(101.0, 100.0, 0.0, +1.0) == "Separative"

    def test_retrograde_reverses_the_reading(self):
        # The same geometry, read backwards: retrograde motion is exactly
        # what makes a "past" aspect apply again.
        assert aspect_movement(101.0, 100.0, 0.0, -1.0) == "Applicative"
        assert aspect_movement(99.0, 100.0, 0.0, -1.0) == "Separative"

    def test_stationary_is_neither(self):
        assert aspect_movement(99.0, 100.0, 0.0, 0.0) == "Stationary"

    def test_unknown_speed_gives_no_opinion(self):
        assert aspect_movement(99.0, 100.0, 0.0, None) is None

    def test_it_works_across_the_zero_degree_wrap(self):
        # 359° applying to a conjunction with 0°.
        assert aspect_movement(359.0, 0.0, 0.0, +1.0) == "Applicative"
        assert aspect_movement(1.0, 0.0, 0.0, +1.0) == "Separative"

    def test_it_works_for_a_square(self):
        assert aspect_movement(89.0, 0.0, 90.0, +1.0) == "Applicative"
        assert aspect_movement(91.0, 0.0, 90.0, +1.0) == "Separative"


@pytest.fixture(scope="module")
def chart():
    return json.loads(create_transit_chart(**BIRTH))


class TestTransitChartReportsDirection:

    def test_every_aspect_says_which_way_it_is_heading(self, chart):
        assert chart["aspects"], "no aspects to check"
        for aspect in chart["aspects"]:
            assert aspect.get("movement") in {
                "Applicative", "Separative", "Stationary", "Exact",
            }, aspect

    def test_the_direction_matches_how_the_orb_actually_moves(self):
        # The check that matters: recompute a day later and confirm an
        # applying aspect really did tighten.
        def snapshot(when):
            data = json.loads(create_transit_chart(transit_date_time=when, **BIRTH))
            return {
                (a["from_object"], a["to_object"], a["type"]): (a["orb"], a.get("movement"))
                for a in data["aspects"]
            }

        now = snapshot("2026-09-26 12:00")
        later = snapshot("2026-09-27 12:00")
        checked = 0
        for key, (orb, movement) in now.items():
            if key not in later or movement not in ("Applicative", "Separative"):
                continue
            checked += 1
            tightened = later[key][0] < orb
            assert tightened == (movement == "Applicative"), (
                f"{key} reported {movement} but orb went {orb} -> {later[key][0]}"
            )
        assert checked, "no aspects persisted across the day to check"

    def test_orbs_are_rounded_like_the_natal_path(self, chart):
        for aspect in chart["aspects"]:
            assert round(aspect["orb"], 2) == aspect["orb"], aspect
