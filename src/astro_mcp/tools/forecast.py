"""Week, month and year forecasts: a digest of what matters over a range.

list_upcoming_transits reports every contact of every planet, day by day.
Over a week that is dominated by the Moon; over a month it is already a
lot; over a year it is hundreds of spans, most of them the fast planets,
and the response has to be cut to fit. A forecast is a different question
-- it is about the planets that shape the period, the handful of exact
dates that matter, where they land in the chart, and the shape of the
period -- so these tools compute the story rather than the raw material.
The horizon decides which planets count: a week keeps the Sun, Mercury,
Venus and Mars that a month leaves out, and a year keeps Jupiter outward.

Same source, less waste: one immanuel natal chart, then daily positions
straight from immanuel's ephemeris module (the same call immanuel makes
inside every chart it builds) instead of a full chart object per day. The
exact-moment refinement and the lunation solver are the ones the transit
and timing tools already use, so every date here agrees with them.
"""

import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from astro_mcp.config import get_config
from astro_mcp.schemas import get_coordinates_for_params
from astro_mcp.tools.timing import lunations_and_eclipses
from astro_mcp.tools.transit import (
    _bisect, _chart_tz, _house_of, _jd_of, _nearest_exact, _object_ids, _peak_facts, _refine_span_exact,
)
from astro_mcp.utils import (
    NATAL_TRANSIT_TARGETS, SIGNS, _aspects_between, aspect_label, describe_chart_error, error_response,
    natal_positions_block, sign_position, validate_date_string, validate_latitude, validate_longitude,
)

