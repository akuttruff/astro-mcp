"""Transit chart tool for astro-mcp."""

import json
from mcp.server.mcpserver import MCPServer
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from astro_mcp.utils import compact_chart_json, error_response, extract_aspect_details, calculate_transit_to_natal_aspects, filter_aspects, validate_date_string, validate_latitude, validate_longitude, validate_house_system, assign_natal_houses_to_transit_objects
from astro_mcp.config import get_config


def _transits_for_date(date_str: str, latitude, longitude, aspects_to, config):
    """Build an immanuel Transits chart for a specific local date/time.

    immanuel's Transits constructor hardcodes datetime.now() and offers no
    way to pass a date, so we replace its subject with the requested moment
    (local time at the chart location, timezone geolocated by immanuel) and
    regenerate the chart data.
    """
    from immanuel import charts

    transit_chart = charts.Transits(
        latitude=latitude,
        longitude=longitude,
        aspects_to=aspects_to,
        config=config,
    )
    transit_chart._native = charts.Subject(
        date_time=date_str,
        latitude=float(latitude),
        longitude=float(longitude),
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
    latitude: str,
    longitude: str,
    transit_date_time: str | None = None,
    house_system: str | None = None,
    aspect_type: str | None = None,
    max_orb: float | None = None,
    object_filter: str | None = None
) -> str:
    """Generate a transit chart showing current (or specified) planetary positions and their aspects to a natal chart.

    This tool shows how current (or specified) planetary positions aspect a natal chart.
    Use it for:
    - Current conditions and timing events
    - Tracking lunar transits (lunations) - set transit_date_time to the exact moment
      of a new or full moon to see where the Moon and other bodies are relative to the natal
    - General transit analysis over any time period

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
        natal_positions = {}
        for obj in natal_chart.objects.values():
            if obj.name in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron']:
                natal_positions[obj.name] = obj.longitude.raw % 360

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
        return compact_chart_json(
            transit_chart,
            chart_type="transit",
            date_time=transit_dt,
            house_system=house_system or 'whole_sign',
            house_overrides=assigned_houses,
            houses_chart=natal_chart,
            aspects=filtered_aspects,
        )

    except ValueError as e:
        return error_response("Transit chart generation failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        return error_response("Transit chart generation failed", f"Unexpected error: {str(e)}")


def list_upcoming_planetary_transits(
    date_time: str,
    latitude: str,
    longitude: str,
    start_date: str | None = None,
    end_date: str | None = None,
    house_system: str | None = None,
    aspect_filter: str | None = None,
    max_orb: float | None = 1.5
) -> str:
    """List upcoming transit aspects to the natal chart over a date range.

    This tool scans a date range (one sample per day, local midnight at the
    chart location) and returns all significant aspects between transiting
    planets and the natal chart. Use it to:
    - See what transits are coming up in the next month or year
    - Identify key transit windows for planning
    - Track specific planets (e.g., Mars, Saturn) over time

    Args:
        date_time: Birth date and time of the natal chart. Format 'YYYY-MM-DD HH:MM'.
        latitude: Latitude of the natal chart location.
        longitude: Longitude of the natal chart location.
        start_date: Start date for scanning transits. Default: today.
        end_date: End date for scanning transits. Default: +365 days.
        house_system: House system to use. Default: 'whole_sign'.
        aspect_filter: Filter by aspect types (comma-separated, e.g., "Conjunction,Square").
        max_orb: Maximum orb threshold in degrees. Aspects with orb <= this value are included. Default: 1.5

    Returns:
        JSON string with list of upcoming transits, each containing date, objects, aspect type, and orb
    """
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
        end_date = (today + timedelta(days=365)).strftime("%Y-%m-%d")

    try:
        from immanuel import charts
        from datetime import date

        # Build config
        config = get_config(house_system)

        # Create subject (birth data)
        native = charts.Subject(
            date_time=date_time.replace("T", " "),
            latitude=float(latitude),
            longitude=float(longitude),
        )

        # Create natal chart (reference)
        natal_chart = charts.Natal(native, config=config)

        # Parse aspect filter
        aspect_types = None
        if aspect_filter:
            aspect_types = [at.strip() for at in aspect_filter.split(",")]

        # Scan date range
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        transits = []
        current_date = start

        while current_date <= end:
            # Create transit chart for this date (local midnight)
            date_str = current_date.isoformat() + " 00:00"

            transit_chart = _transits_for_date(
                date_str, latitude, longitude, natal_chart, config
            )

            # Get aspect details
            aspects_list = extract_aspect_details(transit_chart)

            # Filter by max_orb and aspect types
            filtered = filter_aspects(
                aspects_list,
                aspect_type=aspect_types,
                max_orb=max_orb
            )

            # Add to results if any transits found
            for aspect in filtered:
                transit_entry = {
                    "date": current_date.isoformat(),
                    **aspect
                }
                transits.append(transit_entry)

            current_date += timedelta(days=1)

        # Sort by date
        transits.sort(key=lambda x: x["date"])

        result = {
            "transit_range": {
                "start": start_date,
                "end": end_date
            },
            "total_transits": len(transits),
            "transits": transits
        }

        return json.dumps(result, indent=2)

    except ValueError as e:
        return error_response("Transit scanning failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        return error_response("Transit scanning failed", f"Unexpected error: {str(e)}")


def list_upcoming_transits_to_natal(
    date_time: str,
    latitude: str,
    longitude: str,
    start_date: str | None = None,
    end_date: str | None = None,
    house_system: str | None = None,
    aspect_filter: str | None = None,
    max_orb: float | None = 1.5
) -> str:
    """List upcoming transit aspects to your natal chart over a date range.

    This tool scans a date range (one sample per day, local midnight at the
    chart location) and returns all significant aspects where transiting
    planets aspect your natal chart points (planets, angles).
    Use it to:
    - See what transits are coming up that will affect your natal chart
    - Identify key transit windows for planning major life events
    - Track specific planets (e.g., Mars, Saturn) as they aspect your natal points

    Args:
        date_time: Birth date and time of the natal chart. Format 'YYYY-MM-DD HH:MM'.
        latitude: Latitude of the natal chart location.
        longitude: Longitude of the natal chart location.
        start_date: Start date for scanning transits. Default: today.
        end_date: End date for scanning transits. Default: +365 days.
        house_system: House system to use. Default: 'whole_sign'.
        aspect_filter: Filter by aspect types (comma-separated, e.g., "Conjunction,Square").
        max_orb: Maximum orb threshold in degrees. Aspects with orb <= this value are included. Default: 1.5

    Returns:
        JSON string with list of upcoming transits, each containing date, objects, aspect type, and orb
    """
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
        end_date = (today + timedelta(days=365)).strftime("%Y-%m-%d")

    try:
        from immanuel import charts
        from datetime import date

        # Build config
        config = get_config(house_system)

        # Create subject (birth data)
        native = charts.Subject(
            date_time=date_time.replace("T", " "),
            latitude=float(latitude),
            longitude=float(longitude),
        )

        # Create natal chart (reference)
        natal_chart = charts.Natal(native, config=config)

        # Get natal positions (full-precision longitudes)
        natal_positions = {}
        for obj in natal_chart.objects.values():
            if obj.name in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron']:
                natal_positions[obj.name] = obj.longitude.raw % 360

        # Parse aspect filter
        aspect_types = None
        if aspect_filter:
            aspect_types = [at.strip() for at in aspect_filter.split(",")]

        # Scan date range
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        transits_to_natal = []
        current_date = start

        while current_date <= end:
            # Create transit chart for this date (local midnight)
            date_str = current_date.isoformat() + " 00:00"

            transit_chart = _transits_for_date(
                date_str, latitude, longitude, natal_chart, config
            )

            # Calculate transit-to-natal aspects
            transit_natal_aspects = calculate_transit_to_natal_aspects(transit_chart, natal_positions)

            # Filter by max_orb and aspect types
            filtered = filter_aspects(
                transit_natal_aspects,
                aspect_type=aspect_types,
                max_orb=max_orb
            )

            # Add to results if any transits found
            for aspect in filtered:
                transit_entry = {
                    "date": current_date.isoformat(),
                    **aspect
                }
                transits_to_natal.append(transit_entry)

            current_date += timedelta(days=1)

        # Sort by date
        transits_to_natal.sort(key=lambda x: x["date"])

        result = {
            "transit_range": {
                "start": start_date,
                "end": end_date
            },
            "total_transits_to_natal": len(transits_to_natal),
            "transits_to_natal": transits_to_natal
        }

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
            "Generate a transit chart showing current (or specified) planetary positions and their aspects to a natal chart. "
            "Use this for current conditions, timing events, or tracking lunar transits (lunations). "
            "For lunation work, set transit_date_time to the exact moment of a new or full moon you want to analyze. "
            "The output shows transiting planets against the natal chart's houses and all transiting-to-natal aspects "
            "with full details (type, orb)."
        )
    )

    mcp.add_tool(
        list_upcoming_planetary_transits,
        name="list_upcoming_planetary_transits",
        description=(
            "List upcoming planetary transit aspects over a date range (one sample per day at local midnight). "
            "Use this to see what transits are coming up in the next month or year, "
            "identify key transit windows for planning, or track specific planets over time. "
            "Returns transit-to-natal aspects detected by the ephemeris (all configured aspect types)."
        )
    )

    mcp.add_tool(
        list_upcoming_transits_to_natal,
        name="list_upcoming_transits_to_natal",
        description=(
            "List upcoming transit aspects to your natal chart over a date range. "
            "Use this to see what transits are coming up that will affect your natal chart, "
            "identify key transit windows for planning major life events, or track specific planets as they aspect your natal points. "
            "Returns transit-to-natal aspects only (not planetary alignments)."
        )
    )
