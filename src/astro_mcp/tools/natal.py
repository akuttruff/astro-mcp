"""Natal chart tool for astro-mcp."""

from typing import Annotated

from mcp.server.mcpserver import MCPServer

from pydantic import Field
from astro_mcp.schemas import get_coordinates_for_params
from astro_mcp.utils import describe_chart_error, compact_chart_json, error_response, extract_aspect_details, validate_date_string, validate_latitude, validate_longitude
from astro_mcp.config import get_config


def _location_note(latitude: float, longitude: float, matched: str | None) -> dict:
    """Report the coordinates used, and what a place name resolved to."""
    note = {"latitude": round(latitude, 4), "longitude": round(longitude, 4)}
    if matched:
        note["matched_location"] = matched
    return note


def create_natal_chart(
    date_time: Annotated[str, Field(description="Birth date and time in ISO 8601: 'YYYY-MM-DD HH:MM' (seconds and 'T' separator optional), e.g. '1990-07-04 09:30'. Local time at the birthplace.")],
    time_is_dst: bool | None = None,
    timezone_offset: float | None = None,
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None
) -> str:
    """Generate a full natal chart with planets, houses, aspects, and patterns.

    Use this tool to generate a complete birth chart for any date and location.
    The output includes all planets (Sun through Pluto), angles (Asc, MC, IC, DSC),
    lunar nodes, Chiron, and Arabic parts. Also includes whole-sign house cusps,
    aspects between planets, and aspect patterns (T-squares, grand trines, etc.).

    Args:
        date_time: Birth date and time. 'YYYY-MM-DD HH:MM' or full ISO 8601
            ('YYYY-MM-DDTHH:MM:SS'). Local time at the birthplace.
        time_is_dst: Set true/false to clarify if the time is Daylight Saving Time.
        timezone_offset: Explicit UTC offset in hours (e.g. -8.0 for PST, -7.0 for PDT).
        latitude: Latitude (optional if city is provided). Decimal degrees (e.g. 34.05); negative for south.
        longitude: Longitude (optional if city is provided). Decimal degrees (e.g. -118.24); negative for west.
        city: City name (optional if coordinates are provided). If provided, will be geocoded to coordinates.
        state: State/province code or name (optional, used with city for geocoding).
        country: Country code or name (optional, used with city for geocoding).

    Returns:
        Compact JSON of the natal chart: name-keyed objects (decimal longitude,
        degree-and-minute position, house, planet speed), house cusps, detailed aspects
        (type, orb, condition, movement), aspect patterns, corrected moon
        phase, and diurnal flag. Error JSON if validation fails.
    """
    # Validate date
    valid, error = validate_date_string(date_time)
    if not valid:
        return error_response("Invalid date", error)

    # Get coordinates (either from params or geocoding)
    try:
        lat_val, lon_val, matched = get_coordinates_for_params(
            latitude, longitude, city, state, country
        )
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

    try:
        from immanuel import charts

        # Build config
        config = get_config()

        # Create subject (birth data). When timezone_offset/time_is_dst are
        # not provided, immanuel geolocates the timezone from the coordinates.
        native = charts.Subject(
            date_time=date_time.replace("T", " "),
            latitude=lat_val,
            longitude=lon_val,
            timezone_offset=timezone_offset,
            time_is_dst=time_is_dst,
        )

        # Create natal chart
        natal_chart = charts.Natal(native, config=config)

        # Get aspect details using immanuel's internal Aspect objects
        aspects_list = extract_aspect_details(natal_chart)

        return compact_chart_json(
            natal_chart,
            chart_type="natal",
            date_time=date_time.replace("T", " "),
            house_system="whole_sign",
            aspects=aspects_list,
            extra=_location_note(lat_val, lon_val, matched),
        )

    except ValueError as e:
        return error_response("Chart generation failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        known = describe_chart_error(e)
        if known:
            return error_response(*known)
        return error_response("Chart generation failed", f"Unexpected error: {str(e)}")


def register(mcp: MCPServer):
    """Register the create_natal_chart tool with MCPServer."""
    # Register tool with MCPServer
    mcp.add_tool(
        create_natal_chart,
        name="create_natal_chart",
        description=(
            "Generate a full natal chart with planets, houses, aspects, and patterns. "
            "Use this tool to generate a complete birth chart for any date and location. "
            "The output includes all planets (Sun through Pluto), angles (Asc, MC, IC, Desc), "
            "lunar nodes, Chiron, and Arabic parts. Also includes whole-sign house cusps, detailed aspects "
            "with type (conjunction, opposition, square, trine, sextile), orb values, and "
            "aspect patterns (T-squares, grand trines, etc.). "
            "You can provide either (latitude AND longitude, in decimal degrees) OR (city, state, country). "
        )
    )
