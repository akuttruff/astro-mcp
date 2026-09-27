"""Solar return chart tool for astro-mcp."""

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from astro_mcp.utils import describe_chart_error, compact_chart_json, error_response, extract_aspect_details, validate_date_string, validate_latitude, validate_longitude, validate_house_system
from astro_mcp.config import get_config
from astro_mcp.schemas import get_coordinates_for_params
from astro_mcp.tools.natal import _location_note


def create_solar_return(
    date_time: Annotated[str, Field(description="Birth date and time in ISO 8601: 'YYYY-MM-DD HH:MM' (seconds and 'T' separator optional), e.g. '1984-05-10 20:44'. Local time at the birthplace.")],
    year: int,
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    house_system: str | None = None,
    city: Annotated[str | None, Field(description="City name, geocoded to coordinates. Use instead of latitude/longitude.")] = None,
    state: Annotated[str | None, Field(description="State or province, to disambiguate the city.")] = None,
    country: Annotated[str | None, Field(description="Country, to disambiguate the city.")] = None,
) -> str:
    """Generate a solar return (annual forecast) chart for a given year.

    A solar return chart is cast for the exact moment the Sun returns to its natal
    degree and minute. It's used for annual forecasts, looking at the coming year
    from roughly birthday to birthday.

    Args:
        date_time: Birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'. Local time at the birthplace.
        latitude: Latitude. Decimal degrees (e.g. '34.05') or DMS (e.g. '34n03'). Negative or 's' for south.
        longitude: Longitude. Decimal degrees (e.g. '-118.24') or DMS (e.g. '118w15'). Negative or 'w' for west.
        year: The year for the solar return (e.g., 2025). Must be between 1200 and 4649,
            the span the bundled Swiss Ephemeris files cover.
        house_system: House system to use. Default: 'whole_sign'. See list_house_systems for options.

    Returns:
        JSON string of the solar return chart, or error message if validation fails
    """
    # A place name is accepted instead of coordinates, as in create_natal_chart.
    try:
        lat_val, lon_val, matched = get_coordinates_for_params(
            latitude, longitude, city, state, country
        )
    except ValueError as e:
        return error_response("Invalid location", str(e))
    except Exception as e:
        return error_response("Geocoding failed", str(e))

    latitude = str(lat_val)
    longitude = str(lon_val)

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
    # The bundled ephemeris runs from early 1200 to 4649; the old 4799
    # bound was inherited from the library's documented maximum and failed
    # with a raw file error for the last 150 years of it.
    if year < 1200 or year > 4649:
        return error_response(
            "Year out of range",
            f"Supported range: 1200 to 4649 (the bundled ephemeris). Got: {year}"
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

        return compact_chart_json(
            solar_return_chart,
            chart_type="solar_return",
            # The instant the Sun returns to its natal degree -- what this
            # chart is cast for. The birth time is kept below for reference.
            date_time=solar_return_chart.solar_return_date_time.datetime.isoformat(),
            house_system=house_system or "whole_sign",
            aspects=aspects_list,
            extra={
                "birth_date_time": date_time.replace("T", " "),
                "solar_return_year": year,
                "solar_return_date_time": solar_return_chart.solar_return_date_time.datetime.isoformat(),
            },
        )

    except ValueError as e:
        return error_response("Solar return generation failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        known = describe_chart_error(e)
        if known:
            return error_response(*known)
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
