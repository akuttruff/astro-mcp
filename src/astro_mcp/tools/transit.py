"""Transit chart tool for astro-mcp."""

import json
from mcp.server.mcpserver import MCPServer
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from astro_mcp.utils import compact_chart_json, error_response, calculate_transit_to_natal_aspects, calculate_major_aspects, MAJOR_OBJECTS, filter_aspects, validate_date_string, validate_latitude, validate_longitude, validate_house_system, assign_natal_houses_to_transit_objects
from astro_mcp.config import get_config


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


def _local_now_str(latitude, longitude) -> str:
    """Current wall-clock time at the chart location, 'YYYY-MM-DD HH:MM'.

    Anchoring "now" to the chart location's timezone (rather than the
    machine's local time) keeps the transit moment correct when the server
    runs in a different timezone than the chart's birthplace.
    """
    try:
        from immanuel.tools.date import timezone_lookup
        tz = ZoneInfo(timezone_lookup(float(latitude), float(longitude)))
    except Exception:
        tz = datetime.now().astimezone().tzinfo
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M")


def create_transit_chart(
    date_time: str,
    latitude: str | float,
    longitude: str | float,
    transit_date_time: str | None = None,
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
    - Transit-to-natal aspects (type, orb), filtered by aspect_type/max_orb/
      object_filter when provided

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
                    f"This chart reflects the single moment {transit_dt}. "
                    "For 'when will X happen / how long does it last / what is coming up', "
                    "call list_upcoming_transits with start_date/end_date "
                    "instead of estimating timing from this chart."
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
    start_date: str | None = None,
    end_date: str | None = None,
    date_time: str | None = None,
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    aspect_filter: str | None = None,
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
        max_orb: Maximum orb threshold in degrees. Aspects with orb <= this value are included. Default: 1.5

    Returns:
        JSON string with transit_range, mode ('natal' or 'general'), total_transits,
        and a list of transit spans (start, end, from_object, to_object, type, orb)
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
        # 60-day default: a year-long scan produces a response that far
        # exceeds the compact output budget (MCP clients truncate it).
        # Longer windows are available via an explicit end_date.
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

        # Parse aspect filter
        aspect_types = None
        if aspect_filter:
            aspect_types = [at.strip() for at in aspect_filter.split(",")]

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
                })

        transits.sort(key=lambda x: (x["start"], x["from_object"], x["to_object"]))

        result = {
            "transit_range": {
                "start": start_date,
                "end": end_date
            },
            "mode": "natal" if natal_positions is not None else "general",
            "total_transits": len(transits),
            "transits": transits,
        }
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

        return json.dumps(result, indent=2)

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
            "NOT for timing questions: this tool shows a single moment, so it cannot show when an aspect starts or ends - "
            "do not estimate transit timing or duration from it. For 'what transits are coming up', 'when will X happen', "
            "or 'how long does it last', use list_upcoming_transits, which returns dated aspects from the ephemeris."
        )
    )

    mcp.add_tool(
        list_upcoming_transits,
        name="list_upcoming_transits",
        description=(
            "List dated transit aspects over a date range (one sample per day; default today to +60 days). "
            "THE tool for transit timing questions: 'what transits are coming up', 'when will X next happen', "
            "and 'how long does it last' (each aspect is listed once with start/end dates and its tightest orb, "
            "so the span is the duration). The ephemeris does the timing calculation - do not estimate dates or "
            "durations yourself from a single chart. With birth data (date_time + latitude + longitude): transits in "
            "relation to that natal chart (transiting planets aspecting natal planets). Without birth data: transits "
            "as-is (major aspects among the transiting planets themselves). Provide all three birth parameters or none. "
            "Set start_date/end_date for a specific or longer window."
        )
    )
