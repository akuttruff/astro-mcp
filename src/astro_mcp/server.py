"""MCP server setup, tool registration, and main entry point."""

import json
from mcp.server.mcpserver import MCPServer

from astro_mcp.config import HOUSE_SYSTEMS_INFO
from astro_mcp.tools import natal, solar_return, progressed, transit, synastry, timing, horary

# Create MCPServer instance
mcp = MCPServer(
    name="astro-mcp",
    instructions=(
        "You have access to precise astrological chart calculations using the immanuel-python library. "
        "Use these tools to generate natal charts, transits, solar returns, progressions, and synastry. "
        "All output is structured JSON that you must parse and interpret. "
        "Transit question routing: for 'what transits are coming up', 'when will X happen', or 'how long does this "
        "transit last', use list_upcoming_transits - it returns dated aspects computed by the ephemeris over a date "
        "range (with birth data: transits to that natal chart; without: transits as-is), so never estimate transit "
        "timing or duration yourself from a single chart. "
        "Use create_transit_chart only for one specific moment: 'now' (omit transit_date_time) or a user-given date/time, "
        "e.g. the exact moment of a new or full moon for lunation work. "
        "Transit responses carry the natal positions they are measured against ('natal.positions') and both ends of "
        "every aspect (from_position/to_position): quote those, never recall natal degrees from memory. A planet listed "
        "with 0 in 'spans_per_object' aspects nothing in that window -- say so, do not fill the gap. Before asserting a "
        "transit you have not just read from a tool result, run verify_claim and report its verdict. "
        "Timing and electional routing: for planetary hours ('a Venus hour', 'what hour is it') use planetary_hours; "
        "for 'is the Moon void?' or choosing a time to start something use moon_void_periods; for new/full moons and "
        "eclipses (and how they fall in a birth chart) use lunations_and_eclipses. These compute the traditional rules "
        "for you: report their results, never work out hours, void periods or lunation dates yourself. "
        "Horary routing: when the user asks a yes/no question about a situation ('will I get the job?', 'will he "
        "come back?', 'where is my ring?'), answer it with judge_question: pick quesited_house from its house guide; "
        "the time defaults to now, and a place is required. Lead with its summary, cite its testimony and flagged "
        "considerations, and never judge the chart yourself. Use cast_horary_chart only to show the chart itself. "
        "Horary uses its own traditional settings (Regiomontanus), regardless of the house system used elsewhere. "
        "Use whole_sign houses (default) unless the user explicitly requests another system. "
        "Date format: pass all datetimes as ISO 8601 'YYYY-MM-DD HH:MM' (e.g. '1984-05-10 20:44') and date-only "
        "params as 'YYYY-MM-DD'. Convert natural-language dates from the user (e.g. 'May 10, 1984 8:44 PM' -> "
        "'1984-05-10 20:44') before calling tools - free-form date strings are rejected. "
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
    timing.register(mcp)
    horary.register(mcp)


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


    # Register tools with MCPServer. There is no "what time is it" tool any
    # more: every tool schema costs the model ~500 prompt tokens a turn, and
    # the client (lm-chat) stamps the date and time on each message, so the
    # model already knows what "today" is without a round trip.
    mcp.add_tool(list_house_systems, name="list_house_systems")
    mcp.add_tool(list_chart_objects, name="list_chart_objects")


# Register all tools
register_tools()
register_reference_tools()


def main():
    """Main entry point for the MCP server."""
    # MCPServer v2's run() handles stdio transport internally
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
