"""MCP server setup, tool registration, and main entry point."""

import json
from mcp.server.mcpserver import MCPServer

from astro_mcp.config import HOUSE_SYSTEMS_INFO
from astro_mcp.tools import natal, solar_return, progressed, transit, synastry
from astro_mcp.utils import get_current_datetime

# Create MCPServer instance
mcp = MCPServer(
    name="astro-mcp",
    instructions=(
        "You have access to precise astrological chart calculations using the immanuel-python library. "
        "Use these tools to generate natal charts, transits, solar returns, progressions, and synastry. "
        "All output is structured JSON that you must parse and interpret. "
        "Use create_transit_chart with a specific date/time to track lunar phases (lunations) - set transit_date_time "
        "to the exact moment of a new or full moon to see where the Moon and other bodies are relative to the natal chart. "
        "Use whole_sign houses (default) unless the user explicitly requests another system. "
    ),
)


def register_tools():
    """Register all MCP tools."""
    # Import tool modules and register them
    natal.register(mcp)
    solar_return.register(mcp)
    progressed.register(mcp)
    transit.register(mcp)
    synastry.register(mcp)


def register_reference_tools():
    """Register reference tools that list available options."""
    
    def list_house_systems() -> str:
        """Return a list of all supported house systems with their names and descriptions.

        Use this to help the user choose a house system if they ask for one that's not the default.
        """
        import json
        from astro_mcp.config import HOUSE_SYSTEM_MAP

        systems = []
        for sys_id, description in HOUSE_SYSTEMS_INFO.items():
            systems.append({
                "id": sys_id,
                "name": sys_id.replace("_", " ").title(),
                "description": description
            })

        # Sort alphabetically by id for consistent output
        systems.sort(key=lambda x: x["id"])

        result = {
            "default": "whole_sign",
            "systems": systems
        }

        return json.dumps(result, indent=2)

    def list_chart_objects() -> str:
        """Return the list of celestial objects included in charts by default.

        The natal, solar_return, progressed, transit, and synastry tools all return
        a comprehensive list of objects. This tool describes what's available.

        Returns:
            JSON with included_by_default and available_extras lists.
        """
        import json

        result = {
            "included_by_default": [
                "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
                "Uranus", "Neptune", "Pluto",
                "Ascendant", "MC", "IC", "DSC",
                "North Node", "South Node",
                "Chiron"
            ],
            "available_extras": [
                "Ceres", "Pallas", "Juno", "Vesta",
                "Part of Fortune", "Part of Spirit", "Part of Eros"
            ],
            "note": (
                "Arabic Parts (Fortune, Spirit, Eros) are calculated automatically and included "
                "in the objects dictionary of any chart response. Extras like Ceres, Pallas, "
                "Juno, and Vesta can be added via immanuel's Config.objects if needed."
            )
        }

        return json.dumps(result, indent=2)


    def get_current_datetime_tool() -> str:
        """Return the current date and time for context awareness.

        Use this tool at the start of any interaction to know the current date/time.
        This helps you understand what "today" is when analyzing transits or other
        time-sensitive astrological information.

        Returns:
            JSON with current datetime, date components, and time components
        """
        return json.dumps(get_current_datetime(), indent=2)

    # Register tools with MCPServer
    mcp.add_tool(list_house_systems, name="list_house_systems")
    mcp.add_tool(list_chart_objects, name="list_chart_objects")
    mcp.add_tool(get_current_datetime_tool, name="get_current_datetime")


# Register all tools
register_tools()
register_reference_tools()


def main():
    """Main entry point for the MCP server."""
    # MCPServer v2's run() handles stdio transport internally
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
