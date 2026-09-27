"""Which moment a chart is cast for, and which chart an aspect belongs to.

Progressed, solar return and composite charts all used to report the birth
time as their date_time -- so a progressed chart looked like a natal one, and
the moment that actually mattered was buried in a secondary field.
"""
import json

import pytest

from astro_mcp.tools.natal import create_natal_chart
from astro_mcp.tools.progressed import create_progressed_chart
from astro_mcp.tools.solar_return import create_solar_return
from astro_mcp.tools.transit import create_transit_chart

BIRTH = dict(date_time="1984-05-10 20:44", latitude="34.02", longitude="-118.40")


@pytest.fixture(scope="module")
def progressed():
    return json.loads(create_progressed_chart(target_date="2026-09-26 12:00", **BIRTH))


@pytest.fixture(scope="module")
def solar():
    return json.loads(create_solar_return(year=2026, **BIRTH))


class TestChartsNameTheirOwnMoment:
    def test_progressed_reports_the_progressed_date(self, progressed):
        assert progressed["date_time"].startswith("1984-06-22")
        assert progressed["date_time"] == progressed["progressed_date_time"]

    def test_progressed_keeps_the_birth_time_for_reference(self, progressed):
        assert progressed["birth_date_time"].startswith("1984-05-10")

    def test_solar_return_reports_the_return_moment(self, solar):
        assert solar["date_time"].startswith("2026-05-11")
        assert solar["date_time"] == solar["solar_return_date_time"]

    def test_solar_return_keeps_the_birth_time(self, solar):
        assert solar["birth_date_time"].startswith("1984-05-10")

    def test_natal_still_reports_the_birth_time(self):
        chart = json.loads(create_natal_chart(**BIRTH))
        assert chart["date_time"].startswith("1984-05-10")

    def test_a_transit_snapshot_still_reports_its_own_moment(self):
        chart = json.loads(create_transit_chart(transit_date_time="2026-09-26 12:00", **BIRTH))
        assert chart["date_time"].startswith("2026-09-26")


class TestCrossChartAspectsAreLabelled:
    def test_progressed_aspects_name_both_charts(self, progressed):
        assert progressed["aspects"], "no aspects to check"
        for aspect in progressed["aspects"]:
            assert aspect["from_chart"] == "progressed"
            assert aspect["to_chart"] == "natal"

    def test_the_label_is_not_decoration(self, progressed):
        # progressed Asc conjunct natal Jupiter sits 1.87 away; progressed
        # Jupiter is 1.90. Without the labels the two are indistinguishable.
        match = [
            a for a in progressed["aspects"]
            if a["from_object"] == "Asc" and a["to_object"] == "Jupiter"
        ]
        if not match:
            pytest.skip("that contact is not present in this chart")
        assert match[0]["to_chart"] == "natal"

    def test_a_natal_chart_needs_no_labels(self):
        # Its aspects are internal, so there is nothing to disambiguate.
        chart = json.loads(create_natal_chart(**BIRTH))
        assert all("from_chart" not in a for a in chart["aspects"])
