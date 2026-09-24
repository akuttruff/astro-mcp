"""Transit chart tool for astro-mcp."""

import json
from typing import Annotated
from mcp.server.mcpserver import MCPServer
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pydantic import Field

from astro_mcp.utils import compact_chart_json, error_response, calculate_transit_to_natal_aspects, calculate_major_aspects, MAJOR_OBJECTS, MAJOR_ASPECTS, filter_aspects, validate_date_string, validate_latitude, validate_longitude, validate_house_system, assign_natal_houses_to_transit_objects
from astro_mcp.config import get_config

# MCP clients truncate large tool responses (~25KB). Keep list output
# under this budget; when it is exceeded, high-frequency fast-object spans
# are auto-omitted and reported (see list_upcoming_transits).
_MAX_RESPONSE_CHARS = 20000


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
    latitude: str | float,
    longitude: str | float,
    transit_date_time: Annotated[str | None, Field(description="Transit date and time in ISO 8601: 'YYYY-MM-DD HH:MM'. Omit for 'now'.")] = None,
    house_system: str | None = None,
    aspect_type: str | None = None,
    max_orb: float | None = None,
    object_filter: str | None = None
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
    - Transiting planets (decimal + DMS position, natal house)
    - The natal chart's house cusps
    - Transit-to-natal aspects (type, orb, exact_at: local moment the aspect
      is exact, null when more than 180 days from the snapshot), filtered by
      aspect_type/max_orb/object_filter when provided

    Args:
        date_time: Birth date and time of the natal chart being transited. Format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'.
        latitude: Latitude of the natal chart location. Decimal degrees (e.g. '34.05') or DMS.
        longitude: Longitude of the natal chart location. Decimal degrees (e.g. '-118.24') or DMS.
        transit_date_time: The date/time of the transit. Format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'. If omitted, uses current time. For lunation work, specify the exact time of a new or full moon.
        house_system: House system to use. Default: 'whole_sign'. See list_house_systems for options.
        aspect_type: Filter aspects to specific type(s) (e.g., "Conjunction", "Square"). Multiple types can be comma-separated.
        max_orb: Maximum orb threshold in degrees. Aspects with orb <= this value are included (exact/tight aspects are always kept). Default: 1.5
        object_filter: Filter to specific transiting objects (comma-separated list of planet names).

    Returns:
        JSON string of the transit chart, or error message if validation fails
    """
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

    # Validate house system if provided
    valid, error = validate_house_system(house_system)
    if not valid:
        return error_response("Invalid house system", error)

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

    # Parse filter parameters
    aspect_type_list = None
    if aspect_type:
        aspect_type_list = [at.strip() for at in aspect_type.split(",")]

    object_filter_list = None
    if object_filter:
        object_filter_list = [obj.strip() for obj in object_filter.split(",")]

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
        config = get_config(house_system)

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
            if obj.name in MAJOR_OBJECTS
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
        for aspect in filtered_aspects:
            aspect["exact_at"] = _aspect_exact_at(aspect, object_ids, natal_positions, snapshot)

        # Assign transit objects to natal chart houses (fixes house assignment bug)
        assigned_houses = assign_natal_houses_to_transit_objects(transit_chart, natal_chart, house_system or 'whole_sign')

        # Serialize compactly: transiting objects placed in the NATAL chart's
        # houses, with the filtered transit-to-natal aspects as "aspects".
        # The note steers the calling LLM away from estimating transit timing
        # itself from this single-moment chart.
        return compact_chart_json(
            transit_chart,
            chart_type="transit",
            date_time=transit_dt,
            house_system=house_system or 'whole_sign',
            house_overrides=assigned_houses,
            houses_chart=natal_chart,
            aspects=filtered_aspects,
            extra={
                "note": (
                    f"This chart reflects the single moment {transit_dt}. Each aspect's "
                    "'exact_at' is the local moment it is (or was) exact - null when that "
                    "moment lies more than 180 days from the snapshot. For 'what is coming "
                    "up / how long does it last', call list_upcoming_transits with "
                    "start_date/end_date instead of estimating timing from this chart."
                )
            },
        )

    except ValueError as e:
        return error_response("Transit chart generation failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        return error_response("Transit chart generation failed", f"Unexpected error: {str(e)}")


def list_upcoming_transits(
    start_date: Annotated[str | None, Field(description="First date of the transit scan, 'YYYY-MM-DD' (date only).")] = None,
    end_date: Annotated[str | None, Field(description="Last date of the transit scan, 'YYYY-MM-DD' (date only).")] = None,
    date_time: Annotated[str | None, Field(description="Birth date and time in ISO 8601: 'YYYY-MM-DD HH:MM' (seconds and 'T' separator optional). All-or-nothing with latitude and longitude.")] = None,
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    aspect_filter: str | None = None,
    object_filter: Annotated[str | None, Field(description="Comma-separated transiting objects to include, e.g. 'Moon,Mercury' or 'Sun,Mars,Pluto'. Valid names: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron. If omitted, all objects are included; oversized results auto-omit Moon and Mercury (see the 'omitted' field in the response).")] = None,
    max_orb: float | None = 1.5
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
        aspect_filter: Filter by aspect types (comma-separated, e.g., "Conjunction,Square").
        object_filter: Filter by transiting objects (comma-separated, e.g., "Moon,Mercury").
        max_orb: Maximum orb threshold in degrees. Aspects with orb <= this value are included. Default: 1.5

    Returns:
        Single-line JSON string with transit_range, mode ('natal' or
        'general'), total_transits, and transits. When the result fits the
        response size budget, each transit is an object with (start, end,
        from_object, to_object, type, orb, exact). 'exact' is the local
        date/time (nearest minute) when the aspect is exact; null when that
        moment falls outside the scan window. Oversized results are
        condensed: high-frequency Moon/Mercury spans are auto-omitted
        (reported in 'omitted'), and if still oversized the spans are
        re-encoded as positional arrays matching the 'span_fields' legend.
    """
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
        config = get_config(None)

        # Natal reference (only when birth data was provided)
        natal_chart = None
        natal_positions = None
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
                if obj.name in MAJOR_OBJECTS
            }

        # Timezone + object ids for exact-moment refinement. In general mode
        # there is no natal chart, so the ids come from the first scanned chart.
        lat = float(latitude) if latitude is not None else config.default_latitude
        lon = float(longitude) if longitude is not None else config.default_longitude
        tz = _chart_tz(lat, lon)
        object_ids = _object_ids(natal_chart) if natal_chart is not None else None

        # Parse aspect filter
        aspect_types = None
        if aspect_filter:
            aspect_types = [at.strip() for at in aspect_filter.split(",")]

        # Parse object filter (which transiting objects to include).
        # Names are matched case-insensitively against MAJOR_OBJECTS; any
        # unrecognized name is an error that lists the valid ones.
        object_names = None
        if object_filter:
            lookup = {name.lower(): name for name in MAJOR_OBJECTS}
            object_names = set()
            for raw in object_filter.split(","):
                name = lookup.get(raw.strip().lower())
                if name is None:
                    return error_response(
                        "Invalid object_filter",
                        f"Unrecognized object: {raw.strip()!r}. "
                        f"Recognized objects: {', '.join(MAJOR_OBJECTS)}"
                    )
                object_names.add(name)

        # Scan date range
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

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
                transit_positions = {
                    obj.name: obj.longitude.raw % 360
                    for obj in transit_chart.objects.values()
                    if obj.name in MAJOR_OBJECTS
                }
                aspects_list = calculate_major_aspects(transit_positions)

            # Filter by max_orb and aspect types
            filtered = filter_aspects(
                aspects_list,
                aspect_type=aspect_types,
                max_orb=max_orb
            )

            for aspect in filtered:
                key = (aspect["from_object"], aspect["to_object"], aspect["type"])
                orb_by_day = samples.setdefault(key, {})
                day_iso = current_date.isoformat()
                if day_iso in orb_by_day:
                    orb_by_day[day_iso] = min(orb_by_day[day_iso], aspect["orb"])
                else:
                    orb_by_day[day_iso] = aspect["orb"]

            current_date += timedelta(days=1)

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
                transits.append({
                    "start": run[0],
                    "end": run[-1],
                    "from_object": from_obj,
                    "to_object": to_obj,
                    "type": aspect_type,
                    "orb": round(min(orb_by_day[d] for d in run), 2),
                    # Local moment the aspect is exact; null when the
                    # crossing falls outside the scan window.
                    "exact": _refine_span_exact(
                        run, from_obj, to_obj, aspect_type,
                        object_ids, natal_positions, tz
                    ),
                })

        transits.sort(key=lambda x: (x["start"], x["from_object"], x["to_object"]))

        # Explicit object filter wins over the automatic trimming below
        if object_names is not None:
            transits = [t for t in transits if t["from_object"] in object_names]

        result = {
            "transit_range": {
                "start": start_date,
                "end": end_date
            },
            "mode": "natal" if natal_positions is not None else "general",
            "total_transits": len(transits),
            "transits": transits,
        }
        if object_names is not None:
            result["object_filter"] = sorted(object_names)
        if natal_positions is not None:
            result["natal"] = {
                "date_time": date_time,
                "latitude": float(latitude),
                "longitude": float(longitude),
            }
        else:
            result["note"] = (
                "No birth data was provided - these are major aspects among the "
                "transiting planets themselves (transits as-is). Provide "
                "date_time/latitude/longitude to relate transits to a birth chart."
            )

        # Single-line compact JSON keeps responses small for the LLM
        payload = json.dumps(result, separators=(",", ":"))

        # Self-adaptive size control: MCP clients truncate large responses
        # (~25KB), so oversized results are condensed in two tiers:
        if len(payload) > _MAX_RESPONSE_CHARS:
            # Tier 1: drop the most frequent, short-lived spans (transiting
            # Moon and Mercury) and report exactly what was omitted and how
            # to get it back. An explicit object_filter disables this tier.
            # Filtering on from_object is safe in both modes: in natal mode
            # it is the transiting planet; in general mode the faster object
            # always sorts first in MAJOR_OBJECTS order, so fast-driven
            # pairs are caught too.
            if object_names is None:
                fast_objects = ("Moon", "Mercury")
                omitted = {}
                for t in transits:
                    if t["from_object"] in fast_objects:
                        omitted[t["from_object"]] = omitted.get(t["from_object"], 0) + 1
                if omitted:
                    transits = [t for t in transits if t["from_object"] not in fast_objects]
                    result["total_transits"] = len(transits)
                    result["transits"] = transits
                    result["omitted"] = {
                        "objects": sorted(omitted),
                        "spans": omitted,
                        "reason": "the full list exceeded the response size budget",
                        "hint": "pass object_filter (e.g. 'Moon,Mercury') to include "
                                "these objects, or narrow the range or lower max_orb",
                    }
                    payload = json.dumps(result, separators=(",", ":"))

            # Tier 2: re-encode spans as positional arrays (much smaller
            # than repeated object keys), documented by 'span_fields'.
            if len(payload) > _MAX_RESPONSE_CHARS:
                result["transits"] = [
                    [t["start"], t["end"], t["from_object"], t["to_object"], t["type"], t["orb"], t["exact"]]
                    for t in transits
                ]
                result["span_fields"] = ["start", "end", "from_object", "to_object", "type", "orb", "exact"]
                payload = json.dumps(result, separators=(",", ":"))

        return payload

    except ValueError as e:
        return error_response("Transit scanning failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        return error_response("Transit scanning failed", f"Unexpected error: {str(e)}")


def register(mcp: MCPServer):
    """Register transit tools with MCPServer."""
    mcp.add_tool(
        create_transit_chart,
        name="create_transit_chart",
        description=(
            "Generate a transit chart for ONE specific moment: transiting planet positions (in the natal chart's houses) "
            "and their aspects to the natal chart. Use for 'what is the sky like right now' (omit transit_date_time) "
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
            "the aspect is exact - null when that moment falls outside the scan window). The ephemeris does the "
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
