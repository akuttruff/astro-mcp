"""Synastry chart tool for astro-mcp."""

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from astro_mcp.utils import (
    describe_chart_error,
    NATAL_TRANSIT_TARGETS,
    chart_positions,
    compact_chart_json,
    cross_chart_aspects,
    error_response,
    extract_aspect_details,
    validate_date_string,
    validate_latitude,
    validate_longitude,
)
from astro_mcp.config import get_config


def register(mcp: MCPServer):
    """Register the create_synastry tool with MCPServer."""

    def create_synastry(
        date_time_a: Annotated[str, Field(description="Person A birth date and time in ISO 8601: 'YYYY-MM-DD HH:MM' (seconds and 'T' separator optional), e.g. '1990-07-04 09:30'.")],
        latitude_a: str | float,
        longitude_a: str | float,
        date_time_b: Annotated[str, Field(description="Person B birth date and time in ISO 8601: 'YYYY-MM-DD HH:MM' (seconds and 'T' separator optional), e.g. '1990-07-04 09:30'.")],
        latitude_b: str | float,
        longitude_b: str | float,
    ) -> str:
        """Generate a composite chart and cross-chart aspects between two people.

        Synastry analysis shows how two charts interact. The output includes:
        - Composite chart (midpoint of corresponding objects)
        - Cross-chart aspects (Person A objects → Person B objects)
        - Both individuals' natal data for reference

        This is useful for understanding relationships - romantic, business, family,
        or any significant interpersonal dynamic.

        Args:
            date_time_a: Person A birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'.
            latitude_a: Person A latitude in decimal degrees (e.g. 34.05); negative for south.
            longitude_a: Person A longitude in decimal degrees (e.g. -118.24); negative for west.
            date_time_b: Person B birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'.
            latitude_b: Person B latitude in decimal degrees; negative for south.
            longitude_b: Person B longitude in decimal degrees; negative for west.

        Returns:
            JSON string containing composite chart and cross-aspects, or error message
        """
        # The schema accepts coordinates as numbers (LLMs often send JSON
        # numbers); normalize to str for the string-based validators below.
        latitude_a = str(latitude_a)
        longitude_a = str(longitude_a)
        latitude_b = str(latitude_b)
        longitude_b = str(longitude_b)

        # Validate Person A data
        valid, error = validate_date_string(date_time_a)
        if not valid:
            return error_response("Invalid date/time for person A", error)

        valid, error = validate_latitude(latitude_a)
        if not valid:
            return error_response("Invalid latitude for person A", error)

        valid, error = validate_longitude(longitude_a)
        if not valid:
            return error_response("Invalid longitude for person A", error)

        # Validate Person B data
        valid, error = validate_date_string(date_time_b)
        if not valid:
            return error_response("Invalid date/time for person B", error)

        valid, error = validate_latitude(latitude_b)
        if not valid:
            return error_response("Invalid latitude for person B", error)

        valid, error = validate_longitude(longitude_b)
        if not valid:
            return error_response("Invalid longitude for person B", error)

        try:
            from immanuel import charts

            # Build config
            config = get_config()

            # Create Person A subject and natal chart
            native_a = charts.Subject(
                date_time=date_time_a.replace("T", " "),
                latitude=float(latitude_a),
                longitude=float(longitude_a),
            )
            natal_a = charts.Natal(native_a, config=config)

            # Create Person B subject and natal chart
            native_b = charts.Subject(
                date_time=date_time_b.replace("T", " "),
                latitude=float(latitude_b),
                longitude=float(longitude_b),
            )
            natal_b = charts.Natal(native_b, config=config)

            # No aspects_to: this chart's aspects are the composite's own.
            # Passing the partner's natal here produced composite-to-B
            # aspects presented as if they were internal, which is why
            # entries like "Asc conjunct Asc" appeared.
            composite = charts.Composite(
                native=native_a,
                partner=native_b,
                config=config,
            )

            import json

            composite_data = json.loads(compact_chart_json(
                composite,
                chart_type="composite",
                # The composite is a midpoint construct belonging to no
                # moment; naming person A's birth time here implied it was
                # cast for that instant.
                date_time=None,
                house_system="whole_sign",
                aspects=extract_aspect_details(composite),
            ))

            # The actual synastry: every object of A against every object of
            # B. This is what the tool has always advertised and never
            # returned.
            positions_a = chart_positions(natal_a, NATAL_TRANSIT_TARGETS)
            positions_b = chart_positions(natal_b, NATAL_TRANSIT_TARGETS)
            cross = cross_chart_aspects(positions_a, positions_b, "person_a", "person_b")

            result = {
                "person_a": {
                    "date_time": date_time_a,
                    "latitude": latitude_a,
                    "longitude": longitude_a,
                    "objects": json.loads(compact_chart_json(
                        natal_a, chart_type="natal",
                        date_time=date_time_a.replace("T", " "),
                        house_system="whole_sign",
                        aspects=[],
                    ))["objects"],
                },
                "person_b": {
                    "date_time": date_time_b,
                    "latitude": latitude_b,
                    "longitude": longitude_b,
                    "objects": json.loads(compact_chart_json(
                        natal_b, chart_type="natal",
                        date_time=date_time_b.replace("T", " "),
                        house_system="whole_sign",
                        aspects=[],
                    ))["objects"],
                },
                "composite_chart": composite_data,
                "cross_aspects": cross,
                "note": (
                    "cross_aspects are person A's objects to person B's objects, each "
                    "entry naming both charts. composite_chart.aspects are internal to "
                    "the composite."
                ),
            }

            return json.dumps(result, separators=(",", ":"), ensure_ascii=False)

        except ValueError as e:
            return error_response("Synastry generation failed", str(e))
        except ImportError as e:
            return error_response("immanuel library not available", str(e))
        except Exception as e:
            known = describe_chart_error(e)
            if known:
                return error_response(*known)
            return error_response("Synastry generation failed", f"Unexpected error: {str(e)}")

    # Register tool with MCPServer
    mcp.add_tool(
        create_synastry,
        name="create_synastry",
        description=(
            "Generate a composite chart and cross-chart aspects between two people. "
            "Synastry analysis shows how two charts interact. Use this to understand relationships - "
            "romantic, business, family, or any significant interpersonal dynamic."
        )
    )
