"""Timing tools for electional and horary work: planetary hours, the
void-of-course Moon, and lunations and eclipses.

The astronomy is immanuel's (and the Swiss Ephemeris it is built on):
positions, aspect and sign-change searches, lunations and eclipses. What this
module adds is the traditional rule layer on top -- which planet rules which
hour, when the Moon counts as void -- so the model never has to work either
out for itself. Every result says what it means in plain words.
"""

import json
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from astro_mcp.config import get_config
from astro_mcp.schemas import get_coordinates_for_params
from astro_mcp.utils import error_response, validate_date_string

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Chaldean order, slowest to fastest: the sequence the hours cycle through.
CHALDEAN = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
# Each weekday's ruler (Monday = 0, as datetime.weekday() counts).
DAY_RULERS = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]

# Ptolemaic aspects: the ones that end a void-of-course Moon.
PTOLEMAIC = {"Conjunction": 0.0, "Sextile": 60.0, "Square": 90.0, "Trine": 120.0, "Opposition": 180.0}

MINUTE = 1 / 1440


def _dumps(data: dict) -> str:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def _zone(latitude: float | None, longitude: float | None) -> ZoneInfo | timezone:
    """The place's timezone via immanuel's lookup; the machine's without a place."""
    if latitude is not None and longitude is not None:
        try:
            from immanuel.tools.date import timezone_lookup
            return ZoneInfo(timezone_lookup(float(latitude), float(longitude)))
        except Exception:
            pass
    return datetime.now().astimezone().tzinfo  # type: ignore[return-value]


def _zone_name(tz) -> str:
    return getattr(tz, "key", None) or datetime.now(tz).tzname() or "local"


def _jd(dt: datetime) -> float:
    """Julian day (UT) of an aware datetime."""
    epoch = datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc)
    return 2451545.0 + (dt.astimezone(timezone.utc) - epoch).total_seconds() / 86400.0


def _dt(jd: float, tz) -> datetime:
    epoch = datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc)
    return (epoch + timedelta(days=jd - 2451545.0)).astimezone(tz)


