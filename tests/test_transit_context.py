"""Everything a transit response needs to be quoted rather than completed.

A reader given "Saturn square Saturn" with only the transiting position had
to supply the natal one from memory -- and that is exactly where invented
degrees came from. Transit responses now carry the natal chart they are
measured against, both ends of every aspect, an explicit zero for a planet
that aspects nothing, and a tool to check a claim against the ephemeris.
"""
import json

import pytest

from astro_mcp.config import get_config
from astro_mcp.tools.transit import create_transit_chart, list_upcoming_transits, verify_claim
from astro_mcp.utils import format_dms, sign_position

BIRTH = dict(date_time="1984-05-10T20:44:00", latitude=37.77, longitude=-122.42)


def rows(data):
    if "span_fields" in data:
        return [dict(zip(data["span_fields"], r)) for r in data["transits"]]
    return data["transits"]


def natal_chart():
    from immanuel import charts
    subject = charts.Subject(date_time="1984-05-10 20:44", latitude=BIRTH["latitude"], longitude=BIRTH["longitude"])
    return charts.Natal(subject, config=get_config(None))


@pytest.fixture(scope="module")
def week():
    return json.loads(list_upcoming_transits(start_date="2026-09-25", end_date="2026-10-02", **BIRTH))


@pytest.fixture(scope="module")
def snapshot():
    return json.loads(create_transit_chart(transit_date_time="2026-10-01 12:00", max_orb=8, **BIRTH))


def test_positions_are_spelled_out_in_sign_degrees():
    assert format_dms(12.35) == "12°21'"
    assert format_dms(29.999) == "29°59'"  # never rolls into the next sign
    assert sign_position(222.35) == {"longitude": 222.35, "sign": "Scorpio", "position": "12°21' Scorpio"}


def test_the_natal_chart_rides_along_with_the_spans(week):
    natal = week["natal"]["positions"]
    chart = natal_chart()
    for obj in chart.objects.values():
        if obj.name in natal:
            assert natal[obj.name]["sign"] == obj.sign.name, obj.name
            assert natal[obj.name]["house"] == obj.house.number
    assert {"Asc", "MC", "Saturn"} <= set(natal)
    assert natal["Asc"]["position"].endswith(natal["Asc"]["sign"])
    assert week["natal"]["house_system"] == "whole_sign"


def test_every_span_carries_both_ends(week):
    natal = week["natal"]["positions"]
    for r in rows(week):
        assert r["from_position"].endswith(r["from_sign"])
        assert r["to_position"].endswith(r["to_sign"])
        # The natal end is the same string the natal block gives, so the two can be matched by eye.
        assert r["to_position"] == natal[r["to_object"]]["position"]


def test_every_span_reads_as_one_sentence_with_the_roles_and_moment(week):
    for r in rows(week):
        when = f"exact {r['exact']}" if r["exact"] else f"tightest "
        assert r["label"].startswith(when)
        assert f"transiting {r['from_object']} {r['from_position']} {r['type'].lower()} natal {r['to_object']} {r['to_position']}" in r["label"]
        if r["to_house"]:
            assert r["label"].endswith(f"(natal house {r['to_house']})")
    assert "not where the bodies are today" in week["positions_note"]


def test_the_two_directions_of_a_square_are_told_apart(week):
    # "Jupiter square Sun" and "Sun square Jupiter" are different contacts; the labels can't be confused.
    labels = [r["label"] for r in rows(week)]
    for label in labels:
        assert label.count("transiting") == 1 and label.count("natal") >= 1


def test_the_moon_phase_gives_one_answer(snapshot):
    phase = snapshot["moon_phase"]
    assert phase["phase"] in {
        "New", "Waxing Crescent", "First Quarter", "Waxing Gibbous", "Full", "Disseminating", "Third Quarter", "Balsamic",
    }
    assert phase["phase"] == phase["formatted"]
    assert isinstance(phase["waxing"], bool)
    assert sum(1 for k, v in phase.items() if v is True and k not in ("waxing",)) == 1  # exactly one phase flag


def test_absence_is_an_explicit_zero():
    data = json.loads(list_upcoming_transits(
        start_date="2026-09-25", end_date="2026-10-02", object_filter="Sun,Saturn,Pluto", **BIRTH,
    ))
    per = data["spans_per_object"]
    assert set(per) == {"Sun", "Saturn", "Pluto"}  # every scanned object, aspecting or not
    assert all(isinstance(n, int) for n in per.values())
    assert sum(per.values()) == data["total_transits"]


def test_a_snapshot_carries_the_natal_block_and_both_ends(snapshot):
    natal = snapshot["natal"]["positions"]
    assert {"Asc", "MC"} <= set(natal)
    assert snapshot["aspects"], "no aspects at a wide orb -- the fixture date needs changing"
    for a in snapshot["aspects"]:
        assert a["from_position"].endswith(a["from_sign"])
        assert a["to_position"] == natal[a["to_object"]]["position"]
        assert a["to_house"] == natal[a["to_object"]]["house"]
    # The transiting side agrees with the objects block, to the minute.
    for a in snapshot["aspects"]:
        assert a["from_position"] == sign_position(snapshot["objects"][a["from_object"]]["longitude"])["position"]
        # And the sentence has roles, movement and timing in it.
        assert a["label"].startswith(f"transiting {a['from_object']} {a['from_position']} {a['type'].lower()} natal {a['to_object']}")
        assert ", exact " in a["label"]


def test_verify_claim_confirms_what_the_scan_found(week):
    span = next(r for r in rows(week) if r["exact"] and r["from_object"] != "Moon")
    on_date = span["exact"][:10]
    result = json.loads(verify_claim(
        transiting_object=span["from_object"], natal_object=span["to_object"],
        aspect_type=span["type"].lower(), on_date=on_date, **BIRTH,
    ))
    assert result["verdict"] == "confirmed"
    assert result["on_date"]["within_orb"] is True
    assert result["on_date"]["natal"]["position"] == span["to_position"]
    assert result["exact"] == span["exact"]


def test_verify_claim_rejects_an_invented_transit():
    # Pluto in Aquarius cannot be conjunct a Taurus Sun this decade.
    result = json.loads(verify_claim(
        transiting_object="Pluto", natal_object="Sun", aspect_type="Conjunction", on_date="2026-10-01", **BIRTH,
    ))
    assert result["verdict"] == "not found"
    assert result["exact"] is None


def test_verify_claim_takes_the_names_a_reader_uses():
    result = json.loads(verify_claim(
        transiting_object="saturn", natal_object="Ascendant", aspect_type="TRINE", on_date="2026-10-01", **BIRTH,
    ))
    assert result["claim"].startswith("transiting Saturn trine natal Asc")
    assert result["verdict"] in {"confirmed", "near", "not found"}
    bad = json.loads(verify_claim(
        transiting_object="Vesta", natal_object="Sun", aspect_type="Trine", on_date="2026-10-01", **BIRTH,
    ))
    assert "error" in bad
