"""Shared fixtures for testing astro-mcp."""

import pytest


@pytest.fixture
def reference_nyc():
    """Reference A: NYC, mid-year, diurnal, Northern Hemisphere."""
    return {
        "date_time": "1990-06-15 14:30",
        "latitude": "40.74",
        "longitude": "-73.99",
        "expected_asc_sign": "Cancer",  # Whole sign
        "expected_sun_sign": "Gemini",
    }


@pytest.fixture
def reference_sydney():
    """Reference B: Sydney, Southern Hemisphere, nocturnal, early year."""
    return {
        "date_time": "1985-01-28 03:15",
        "latitude": "-33.87",
        "longitude": "151.21",
        "expected_asc_sign": "Libra",  # Whole sign
    }


@pytest.fixture
def reference_london():
    """Reference C: London, near vernal equinox."""
    return {
        "date_time": "2000-03-20 09:00",
        "latitude": "51.51",
        "longitude": "-0.13",
    }


@pytest.fixture
def reference_tokyo():
    """Reference D: Tokyo, near winter solstice."""
    return {
        "date_time": "1975-12-21 22:45",
        "latitude": "35.68",
        "longitude": "139.69",
    }


@pytest.fixture
def reference_paris():
    """Reference E: Paris, for synastry test with NYC."""
    return {
        "date_time": "1992-09-09 08:00",
        "latitude": "48.86",
        "longitude": "2.35",
    }


@pytest.fixture
def fixed_transit_time():
    """Fixed transit time for deterministic tests."""
    return "2025-01-15 12:00"


@pytest.fixture
def fixture_dir():
    """Path to test fixtures directory."""
    import os
    return os.path.join(os.path.dirname(__file__), "fixtures")
