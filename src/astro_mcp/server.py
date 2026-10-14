"""MCP server setup, tool registration, and main entry point."""

import json

from mcp.server.mcpserver import MCPServer

from astro_mcp.tools import natal, solar_return, progressed, transit, synastry, timing, horary, forecast

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
        "timing or duration yourself from a single chart. For a whole month ('my forecast for October') use "
        "forecast_month, and for a year ahead use forecast_year: each returns a ranked, labelled digest to quote "
        "from -- lead with its headline transits in order and do not add transits it does not list. "
        "Use create_transit_chart only for one specific moment: 'now' (omit transit_date_time) or a user-given date/time, "
        "e.g. the exact moment of a new or full moon for lunation work. "
        "The chat client draws a chart wheel from create_transit_chart and create_natal_chart results, so when the "
        "user asks to see or draw their transits, call create_transit_chart -- never create_natal_chart, which shows "
        "the birth chart alone. The upcoming, month and year tools return lists, not a wheel. "
        "Transit responses carry the natal positions they are measured against ('natal.positions') and both ends of "
        "every aspect (from_position/to_position): quote those, never recall natal degrees from memory. A planet listed "
        "with 0 in 'spans_per_object' aspects nothing in that window -- say so, do not fill the gap. Before asserting a "
        "transit you have not just read from a tool result, run verify_claim and report its verdict. "
        "Every aspect record carries its standard glyph in 'symbol' (conjunction \u260c, opposition \u260d, square \u25a1, "
        "trine \u25b3, sextile \u26b9, quincunx \u26bb, semi-sextile \u26ba): when you write an aspect with a symbol, use that "
        "one exactly, never a planet glyph or any other sign. "
        "Every planet record says whether it is retrograde ('retrograde': true, and 'speed' below zero); transit "
        "aspects say it for each end in from_retrograde/to_retrograde and their labels. Whenever you name a planet "
        "that is retrograde -- in a table, a list, a chart summary or a sentence -- mark it \u211e right after its "
        "name (e.g. 'Saturn \u211e 10\u00b036' Aries'); give a positions table a Motion column (\u211e or direct) "
        "when any planet in it is retrograde. Never mark a planet whose record does not say so. "
        "Timing and electional routing: for planetary hours ('a Venus hour', 'what hour is it') use planetary_hours; "
        "for 'is the Moon void?' or choosing a time to start something use moon_void_periods; for new/full moons and "
        "eclipses (and how they fall in a birth chart) use lunations_and_eclipses. These compute the traditional rules "
        "for you: report their results, never work out hours, void periods or lunation dates yourself. "
        "Horary routing: when the user asks a yes/no question about a situation ('will I get the job?', 'will he "
        "come back?', 'where is my ring?'), answer it with judge_question: pick quesited_house from its house guide; "
        "the time defaults to now, and a place is required. Lead with its summary, cite its testimony and flagged "
        "considerations, and never judge the chart yourself. Use cast_horary_chart only to show the chart itself. "
        "Houses are whole sign in every chart; horary alone uses its own traditional settings (Regiomontanus). "
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
    forecast.register(mcp)


def register_reference_tools():
    """Register reference tools that list available options."""

    def list_chart_objects() -> str:
        """Return the list of celestial objects included in charts by default.

        The natal, solar_return, progressed, transit, and synastry tools all return
        a comprehensive list of objects. This tool describes what's available.

        Returns:
            JSON with included_by_default and available_extras lists.
        """
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


    # Every tool schema costs the model ~500 prompt tokens a turn, so there is
    # no "what time is it" tool (the client stamps the date on each message)
    # and no house-system list (houses are always whole sign).
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