def _local(jd: float, tz) -> str:
    """'YYYY-MM-DD HH:MM', rounded to the nearest minute, in `tz`."""
    return (_dt(jd, tz) + timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M")


def _position(longitude: float) -> str:
    """"18°34' Aries" -- degree within the sign, truncated to the minute."""
    lon = longitude % 360
    within = lon % 30
    degrees = int(within)
    minutes = int((within - degrees) * 60)
    return f"{degrees}°{minutes:02d}' {SIGNS[int(lon // 30)]}"


def _resolve_place(latitude, longitude, city, state, country, required: bool):
    """(lat, lon, matched-name) or (None, None, None) when optional and absent."""
    if latitude is None and longitude is None and not city:
        if required:
            raise ValueError("A place is required: give latitude and longitude, or a city.")
        return None, None, None
    return get_coordinates_for_params(latitude, longitude, city, state, country)


def _parse_day(value: str | None, label: str, tz) -> date:
    if not value:
        return datetime.now(tz).date()
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        raise ValueError(f"{label} must be a date as 'YYYY-MM-DD', got {value!r}.")


def _place_note(lat, lon, matched, tz) -> dict:
    note: dict = {"timezone": _zone_name(tz)}
    if lat is not None:
        note["latitude"] = round(float(lat), 4)
        note["longitude"] = round(float(lon), 4)
    if matched:
        note["matched_location"] = matched
    return note


# ---------------------------------------------------------------------------
# Planetary hours
# ---------------------------------------------------------------------------

def _sun_event(jd_start: float, lat: float, lon: float, rise: bool) -> float | None:
    """Next sunrise or sunset after jd_start (UT), by the almanac convention
    (the Sun's upper limb, with refraction). None where the Sun neither rises
    nor sets that day (polar day or night)."""
    import swisseph as swe
    flag = swe.CALC_RISE if rise else swe.CALC_SET
    res, tret = swe.rise_trans(jd_start, swe.SUN, flag, (float(lon), float(lat), 0.0))
    return tret[0] if res == 0 else None


def hour_at(jd: float, lat: float, lon: float, tz) -> dict | None:
    """The planetary hour in effect at a moment: its ruler, number and the
    day's ruler. The planetary day runs from sunrise to sunrise, so a moment
    before dawn belongs to the previous day. None where the Sun doesn't rise
    and set (polar day or night)."""
    rise = _sun_event(jd - 2, lat, lon, rise=True)
    if rise is None:
        return None
    while True:
        following = _sun_event(rise + 0.01, lat, lon, rise=True)
        if following is None or following > jd:
            break
        rise = following
    sunset = _sun_event(rise, lat, lon, rise=False)
    next_rise = _sun_event(sunset, lat, lon, rise=True) if sunset is not None else None
    if sunset is None or next_rise is None:
        return None
    day_ruler = DAY_RULERS[_dt(rise, tz).weekday()]
    if jd < sunset:
        n = int((jd - rise) / ((sunset - rise) / 12))
    else:
        n = 12 + int((jd - sunset) / ((next_rise - sunset) / 12))
    n = max(0, min(23, n))
    return {
        "hour": n + 1,
        "period": "day" if n < 12 else "night",
        "ruler": CHALDEAN[(CHALDEAN.index(day_ruler) + n) % 7],
        "day_ruler": day_ruler,
    }


def planetary_hours(
    date: Annotated[str | None, Field(description="The day, 'YYYY-MM-DD'. Omit for today at the place.")] = None,
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    city: Annotated[str | None, Field(description="City, geocoded to coordinates. Use instead of latitude/longitude.")] = None,
    state: str | None = None,
    country: str | None = None,
) -> str:
    """The 24 planetary hours of a day at a place, and the one in effect now.

    Use for electional timing ("a good hour to send this", "what's the hour of
    Venus today") and horary radicality (the hour ruler at the moment a
    question is asked). A place is required: hours run from local sunrise to
    sunset (12 day hours) and sunset to the next sunrise (12 night hours), so
    they are unequal and differ by location and season.

    Report the hours as returned -- do not compute hour lengths or rulers
    yourself. Times are local to the place.
    """
    try:
        lat, lon, matched = _resolve_place(latitude, longitude, city, state, country, required=True)
        tz = _zone(lat, lon)
        day = _parse_day(date, "date", tz)
    except ValueError as e:
        return error_response("Invalid input", str(e))
    except RuntimeError as e:
        return error_response("Geocoding failed", str(e))

    try:
        midnight = _jd(datetime(day.year, day.month, day.day, tzinfo=tz))
        sunrise = _sun_event(midnight, lat, lon, rise=True)
        sunset = _sun_event(sunrise, lat, lon, rise=False) if sunrise is not None else None
        next_sunrise = _sun_event(sunset, lat, lon, rise=True) if sunset is not None else None
    except Exception as e:
        return error_response("Sunrise calculation failed", str(e))
    if sunrise is None or sunset is None or next_sunrise is None or _dt(sunrise, tz).date() != day:
        return error_response(
            "No planetary hours for this day",
            "The Sun doesn't both rise and set here on this date (polar day or night), "
            "so the day can't be divided into planetary hours.",
        )

    day_ruler = DAY_RULERS[day.weekday()]
    start_index = CHALDEAN.index(day_ruler)
    day_len = (sunset - sunrise) / 12
    night_len = (next_sunrise - sunset) / 12

    hours = []
    for n in range(24):
        is_day = n < 12
        begin = sunrise + n * day_len if is_day else sunset + (n - 12) * night_len
        end = begin + (day_len if is_day else night_len)
        hours.append({
            "hour": n + 1,
            "period": "day" if is_day else "night",
            "ruler": CHALDEAN[(start_index + n) % 7],
            "start": _local(begin, tz)[11:],
            "end": _local(end, tz)[11:],
            "_jd": (begin, end),
        })

    now_jd = _jd(datetime.now(timezone.utc))
    current = next((h for h in hours if h["_jd"][0] <= now_jd < h["_jd"][1]), None)
    for h in hours:
        del h["_jd"]

    result = {
        "date": day.isoformat(),
        "day_ruler": day_ruler,
        "sunrise": _local(sunrise, tz)[11:],
        "sunset": _local(sunset, tz)[11:],
        "next_sunrise": _local(next_sunrise, tz),
        "day_hour_minutes": round(day_len * 1440, 1),
        "night_hour_minutes": round(night_len * 1440, 1),
        "current_hour": (
            {k: current[k] for k in ("hour", "period", "ruler", "start", "end")} if current else None
        ),
        "hours": hours,
        "how_to_read": (
            f"The day ({day.strftime('%A')}) belongs to {day_ruler}, which rules the first hour after sunrise; "
            "the rest follow in Chaldean order. Day hours and night hours differ in length. "
            "current_hour is null unless this planetary day is under way now."
        ),
        **_place_note(lat, lon, matched, tz),
    }
    return _dumps(result)


# ---------------------------------------------------------------------------
# Void-of-course Moon
# ---------------------------------------------------------------------------

TRADITIONAL_PLANETS = ["Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
OUTER_PLANETS = ["Uranus", "Neptune", "Pluto"]


def _planet_id(name: str) -> int:
    from immanuel.const import chart
    return getattr(chart, name.upper())


def _moon_sign_stays(jd_from: float, jd_to: float) -> list[tuple[int, float, float]]:
    """(sign, entry jd, exit jd) for each sign the Moon occupies in the window.

    Built by chaining sign exits from a few days earlier, so each stay's entry
    is exactly the previous stay's exit. (immanuel's previous_sign_ingress,
    asked while the Moon is still in the sign, returns her *previous* visit's
    ingress -- a month early -- so it isn't used.)
    """
    from immanuel.const import chart
    from immanuel.tools import sweph, transit

    stays = []
    jd = jd_from - 3  # the Moon spends at most ~2.7 days in a sign
    entry = None
    while jd < jd_to:
        sign = int((sweph.planet(chart.MOON, jd)["lon"] % 360) // 30) + 1
        exit_ = transit.next_sign_egress(chart.MOON, sign, jd)
        if entry is not None and exit_ > jd_from:
            stays.append((sign, entry, exit_))
        entry = exit_
        jd = exit_ + MINUTE / 60
    return stays


def _last_aspect(entry: float, exit_: float, planets: list[str]) -> tuple[str, str, float] | None:
    """The Moon's last exact Ptolemaic aspect to any of `planets` while in the
    sign: (aspect, planet, jd), or None if she makes none there."""
    from immanuel.const import chart
    from immanuel.tools import transit

    best = None
    for planet in planets:
        pid = _planet_id(planet)
        for aspect, angle in PTOLEMAIC.items():
            jd = transit.previous_aspect_between(chart.MOON, pid, exit_ - MINUTE / 60, angle)
            if entry <= jd < exit_ and (best is None or jd > best[2]):
                best = (aspect, planet, jd)
    return best


def void_periods(jd_from: float, jd_to: float, include_outer_planets: bool = False) -> list[dict]:
    """Void-of-course windows overlapping [jd_from, jd_to], raw jds, for tests and reuse."""
    planets = TRADITIONAL_PLANETS + (OUTER_PLANETS if include_outer_planets else [])
    out = []
    for sign, entry, exit_ in _moon_sign_stays(jd_from, jd_to):
        last = _last_aspect(entry, exit_, planets)
        start = last[2] if last else entry
        if exit_ <= jd_from or start >= jd_to:
            continue
        out.append({"sign": SIGNS[sign - 1], "next_sign": SIGNS[sign % 12], "entry": entry,
                    "start": start, "end": exit_, "last_aspect": last})
    return out


def moon_void_periods(
    start_date: Annotated[str | None, Field(description="First day to cover, 'YYYY-MM-DD'. Default: today.")] = None,
    end_date: Annotated[str | None, Field(description="Last day to cover, 'YYYY-MM-DD'. Default: 14 days after start. At most 92 days.")] = None,
    include_outer_planets: Annotated[bool, Field(description="Count aspects to Uranus, Neptune and Pluto too (modern practice). Default false: the traditional seven planets only.")] = False,
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    city: Annotated[str | None, Field(description="City whose local time to report in. Optional; without a place, times are in the server's timezone.")] = None,
    state: str | None = None,
    country: str | None = None,
) -> str:
    """When the Moon is void of course: from her last exact major aspect in a
    sign until she enters the next sign.

    Use for electional questions ("is the Moon void now?", "when is a good
    time to sign, launch or start something?") and horary considerations (a
    void Moon traditionally means "nothing will come of the matter"). Each
    period gives local start and end times, its length, and the aspect that
    began it. `void_now` answers "is it void right now?" directly.

    Report the periods as returned -- do not work out void times yourself.
    A place only sets which local time is shown; the void periods themselves
    are the same everywhere.
    """
    try:
        lat, lon, matched = _resolve_place(latitude, longitude, city, state, country, required=False)
        tz = _zone(lat, lon)
        first = _parse_day(start_date, "start_date", tz)
        last = _parse_day(end_date, "end_date", tz) if end_date else first + timedelta(days=14)
    except ValueError as e:
        return error_response("Invalid input", str(e))
    except RuntimeError as e:
        return error_response("Geocoding failed", str(e))
    if last < first:
        return error_response("Invalid range", "end_date is before start_date.")
    if (last - first).days > 92:
        return error_response("Range too long", "Ask for at most 92 days at a time.")

    jd_from = _jd(datetime(first.year, first.month, first.day, tzinfo=tz))
    jd_to = _jd(datetime(last.year, last.month, last.day, tzinfo=tz) + timedelta(days=1))
    try:
        periods = void_periods(jd_from, jd_to, include_outer_planets)
    except Exception as e:
        return error_response("Void-of-course calculation failed", str(e))

    now_jd = _jd(datetime.now(timezone.utc))
    void_now = None
    listed = []
    for p in periods:
        entry = {
            "moon_in": p["sign"],
            "void_from": _local(p["start"], tz),
            "void_until": _local(p["end"], tz),
            "enters": p["next_sign"],
            "hours": round((p["end"] - p["start"]) * 24, 1),
            "began_with": (
                f"Moon {p['last_aspect'][0].lower()} {p['last_aspect'][1]}" if p["last_aspect"]
                else f"no aspect in {p['sign']}: void for the whole sign"
            ),
        }
        listed.append(entry)
        if p["start"] <= now_jd < p["end"]:
            void_now = entry

    result = {
        "range": {"start": first.isoformat(), "end": last.isoformat()},
        "planets_counted": "traditional seven" if not include_outer_planets else "including Uranus, Neptune, Pluto",
        "void_now": void_now,
        "periods": listed,
        "how_to_read": (
            "Each period runs from the Moon's last exact major aspect (conjunction, sextile, square, trine, "
            "opposition) in her sign until she enters the next sign. void_now is the period in effect now, "
            "or null if the Moon isn't void. Times are local, to the minute."
        ),
        **_place_note(lat, lon, matched, tz),
    }
    return _dumps(result)


# ---------------------------------------------------------------------------
# Lunations and eclipses
# ---------------------------------------------------------------------------

NATAL_POINTS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
                "Uranus", "Neptune", "Pluto", "Asc", "MC"]
CONTACT_ASPECTS = {"conjunction": 0.0, "opposition": 180.0, "square": 90.0}
CONTACT_ORB = 3.0


def _house_of(longitude: float, cusps: list[float]) -> int:
    """House (1-12) a longitude falls in, from the twelve cusp longitudes."""
    lon = longitude % 360
    for i in range(12):
        a, b = cusps[i] % 360, cusps[(i + 1) % 12] % 360
        span = (b - a) % 360
        if (lon - a) % 360 < span:
            return i + 1
    return 12


def _natal_frame(date_time: str, lat: float, lon: float, house_system: str | None):
    """(natal point longitudes, house cusps) of a birth chart, via immanuel."""
    from immanuel import charts
    natal = charts.Natal(
        charts.Subject(date_time=date_time.replace("T", " "), latitude=lat, longitude=lon),
        config=get_config(house_system),
    )
    points = {o.name: o.longitude.raw % 360 for o in natal.objects.values() if o.name in NATAL_POINTS}
    cusps = [h.longitude.raw for h in sorted(natal.houses.values(), key=lambda h: h.number)]
    return points, cusps


def _contacts(longitude: float, points: dict[str, float]) -> list[str]:
    found = []
    for name, p in points.items():
        sep = abs((longitude - p + 180) % 360 - 180)
        for aspect, angle in CONTACT_ASPECTS.items():
            orb = abs(sep - angle)
            if orb <= CONTACT_ORB:
                found.append((orb, f"{aspect} natal {name} ({orb:.1f}°)"))
    return [text for _, text in sorted(found)]


def _eclipse_kind(code) -> str:
    """immanuel's eclipse type code as a word: 'total', 'annular', 'partial'..."""
    from immanuel.const import names
    return names.ECLIPSE_TYPES.get(code, "").lower()


def lunations_and_eclipses(
    start_date: Annotated[str | None, Field(description="First day to cover, 'YYYY-MM-DD'. Default: today.")] = None,
    end_date: Annotated[str | None, Field(description="Last day to cover, 'YYYY-MM-DD'. Default: 6 months after start. At most 2 years.")] = None,
    date_time: Annotated[str | None, Field(description="Optional birth date and time, 'YYYY-MM-DD HH:MM' local. With a birth place, each event gets its natal house and contacts.")] = None,
    house_system: Annotated[str | None, Field(description="House system for natal houses. Default 'whole_sign'.")] = None,
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    city: Annotated[str | None, Field(description="With date_time: the birthplace. Without: the place whose local time to report in.")] = None,
    state: str | None = None,
    country: str | None = None,
) -> str:
    """New moons, full moons and eclipses in a date range, each with its
    exact local time and zodiac degree.

    Use for "when is the next new/full moon or eclipse?", planning around
    lunations, and eclipse seasons. Give a birth date_time and birthplace to
    also get, for each event, the natal house it falls in and any natal
    planets or angles it conjoins, opposes or squares within 3 degrees --
    how it lands in that person's chart.

    Report the dates and degrees as returned -- do not calculate lunations or
    eclipses yourself.
    """
    try:
        lat, lon, matched = _resolve_place(latitude, longitude, city, state, country, required=bool(date_time))
        tz = _zone(lat, lon)
        first = _parse_day(start_date, "start_date", tz)
        last = _parse_day(end_date, "end_date", tz) if end_date else first + timedelta(days=183)
    except ValueError as e:
        return error_response("Invalid input", str(e))
    except RuntimeError as e:
        return error_response("Geocoding failed", str(e))
    if last < first:
        return error_response("Invalid range", "end_date is before start_date.")
    if (last - first).days > 731:
        return error_response("Range too long", "Ask for at most 2 years at a time.")
    if date_time:
        valid, err = validate_date_string(date_time)
        if not valid:
            return error_response("Invalid date", err)

    from immanuel.const import chart
    from immanuel.tools import sweph, transit

    jd_from = _jd(datetime(first.year, first.month, first.day, tzinfo=tz))
    jd_to = _jd(datetime(last.year, last.month, last.day, tzinfo=tz) + timedelta(days=1))

    try:
        natal = _natal_frame(date_time, lat, lon, house_system) if date_time else None
        events: list[tuple[float, str, float]] = []
        for kind, finder, body in (("new moon", transit.next_new_moon, chart.SUN),
                                   ("full moon", transit.next_full_moon, chart.MOON)):
            jd = jd_from
            while True:
                jd = finder(jd)
                if jd >= jd_to:
                    break
                events.append((jd, kind, sweph.planet(body, jd)["lon"]))
                jd += 1
        for kind, finder, body in (("solar eclipse", transit.next_solar_eclipse, chart.SUN),
                                   ("lunar eclipse", transit.next_lunar_eclipse, chart.MOON)):
            jd = jd_from
            while True:
                found = finder(jd)
                eclipse_type, jd = (found if isinstance(found, tuple) else (None, found))
                if jd >= jd_to:
                    break
                events.append((jd, f"{_eclipse_kind(eclipse_type)} {kind}".strip(),
                               sweph.planet(body, jd)["lon"]))
                jd += 1
    except Exception as e:
        return error_response("Lunation calculation failed", str(e))

    events.sort()
    listed = []
    for jd, kind, lon_ in events:
        entry = {"event": kind, "exact": _local(jd, tz), "position": _position(lon_)}
        if natal:
            points, cusps = natal
            entry["natal_house"] = _house_of(lon_, cusps)
            entry["contacts"] = _contacts(lon_, points)
        listed.append(entry)

    result = {
        "range": {"start": first.isoformat(), "end": last.isoformat()},
        "events": listed,
        "how_to_read": (
            "position is the Sun's degree for new moons and solar eclipses, the Moon's for full moons and "
            "lunar eclipses. An eclipse falls within a day of the new or full moon it coincides with."
            + (" natal_house and contacts relate each event to the birth chart given."
               if natal else "")
        ),
        **_place_note(lat, lon, matched, tz),
    }
    if natal:
        result["house_system"] = house_system or "whole_sign"
    return _dumps(result)


def register(mcp: MCPServer):
    """Register the timing tools."""
    mcp.add_tool(
        planetary_hours,
        name="planetary_hours",
        description=(
            "The 24 planetary hours of a day at a place (unequal hours from local sunrise and sunset, "
            "Chaldean order), the day's ruler, and the hour in effect now. Use for electional timing "
            "('a Venus hour today', 'the best hour to send this') and for the hour ruler in horary. "
            "Needs a place (latitude/longitude or city). Report the hours exactly as returned; "
            "never compute planetary hours yourself."
        ),
    )
    mcp.add_tool(
        moon_void_periods,
        name="moon_void_periods",
        description=(
            "When the Moon is void of course -- from her last exact major aspect in a sign until she "
            "changes sign -- over a date range, and whether she is void right now (void_now). Use for "
            "'is the Moon void?', choosing a time to start, sign or launch something, and horary "
            "considerations. Traditional seven planets by default; include_outer_planets for modern "
            "practice. Report the periods exactly as returned; never work out void times yourself."
        ),
    )
    mcp.add_tool(
        lunations_and_eclipses,
        name="lunations_and_eclipses",
        description=(
            "New moons, full moons, and solar and lunar eclipses in a date range, with exact local time "
            "and degree. Add a birth date_time and birthplace to get each event's natal house and any "
            "natal planets or angles it conjoins, opposes or squares (within 3 degrees). Use for "
            "'when is the next new moon / eclipse?' and how lunations fall in someone's chart. Report "
            "results exactly as returned; never calculate lunations or eclipses yourself."
        ),
    )
