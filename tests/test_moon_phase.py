"""Tests for corrected moon phase classification.

immanuel's moon_phase_from() uses the principal elongations (0, 45, 90, ...)
as bin edges, so any Moon between 90° and 135° from the Sun was labeled
'First Quarter' — but a Moon at 119° is ~74% illuminated, i.e. a waxing
gibbous Moon. Our tools now reclassify with the standard equal-width bins
centered on each principal phase (edges at 22.5° + 45°·k).
"""

import json

import pytest

from astro_mcp.utils import classify_moon_phase, corrected_moon_phase

_PHASE_FLAGS = (
    "new_moon", "waxing_crescent", "first_quarter", "waxing_gibbous",
    "full_moon", "disseminating", "third_quarter", "balsamic",
)


class TestClassifyMoonPhase:
    """Unit tests for the corrected 8-phase binning."""

    def test_principal_phases_centered_on_their_elongations(self):
        cases = [
            (0, "new_moon", "New"),
            (45, "waxing_crescent", "Waxing Crescent"),
            (90, "first_quarter", "First Quarter"),
            (135, "waxing_gibbous", "Waxing Gibbous"),
            (180, "full_moon", "Full"),
            (225, "disseminating", "Disseminating"),
            (270, "third_quarter", "Third Quarter"),
            (315, "balsamic", "Balsamic"),
        ]
        for elongation, flag, name in cases:
            phase = classify_moon_phase(0.0, float(elongation))
            assert phase[flag] is True, f"elongation {elongation} should be {name}"
            assert phase["formatted"] == name

    def test_exactly_one_phase_flag_set(self):
        for moon_lon in range(0, 360, 7):
            phase = classify_moon_phase(0.0, float(moon_lon))
            assert sum(phase[f] for f in _PHASE_FLAGS) == 1, (
                f"elongation {moon_lon}: expected exactly one phase flag, got {phase}"
            )

    def test_output_shape_matches_immanuel(self):
        """Existing immanuel keys (8 booleans + formatted) must all be present."""
        phase = classify_moon_phase(10.0, 130.0)
        for key in (*_PHASE_FLAGS, "formatted"):
            assert key in phase, f"missing key {key}"

    def test_boundaries_at_midpoints(self):
        """Bin edges sit at 22.5° + 45°·k, not on the principal elongations."""
        cases = [
            (22.4, "new_moon"), (22.6, "waxing_crescent"),
            (67.4, "waxing_crescent"), (67.6, "first_quarter"),
            (112.4, "first_quarter"), (112.6, "waxing_gibbous"),
            (157.4, "waxing_gibbous"), (157.6, "full_moon"),
            (202.4, "full_moon"), (202.6, "disseminating"),
            (247.4, "disseminating"), (247.6, "third_quarter"),
            (292.4, "third_quarter"), (292.6, "balsamic"),
            (337.4, "balsamic"), (337.6, "new_moon"),
        ]
        for elongation, flag in cases:
            phase = classify_moon_phase(0.0, elongation)
            assert phase[flag] is True, f"elongation {elongation} should be {flag}, got {phase['formatted']}"

    def test_119_deg_is_waxing_gibbous_not_first_quarter(self):
        """Regression: the 2026-09-21 Moon (118.8° elongation) was labeled
        'First Quarter' by immanuel's binning. At ~74% illumination, waxing,
        it is a waxing gibbous Moon."""
        phase = classify_moon_phase(178.5297, 297.3643)
        assert phase["waxing_gibbous"] is True
        assert phase["first_quarter"] is False
        assert phase["formatted"] == "Waxing Gibbous"
        assert phase["elongation"] == pytest.approx(118.83, abs=0.01)

    def test_illumination_fraction(self):
        assert classify_moon_phase(0.0, 0.0)["illumination"] == 0.0
        assert classify_moon_phase(0.0, 90.0)["illumination"] == 0.5
        assert classify_moon_phase(0.0, 180.0)["illumination"] == 1.0
        assert classify_moon_phase(0.0, 270.0)["illumination"] == 0.5

    def test_wrap_around_new_moon(self):
        """Moon just past the Sun (elongation crossing 360° → 0°) is New."""
        phase = classify_moon_phase(350.0, 10.0)
        assert phase["new_moon"] is True
        assert phase["elongation"] == pytest.approx(20.0, abs=0.01)


class TestCorrectedMoonPhase:
    """corrected_moon_phase reads Sun/Moon from a chart's objects."""

    def _fake_chart(self, *names):
        class _Angle:
            def __init__(self, raw):
                self.raw = raw

        class _Obj:
            def __init__(self, name, lon):
                self.name = name
                self.longitude = _Angle(lon)

        longitudes = {"Sun": 10.0, "Moon": 130.0, "Mars": 50.0}
        return type("Chart", (), {"objects": {i: _Obj(n, longitudes[n]) for i, n in enumerate(names)}})

    def test_returns_none_when_sun_or_moon_missing(self):
        assert corrected_moon_phase(self._fake_chart("Sun")) is None
        assert corrected_moon_phase(self._fake_chart("Mars", "Moon")) is None

    def test_classifies_from_chart_longitudes(self):
        phase = corrected_moon_phase(self._fake_chart("Sun", "Moon", "Mars"))
        assert phase is not None
        assert phase["waxing_gibbous"] is True  # elongation 130-10=120° → waxing gibbous


class TestMoonPhaseInToolOutput:
    """Integration: chart tools must emit the corrected moon_phase."""

    def test_transit_chart_2026_09_21_is_waxing_gibbous(self):
        """The incident that prompted the fix: on 2026-09-21 an LLM reported a
        first quarter Moon, but the Moon at ~120° elongation is waxing gibbous."""
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time="1984-05-10 20:44",
            latitude="34.02",
            longitude="-118.40",
            transit_date_time="2026-09-21 12:00",
        )
        data = json.loads(result)
        assert "error" not in data, data
        phase = data["moon_phase"]
        assert phase["formatted"] == "Waxing Gibbous"
        assert phase["waxing_gibbous"] is True
        assert phase["first_quarter"] is False
        assert phase["elongation"] == pytest.approx(122.07, abs=0.1)

    def test_natal_chart_moon_phase_corrected(self):
        """1984-05-10 20:44: Sun 50.64°, Moon 176.26° → 125.6° elongation,
        ~79% illuminated, waxing → waxing gibbous (immanuel said First Quarter)."""
        from astro_mcp.tools.natal import create_natal_chart

        result = create_natal_chart(
            date_time="1984-05-10 20:44",
            latitude="34.02",
            longitude="-118.40",
        )
        data = json.loads(result)
        assert "error" not in data, data
        phase = data["moon_phase"]
        assert phase["formatted"] == "Waxing Gibbous"
        assert phase["elongation"] == pytest.approx(125.62, abs=0.05)
