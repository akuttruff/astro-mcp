"""Solar return chart tool for astro-mcp."""

import json
from mcp.server.mcpserver import MCPServer

from astro_mcp.utils import chart_to_json, corrected_moon_phase, error_response, extract_aspect_details, validate_date_string, validate_latitude, validate_longitude, validate_house_system
from astro_mcp.config import get_config


def create_solar_return(
    date_time: str,
    latitude: str,
    longitude: str,
    year: int,
    house_system: str | None = None
) -> str:
    """Generate a solar return (annual forecast) chart for a given year.

    A solar return chart is cast for the exact moment the Sun returns to its natal
    degree and minute. It's used for annual forecasts, looking at the coming year
    from roughly birthday to birthday.

    Args:
        date_time: Birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'. Local time at the birthplace.
        latitude: Latitude. Decimal degrees (e.g. '34.05') or DMS (e.g. '34n03'). Negative or 's' for south.
        longitude: Longitude. Decimal degrees (e.g. '-118.24') or DMS (e.g. '118w15'). Negative or 'w' for west.
        year: The year for the solar return (e.g., 2025). Must be between 1200 and 4799.
        house_system: House system to use. Default: 'whole_sign'. See list_house_systems for options.

    Returns:
        JSON string of the solar return chart, or error message if validation fails
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

    # Validate year
    if year < 1200 or year > 4799:
        return error_response(
            "Year out of range",
            f"Supported range: 1200 to 4799. Got: {year}"
        )

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

        # Create solar return chart (uses native directly, not natal_chart)
        solar_return_chart = charts.SolarReturn(
            native=native,
            year=year,
            config=config
        )

        # Get aspect details using immanuel's internal Aspect objects
        aspects_list = extract_aspect_details(solar_return_chart)

        # Serialize to JSON with aspect details
        result_json = json.loads(chart_to_json(solar_return_chart))

        # Replace the aspects array with detailed aspect information
        result_json["aspects"] = aspects_list

        # immanuel's moon phase bins are mislabeled (see corrected_moon_phase)
        moon_phase = corrected_moon_phase(solar_return_chart)
        if moon_phase is not None:
            result_json["moon_phase"] = moon_phase

        return json.dumps(result_json, indent=2)

    except ValueError as e:
        return error_response("Solar return generation failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        return error_response("Solar return generation failed", f"Unexpected error: {str(e)}")


def register(mcp: MCPServer):
    """Register the create_solar_return tool with MCPServer."""
    # Register tool with MCPServer
    mcp.add_tool(
        create_solar_return,
        name="create_solar_return",
        description=(
            "Generate a solar return (annual forecast) chart for a given year. "
            "A solar return chart is cast for the exact moment the Sun returns to its natal "
            "degree and minute. It's used for annual forecasts, looking at the coming year "
            "from roughly birthday to birthday. Output includes detailed aspects with type, "
            "orb values, and aspect patterns."
        )
    )
