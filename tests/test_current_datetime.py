"""get_current_datetime states which local time it means.

It used to return naive local time with no zone, and the model uses it to
decide what "today" is for transits.
"""
from datetime import datetime, timedelta

from astro_mcp.utils import get_current_datetime, validate_date_string


def test_it_names_the_zone_and_offset():
    d = get_current_datetime()
    assert d["timezone"]
    assert d["timezone_abbreviation"]
    sign, hh, mm = d["utc_offset"][0], d["utc_offset"][1:3], d["utc_offset"][4:6]
    assert sign in "+-" and hh.isdigit() and mm.isdigit() and d["utc_offset"][3] == ":"


def test_the_utc_instant_agrees_with_the_local_time():
    d = get_current_datetime()
    local = datetime.fromisoformat(d["current_datetime"])
    utc = datetime.fromisoformat(d["utc_datetime"]).replace(tzinfo=None)
    sign = -1 if d["utc_offset"][0] == "-" else 1
    offset = timedelta(hours=int(d["utc_offset"][1:3]), minutes=int(d["utc_offset"][4:6]))
    assert abs((local - sign * offset) - utc) < timedelta(seconds=2)


def test_current_datetime_can_still_be_passed_to_the_chart_tools():
    # The reason the offset is reported beside the value, not inside it:
    # the chart tools reject offsets, and this flow must keep working.
    assert validate_date_string(get_current_datetime()["current_datetime"])[0]
