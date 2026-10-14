"""Transit chart tool for astro-mcp."""

import json
from typing import Annotated
from mcp.server.mcpserver import MCPServer
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pydantic import Field

from astro_mcp.utils import (
    aspect_symbol,
    describe_chart_error, NATAL_TRANSIT_TARGETS, SIGNS, SPEED_ORDER, compact_chart_json, error_response,
    calculate_transit_to_natal_aspects, calculate_major_aspects, MAJOR_OBJECTS, MAJOR_ASPECTS, filter_aspects,
    validate_date_string, validate_latitude, validate_longitude, parse_names,
    assign_natal_houses_to_transit_objects, sign_position, natal_positions_block, canonical_point, orb_for,
    aspect_label,
)
from astro_mcp.config import get_config
from astro_mcp.schemas import get_coordinates_for_params

# MCP clients truncate large tool responses (~25KB). Keep list output
# under this budget; when it is exceeded the spans are first re-encoded as
# positional arrays (lossless), and only if that is still too large are
# high-frequency fast-object spans omitted and reported.
_MAX_RESPONSE_CHARS = 25000


def _transits_for_date(date_str: str, latitude, longitude, aspects_to, config):
    """Build an immanuel Transits chart for a specific local date/time.

    immanuel's Transits constructor hardcodes datetime.now() and offers no
    way to pass a date, so we replace its subject with the requested moment
    (local time at the chart location, timezone geolocated by immanuel) and
    regenerate the chart data.

    latitude/longitude may be None (transits without a birth chart); the
    config's default location is used. Ecliptic planet positions — and thus
    the aspects reported — do not depend on the location.
    """
    from immanuel import charts

    lat = float(latitude) if latitude is not None else config.default_latitude
    lon = float(longitude) if longitude is not None else config.default_longitude

    transit_chart = charts.Transits(
        latitude=lat,
        longitude=lon,
        aspects_to=aspects_to,
        config=config,
    )
    transit_chart._native = charts.Subject(
        date_time=date_str,
        latitude=lat,
        longitude=lon,
    )
    transit_chart.generate()
    transit_chart.set_aspects()
    transit_chart.wrap()
    return transit_chart


def _chart_tz(latitude, longitude) -> "ZoneInfo":
    """Timezone of the chart location via immanuel's own geolocation lookup.

    Falls back to the machine's local timezone when the lookup fails, so
    times are always reported in *a* well-defined zone.
    """
    try:
        from immanuel.tools.date import timezone_lookup
        return ZoneInfo(timezone_lookup(float(latitude), float(longitude)))
    except Exception:
        return datetime.now().astimezone().tzinfo


def _local_now_str(latitude, longitude) -> str:
    """Current wall-clock time at the chart location, 'YYYY-MM-DD HH:MM'.

    Anchoring "now" to the chart location's timezone (rather than the
    machine's local time) keeps the transit moment correct when the server
    runs in a different timezone than the chart's birthplace.
    """
    return datetime.now(_chart_tz(latitude, longitude)).strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Exact aspect moments
#
# Spans and snapshots report aspect ORBS from once-per-day samples. The
# moment an aspect is exact (orb 0) is refined by bisection on raw
# Swiss-Ephemeris single-planet queries (immanuel's backend, ~3us each -
# ~4000x cheaper than a full chart generation), bracketed by the midnight
# samples the scan already computed.
# ---------------------------------------------------------------------------

# The Moon moves ~13 degrees a day, so at the default 1.5 degree orb an
# aspect of hers lasts only about five hours. Once-a-day sampling therefore
# misses most lunar contacts outright and reports the survivors -- the ones
# that happen to straddle midnight -- as if they lasted a day. Sampling her
# separately at this step catches them; the ephemeris queries cost
# microseconds each, so the finer pass is effectively free.
FAST_BODIES = {'Moon': 2}  # name -> sampling step in hours

# Beyond this horizon a fast body is left out of the scan unless explicitly
# asked for. Sampled properly the Moon aspects something every few hours, so
# over two months she is 80% of the spans and drowns everything slower. The
# old behaviour reported a tenth of her contacts, which was not a filter but
# an accident of once-a-day sampling: a wrong number that looked like a
# short list. Better to be accurate when asked and quiet when not.
FAST_BODY_HORIZON_DAYS = 10


def _sample_fast_body(samples: dict, name: str, step_hours: int,
                      targets: dict | list[str], ids: dict[str, int],
                      start: date, end: date, tz,
                      aspect_types, max_orb) -> None:
    """Add sub-daily samples for a fast body into the daily sample map.

    Writes into the same {key: {day: orb}} structure the daily scan builds,
    so span merging and exactness refinement are unchanged -- this only
    stops fast contacts being missed between midnights.

    `targets` is either the natal positions (a dict: fixed points, the key
    is (fast body, natal point, aspect)) or, in a scan without a birth
    chart, the names of the other transiting bodies, read from the
    ephemeris at each moment. Those pairs are keyed faster body first, as
    the daily scan keys them (see SPEED_ORDER), so the two sets of samples
    merge into one span.
    """
    from immanuel.tools import ephemeris
    from astro_mcp.utils import _aspects_between

    object_id = ids.get(name)
    if object_id is None:
        return

    base = datetime(start.year, start.month, start.day, tzinfo=tz)
    total_hours = ((end - start).days + 1) * 24
    moving = None if isinstance(targets, dict) else [t for t in targets if t != name and t in ids]

    for hour in range(0, total_hours, step_hours):
        moment = base + timedelta(hours=hour)
        jd = _jd_of(moment)
        longitude = ephemeris.get_planet(object_id, jd)["lon"] % 360
        day_iso = moment.date().isoformat()

        if moving is None:
            others = list(targets.items())
        else:
            others = [(other, ephemeris.get_planet(ids[other], jd)["lon"] % 360) for other in moving]

        for other, other_longitude in others:
            if moving is None or SPEED_ORDER.index(name) < SPEED_ORDER.index(other):
                key_pair = (name, other)
            else:
                key_pair = (other, name)
            for aspect_name, orb in _aspects_between(
                longitude, other_longitude, name, other
            ):
                if aspect_types and aspect_name not in aspect_types:
                    continue
                if max_orb is not None and orb > max_orb:
                    continue
                by_day = samples.setdefault((*key_pair, aspect_name), {})
                previous = by_day.get(day_iso)
                by_day[day_iso] = orb if previous is None else min(previous, orb)


ZODIAC = SIGNS

# Field order for spans encoded as positional arrays (see span_fields) --
# the slimmed form an oversized response falls back to. Only what can't be
# read off elsewhere is kept: from_sign is the last word of from_position,
# and in natal mode the natal end is natal.positions[to_object], so those
# are left out here (the full-object form carries all of them). The house
# fields need a birth chart to mean anything, so general mode omits them.
COMPACT_BASE_FIELDS = ["start", "end", "from_object", "to_object", "type", "orb", "exact", "from_position"]
NATAL_FIELDS = COMPACT_BASE_FIELDS + ["from_house", "to_house", "from_retrograde"]
GENERAL_FIELDS = COMPACT_BASE_FIELDS + ["to_position", "from_retrograde", "to_retrograde"]
SPAN_FIELDS_NOTE = (
    "Spans are positional arrays in span_fields order (the per-span 'label' sentence is left out in this form). "
    "A sign is the last word of a *_position; in natal mode from_object is the transiting body, to_object the "
    "natal point, and the natal end of each span is natal.positions[to_object]."
)


