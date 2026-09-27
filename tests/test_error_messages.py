"""Failures the caller can act on.

Swiss Ephemeris raises for conditions that are properties of the request,
not faults. Passed through raw they arrived as
"Unexpected error: swisseph.houses_ex2: within polar circle, switched to
Porphyry", which tells a reader nothing about what to do differently.
"""
import json

import pytest

from astro_mcp.tools.natal import create_natal_chart
from astro_mcp.tools.progressed import create_progressed_chart
from astro_mcp.tools.solar_return import create_solar_return
from astro_mcp.utils import describe_chart_error

POLAR = dict(date_time="1984-05-10 12:00", latitude="78.2", longitude="15.6")
TEMPERATE = dict(date_time="1984-05-10 12:00", latitude="34.02", longitude="-118.40")


class TestPolarLatitudes:
    def test_natal_explains_itself(self):
        data = json.loads(create_natal_chart(**POLAR))
        assert data["error"] == "Location is inside the polar circle"
        assert "66 degrees" in data["detail"]
        assert "swisseph" not in data["detail"]

    def test_so_do_the_other_chart_tools(self):
        for result in (
            create_solar_return(year=2026, **POLAR),
            create_progressed_chart(target_date="2026-09-26 12:00", **POLAR),
        ):
            data = json.loads(result)
            assert "polar circle" in data["error"]

    def test_temperate_latitudes_are_unaffected(self):
        assert "error" not in json.loads(create_natal_chart(**TEMPERATE))


class TestEphemerisRange:
    def test_a_date_outside_the_files_is_refused(self):
        data = json.loads(create_natal_chart(
            date_time="1100-01-01 12:00", latitude="34", longitude="-118"))
        assert "out of range" in data["detail"]
        assert "4649" in data["detail"], "still advertising a range it cannot serve"

    def test_the_first_days_of_1200_are_refused_by_the_library(self):
        # Validation allows 1200-01-01 but the files begin a month later.
        data = json.loads(create_natal_chart(
            date_time="1200-01-01 12:00", latitude="34", longitude="-118"))
        assert data["error"] == "Date outside the available ephemeris"

    @pytest.mark.parametrize("year,valid", [(1199, False), (4649, True), (4650, False)])
    def test_solar_return_advertises_the_real_range(self, year, valid):
        # The old bound of 4799 came from the library's documented maximum
        # and failed with a raw file error for its last 150 years.
        data = json.loads(create_solar_return(year=year, **TEMPERATE))
        assert ("error" not in data) == valid


class TestDescribeChartError:
    def test_it_passes_through_what_it_does_not_recognise(self):
        assert describe_chart_error(ValueError("something else entirely")) is None

    def test_it_recognises_the_polar_case(self):
        message, detail = describe_chart_error(
            Exception("swisseph.houses_ex2: within polar circle, switched to Porphyry"))
        assert "polar" in message.lower()
        assert detail
