"""Transit chart tool for astro-mcp."""

import json
from mcp.server.mcpserver import MCPServer
from datetime import datetime, timedelta

from astro_mcp.utils import chart_to_json, error_response, extract_aspect_details, calculate_transit_to_natal_aspects, filter_aspects, validate_date_string, validate_latitude, validate_longitude, validate_house_system, assign_natal_houses_to_transit_objects
from astro_mcp.config import get_config


def create_transit_chart(
    date_time: str,
    latitude: str,
    longitude: str,
    transit_date_time: str | None = None,
    house_system: str | None = None,
    aspect_type: str | None = None,
    min_orb: float | None = None,
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
    - Transiting planets positioned against the natal chart's houses
    - All transiting-to-natal aspects with full details (type, orb, condition)
    - The natal chart data for reference

    Args:
        date_time: Birth date and time of the natal chart being transited. Format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'.
        latitude: Latitude of the natal chart location. Decimal degrees (e.g. '34.05') or DMS.
        longitude: Longitude of the natal chart location. Decimal degrees (e.g. '-118.24') or DMS.
        transit_date_time: The date/time of the transit. Format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'. If omitted, uses current time. For lunation work, specify the exact time of a new or full moon.
        house_system: House system to use. Default: 'whole_sign'. See list_house_systems for options.
        aspect_type: Filter aspects to specific type(s) (e.g., "Conjunction", "Square"). Multiple types can be comma-separated.
        min_orb: Minimum orb threshold in degrees. Aspects with orb >= this value are included. Default: 0.5
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
    transit_dt = None
    if transit_date_time:
        valid, error = validate_date_string(transit_date_time)
        if not valid:
            return error_response("Invalid transit date", error)
        transit_dt = transit_date_time.replace("T", " ")
    else:
        # Use current time if no transit date specified
        transit_dt = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Parse filter parameters
    aspect_type_list = None
    if aspect_type:
        aspect_type_list = [at.strip() for at in aspect_type.split(",")]

    object_filter_list = None
    if object_filter:
        object_filter_list = [obj.strip() for obj in object_filter.split(",")]

    # Validate min_orb if provided
    if min_orb is not None:
        try:
            min_orb_val = float(min_orb)
            if min_orb_val < 0:
                return error_response("Invalid min_orb", "Must be a positive number")
        except ValueError:
            return error_response("Invalid min_orb", "Must be a valid number")
    else:
        min_orb_val = 0.5

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

        # Create transit chart (using Transits class)
        transit_chart = charts.Transits(
            latitude=latitude,
            longitude=longitude,
            aspects_to=natal_chart,
            config=config
        )

        # Calculate transit-to-natal aspects for all major objects
        natal_positions = {}
        for obj in natal_chart.objects.values():
            if obj.name in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron']:
                natal_positions[obj.name] = obj.longitude.degrees

        transit_natal_aspects = calculate_transit_to_natal_aspects(transit_chart, natal_positions)

        # Apply filtering if specified
        filtered_aspects = filter_aspects(
            transit_natal_aspects,
            aspect_type=aspect_type_list,
            min_orb=min_orb_val,
            object_filter=object_filter_list
        )

        # Serialize to JSON with aspect details
        result_json = json.loads(chart_to_json(transit_chart))

        # Assign transit objects to natal chart houses (fixes house assignment bug)
        assigned_houses = assign_natal_houses_to_transit_objects(transit_chart, natal_chart, house_system or 'whole_sign')

        # Update object houses in the result
        if 'objects' in result_json:
            for obj_id, obj_data in result_json['objects'].items():
                obj_name = obj_data.get('name', '')
                if obj_name in assigned_houses:
                    house_number = assigned_houses[obj_name]
                    # Update the house number
                    result_json['objects'][obj_id]['house'] = {
                        'index': 2000000 + house_number,
                        'number': house_number,
                        'name': f'{house_number}th House'
                    }

        # Replace the aspects array with filtered aspect information
        result_json["aspects"] = filtered_aspects

        return json.dumps(result_json, indent=2)

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
    min_orb: float | None = 1.0
) -> str:
    """List upcoming planetary transits over a date range.

    This tool scans a date range and returns all significant aspects between
    transiting planets/asteroids. Use it to:
    - See what planetary alignments are coming up in the next month or year
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
        min_orb: Minimum orb threshold in degrees. Default: 1.0

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
            # Create transit chart for this date
            current_dt = datetime.combine(current_date, datetime.min.time())
            date_str = current_dt.strftime("%Y-%m-%d 00:00")

            transit_chart = charts.Transits(
                latitude=float(latitude),
                longitude=float(longitude),
                aspects_to=natal_chart,
                config=config
            )

            # Get aspect details
            aspects_list = extract_aspect_details(transit_chart)

            # Filter by min_orb and aspect types
            filtered = filter_aspects(
                aspects_list,
                aspect_type=aspect_types,
                min_orb=min_orb
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
    min_orb: float | None = 1.0
) -> str:
    """List upcoming transit aspects to your natal chart over a date range.

    This tool scans a date range and returns all significant aspects where
    transiting planets/asteroids aspect your natal chart points (planets, angles).
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
        min_orb: Minimum orb threshold in degrees. Default: 1.0

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

        # Get natal positions
        natal_positions = {}
        for obj in natal_chart.objects.values():
            if obj.name in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron']:
                natal_positions[obj.name] = obj.longitude.degrees

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
            # Create transit chart for this date
            current_dt = datetime.combine(current_date, datetime.min.time())
            date_str = current_dt.strftime("%Y-%m-%d 00:00")

            transit_chart = charts.Transits(
                latitude=float(latitude),
                longitude=float(longitude),
                aspects_to=natal_chart,
                config=config
            )

            # Calculate transit-to-natal aspects
            transit_natal_aspects = calculate_transit_to_natal_aspects(transit_chart, natal_positions)

            # Filter by min_orb and aspect types
            filtered = filter_aspects(
                transit_natal_aspects,
                aspect_type=aspect_types,
                min_orb=min_orb
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
            "List upcoming planetary transit aspects over a date range. "
            "Use this to see what planetary alignments are coming up in the next month or year, "
            "identify key transit windows for planning, or track specific planets over time. "
            "Returns aspects between transiting planets/asteroids (not transit-to-natal)."
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