def _house_of(lon: float, cusps: list[tuple[int, float]]) -> int:
    """House number a longitude falls in, from the natal chart's cusps.

    cusps is [(house number, cusp longitude)] in house order, which is also
    zodiacal order, so house n runs from its cusp to the next one. Works for
    any house system, not only whole sign.
    """
    for i, (number, cusp) in enumerate(cusps):
        following = cusps[(i + 1) % len(cusps)][1]
        if (lon - cusp) % 360 < (following - cusp) % 360:
            return number
    return cusps[0][0]


def _peak_facts(from_name: str, to_name: str, ids: dict[str, int],
                natal_positions: dict | None, natal_houses: dict | None,
                cusps: list[tuple[int, float]] | None,
                exact: str | None, peak_day: str, tz) -> dict:
    """What the two bodies are doing at the aspect's tightest moment.

    Sign and degree ("11°24' Aries") for both ends, so an aspect reads as
    "Saturn 11°24' Aries square natal Saturn 12°03' Scorpio" with nothing
    left for the reader to supply; in natal mode the natal houses involved
    and whether the transiting body is retrograde, in general mode whether
    either is. That moment is the exact one when the scan found it,
    otherwise local midnight of the day with the smallest orb. Read from
    the same ephemeris the aspect was found with, so it always agrees with
    the spans.
    """
    from immanuel.tools import ephemeris

    if exact:
        moment = datetime.strptime(exact, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    else:
        day = date.fromisoformat(peak_day)
        moment = datetime(day.year, day.month, day.day, tzinfo=tz)
    jd = _jd_of(moment)

    a = ephemeris.get_planet(ids[from_name], jd)
    at = sign_position(a["lon"])
    facts = {"from_sign": at["sign"], "from_position": at["position"]}
    if natal_positions is not None:
        to = sign_position(natal_positions[to_name])
        facts["to_sign"] = to["sign"]
        facts["to_position"] = to["position"]
        facts["from_house"] = _house_of(at["longitude"], cusps) if cusps else None
        facts["to_house"] = natal_houses.get(to_name) if natal_houses else None
        facts["from_retrograde"] = a["speed"] < 0
    else:
        b = ephemeris.get_planet(ids[to_name], jd)
        to = sign_position(b["lon"])
        facts["to_sign"] = to["sign"]
        facts["to_position"] = to["position"]
        facts["from_retrograde"] = a["speed"] < 0
        facts["to_retrograde"] = b["speed"] < 0
    return facts


def _spans_per_object(transits: list[dict], scanned: list[str], natal_mode: bool) -> dict:
    """How many spans each scanned object has -- zeros included.

    A planet with no aspects in the window is listed as 0 rather than left
    out: absence in a list is what a reader quietly fills in, an explicit
    zero is a fact. In general mode both ends of a pair count, since the
    pair's order is only a convention.
    """
    counts = {name: 0 for name in scanned}
    for t in transits:
        counts[t["from_object"]] = counts.get(t["from_object"], 0) + 1
        if not natal_mode:
            counts[t["to_object"]] = counts.get(t["to_object"], 0) + 1
    return counts


def _object_ids(chart) -> dict[str, int]:
    """Major object name -> immanuel object id, for raw ephemeris queries.

    Object ids are static per name, so the map can come from any chart.
    """
    return {
        obj.name: object_id
        for object_id, obj in chart.objects.items()
        if obj.name in MAJOR_OBJECTS
    }


def _jd_of(dt: datetime) -> float:
    """Julian day (UT) of an aware datetime."""
    epoch = datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc)
    return 2451545.0 + (dt.astimezone(timezone.utc) - epoch).total_seconds() / 86400.0


def _signed_orb(lon_a: float, lon_b: float, angle: float, eps: float) -> float:
    """Signed deviation from an aspect angle - the orb with a direction.

    eps (+1/-1) selects which side of the pair the aspect sits on; the
    magnitude equals the orb _aspects_between() reports, so a zero
    crossing is exactly the moment the aspect is exact.
    """
    f = (lon_a - lon_b - eps * angle) % 360
    if f > 180:
        f -= 360
    return f


def _aspect_side(lon_a: float, lon_b: float, angle: float) -> float:
    """eps for _signed_orb: +1 when the pair sits at +angle, -1 at -angle."""
    d = (lon_a - lon_b) % 360
    if d > 180:
        d -= 360
    return 1.0 if abs(d - angle) <= abs(d + angle) else -1.0


def _bisect(f, jd_lo: float, jd_hi: float, iterations: int = 14) -> float | None:
    """Bisect f over [jd_lo, jd_hi]; a sign change there is required.

    14 iterations shrink a 24h bracket to under 6s, far beyond the
    minute granularity reported. Returns None when no crossing exists.
    """
    f_lo = f(jd_lo)
    f_hi = f(jd_hi)
    if f_lo == 0:
        return jd_lo
    if f_hi == 0:
        return jd_hi
    if f_lo * f_hi > 0:
        return None
    for _ in range(iterations):
        mid = (jd_lo + jd_hi) / 2
        f_mid = f(mid)
        if f_mid == 0:
            return mid
        if f_lo * f_mid < 0:
            jd_hi, f_hi = mid, f_mid
        else:
            jd_lo, f_lo = mid, f_mid
    return (jd_lo + jd_hi) / 2


def _refine_span_exact(run_days: list[str], from_name: str, to_name: str,
                       aspect_type: str, ids: dict[str, int],
                       natal_positions: dict | None, tz) -> str | None:
    """Exact moment of a span as local 'YYYY-MM-DD HH:MM', or None.

    Midnight samples from start-1 through end+1 bracket the crossing
    (for a monotone object the crossing always lies in that window: one
    extra day before covers the aspect that becomes exact in the 24h
    before the first in-orb midnight). Scan them for the first sign
    change of the signed orb, then bisect within that day. None when the
    crossing falls outside that bracket (the span is clipped by the scan
    window).
    """
    from immanuel.tools import ephemeris

    angle = MAJOR_ASPECTS[aspect_type][0]
    start_day = date.fromisoformat(run_days[0])
    end_day = date.fromisoformat(run_days[-1])

    ref_dt = datetime(start_day.year, start_day.month, start_day.day, tzinfo=tz)
    ref_dt -= timedelta(days=1)
    ref_jd = _jd_of(ref_dt)

    def lon_of(name: str, jd: float) -> float:
        if natal_positions is not None:
            return natal_positions[name]
        return ephemeris.get_planet(ids[name], jd)["lon"]

    a0 = ephemeris.get_planet(ids[from_name], ref_jd)["lon"]
    b0 = lon_of(to_name, ref_jd)
    eps = _aspect_side(a0, b0, angle)

    def f(jd: float) -> float:
        return _signed_orb(
            ephemeris.get_planet(ids[from_name], jd)["lon"],
            lon_of(to_name, jd), angle, eps
        )

    n_midnights = (end_day - start_day).days + 3  # start-1 00:00 .. end+1 00:00
    jd_exact = None
    prev_jd, prev_f = ref_jd, f(ref_jd)
    for i in range(1, n_midnights):
        jd = ref_jd + i
        f_now = f(jd)
        if f_now == 0:
            jd_exact = jd
            break
        if prev_f * f_now < 0:
            jd_exact = _bisect(f, prev_jd, jd)
            break
        prev_jd, prev_f = jd, f_now

    if jd_exact is None:
        return None
    # Round to the nearest minute (truncate after a 30s offset)
    dt = ref_dt + timedelta(days=jd_exact - ref_jd, seconds=30)
    return dt.strftime("%Y-%m-%d %H:%M")


