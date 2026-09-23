"""Synastry chart tool for astro-mcp."""

from mcp.server.mcpserver import MCPServer

from astro_mcp.utils import compact_chart_json, error_response, extract_aspect_details, validate_date_string, validate_latitude, validate_longitude, validate_house_system
from astro_mcp.config import get_config


def register(mcp: MCPServer):
    """Register the create_synastry tool with MCPServer."""

    def create_synastry(
        date_time_a: str,
        latitude_a: str | float,
        longitude_a: str | float,
        date_time_b: str,
        latitude_b: str | float,
        longitude_b: str | float,
        house_system: str | None = None
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
            latitude_a: Person A latitude. Decimal degrees (e.g. '34.05') or DMS.
            longitude_a: Person A longitude. Decimal degrees (e.g. '-118.24') or DMS.
            date_time_b: Person B birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'.
            latitude_b: Person B latitude. Decimal degrees (e.g. '34.05') or DMS.
            longitude_b: Person B longitude. Decimal degrees (e.g. '-118.24') or DMS.
            house_system: House system to use. Default: 'whole_sign'. See list_house_systems for options.

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

        # Validate house system if provided
        valid, error = validate_house_system(house_system)
        if not valid:
            return error_response("Invalid house system", error)

        try:
            from immanuel import charts

            # Build config
            config = get_config(house_system)

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

            # Create composite chart with cross-aspects to Person B's natal
            composite = charts.Composite(
                native=native_a,
                partner=native_b,
                config=config,
                aspects_to=natal_b
            )

            # Build response with both individuals' data and composite
            import json

            composite_data = json.loads(compact_chart_json(
                composite,
                chart_type="composite",
                date_time=date_time_a.replace("T", " "),
                house_system=house_system or "whole_sign",
                aspects=extract_aspect_details(composite),
            ))

            result = {
                "person_a": {
                    "date_time": date_time_a,
                    "latitude": latitude_a,
                    "longitude": longitude_a,
                },
                "person_b": {
                    "date_time": date_time_b,
                    "latitude": latitude_b,
                    "longitude": longitude_b,
                },
                "composite_chart": composite_data,
                "cross_aspects": {
                    "description": (
                        "Aspects from Person A's planets to Person B's planets. "
                        "The composite chart above also includes aspects between the composite positions."
                    )
                }
            }

            return json.dumps(result, indent=2)

        except ValueError as e:
            return error_response("Synastry generation failed", str(e))
        except ImportError as e:
            return error_response("immanuel library not available", str(e))
        except Exception as e:
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
