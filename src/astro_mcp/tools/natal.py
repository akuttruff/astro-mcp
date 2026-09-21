"""Natal chart tool for astro-mcp."""

import json
from mcp.server.mcpserver import MCPServer

from pydantic import TypeAdapter
from astro_mcp.schemas import NatalChartParams, get_coordinates_for_params
from astro_mcp.utils import chart_to_json, error_response, extract_aspect_details, validate_date_string, validate_latitude, validate_longitude, validate_house_system, get_current_datetime
from astro_mcp.config import get_config


def create_natal_chart(
    date_time: str,
    house_system: str | None = None,
    time_is_dst: bool | None = None,
    timezone_offset: float | None = None,
    latitude: str | None = None,
    longitude: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None
) -> str:
    """Generate a full natal chart with planets, houses, aspects, dignities, and patterns.

    Use this tool to generate a complete birth chart for any date and location.
    The output includes all planets (Sun through Pluto), angles (Asc, MC, IC, DSC),
    lunar nodes, Chiron, and Arabic parts. Also includes house cusps, aspects between
    planets, aspect patterns (T-squares, grand trines, etc.), and chart weightings.

    NOTE: This tool is called by the LLM. The current date/time context is available
    via get_current_datetime() from astro_mcp.utils for reference.

    Args:
        date_time: Birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'. Local time at the birthplace.
        house_system: House system to use. Default: 'whole_sign'. See list_house_systems for options.
        time_is_dst: Set true/false to clarify if the time is Daylight Saving Time.
        timezone_offset: Explicit UTC offset in hours (e.g. -8.0 for PST, -7.0 for PDT).
        latitude: Latitude (optional if city is provided). Decimal degrees (e.g. '34.05') or DMS (e.g. '34n03'). Negative or 's' for south.
        longitude: Longitude (optional if city is provided). Decimal degrees (e.g. '-118.24') or DMS (e.g. '118w15'). Negative or 'w' for west.
        city: City name (optional if coordinates are provided). If provided, will be geocoded to coordinates.
        state: State/province code or name (optional, used with city for geocoding).
        country: Country code or name (optional, used with city for geocoding).

    Returns:
        JSON string of the complete natal chart, or error message if validation fails
    """
    # Validate date
    valid, error = validate_date_string(date_time)
    if not valid:
        return error_response("Invalid date", error)

    # Get coordinates (either from params or geocoding)
    try:
        lat_val, lon_val = get_coordinates_for_params(latitude, longitude, city, state, country)
    except ValueError as e:
        return error_response("Invalid location", str(e))
    except RuntimeError as e:
        return error_response("Geocoding failed", str(e))

    # Validate latitude and longitude
    valid, error = validate_latitude(str(lat_val))
    if not valid:
        return error_response("Invalid latitude", error)

    valid, error = validate_longitude(str(lon_val))
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
            latitude=lat_val,
            longitude=lon_val,
        )

        # Create natal chart
        natal_chart = charts.Natal(native, config=config)

        # Get aspect details using immanuel's internal Aspect objects
        aspects_list = extract_aspect_details(natal_chart)

        # Serialize to JSON with aspect details
        result_json = json.loads(chart_to_json(natal_chart))
        
        # Replace the aspects array with detailed aspect information
        result_json["aspects"] = aspects_list
        
        return json.dumps(result_json, indent=2)

    except ValueError as e:
        return error_response("Chart generation failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        return error_response("Chart generation failed", f"Unexpected error: {str(e)}")


def register(mcp: MCPServer):
    """Register the create_natal_chart tool with MCPServer."""
    # Register tool with MCPServer
    mcp.add_tool(
        create_natal_chart,
        name="create_natal_chart",
        description=(
            "Generate a full natal chart with planets, houses, aspects, dignities, and patterns. "
            "Use this tool to generate a complete birth chart for any date and location. "
            "The output includes all planets (Sun through Pluto), angles (Asc, MC, IC, Desc), "
            "lunar nodes, Chiron, and Arabic parts. Also includes house cusps, detailed aspects "
            "with type (conjunction, opposition, square, trine, sextile), orb values, and "
            "aspect patterns (T-squares, grand trines, etc.), and chart weightings. "
            "You can provide either (latitude AND longitude) OR (city, state, country). "
        )
    )