# How much a transiting planet's contact weighs: the slower the planet, the
# longer and rarer the transit, the more it shapes a period. The Sun,
# Mercury and Venus only count in a week, where a contact that lasts a day
# or two is the week's texture.
SLOWNESS = {
    'Mercury': 0.5, 'Venus': 0.7, 'Sun': 0.8, 'Mars': 1,
    'Jupiter': 3, 'Chiron': 3, 'Saturn': 4, 'Uranus': 4, 'Neptune': 5, 'Pluto': 5,
}
WEEK_MOVERS = ['Sun', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Chiron', 'Uranus', 'Neptune', 'Pluto']
MONTH_MOVERS = ['Mars', 'Jupiter', 'Saturn', 'Chiron', 'Uranus', 'Neptune', 'Pluto']
YEAR_MOVERS = ['Jupiter', 'Saturn', 'Chiron', 'Uranus', 'Neptune', 'Pluto']
# Stations and ingresses are rarer than aspects, so the faster planets can be included.
WEEK_EVENT_MOVERS = WEEK_MOVERS
MONTH_EVENT_MOVERS = ['Mercury', 'Venus'] + MONTH_MOVERS
YEAR_EVENT_MOVERS = ['Mars'] + YEAR_MOVERS
ASPECT_WEIGHT = {'Conjunction': 1.0, 'Opposition': 1.0, 'Square': 0.9, 'Trine': 0.7, 'Sextile': 0.5}
# The natal points whose transits matter most, with the chart ruler added per chart.
KEY_POINTS = {'Sun', 'Moon', 'Asc', 'MC'}
WEEK_HEADLINES = 8
MONTH_HEADLINES = 12
YEAR_HEADLINES = 25
PER_MONTH = 3
ECLIPSE_WEIGHT = 6.0
# How far outside the period the exact moment of a contact in orb is looked for.
NEAREST_EXACT_DAYS = 366
WEEK_DAYS = 7

# What each horizon scans and keeps. The Moon is never a headline: it
# aspects something every few hours, which is list_upcoming_transits' job.
HORIZONS = {
    "week": {
        "movers": WEEK_MOVERS, "event_movers": WEEK_EVENT_MOVERS, "headlines": WEEK_HEADLINES, "eclipses_only": False,
        "exact_first": True,
        "left_out": {"objects": ["Moon"], "why": "hourly material; ask list_upcoming_transits with object_filter='Moon' for the Moon's contacts"},
    },
    "month": {
        "movers": MONTH_MOVERS, "event_movers": MONTH_EVENT_MOVERS, "headlines": MONTH_HEADLINES, "eclipses_only": False,
        "left_out": {"objects": ["Moon", "Sun", "Mercury", "Venus"], "why": "daily material; for a particular week use forecast_week, or list_upcoming_transits with object_filter='Moon'"},
    },
    "year": {
        "movers": YEAR_MOVERS, "event_movers": YEAR_EVENT_MOVERS, "headlines": YEAR_HEADLINES, "eclipses_only": True,
        "left_out": {"objects": ["Moon", "Sun", "Mercury", "Venus", "Mars (aspects)"], "why": "fast movers aspect something every few days; for a particular month use forecast_month"},
    },
}


def _chart_ruler(natal_chart) -> str | None:
    """Traditional ruler of the Ascendant's sign, from immanuel's own table."""
    from immanuel.const import dignities, names
    asc = next((o for o in natal_chart.objects.values() if o.name == 'Asc'), None)
    if asc is None:
        return None
    sign_index = int((asc.longitude.raw % 360) // 30)
    return names.PLANETS.get(dignities.TRADITIONAL_RULERSHIPS[sign_index + 1])


def _daily_positions(ids: dict[str, int], names: list[str], first: date, last: date, tz) -> dict[str, list[tuple[date, float, float]]]:
    """(day, longitude, speed) per planet at local midnight, one day of margin either side."""
    from immanuel.tools import ephemeris
    out: dict[str, list[tuple[date, float, float]]] = {name: [] for name in names}
    day = first - timedelta(days=1)
    stop = last + timedelta(days=1)
    while day <= stop:
        jd = _jd_of(datetime(day.year, day.month, day.day, tzinfo=tz))
        for name in names:
            p = ephemeris.get_planet(ids[name], jd)
            out[name].append((day, p["lon"] % 360, p["speed"]))
        day += timedelta(days=1)
    return out


def _aspect_spans(daily, movers: list[str], natal_positions: dict, first: date, last: date, max_orb: float):
    """Consecutive in-orb days per (planet, natal point, aspect), like the transit scan's runs.

    Only the aspect movers: the faster planets in `daily` are sampled for
    their stations and ingresses, not for contacts.
    """
    samples: dict[tuple[str, str, str], dict[str, float]] = {}
    for planet in movers:
        for day, lon, _speed in daily[planet]:
            if day < first or day > last:
                continue
            for natal_name, natal_lon in natal_positions.items():
                for aspect, orb in _aspects_between(lon, natal_lon, planet, natal_name):
                    if orb > max_orb:
                        continue
                    samples.setdefault((planet, natal_name, aspect), {})[day.isoformat()] = orb
    spans: dict[tuple[str, str, str], list[list[str]]] = {}
    for key, orb_by_day in samples.items():
        days = sorted(orb_by_day)
        runs, run = [], [days[0]]
        for d in days[1:]:
            if (date.fromisoformat(d) - date.fromisoformat(run[-1])).days > 1:
                runs.append(run)
                run = [d]
            else:
                run.append(d)
        runs.append(run)
        spans[key] = runs
    return samples, spans


def _headline_transits(daily, movers, natal_chart, natal_positions, ids, tz, first, last, max_orb, limit, ruler,
                       exact_first: bool = False):
    """Ranked transit-to-natal contacts, each with its exact moment and both ends spelled out.

    With `exact_first`, a contact exact within the period outranks any that
    is not, whatever its weight: over a week the slow planets sit in orb
    without going exact, and by weight alone they would fill every slot
    ahead of the week's own events. Within each group the weight ranks.
    """
    natal_houses = {
        o.name: o.house.number for o in natal_chart.objects.values()
        if o.name in NATAL_TRANSIT_TARGETS and getattr(o, 'house', None)
    }
    cusps = sorted((h.number, h.longitude.raw % 360) for h in natal_chart.houses.values())
    samples, spans = _aspect_spans(daily, movers, natal_positions, first, last, max_orb)

    entries = []
    for (planet, natal_name, aspect), runs in spans.items():
        for i, run in enumerate(runs):
            orb_by_day = samples[(planet, natal_name, aspect)]
            exact = _refine_span_exact(run, planet, natal_name, aspect, ids, natal_positions, tz)
            peak_day = min(run, key=lambda d: orb_by_day[d])
            facts = _peak_facts(planet, natal_name, ids, natal_positions, natal_houses, cusps, exact, peak_day, tz)
            weight = SLOWNESS[planet] * (2 if natal_name in KEY_POINTS or natal_name == ruler else 1) * ASPECT_WEIGHT[aspect]
            when = f"exact {exact}" if exact else f"tightest {peak_day}"
            label = f"{when}: " + aspect_label(
                planet, facts["from_position"], aspect, natal_name, facts["to_position"], natal_house=facts.get("to_house"),
            )
            if len(runs) > 1:
                label += f" -- pass {i + 1} of {len(runs)} of this contact in the period"
            if facts.get("from_retrograde"):
                label += ", retrograde"
            # Which way it is going over the period, for a contact that does not perfect in it:
            # the orb closing from the first in-orb day to the last is applying, opening is separating.
            movement = None
            if not exact and len(run) > 1:
                movement = "applying" if orb_by_day[run[-1]] < orb_by_day[run[0]] else "separating"
            # A slow planet can sit in orb all period without perfecting: say when it does.
            nearest = exact
            if not exact:
                nearest_dt = _nearest_exact(
                    planet, natal_name, aspect, ids, natal_positions,
                    datetime.combine(date.fromisoformat(run[0]), datetime.min.time(), tzinfo=tz),
                    datetime.combine(date.fromisoformat(run[-1]), datetime.min.time(), tzinfo=tz) + timedelta(days=1),
                    NEAREST_EXACT_DAYS,
                )
                nearest = nearest_dt.strftime("%Y-%m-%d %H:%M") if nearest_dt else None
                if nearest:
                    label += f"; not exact in the period, exact {nearest}"
                else:
                    label += f"; not exact within {NEAREST_EXACT_DAYS} days of the period"
                if movement:
                    label += f", {movement}"
            entries.append({
                "transiting": planet, "natal": natal_name, "aspect": aspect,
                "start": run[0], "end": run[-1], "exact": exact, "nearest_exact": nearest, "movement": movement,
                "orb": round(min(orb_by_day[d] for d in run), 2),
                "pass": f"{i + 1} of {len(runs)}" if len(runs) > 1 else None,
                "from_position": facts["from_position"], "to_position": facts["to_position"],
                "natal_house": facts.get("to_house"), "retrograde": facts.get("from_retrograde", False),
                "weight": round(weight, 2), "label": label,
            })
    entries.sort(key=lambda e: (0 if exact_first and e["exact"] else 1, -e["weight"], e["orb"], e["start"]))
    total = len(entries)
    return entries[:limit], total


def _stations(daily, movers, first, last, ids, tz, cusps) -> list[dict]:
    """Where a planet turns retrograde or direct: a daily speed changing sign, bisected to the minute."""
    from immanuel.tools import ephemeris
    found = []
    for planet in movers:
        rows = daily[planet]
        for (d0, _l0, s0), (d1, _l1, s1) in zip(rows, rows[1:]):
            if s0 == 0 or s1 == 0 or (s0 > 0) == (s1 > 0):
                continue
            jd0 = _jd_of(datetime(d0.year, d0.month, d0.day, tzinfo=tz))
            jd = _bisect(lambda j: ephemeris.get_planet(ids[planet], j)["speed"], jd0, jd0 + 1)
            if jd is None:
                continue
            moment = datetime(d0.year, d0.month, d0.day, tzinfo=tz) + timedelta(days=jd - jd0, seconds=30)
            if not (first <= moment.date() <= last):
                continue
            pos = sign_position(ephemeris.get_planet(ids[planet], jd)["lon"])
            kind = "retrograde" if s1 < 0 else "direct"
            house = _house_of(pos["longitude"], cusps) if cusps else None
            found.append({
                "planet": planet, "station": kind, "exact": moment.strftime("%Y-%m-%d %H:%M"),
                "position": pos["position"], "natal_house": house,
                "label": f"{moment.strftime('%Y-%m-%d')}: {planet} stations {kind} at {pos['position']}"
                         + (f" (natal house {house})" if house else ""),
            })
    found.sort(key=lambda e: e["exact"])
    return found


def _ingresses(daily, movers, first, last, ids, tz, cusps) -> list[dict]:
    """A planet crossing into a new sign, bisected to the minute, with the natal house it enters."""
    from immanuel.tools import ephemeris
    found = []
    for planet in movers:
        rows = daily[planet]
        for (d0, l0, _s0), (d1, l1, _s1) in zip(rows, rows[1:]):
            i0, i1 = int(l0 // 30), int(l1 // 30)
            if i0 == i1:
                continue
            forward = ((l1 - l0 + 180) % 360) - 180 > 0
            boundary = (i1 if forward else i0) * 30.0
            jd0 = _jd_of(datetime(d0.year, d0.month, d0.day, tzinfo=tz))

            def f(j, _b=boundary, _p=planet):
                return ((ephemeris.get_planet(ids[_p], j)["lon"] - _b + 180) % 360) - 180

            jd = _bisect(f, jd0, jd0 + 1)
            if jd is None:
                continue
            moment = datetime(d0.year, d0.month, d0.day, tzinfo=tz) + timedelta(days=jd - jd0, seconds=30)
            if not (first <= moment.date() <= last):
                continue
            new_sign = SIGNS[i1]
            house = _house_of(i1 * 30.0 + (0.01 if forward else 29.99), cusps) if cusps else None
            found.append({
                "planet": planet, "enters": new_sign, "exact": moment.strftime("%Y-%m-%d %H:%M"),
                "retrograde": not forward, "natal_house": house,
                "label": f"{moment.strftime('%Y-%m-%d')}: {planet} enters {new_sign}"
                         + (" (retrograde, backing in)" if not forward else "")
                         + (f", natal house {house}" if house else ""),
            })
    found.sort(key=lambda e: e["exact"])
    return found


def _lunations(first: date, last: date, date_time: str, lat: float, lon: float, eclipses_only: bool) -> list[dict]:
    """New/full moons and eclipses from the timing tool, so the dates are the same ones it reports."""
    raw = json.loads(lunations_and_eclipses(
        start_date=first.isoformat(), end_date=last.isoformat(), date_time=date_time, latitude=lat, longitude=lon,
    ))
    events = raw.get("events", []) if isinstance(raw, dict) else []
    out = []
    for e in events:
        if eclipses_only and "eclipse" not in e["event"]:
            continue
        house = e.get("natal_house")
        contacts = e.get("contacts") or []
        label = f"{e['exact'][:10]}: {e['event']} at {e['position']}" + (f" in natal house {house}" if house else "")
        if contacts:
            label += ", touching " + ", ".join(contacts)
        out.append({**e, "label": label})
    return out


# MCP clients truncate large tool responses (~25KB), so a digest is kept
# under this: the headlines are ranked, so the lowest go first if it must shrink.
_MAX_RESPONSE_CHARS = 24000


def _bounded(result: dict) -> str:
    payload = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
    trimmed = 0
    while len(payload) > _MAX_RESPONSE_CHARS and result["headline_transits"]:
        result["headline_transits"].pop()
        trimmed += 1
        if trimmed == 1:
            result["headline_note"] += " Some of the lowest-ranked contacts were left out to fit the response."
        payload = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
    return payload


def _resolve(latitude, longitude, city, state, country):
    if city is not None and (latitude is None or longitude is None):
        lat_val, lon_val, _matched = get_coordinates_for_params(None, None, city, state, country)
        latitude, longitude = lat_val, lon_val
    if latitude is None or longitude is None:
        raise ValueError("Provide latitude and longitude, or a city (with state/country to disambiguate).")
    return str(latitude), str(longitude)


def _validate(date_time, latitude, longitude):
    for label, check, value in (
        ("Invalid birth date", validate_date_string, date_time),
        ("Invalid latitude", validate_latitude, latitude),
        ("Invalid longitude", validate_longitude, longitude),
    ):
        valid, error = check(value)
        if not valid:
            return error_response(label, error)
    return None


def _digest(date_time: str, latitude: str, longitude: str, first: date, last: date, max_orb: float, horizon: str) -> dict:
    """The shared engine behind the three tools; `horizon` is 'week', 'month' or 'year' (see HORIZONS)."""
    from immanuel import charts

    config = get_config()
    native = charts.Subject(date_time=date_time.replace("T", " "), latitude=float(latitude), longitude=float(longitude))
    natal_chart = charts.Natal(native, config=config)
    natal_positions = {
        o.name: o.longitude.raw % 360 for o in natal_chart.objects.values() if o.name in NATAL_TRANSIT_TARGETS
    }
    cusps = sorted((h.number, h.longitude.raw % 360) for h in natal_chart.houses.values())
    ids = _object_ids(natal_chart)
    tz = _chart_tz(latitude, longitude)
    ruler = _chart_ruler(natal_chart)

    scope = HORIZONS[horizon]
    movers = scope["movers"]
    event_movers = scope["event_movers"]
    daily = _daily_positions(ids, sorted(set(movers) | set(event_movers), key=event_movers.index), first, last, tz)

    headline, total = _headline_transits(
        daily, movers, natal_chart, natal_positions, ids, tz, first, last, max_orb, scope["headlines"], ruler,
        exact_first=scope.get("exact_first", False),
    )
    stations = _stations(daily, event_movers, first, last, ids, tz, cusps)
    ingresses = _ingresses(daily, event_movers, first, last, ids, tz, cusps)
    lunations = _lunations(first, last, date_time, float(latitude), float(longitude), eclipses_only=scope["eclipses_only"])

    result = {
        "forecast": horizon,
        "range": {"start": first.isoformat(), "end": last.isoformat()},
        "natal": {
            "date_time": date_time.replace("T", " "), "house_system": "whole_sign",
            "chart_ruler": ruler, "positions": natal_positions_block(natal_chart),
        },
        "headline_transits": headline,
        "headline_note": (
            f"The {len(headline)} weightiest of {total} contacts within {max_orb}° in the period, ranked by how slow "
            f"the transiting planet is, how central the natal point is (Sun, Moon, Asc, MC and the chart ruler "
            f"{ruler} count double) and the aspect"
            + (": the contacts exact within the week come first as its events, then the slow planets in orb as its "
               "backdrop" if scope.get("exact_first") else "")
            + ". Positions are at the exact moment. A contact listed with 'pass n of m' recurs as the planet retrogrades. "
            "'exact' is the exact moment when it falls in the period; 'nearest_exact' is that moment, or otherwise the "
            "nearest one before or after the period, with 'movement' saying whether the orb closes (applying) or opens "
            "(separating) across the period."
        ),
        ("eclipses" if scope["eclipses_only"] else "lunations"): lunations,
        "ingresses": ingresses,
        "stations": stations,
    }

    if horizon == "year":
        by_month: dict[str, list[dict]] = {}
        cursor = date(first.year, first.month, 1)
        while cursor <= last:
            by_month[cursor.strftime("%Y-%m")] = []
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        candidates = (
            [(e["weight"], (e["exact"] or e["start"])[:7], e["label"]) for e in headline]
            + [(ECLIPSE_WEIGHT, e["exact"][:7], e["label"]) for e in lunations]
            + [(SLOWNESS.get(e["planet"], 1) + 1, e["exact"][:7], e["label"]) for e in stations]
        )
        for weight, month, label in sorted(candidates, key=lambda c: -c[0]):
            if month in by_month and len(by_month[month]) < PER_MONTH:
                by_month[month].append(label)
        result["by_month"] = by_month
        themes: dict[str, set[str]] = {}
        for e in headline:
            if e["natal_house"]:
                themes.setdefault(str(e["natal_house"]), set()).add(e["transiting"])
        result["themes"] = {
            f"natal house {h}": sorted(p) for h, p in sorted(themes.items(), key=lambda kv: int(kv[0]))
        }

    result["left_out"] = scope["left_out"]
    result["how_to_read"] = (
        "Quote the labels; every date and degree here comes from the ephemeris. Lead with the headline transits "
        "in order, then the lunations/eclipses, stations and ingresses that fall in the period. Do not add transits "
        "that are not listed -- check any you want to mention with verify_claim."
    )
    return result


def forecast_week(
    date_time: Annotated[str, Field(description="Birth date and time, 'YYYY-MM-DD HH:MM'.")],
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    start_date: Annotated[str | None, Field(description="First of the seven days, 'YYYY-MM-DD'. Omit for today.")] = None,
    max_orb: Annotated[float | None, Field(description="Widest orb that counts, in degrees. Default 1.5.")] = None,
    city: Annotated[str | None, Field(description="Birth city, instead of latitude/longitude.")] = None,
    state: str | None = None,
    country: str | None = None,
) -> str:
    """A week's forecast for a birth chart, seven days from start_date: the weightiest transits (Sun, Mercury, Venus, Mars and the slow planets) with exact moments, the week's new/full moons and eclipses in the natal houses, and every station and sign ingress. Use for "my forecast for this week / the week ahead" only. Not for a single day: for "today", "tomorrow" or one named day use create_transit_chart."""
    try:
        latitude, longitude = _resolve(latitude, longitude, city, state, country)
    except ValueError as e:
        return error_response("Invalid location", str(e))
    except Exception as e:
        return error_response("Geocoding failed", str(e))
    bad = _validate(date_time, latitude, longitude)
    if bad:
        return bad
    tz = _chart_tz(latitude, longitude)
    if start_date:
        valid, error = validate_date_string(f"{start_date} 00:00")
        if not valid:
            return error_response("Invalid start_date", error)
        first = date.fromisoformat(start_date)
    else:
        first = datetime.now(tz).date()
    last = first + timedelta(days=WEEK_DAYS - 1)
    orb = 1.5 if max_orb is None else float(max_orb)
    try:
        return _bounded(_digest(date_time, latitude, longitude, first, last, orb, "week"))
    except Exception as e:
        known = describe_chart_error(e)
        return error_response(*known) if known else error_response("Forecast failed", str(e))


def forecast_month(
    date_time: Annotated[str, Field(description="Birth date and time, 'YYYY-MM-DD HH:MM'.")],
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    month: Annotated[str | None, Field(description="The month, 'YYYY-MM'. Omit for the current month.")] = None,
    max_orb: Annotated[float | None, Field(description="Widest orb that counts, in degrees. Default 1.5.")] = None,
    city: Annotated[str | None, Field(description="Birth city, instead of latitude/longitude.")] = None,
    state: str | None = None,
    country: str | None = None,
) -> str:
    """A month's forecast for a birth chart: the weightiest transits (Mars outward) with exact dates, the month's new and full moons and eclipses in the natal houses, and every station and sign ingress. Use for "my forecast for this month / October"."""
    try:
        latitude, longitude = _resolve(latitude, longitude, city, state, country)
    except ValueError as e:
        return error_response("Invalid location", str(e))
    except Exception as e:
        return error_response("Geocoding failed", str(e))
    bad = _validate(date_time, latitude, longitude)
    if bad:
        return bad
    try:
        tz = _chart_tz(latitude, longitude)
        if month:
            y, m = (int(x) for x in month.split("-"))
            first = date(y, m, 1)
        else:
            today = datetime.now(tz).date()
            first = date(today.year, today.month, 1)
        last = date(first.year, first.month, monthrange(first.year, first.month)[1])
    except (ValueError, TypeError):
        return error_response("Invalid month", "Use 'YYYY-MM', e.g. '2026-10'.")
    orb = 1.5 if max_orb is None else float(max_orb)
    try:
        return _bounded(_digest(date_time, latitude, longitude, first, last, orb, "month"))
    except Exception as e:
        known = describe_chart_error(e)
        return error_response(*known) if known else error_response("Forecast failed", str(e))


def forecast_year(
    date_time: Annotated[str, Field(description="Birth date and time, 'YYYY-MM-DD HH:MM'.")],
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    start_date: Annotated[str | None, Field(description="First day of the year to cover, 'YYYY-MM-DD'. Omit for today.")] = None,
    max_orb: Annotated[float | None, Field(description="Widest orb that counts, in degrees. Default 1.5.")] = None,
    city: Annotated[str | None, Field(description="Birth city, instead of latitude/longitude.")] = None,
    state: str | None = None,
    country: str | None = None,
) -> str:
    """A year's forecast for a birth chart, from start_date: the weightiest slow-planet transits (Jupiter outward) with exact dates and retrograde passes, the eclipses in the natal houses, stations and ingresses, a month-by-month skeleton and the natal houses most activated. Use for "my forecast for the year ahead / for 2027"."""
    try:
        latitude, longitude = _resolve(latitude, longitude, city, state, country)
    except ValueError as e:
        return error_response("Invalid location", str(e))
    except Exception as e:
        return error_response("Geocoding failed", str(e))
    bad = _validate(date_time, latitude, longitude)
    if bad:
        return bad
    tz = _chart_tz(latitude, longitude)
    if start_date:
        valid, error = validate_date_string(f"{start_date} 00:00")
        if not valid:
            return error_response("Invalid start_date", error)
        first = date.fromisoformat(start_date)
    else:
        first = datetime.now(tz).date()
    last = first + timedelta(days=365)
    orb = 1.5 if max_orb is None else float(max_orb)
    try:
        return _bounded(_digest(date_time, latitude, longitude, first, last, orb, "year"))
    except Exception as e:
        known = describe_chart_error(e)
        return error_response(*known) if known else error_response("Forecast failed", str(e))


def register(mcp: MCPServer):
    """Register the forecast tools."""
    mcp.add_tool(
        forecast_week,
        name="forecast_week",
        description=(
            "A week's forecast for a birth chart, seven days from start_date (today if omitted): the weightiest "
            "transits of the Sun, Mercury, Venus, Mars and the slow planets with exact moments and both positions, "
            "the week's new/full moons and eclipses in the natal houses, and every station and sign ingress -- ranked "
            "and labelled, ready to quote. Use for 'my forecast for this week / the week ahead / next week'. The Moon "
            "is left out: for its contacts use list_upcoming_transits with object_filter='Moon'. For a month use "
            "forecast_month; for a year use forecast_year."
        ),
    )
    mcp.add_tool(
        forecast_month,
        name="forecast_month",
        description=(
            "A month's forecast for a birth chart: the weightiest transits (Mars outward) with exact dates and both "
            "positions, the month's new/full moons and eclipses in the natal houses, and every station and sign "
            "ingress -- ranked and labelled, ready to quote. Use for 'my forecast for this month / for October'. "
            "For a week use forecast_week; for a year use forecast_year."
        ),
    )
    mcp.add_tool(
        forecast_year,
        name="forecast_year",
        description=(
            "A year's forecast for a birth chart from start_date: the weightiest slow-planet transits (Jupiter "
            "outward) with exact dates and retrograde passes, the eclipses in the natal houses, stations, ingresses, "
            "a month-by-month skeleton and the natal houses most activated -- ranked and labelled. Use for 'my "
            "forecast for the year ahead / for 2027'. For one month use forecast_month."
        ),
    )
