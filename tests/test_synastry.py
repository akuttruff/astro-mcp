"""Tests for create_synastry tool."""


class TestSynastryNumericCoordinateSchema:
    """LLMs send coordinates as JSON numbers. The tool input schemas
    (generated from the function type hints) must accept numbers as well as
    strings, or the whole call is rejected with a parse error before the
    tool body ever runs ('params.latitude is not any of [subschema 0]...')."""

    @staticmethod
    def _registered_tool():
        from mcp.server.mcpserver import MCPServer
        from astro_mcp.tools import synastry

        mcp = MCPServer(name="test")
        synastry.register(mcp)
        return mcp._tool_manager._tools["create_synastry"]

    def test_accepts_numeric_coordinates(self):
        args = self._registered_tool().fn_metadata.validate_arguments({
            "date_time_a": "1984-05-10 20:44",
            "latitude_a": 34.0211,
            "longitude_a": -118.3968,
            "date_time_b": "1990-01-15 08:30",
            "latitude_b": 40.7128,
            "longitude_b": -74.006,
        })
        assert args["latitude_a"] == 34.0211
        assert args["longitude_a"] == -118.3968
        assert args["latitude_b"] == 40.7128
        assert args["longitude_b"] == -74.006

    def test_accepts_string_coordinates(self):
        args = self._registered_tool().fn_metadata.validate_arguments({
            "date_time_a": "1984-05-10 20:44",
            "latitude_a": "34.0211",
            "longitude_a": "-118.3968",
            "date_time_b": "1990-01-15 08:30",
            "latitude_b": "40.7128",
            "longitude_b": "-74.006",
        })
        assert args["latitude_a"] == "34.0211"

    def test_numeric_coordinates_end_to_end(self):
        import json
        from astro_mcp.tools import synastry
        from mcp.server.mcpserver import MCPServer

        mcp = MCPServer(name="test")
        synastry.register(mcp)
        tool = mcp._tool_manager._tools["create_synastry"]
        args = tool.fn_metadata.validate_arguments({
            "date_time_a": "1984-05-10 20:44",
            "latitude_a": 34.0211,
            "longitude_a": -118.3968,
            "date_time_b": "1990-01-15 08:30",
            "latitude_b": 40.7128,
            "longitude_b": -74.006,
        })

        data = json.loads(tool.fn(**args))
        assert "person_a" in data
        assert "person_b" in data
        assert data["composite_chart"]["chart_type"] == "composite"
        # Coordinates survive the body's str() normalization
        assert data["person_a"]["latitude"] == "34.0211"
        assert data["person_b"]["longitude"] == "-74.006"