def _aspect_exact_at(aspect: dict, ids: dict[str, int],
                     natal_positions: dict | None,
                     snapshot: datetime) -> str | None:
    """Exact moment of a snapshot aspect as local 'YYYY-MM-DD HH:MM', or None.

    Expands outward from the snapshot one day at a time (both directions,
    capped at 180 days) until the signed orb changes sign, then bisects.
    None when the exact moment lies beyond the search radius (slow outer
    planets) - the span list remains the source for those.
    """
    from immanuel.tools import ephemeris

    from_name = aspect["from_object"]
    to_name = aspect["to_object"]
    angle = MAJOR_ASPECTS[aspect["type"]][0]

    ref_jd = _jd_of(snapshot)

    def lon_of(name: str, jd: float) -> float:
        if natal_positions is not None:
            return natal_positions[name]
        return ephemeris.get_planet(ids[name], jd)["lon"]

    a0 = ephemeris.get_planet(ids[from_name], ref_jd)["lon"]
    b0 = lon_of(to_name, ref_jd)
    eps = _aspect_side(a0, b0, angle)

    def f(jd: float) -> float:
        return _signed_orb(
            ephemeris.get_planet(ids[from_name], jd)["lon"],
            lon_of(to_name, jd), angle, eps
        )

    f0 = f(ref_jd)
    if abs(f0) < 0.005:  # exact at the snapshot, to within a couple of arcminutes
        return (snapshot + timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M")

    jd_exact = None
    for days_out in range(1, 181):
        for jd_try in (ref_jd + days_out / 24, ref_jd - days_out / 24):
            f_try = f(jd_try)
            if f0 * f_try < 0:
                lo, hi = sorted((ref_jd, jd_try))
                jd_exact = _bisect(f, lo, hi)
                break
        if jd_exact is not None:
            break

    if jd_exact is None:
        return None
    dt = snapshot + timedelta(days=jd_exact - ref_jd, seconds=30)
    return dt.strftime("%Y-%m-%d %H:%M")


def create_transit_chart(
    date_time: Annotated[str, Field(description="Birth date and time of the natal chart in ISO 8601: 'YYYY-MM-DD HH:MM' (seconds and 'T' separator optional), e.g. '1984-05-10 20:44'.")],
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    transit_date_time: Annotated[str | None, Field(description="Transit date and time in ISO 8601: 'YYYY-MM-DD HH:MM'. Omit for 'now'.")] = None,
    aspect_type: Annotated[str | None, Field(description="Keep only these aspect types, comma-separated, any case: Conjunction, Opposition, Square, Trine, Sextile.")] = None,
    max_orb: float | None = None,
    object_filter: Annotated[str | None, Field(description="Keep only these transiting bodies, comma-separated, any case: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron.")] = None,
    city: Annotated[str | None, Field(description="Birth city, geocoded to coordinates. Use instead of latitude/longitude.")] = None,
    state: Annotated[str | None, Field(description="State or province, to disambiguate the city.")] = None,
    country: Annotated[str | None, Field(description="Country, to disambiguate the city.")] = None,
) -> str:
    """Generate a transit chart for ONE specific moment: transiting planet positions (placed in the natal chart's houses) and their aspects to the natal chart.

    Use this tool when:
    - The user asks what the sky looks like right now (transit_date_time omitted = current time)
    - The user gives a specific date/time for a transit snapshot
    - Tracking lunar transits (lunations) - set transit_date_time to the exact moment
      of a new or full moon to see where the Moon and other bodies are relative to the natal

    Do NOT use this tool for timing questions ("what transits are coming up",
    "when will X next aspect my natal Y", "how long does this transit last").
    A single chart shows one moment; it cannot show when aspects start or end,
    and you must not estimate timing or duration from the positions yourself.
    Use list_upcoming_transits for those questions - it returns dated
    aspects from the ephemeris over a date range.

    The output includes:
    - Transiting planets (decimal + degree-and-minute position, natal house)
    - The natal chart's house cusps
    - Transit-to-natal aspects (type, orb, exact_at: local moment the aspect
      is exact, null when more than 180 days from the snapshot), filtered by
      aspect_type/max_orb/object_filter when provided

    Args:
        date_time: Birth date and time of the natal chart being transited. Format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'.
        latitude: Latitude of the natal chart location, in decimal degrees (e.g. 34.05); negative for south.
        longitude: Longitude of the natal chart location, in decimal degrees (e.g. -118.24); negative for west.
        transit_date_time: The date/time of the transit. Format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'. If omitted, uses current time. For lunation work, specify the exact time of a new or full moon.
        aspect_type: Filter aspects to specific type(s) (e.g., "Conjunction", "Square"). Comma-separated, any case.
        max_orb: Maximum orb threshold in degrees. Aspects with orb <= this value are included (exact/tight aspects are always kept). Default: 1.5
        object_filter: Filter to specific transiting objects (comma-separated planet names, any case).

    Returns:
        JSON string of the transit chart, or error message if validation fails
    """
    # A place name is accepted instead of coordinates, as in
    # create_natal_chart. Resolved before the string validators, which would
    # otherwise see None as the literal text "None".
    if city is not None and (latitude is None or longitude is None):
        try:
            lat_val, lon_val, _matched = get_coordinates_for_params(
                None, None, city, state, country
            )
        except Exception as e:
            return error_response("Geocoding failed", str(e))
        latitude, longitude = lat_val, lon_val

    if latitude is None or longitude is None:
        return error_response(
            "Invalid location",
            "Provide latitude and longitude, or a city (with state/country to disambiguate).",
        )
    # The schema accepts coordinates as numbers (LLMs often send JSON
    # numbers); normalize to str for the string-based validators below.
    latitude = str(latitude)
    longitude = str(longitude)

    # Validate birth date
    valid, error = validate_date_string(date_time)
    if not valid:
        return error_response("Invalid birth date", error)

    # Validate latitude
    valid, error = validate_latitude(latitude)
    if not valid:
        return error_response("Invalid latitude", error)

    # Validate longitude
    valid, error = validate_longitude(longitude)
    if not valid:
        return error_response("Invalid longitude", error)

    # Validate transit date if provided
    if transit_date_time:
        valid, error = validate_date_string(transit_date_time)
        if not valid:
            return error_response("Invalid transit date", error)
        transit_dt = transit_date_time.replace("T", " ")
    else:
        # Use current time if no transit date specified (anchored to the
        # chart location's timezone, not the machine's)
        transit_dt = _local_now_str(latitude, longitude)

    # Filters, matched to the chart's own spellings whatever case they came in;
    # an unknown name is an error, not an empty result.
    aspect_type_list, error = parse_names(aspect_type, list(MAJOR_ASPECTS), "aspect type")
    if error:
        return error_response("Invalid aspect_type", error)
    object_filter_list, error = parse_names(object_filter, MAJOR_OBJECTS, "object")
    if error:
        return error_response("Invalid object_filter", error)

    # Validate max_orb if provided
    if max_orb is not None:
        try:
            max_orb_val = float(max_orb)
            if max_orb_val < 0:
                return error_response("Invalid max_orb", "Must be a positive number")
        except ValueError:
            return error_response("Invalid max_orb", "Must be a valid number")
    else:
        max_orb_val = 1.5

    try:
        from immanuel import charts

        # Build config
        config = get_config()

        # Create subject (birth data)
        native = charts.Subject(
            date_time=date_time.replace("T", " "),
            latitude=float(latitude),
            longitude=float(longitude),
        )

        # Create natal chart first (needed as reference)
        natal_chart = charts.Natal(native, config=config)

        # Create transit chart for the requested moment (immanuel's Transits
        # constructor hardcodes datetime.now(), so the date is applied here)
        transit_chart = _transits_for_date(transit_dt, latitude, longitude, natal_chart, config)

        # Calculate transit-to-natal aspects for all major objects
        # (full-precision longitudes; .degrees would quantize to whole degrees)
        natal_positions = {
            obj.name: obj.longitude.raw % 360
            for obj in natal_chart.objects.values()
            if obj.name in NATAL_TRANSIT_TARGETS
        }

        transit_natal_aspects = calculate_transit_to_natal_aspects(transit_chart, natal_positions)

        # Apply filtering if specified
        filtered_aspects = filter_aspects(
            transit_natal_aspects,
            aspect_type=aspect_type_list,
            max_orb=max_orb_val,
            object_filter=object_filter_list
        )

        # Refine each aspect to its exact moment (orb 0) so the snapshot
        # answers 'when exactly?' without a second tool call.
        tz = _chart_tz(latitude, longitude)
        object_ids = _object_ids(transit_chart)
        snapshot = datetime.fromisoformat(transit_dt).replace(tzinfo=tz)
        natal_block = natal_positions_block(natal_chart)
        transit_positions = {
            obj.name: obj.longitude.raw % 360
            for obj in transit_chart.objects.values()
            if obj.name in MAJOR_OBJECTS
        }
        for aspect in filtered_aspects:
            aspect["exact_at"] = _aspect_exact_at(aspect, object_ids, natal_positions, snapshot)
            # Both ends spelled out, so "Saturn square Saturn" can only be
            # read as what it is: the transiting and the natal degree.
            moving = sign_position(transit_positions[aspect["from_object"]])
            fixed = natal_block[aspect["to_object"]]
            aspect["from_sign"] = moving["sign"]
            aspect["from_position"] = moving["position"]
            aspect["to_sign"] = fixed["sign"]
            aspect["to_position"] = fixed["position"]
            aspect["to_house"] = fixed["house"]
            # One sentence with the roles, the movement and the timing, so
            # nothing has to be assembled from the fields.
            label = aspect_label(
                aspect["from_object"], moving["position"], aspect["type"], aspect["to_object"], fixed["position"],
                natal_house=fixed["house"],
            )
            movement = aspect.get("movement")
            if movement:
                label += f", {movement.lower().replace('applicative', 'applying').replace('separative', 'separating')}"
            label += f", exact {aspect['exact_at']}" if aspect["exact_at"] else ", exact more than 180 days away"
            aspect["label"] = label

        # Transiting objects placed in the natal chart's (whole sign) houses.
        assigned_houses = assign_natal_houses_to_transit_objects(transit_chart, natal_chart)

        # Serialize compactly: transiting objects placed in the NATAL chart's
        # houses, with the filtered transit-to-natal aspects as "aspects" and
        # the natal positions they are measured against as "natal". The note
        # steers the calling LLM away from estimating transit timing itself
        # from this single-moment chart.
        return compact_chart_json(
            transit_chart,
            chart_type="transit",
            date_time=transit_dt,
            house_system='whole_sign',
            house_overrides=assigned_houses,
            houses_chart=natal_chart,
            aspects=filtered_aspects,
            extra={
                "natal": {
                    "date_time": date_time.replace("T", " "),
                    "house_system": 'whole_sign',
                    "positions": natal_block,
                },
                "note": (
                    f"This chart reflects the single moment {transit_dt}. 'objects' are the "
                    "transiting bodies (in the natal chart's houses); 'natal.positions' are the "
                    "natal points, angles included, that 'aspects' are measured against -- quote "
                    "both ends from from_position/to_position. Each aspect's 'exact_at' is the "
                    "local moment it is (or was) exact - null when that moment lies more than "
                    "180 days from the snapshot. For 'what is coming up / how long does it last', "
                    "call list_upcoming_transits with start_date/end_date instead of estimating "
                    "timing from this chart."
                ),
            },
        )

    except ValueError as e:
        return error_response("Transit chart generation failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        known = describe_chart_error(e)
        if known:
            return error_response(*known)
        return error_response("Transit chart generation failed", f"Unexpected error: {str(e)}")


def list_upcoming_transits(
    start_date: Annotated[str | None, Field(description="First date of the transit scan, 'YYYY-MM-DD' (date only).")] = None,
    end_date: Annotated[str | None, Field(description="Last date of the transit scan, 'YYYY-MM-DD' (date only).")] = None,
    date_time: Annotated[str | None, Field(description="Birth date and time in ISO 8601: 'YYYY-MM-DD HH:MM' (seconds and 'T' separator optional). All-or-nothing with latitude and longitude.")] = None,
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    aspect_filter: Annotated[str | None, Field(description="Keep only these aspect types, comma-separated, any case: Conjunction, Opposition, Square, Trine, Sextile.")] = None,
    object_filter: Annotated[str | None, Field(description="Comma-separated objects to include, any case, e.g. 'Moon,Mercury' or 'Sun,Mars,Pluto'. Valid names: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron. With a birth chart these are the transiting bodies; without one, a span is kept when either of its bodies is listed. If omitted, all objects are included; oversized results auto-omit Moon and Mercury (see the 'omitted' field in the response).")] = None,
    max_orb: float | None = 1.5,
    city: Annotated[str | None, Field(description="Birth city, geocoded to coordinates. Use instead of latitude/longitude.")] = None,
    state: Annotated[str | None, Field(description="State or province, to disambiguate the city.")] = None,
    country: Annotated[str | None, Field(description="Country, to disambiguate the city.")] = None,
) -> str:
    """List dated transit aspects over a date range (one sample per day) - the tool for transit timing questions.

    This tool scans a date range and returns every significant major
    aspect (Conjunction, Opposition, Square, Trine, Sextile). Each aspect
    is listed once with start/end dates (the days it is within the orb)
    and its tightest orb over that span.
    Use it whenever the user asks:
    - "What transits are coming up?" (default range: today to +60 days)
    - "When will X next aspect Y?"
    - "How long does this transit/aspect last?" (the span's start/end dates
      are the duration)

    The ephemeris does the timing calculation - do not estimate dates or
    durations yourself from a single chart (create_transit_chart shows one
    moment and cannot answer when/duration questions). Set
    start_date/end_date for a specific or longer window.

    Two modes:
    - With a birth chart (date_time + latitude + longitude): transits in
      relation to that natal chart - transiting planets aspecting natal
      planets.
    - Without birth data: transits as-is - major aspects among the
      transiting planets themselves.

    Provide all three birth parameters or none of them.

    Args:
        start_date: Start date for scanning transits. Default: today.
        end_date: End date for scanning transits. Default: +60 days.
        date_time: Birth date and time of the natal chart. Format 'YYYY-MM-DD HH:MM'.
            With latitude and longitude, transits are related to this birth chart.
        latitude: Latitude of the natal chart location.
        longitude: Longitude of the natal chart location.
        aspect_filter: Filter by aspect types (comma-separated, any case, e.g., "Conjunction,Square").
        object_filter: Filter by objects (comma-separated, any case, e.g., "Moon,Mercury"): the transiting
            bodies with a birth chart; either body of a pair without one.
        max_orb: Maximum orb threshold in degrees. Aspects with orb <= this value are included. Default: 1.5

    Returns:
        Single-line JSON string with transit_range, mode ('natal' or
        'general'), total_transits, and transits. When the result fits the
        response size budget, each transit is an object with (start, end,
        from_object, to_object, type, orb, exact, from_sign, to_sign, plus
        the fields below). 'exact' is the local date/time (nearest minute)
        when the aspect is exact; null when that moment falls outside the
        scan window. Everything after 'exact' describes the tightest moment,
        so read it from here rather than working it out from a chart:
        from_sign / to_sign are the zodiac signs of the two objects ("Mars
        square Pluto" reads as Mars in Leo, Pluto in Scorpio); with a birth
        chart, from_house is the natal house the transiting object is moving
        through, to_house the natal house of the natal object it touches, and
        from_retrograde whether the transiting object is retrograde; without
        one, from_retrograde and to_retrograde say that for each of the two.
        Oversized results are
        condensed: high-frequency Moon/Mercury spans are auto-omitted
        (reported in 'omitted'), and if still oversized the spans are
        re-encoded as positional arrays matching the 'span_fields' legend.
    """
    # A place name is accepted instead of coordinates, as in
    # create_natal_chart. Resolved before the string validators, which would
    # otherwise see None as the literal text "None".
    if city is not None and (latitude is None or longitude is None):
        try:
            lat_val, lon_val, _matched = get_coordinates_for_params(
                None, None, city, state, country
            )
        except Exception as e:
            return error_response("Geocoding failed", str(e))
        latitude, longitude = lat_val, lon_val

    # The schema accepts coordinates as numbers (LLMs often send JSON
    # numbers); normalize to str for the string-based validators below.
    if latitude is not None:
        latitude = str(latitude)
    if longitude is not None:
        longitude = str(longitude)

    # Birth data must be all-or-nothing
    birth_params = (date_time, latitude, longitude)
    if any(p is not None for p in birth_params) and not all(p is not None for p in birth_params):
        return error_response(
            "Incomplete birth data",
            "Provide all of date_time, latitude, and longitude to relate transits "
            "to a birth chart, or none of them for transits as-is."
        )
    has_natal = all(p is not None for p in birth_params)

    # Validate birth data
    if has_natal:
        valid, error = validate_date_string(date_time)
        if not valid:
            return error_response("Invalid birth date", error)

        valid, error = validate_latitude(latitude)
        if not valid:
            return error_response("Invalid latitude", error)

        valid, error = validate_longitude(longitude)
        if not valid:
            return error_response("Invalid longitude", error)

    # Validate date range
    today = datetime.now().date()

    if start_date:
        valid, error = validate_date_string(start_date + " 00:00")
        if not valid:
            return error_response("Invalid start_date", error)
    else:
        start_date = today.strftime("%Y-%m-%d")

    if end_date:
        valid, error = validate_date_string(end_date + " 00:00")
        if not valid:
            return error_response("Invalid end_date", error)
    else:
        # 60-day default. Longer windows (a full year is a common forecast
        # ask) are supported via an explicit end_date; oversized results are
        # auto-trimmed to the response budget (see _MAX_RESPONSE_CHARS).
        end_date = (today + timedelta(days=60)).strftime("%Y-%m-%d")

    try:
        from immanuel import charts
        from datetime import date

        # Build config (house system has no effect on ecliptic aspects)
        config = get_config()

        # Natal reference (only when birth data was provided)
        natal_chart = None
        natal_positions = None
        natal_houses = None
        cusps = None
        if has_natal:
            native = charts.Subject(
                date_time=date_time.replace("T", " "),
                latitude=float(latitude),
                longitude=float(longitude),
            )
            natal_chart = charts.Natal(native, config=config)
            natal_positions = {
                obj.name: obj.longitude.raw % 360
                for obj in natal_chart.objects.values()
                if obj.name in NATAL_TRANSIT_TARGETS
            }
            natal_houses = {
                obj.name: obj.house.number
                for obj in natal_chart.objects.values()
                if obj.name in NATAL_TRANSIT_TARGETS and obj.house
            }
            cusps = sorted(
                (h.number, h.longitude.raw % 360) for h in natal_chart.houses.values()
            )

        # Timezone + object ids for exact-moment refinement. In general mode
        # there is no natal chart, so the ids come from the first scanned chart.
        lat = float(latitude) if latitude is not None else config.default_latitude
        lon = float(longitude) if longitude is not None else config.default_longitude
        tz = _chart_tz(lat, lon)
        object_ids = _object_ids(natal_chart) if natal_chart is not None else None

        # Filters, matched to the chart's own spellings whatever case they
        # came in; an unknown name is an error that lists the valid ones.
        aspect_types, error = parse_names(aspect_filter, list(MAJOR_ASPECTS), "aspect type")
        if error:
            return error_response("Invalid aspect_filter", error)
        object_list, error = parse_names(object_filter, MAJOR_OBJECTS, "object")
        if error:
            return error_response("Invalid object_filter", error)
        object_names = set(object_list) if object_list is not None else None

        # Scan date range
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        # Fast bodies are in scope for short windows, or when asked for by
        # name; over longer ranges they are excluded and reported.
        span_days = (end - start).days
        excluded_fast = {
            name for name in FAST_BODIES
            if span_days > FAST_BODY_HORIZON_DAYS
            and (object_names is None or name not in object_names)
        }

        # Collect daily aspect samples (key -> {date: orb})
        samples = {}
        current_date = start

        while current_date <= end:
            # Create transit chart for this date (local midnight)
            date_str = current_date.isoformat() + " 00:00"

            transit_chart = _transits_for_date(
                date_str, latitude, longitude, natal_chart, config
            )

            if object_ids is None:
                object_ids = _object_ids(transit_chart)

            if natal_positions is not None:
                aspects_list = calculate_transit_to_natal_aspects(transit_chart, natal_positions)
            else:
                # Fastest body first in each pair (SPEED_ORDER), so from_object
                # is the one that makes the contact come and go, and the
                # fast-body pass below keys its samples the same way.
                by_name = {
                    obj.name: obj.longitude.raw % 360
                    for obj in transit_chart.objects.values()
                    if obj.name in MAJOR_OBJECTS
                }
                transit_positions = {name: by_name[name] for name in SPEED_ORDER if name in by_name}
                aspects_list = calculate_major_aspects(transit_positions)

            # Filter by max_orb and aspect types
            filtered = filter_aspects(
                aspects_list,
                aspect_type=aspect_types,
                max_orb=max_orb
            )

            for aspect in filtered:
                if aspect["from_object"] in excluded_fast:
                    continue
                key = (aspect["from_object"], aspect["to_object"], aspect["type"])
                orb_by_day = samples.setdefault(key, {})
                day_iso = current_date.isoformat()
                if day_iso in orb_by_day:
                    orb_by_day[day_iso] = min(orb_by_day[day_iso], aspect["orb"])
                else:
                    orb_by_day[day_iso] = aspect["orb"]

            current_date += timedelta(days=1)

        # Fast bodies need a finer pass; see FAST_BODIES. In a scan without a
        # birth chart the targets are the other transiting bodies, read at
        # each sample moment.
        if object_ids is not None:
            for fast_name, step_hours in FAST_BODIES.items():
                if fast_name in excluded_fast:
                    continue
                if object_names is not None and fast_name not in object_names:
                    continue
                _sample_fast_body(
                    samples, fast_name, step_hours,
                    natal_positions if natal_positions is not None else list(MAJOR_OBJECTS),
                    object_ids, start, end, tz, aspect_types, max_orb,
                )

        # Merge consecutive in-orb days into spans: each aspect is listed
        # once with start/end dates (its duration) instead of one near-
        # identical entry per sampled day, which keeps year-long scans
        # within the compact output budget.
        transits = []
        for (from_obj, to_obj, aspect_type), orb_by_day in samples.items():
            days = sorted(orb_by_day)
            runs, run = [], [days[0]]
            for d in days[1:]:
                if (date.fromisoformat(d) - date.fromisoformat(run[-1])).days > 1:
                    runs.append(run)
                    run = [d]
                else:
                    run.append(d)
            runs.append(run)
            for run in runs:
                exact = _refine_span_exact(
                    run, from_obj, to_obj, aspect_type,
                    object_ids, natal_positions, tz
                )
                peak_day = min(run, key=lambda d: orb_by_day[d])
                facts = _peak_facts(
                    from_obj, to_obj, object_ids, natal_positions, natal_houses,
                    cusps, exact, peak_day, tz
                )
                # The whole contact as one sentence, roles and moment
                # included: "exact 2026-10-05 16:59: transiting Sun 12°46'
                # Libra square natal Jupiter 12°46' Capricorn (natal house
                # 2)". The positions are those of that moment, which the
                # sentence says, so a Sun quoted at 12° is not mistaken for
                # where the Sun is today.
                when = f"exact {exact}" if exact else f"tightest {peak_day}"
                label = f"{when}: " + aspect_label(
                    from_obj, facts["from_position"], aspect_type, to_obj, facts["to_position"],
                    natal_mode=natal_positions is not None, natal_house=facts.get("to_house"),
                )
                transits.append({
                    "start": run[0],
                    "end": run[-1],
                    "from_object": from_obj,
                    "to_object": to_obj,
                    "type": aspect_type,
                    "symbol": aspect_symbol(aspect_type),
                    "orb": round(min(orb_by_day[d] for d in run), 2),
                    # Local moment the aspect is exact; null when the
                    # crossing falls outside the scan window.
                    "exact": exact,
                    "label": label,
                    # Signs, houses and retrograde state at the tightest
                    # moment, so "Mars square Pluto" arrives as "Mars in Leo
                    # (5th house) square Pluto in Scorpio".
                    **facts,
                })

        transits.sort(key=lambda x: (x["start"], x["from_object"], x["to_object"]))

        # Explicit object filter wins over the automatic trimming below. With a
        # birth chart it names transiting bodies; without one, either end.
        if object_names is not None:
            if natal_positions is not None:
                transits = [t for t in transits if t["from_object"] in object_names]
            else:
                transits = [t for t in transits if t["from_object"] in object_names or t["to_object"] in object_names]

        # Every object the scan actually covered: the per-object counts below
        # list each of these, zero or not.
        scanned = [
            name for name in MAJOR_OBJECTS
            if name not in excluded_fast and (object_names is None or name in object_names)
        ]
        natal_mode = natal_positions is not None

        result = {
            "transit_range": {
                "start": start_date,
                "end": end_date
            },
            "mode": "natal" if natal_mode else "general",
            "total_transits": len(transits),
            "spans_per_object": _spans_per_object(transits, scanned, natal_mode),
            "positions_note": (
                "In each span, from_object is the transiting body and to_object the natal point it aspects"
                if natal_mode else "In each span, both objects are transiting bodies"
            ) + "; from_position/to_position (and each span's 'label') are the positions at the span's exact "
                "moment, or its tightest sampled day when 'exact' is null -- not where the bodies are today.",
            "transits": transits,
        }
        if excluded_fast:
            # Silence here would read as "no lunar transits", which is never
            # true over a long window.
            result["excluded"] = {
                "objects": sorted(excluded_fast),
                "reason": (
                    f"sampled properly these aspect something every few hours, so over "
                    f"{span_days} days they would outnumber everything slower"
                ),
                "hint": "pass object_filter (e.g. 'Moon') or narrow the range to include them",
            }
        if object_names is not None:
            result["object_filter"] = sorted(object_names)
        if natal_positions is not None:
            # The natal chart the spans are measured against, so each
            # 'to_object' can be read off here rather than remembered.
            result["natal"] = {
                "date_time": date_time.replace("T", " "),
                "latitude": float(latitude),
                "longitude": float(longitude),
                "house_system": "whole_sign",
                "positions": natal_positions_block(natal_chart),
            }
        else:
            result["note"] = (
                "No birth data was provided - these are major aspects among the "
                "transiting planets themselves (transits as-is). Provide "
                "date_time/latitude/longitude to relate transits to a birth chart."
            )

        fields = NATAL_FIELDS if natal_positions is not None else GENERAL_FIELDS

        # Single-line compact JSON keeps responses small for the LLM
        payload = json.dumps(result, separators=(",", ":"), ensure_ascii=False)

        # Self-adaptive size control: MCP clients truncate large responses
        # (~25KB), so oversized results are condensed in two tiers. Lossless
        # compaction comes first: dropping real aspects to save bytes that a
        # cheaper encoding would have saved anyway is a bad trade.
        if len(payload) > _MAX_RESPONSE_CHARS:
            # Tier 0: drop the per-span 'label' sentences first. They repeat
            # what the fields say (roles, positions, moment) in prose, so
            # losing them costs nothing the legend can't explain -- and it
            # keeps a scan that fit before labels existed in the readable
            # named-object form.
            for t in transits:
                t.pop("label", None)
            result["positions_note"] += (
                " (Per-span 'label' sentences were left out to fit the response budget: "
                "from_object is the transiting body, to_object the natal point.)"
                if natal_mode else
                " (Per-span 'label' sentences were left out to fit the response budget.)"
            )
            payload = json.dumps(result, separators=(",", ":"), ensure_ascii=False)

        if len(payload) > _MAX_RESPONSE_CHARS:
            # Tier 1: re-encode spans as positional arrays (much smaller than
            # repeated object keys), documented by 'span_fields'. No data is
            # lost -- only the key names, which the legend restores.
            result["transits"] = [
                [t[f] for f in fields]
                for t in transits
            ]
            result["span_fields"] = fields
            result["span_fields_note"] = SPAN_FIELDS_NOTE
            payload = json.dumps(result, separators=(",", ":"), ensure_ascii=False)

            # Tier 2: only if compaction was not enough, drop the most
            # frequent, short-lived spans (transiting Moon and Mercury) and
            # report exactly what went and how to get it back. An explicit
            # object_filter disables this tier.
            # Filtering on from_object is safe in both modes: in natal mode
            # it is the transiting planet; in general mode the faster body is
            # always first (SPEED_ORDER), so fast-driven pairs are caught too.
            if len(payload) > _MAX_RESPONSE_CHARS and object_names is None:
                fast_objects = ("Moon", "Mercury")
                omitted = {}
                for t in transits:
                    if t["from_object"] in fast_objects:
                        omitted[t["from_object"]] = omitted.get(t["from_object"], 0) + 1
                if omitted:
                    transits = [t for t in transits if t["from_object"] not in fast_objects]
                    result["total_transits"] = len(transits)
                    result["spans_per_object"] = _spans_per_object(
                        transits, [n for n in scanned if n not in fast_objects], natal_mode
                    )
                    result["transits"] = [
                        [t[f] for f in fields]
                        for t in transits
                    ]
                    result["omitted"] = {
                        "objects": sorted(omitted),
                        "spans": omitted,
                        "reason": "the full list exceeded the response size budget even when compacted",
                        "hint": "pass object_filter (e.g. 'Moon,Mercury') to include "
                                "these objects, or narrow the range or lower max_orb",
                    }
                    payload = json.dumps(result, separators=(",", ":"), ensure_ascii=False)

            # An explicit object_filter disables the omission tier, which is
            # right -- the caller asked for those objects -- but the client
            # will truncate what it cannot carry, so say so rather than
            # returning something that arrives half-eaten.
            if len(payload) > _MAX_RESPONSE_CHARS:
                result["warning"] = (
                    f"This response is {len(payload)} characters and may be truncated "
                    f"by the client (budget {_MAX_RESPONSE_CHARS}). Narrow the date "
                    f"range, raise max_orb selectivity, or drop fast objects from "
                    f"object_filter."
                )
                payload = json.dumps(result, separators=(",", ":"), ensure_ascii=False)

        return payload

    except ValueError as e:
        return error_response("Transit scanning failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        known = describe_chart_error(e)
        if known:
            return error_response(*known)
        return error_response("Transit scanning failed", f"Unexpected error: {str(e)}")


def verify_claim(
    date_time: Annotated[str, Field(description="Birth date and time of the natal chart in ISO 8601: 'YYYY-MM-DD HH:MM'.")],
    transiting_object: Annotated[str, Field(description="The transiting planet in the claim, e.g. 'Saturn'. One of: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron.")],
    natal_object: Annotated[str, Field(description="The natal point it is said to aspect, e.g. 'Saturn', 'Asc' (or 'Ascendant'), 'MC' (or 'Midheaven'), 'North Node'.")],
    aspect_type: Annotated[str, Field(description="Conjunction, Opposition, Square, Trine or Sextile.")],
    on_date: Annotated[str, Field(description="The date the claim is about, 'YYYY-MM-DD': the day the aspect is said to be exact or in effect.")],
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    max_orb: Annotated[float | None, Field(description="Widest orb that still counts as 'in effect' on that date. Default: the orb the transit scan itself uses for these two bodies.")] = None,
    city: Annotated[str | None, Field(description="Birth city, geocoded to coordinates. Use instead of latitude/longitude.")] = None,
    state: Annotated[str | None, Field(description="State or province, to disambiguate the city.")] = None,
    country: Annotated[str | None, Field(description="Country, to disambiguate the city.")] = None,
) -> str:
    """Check one transit claim against the ephemeris: was this aspect really in effect on that date, and when is it exact?

    Use it before stating a transit you have not just read from a tool
    result -- "Saturn trine natal Saturn, exact Oct 3" -- and report what it
    returns rather than the claim. Cheap: one ephemeris lookup, the same
    engine the transit tools use.

    Returns a verdict:
    - 'confirmed': the aspect is within orb on that date (positions and orb
      given, and the exact moment if it falls within 180 days).
    - 'near': not within orb that day, but exact within 30 days of it -- the
      claim has the right aspect and the wrong date; the exact moment says
      which.
    - 'not found': nothing like it in the ephemeris around that date.
    """
    if city is not None and (latitude is None or longitude is None):
        try:
            lat_val, lon_val, _matched = get_coordinates_for_params(None, None, city, state, country)
        except Exception as e:
            return error_response("Geocoding failed", str(e))
        latitude, longitude = lat_val, lon_val
    if latitude is None or longitude is None:
        return error_response(
            "Invalid location",
            "Provide latitude and longitude, or a city (with state/country to disambiguate).",
        )
    latitude, longitude = str(latitude), str(longitude)

    for label, check, value in (
        ("Invalid birth date", validate_date_string, date_time),
        ("Invalid latitude", validate_latitude, latitude),
        ("Invalid longitude", validate_longitude, longitude),
        ("Invalid on_date", validate_date_string, f"{on_date} 00:00"),
    ):
        valid, error = check(value)
        if not valid:
            return error_response(label, error)

    moving = canonical_point(transiting_object, MAJOR_OBJECTS)
    if moving is None:
        return error_response(
            "Unknown transiting object",
            f"{transiting_object!r} is not one of {', '.join(MAJOR_OBJECTS)}",
        )
    fixed = canonical_point(natal_object, NATAL_TRANSIT_TARGETS)
    if fixed is None:
        return error_response(
            "Unknown natal point",
            f"{natal_object!r} is not one of {', '.join(NATAL_TRANSIT_TARGETS)} (Ascendant, Midheaven and North Node are accepted too)",
        )
    aspect = next((name for name in MAJOR_ASPECTS if name.lower() == (aspect_type or "").strip().lower()), None)
    if aspect is None:
        return error_response("Unknown aspect", f"{aspect_type!r} is not one of {', '.join(MAJOR_ASPECTS)}")
    if max_orb is not None:
        try:
            max_orb = float(max_orb)
        except (TypeError, ValueError):
            return error_response("Invalid max_orb", "Must be a number")
        if max_orb < 0:
            return error_response("Invalid max_orb", "Must be a positive number")

    try:
        from immanuel import charts
        from immanuel.tools import ephemeris

        config = get_config()
        native = charts.Subject(
            date_time=date_time.replace("T", " "), latitude=float(latitude), longitude=float(longitude),
        )
        natal_chart = charts.Natal(native, config=config)
        natal_positions = {
            obj.name: obj.longitude.raw % 360
            for obj in natal_chart.objects.values()
            if obj.name in NATAL_TRANSIT_TARGETS
        }
        natal_block = natal_positions_block(natal_chart)
        ids = _object_ids(natal_chart)

        # Local noon of the claimed day: the middle of it, so a same-day
        # aspect is judged at its most representative moment.
        tz = _chart_tz(latitude, longitude)
        day = date.fromisoformat(on_date)
        noon = datetime(day.year, day.month, day.day, 12, 0, tzinfo=tz)
        at = ephemeris.get_planet(ids[moving], _jd_of(noon))
        angle = MAJOR_ASPECTS[aspect][0]
        natal_lon = natal_positions[fixed]
        orb = abs(_signed_orb(at["lon"], natal_lon, angle, _aspect_side(at["lon"], natal_lon, angle)))
        allowed = max_orb if max_orb is not None else orb_for(aspect, moving, fixed)
        within = orb <= allowed

        exact = _aspect_exact_at(
            {"from_object": moving, "to_object": fixed, "type": aspect}, ids, natal_positions, noon,
        )
        days_off = None
        if exact:
            exact_dt = datetime.strptime(exact, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            days_off = round((exact_dt - noon).total_seconds() / 86400, 1)

        if within:
            verdict = "confirmed"
        elif days_off is not None and abs(days_off) <= 30:
            verdict = "near"
        else:
            verdict = "not found"

        claim = f"transiting {moving} {aspect.lower()} natal {fixed} on {on_date}"
        notes = {
            "confirmed": f"In effect on {on_date}: orb {orb:.2f}° (allowed {allowed:.2f}°)."
                         + (f" Exact at {exact}." if exact else " Exact moment more than 180 days away."),
            "near": f"Not within orb on {on_date} ({orb:.2f}°, allowed {allowed:.2f}°), but exact at {exact}, "
                    f"{abs(days_off or 0):.1f} days {'later' if (days_off or 0) > 0 else 'earlier'}. The date is off, not the aspect.",
            "not found": f"No {aspect.lower()} between transiting {moving} and natal {fixed} on {on_date} "
                         f"(orb {orb:.2f}°, allowed {allowed:.2f}°)"
                         + (f"; the nearest exact moment is {exact}." if exact else "; none within 180 days of it."),
        }
        return json.dumps({
            "claim": claim,
            "verdict": verdict,
            "on_date": {
                "date": on_date,
                "orb": round(orb, 2),
                "allowed_orb": round(allowed, 2),
                "within_orb": within,
                "transiting": {**sign_position(at["lon"]), "retrograde": at["speed"] < 0},
                "natal": natal_block[fixed],
            },
            "exact": exact,
            "days_from_date": days_off,
            "note": notes[verdict],
        }, separators=(",", ":"), ensure_ascii=False)

    except ValueError as e:
        return error_response("Claim check failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        known = describe_chart_error(e)
        if known:
            return error_response(*known)
        return error_response("Claim check failed", f"Unexpected error: {str(e)}")


def register(mcp: MCPServer):
    """Register transit tools with MCPServer."""
    mcp.add_tool(
        verify_claim,
        name="verify_claim",
        description=(
            "Check one transit claim against the ephemeris before stating it: 'is transiting Saturn trine natal "
            "Saturn in effect on 2026-10-03, and when is it exact?' Returns 'confirmed' (within orb that day, with "
            "both positions, the orb and the exact moment), 'near' (right aspect, wrong date -- exact within 30 days, "
            "and when), or 'not found'. Use it whenever you are about to assert a transit you have not just read "
            "from create_transit_chart or list_upcoming_transits, and report its verdict, not the claim."
        ),
    )
    mcp.add_tool(
        create_transit_chart,
        name="create_transit_chart",
        description=(
            "Generate a transit chart for ONE specific moment: transiting planet positions (in the natal chart's houses), "
            "the natal positions they are measured against ('natal.positions', angles included), and the aspects between "
            "them -- each aspect carries both ends as from_position/to_position (e.g. \"Saturn 11°24' Aries square natal "
            "Saturn 12°03' Scorpio\"), so quote those rather than recalling the natal chart. "
            "Use for 'what is the sky like right now' (omit transit_date_time) "
            "or a user-given date/time, and for lunation work (set transit_date_time to the exact moment of a new or full moon). "
            "Each aspect includes 'exact_at': the local moment (nearest minute) it is or was exact, so 'when exactly does X "
            "aspect Y' is answered directly (null when more than 180 days away). NOT for span or duration questions - it "
            "shows one moment and cannot show when an aspect starts or ends. For 'what transits are coming up', 'when will X "
            "happen', or 'how long does it last', use list_upcoming_transits, which returns dated aspects from the ephemeris."
        )
    )

    mcp.add_tool(
        list_upcoming_transits,
        name="list_upcoming_transits",
        description=(
            "List dated transit aspects over a date range (one sample per day; default today to +60 days). "
            "THE tool for transit timing questions: 'what transits are coming up', 'when will X next happen', "
            "and 'how long does it last' (each aspect is listed once with start/end dates and its tightest orb, "
            "so the span is the duration; each span also carries 'exact', the local date/time to the minute when "
            "the aspect is exact - null when that moment falls outside the scan window, and both ends as "
            "from_position/to_position with sign and degree). With birth data the response includes 'natal.positions' "
            "(every natal point, angles included, with sign, degree and house) and 'spans_per_object' (a count per "
            "scanned planet, 0 when it aspects nothing in the window -- an explicit zero, not an omission). The ephemeris does the "
            "timing calculation - do not estimate dates or durations yourself from a single chart. With birth data "
            "(date_time + latitude + longitude): transits in "
            "relation to that natal chart (transiting planets aspecting natal planets). Without birth data: transits "
            "as-is (major aspects among the transiting planets themselves). Provide all three birth parameters or none. "
            "Set start_date/end_date for a specific or longer window. Yearly forecasts are supported: if the full "
            "list would exceed the response size budget, high-frequency Moon and Mercury aspects are auto-omitted "
            "(reported in the response's 'omitted' field) and the spans are re-encoded as compact positional arrays "
            "(see 'span_fields'); pass object_filter to include specific objects, or narrow the range / lower max_orb."
        )
    )
