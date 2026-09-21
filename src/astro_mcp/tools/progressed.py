"""Progressed chart tool for astro-mcp."""

import json
from mcp.server.mcpserver import MCPServer

from astro_mcp.utils import chart_to_json, error_response, extract_aspect_details, validate_date_string, validate_latitude, validate_longitude, validate_house_system
from astro_mcp.config import get_config


def create_progressed_chart(
    date_time: str,
    latitude: str,
    longitude: str,
    target_date: str,
    house_system: str | None = None
) -> str:
    """Generate a secondary progressed chart for a target date.

    Secondary progression uses the "1 day = 1 year" method, where each day after
    birth corresponds to a year of life. This is one of the most common techniques
    for tracking chart evolution over time.

    Args:
        date_time: Birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'. Local time at the birthplace.
        latitude: Latitude. Decimal degrees (e.g. '34.05') or DMS (e.g. '34n03'). Negative or 's' for south.
        longitude: Longitude. Decimal degrees (e.g. '-118.24') or DMS (e.g. '118w15'). Negative or 'w' for west.
        target_date: The date to progress to, in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'.
        house_system: House system to use. Default: 'whole_sign'. See list_house_systems for options.

    Returns:
        JSON string of the progressed chart, or error message if validation fails
    """
    # Validate birth date
    valid, error = validate_date_string(date_time)
    if not valid:
        return error_response("Invalid birth date", error)

    # Validate target date
    valid, error = validate_date_string(target_date)
    if not valid:
        return error_response("Invalid target date", error)

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

        # Create natal chart first (needed for progression)
        natal_chart = charts.Natal(native, config=config)

        # Create progressed chart
        # Progressed uses date_time as the target date, and aspects_to as the natal chart
        progressed_chart = charts.Progressed(
            native=native,
            date_time=target_date.replace("T", " "),
            aspects_to=natal_chart,
            config=config
        )

        # Get aspect details using immanuel's internal Aspect objects
        aspects_list = extract_aspect_details(progressed_chart)

        # Serialize to JSON with aspect details
        result_json = json.loads(chart_to_json(progressed_chart))
        
        # Replace the aspects array with detailed aspect information
        result_json["aspects"] = aspects_list
        
        return json.dumps(result_json, indent=2)

    except ValueError as e:
        return error_response("Progressed chart generation failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        return error_response("Progressed chart generation failed", f"Unexpected error: {str(e)}")


def register(mcp: MCPServer):
    """Register the create_progressed_chart tool with MCPServer."""
    # Register tool with MCPServer
    mcp.add_tool(
        create_progressed_chart,
        name="create_progressed_chart",
        description=(
            "Generate a secondary progressed chart for a target date. "
            "Secondary progression uses the '1 day = 1 year' method, where each day after "
            "birth corresponds to a year of life. This is one of the most common techniques "
            "for tracking chart evolution over time. Output includes detailed aspects with type, "
            "orb values, and aspect patterns."
        )
    )
