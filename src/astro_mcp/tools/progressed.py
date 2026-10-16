"""Progressed chart tool for astro-mcp."""

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from astro_mcp.utils import describe_chart_error, compact_chart_json, error_response, extract_aspect_details, validate_date_string, validate_latitude, validate_longitude
from astro_mcp.config import get_config
from astro_mcp.schemas import get_coordinates_for_params


def create_progressed_chart(
    date_time: Annotated[str, Field(description="Birth date and time in ISO 8601: 'YYYY-MM-DD HH:MM' (seconds and 'T' separator optional), e.g. '1990-07-04 09:30'. Local time at the birthplace.")],
    target_date: Annotated[str, Field(description="Date to progress to, in ISO 8601: 'YYYY-MM-DD HH:MM' (seconds and 'T' separator optional).")],
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    city: Annotated[str | None, Field(description="City name, geocoded to coordinates. Use instead of latitude/longitude.")] = None,
    state: Annotated[str | None, Field(description="State or province, to disambiguate the city.")] = None,
    country: Annotated[str | None, Field(description="Country, to disambiguate the city.")] = None,
) -> str:
    """Generate a secondary progressed chart for a target date.

    Secondary progression uses the "1 day = 1 year" method, where each day after
    birth corresponds to a year of life. This is one of the most common techniques
    for tracking chart evolution over time.

    Args:
        date_time: Birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'. Local time at the birthplace.
        latitude: Latitude in decimal degrees (e.g. 34.05); negative for south.
        longitude: Longitude in decimal degrees (e.g. -118.24); negative for west.
        target_date: The date to progress to, in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'.

    Returns:
        JSON string of the progressed chart, or error message if validation fails
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

        # Built with aspects_to=natal_chart, so every aspect runs from a
        # progressed object to a natal one. Say so: "progressed Asc conjunct
        # Jupiter" is ambiguous, and progressed and natal Jupiter can sit a
        # fraction of a degree apart.
        aspects_list = extract_aspect_details(progressed_chart)
        for aspect in aspects_list:
            aspect["from_chart"] = "progressed"
            aspect["to_chart"] = "natal"

        progressed_moment = progressed_chart.progressed_date_time.datetime.isoformat()

        return compact_chart_json(
            progressed_chart,
            chart_type="progressed",
            # The moment this chart is actually cast for. Naming the birth
            # time here made a progressed chart look like a natal one.
            date_time=progressed_moment,
            house_system="whole_sign",
            aspects=aspects_list,
            extra={
                "birth_date_time": date_time.replace("T", " "),
                "target_date": target_date.replace("T", " "),
                "progressed_date_time": progressed_moment,
                "note": (
                    "Positions are progressed to progressed_date_time (secondary "
                    "progression, one day per year of life). Aspects run from a "
                    "progressed object to a natal one, as each entry's from_chart "
                    "and to_chart record."
                ),
            },
        )

    except ValueError as e:
        return error_response("Progressed chart generation failed", str(e))
    except ImportError as e:
        return error_response("immanuel library not available", str(e))
    except Exception as e:
        known = describe_chart_error(e)
        if known:
            return error_response(*known)
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
