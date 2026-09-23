"""Tests for create_solar_return tool."""

import pytest


@pytest.fixture
def reference_a():
    """Reference A: NYC, mid-year, diurnal, Northern Hemisphere."""
    return {
        "date_time": "1990-06-15 14:30",
        "latitude": "40.74",
        "longitude": "-73.99",
    }


@pytest.fixture
def fixture_data_solar_return():
    """Fixture data for NYC solar return 2025."""
    import json
    import os
    
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "reference_a_nyc_solar_return_2025.json")
    with open(fixture_path, "r") as f:
        return json.load(f)


class TestSolarReturnHappyPath:
    """Test happy path scenarios for solar return chart generation."""

    def test_create_solar_return_chart(self, reference_a):
        """Test generating a solar return chart."""
        from astro_mcp.tools import solar_return
        from mcp.server.mcpserver import MCPServer
        
        mcp = MCPServer(name="test")
        solar_return.register(mcp)
        
        # Get registered tools
        tools = list(mcp._tool_manager._tools.values())
        tool_names = [t.name for t in tools]
        
        assert "create_solar_return" in tool_names

    def test_solar_return_returns_valid_json(self, reference_a):
        """Test that solar return tool returns valid JSON structure."""
        from astro_mcp.tools.solar_return import create_solar_return
        
        result = create_solar_return(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            year=2025
        )
        
        import json
        data = json.loads(result)
        
        assert "chart_type" in data
        assert data["chart_type"] == "solar_return"

        assert "date_time" in data
        assert "house_system" in data

    def test_solar_return_has_expected_year(self, reference_a):
        """Test that solar return chart has correct year."""
        from astro_mcp.tools.solar_return import create_solar_return
        
        result = create_solar_return(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            year=2025
        )
        
        import json
        data = json.loads(result)
        
        assert "solar_return_year" in data
        assert data["solar_return_year"] == 2025

    def test_solar_return_has_date_time(self, reference_a):
        """Test that solar return chart has solar return date time."""
        from astro_mcp.tools.solar_return import create_solar_return
        
        result = create_solar_return(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            year=2025
        )
        
        import json
        data = json.loads(result)
        
        assert "solar_return_date_time" in data
        assert data["solar_return_date_time"].startswith("2025-")


class TestSolarReturnValidation:
    """Test validation and error handling for solar return charts."""

    def test_invalid_date_format(self, reference_a):
        """Test that invalid date format returns error."""
        from astro_mcp.tools.solar_return import create_solar_return
        
        result = create_solar_return(
            date_time="invalid-date",
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            year=2025
        )
        
        import json
        data = json.loads(result)
        
        assert "error" in data

    def test_invalid_latitude(self, reference_a):
        """Test that invalid latitude returns error."""
        from astro_mcp.tools.solar_return import create_solar_return
        
        result = create_solar_return(
            date_time=reference_a["date_time"],
            latitude="100",
            longitude=reference_a["longitude"],
            year=2025
        )
        
        import json
        data = json.loads(result)
        
        assert "error" in data

    def test_invalid_longitude(self, reference_a):
        """Test that invalid longitude returns error."""
        from astro_mcp.tools.solar_return import create_solar_return
        
        result = create_solar_return(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude="200",
            year=2025
        )
        
        import json
        data = json.loads(result)
        
        assert "error" in data

    def test_year_out_of_range_low(self, reference_a):
        """Test that year below 1200 returns error."""
        from astro_mcp.tools.solar_return import create_solar_return
        
        result = create_solar_return(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            year=1000
        )
        
        import json
        data = json.loads(result)
        
        assert "error" in data
        assert "range" in data.get("detail", "").lower()

    def test_year_out_of_range_high(self, reference_a):
        """Test that year above 4799 returns error."""
        from astro_mcp.tools.solar_return import create_solar_return
        
        result = create_solar_return(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            year=5000
        )
        
        import json
        data = json.loads(result)
        
        assert "error" in data
        assert "range" in data.get("detail", "").lower()

    def test_unknown_house_system(self, reference_a):
        """Test that unknown house system returns error."""
        from astro_mcp.tools.solar_return import create_solar_return
        
        result = create_solar_return(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            year=2025,
            house_system="invalid_system"
        )
        
        import json
        data = json.loads(result)
        
        assert "error" in data


class TestSolarReturnHouseSystems:
    """Test different house systems for solar return."""

    def test_whole_sign_houses_start_at_0(self, reference_a):
        """Test that Whole Sign houses start at 0° of each sign."""
        from astro_mcp.tools.solar_return import create_solar_return
        
        result = create_solar_return(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            year=2025,
            house_system="whole_sign"
        )
        
        import json
        data = json.loads(result)
        
        # In Whole Sign houses, each house starts at 0° of a sign
        for house_key, house in data.get("houses", {}).items():
            longitude_value = house["cusp"]
            assert abs(longitude_value % 30) < 0.01, f"House {house_key} not at sign start: {longitude_value}"

    def test_placidus_houses_differ_from_whole_sign(self, reference_a):
        """Test that Placidus houses differ from Whole Sign."""
        from astro_mcp.tools.solar_return import create_solar_return
        
        # Get Whole Sign result
        result_whole = create_solar_return(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            year=2025,
            house_system="whole_sign"
        )
        
        # Get Placidus result
        result_placidus = create_solar_return(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            year=2025,
            house_system="placidus"
        )
        
        import json
        data_whole = json.loads(result_whole)
        data_placidus = json.loads(result_placidus)
        
        # House cusps should differ between systems
        # Use the first house key (numeric ID like "2000001")
        whole_house_keys = list(data_whole["houses"].keys())
        placidus_house_keys = list(data_placidus["houses"].keys())
        
        whole_cusp1 = data_whole["houses"][whole_house_keys[0]]["cusp"]
        placidus_cusp1 = data_placidus["houses"][placidus_house_keys[0]]["cusp"]
        
        # They should be different (within tolerance for rounding)
        assert abs(whole_cusp1 - placidus_cusp1) > 0.5, "Placidus and Whole Sign should differ"


class TestSolarReturnObjects:
    """Test chart objects in solar return."""

    def test_chiron_included(self, fixture_data_solar_return):
        """Test that Chiron is included in the solar return chart."""
        data = fixture_data_solar_return
        
        object_names = list(data.get("objects", {}).keys())
        assert "Chiron" in object_names

    def test_all_planets_present(self, fixture_data_solar_return):
        """Test that all planets are included."""
        data = fixture_data_solar_return
        
        object_names = list(data.get("objects", {}).keys())

        expected_planets = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                           "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

        for planet in expected_planets:
            assert planet in object_names, f"Missing planet: {planet}"

    def test_angles_present(self, fixture_data_solar_return):
        """Test that all angles are included."""
        data = fixture_data_solar_return
        
        object_names = list(data.get("objects", {}).keys())

        expected_angles = ["Asc", "MC", "IC", "Desc"]
        
        for angle in expected_angles:
            assert angle in object_names, f"Missing angle: {angle}"

    def test_lunar_nodes_present(self, fixture_data_solar_return):
        """Test that lunar nodes are included."""
        data = fixture_data_solar_return
        
        object_names = list(data.get("objects", {}).keys())

        assert "True North Node" in object_names
        assert "True South Node" in object_names


class TestSolarReturnAspects:
    """Test aspect calculations in solar return."""

    def test_aspects_calculated(self, fixture_data_solar_return):
        """Test that aspects are calculated."""
        data = fixture_data_solar_return
        
        assert len(data.get("aspects", [])) > 0, "No aspects calculated"

    def test_aspect_patterns_present(self, fixture_data_solar_return):
        """Test that aspect patterns are calculated."""
        data = fixture_data_solar_return
        
        assert "aspect_patterns" in data
        patterns = data["aspect_patterns"]
        
        # Check that all expected pattern keys exist
        assert "t_square" in patterns
        assert "grand_trine" in patterns
        assert "yod" in patterns


class TestSolarReturnMoonPhase:
    """Test moon phase calculations in solar return."""

    def test_moon_phase_calculated(self, fixture_data_solar_return):
        """Test that moon phase is calculated."""
        data = fixture_data_solar_return
        
        assert "moon_phase" in data
        moon_phase = data["moon_phase"]
        
        # Check that phase fields exist
        assert "new_moon" in moon_phase
        assert "full_moon" in moon_phase
        assert "formatted" in moon_phase


class TestSolarReturnDiurnal:
    """Test diurnal flag in solar return."""

    def test_diurnal_flag_set(self, fixture_data_solar_return):
        """Test that diurnal flag is set."""
        data = fixture_data_solar_return
        
        assert "diurnal" in data
        # Should be a boolean
        assert isinstance(data["diurnal"], bool)


class TestSolarReturnSerialization:
    """Test JSON serialization for solar return."""

    def test_chart_serializes_to_json(self, fixture_data_solar_return):
        """Test that chart serializes to valid JSON."""
        data = fixture_data_solar_return

        assert "chart_type" in data
        assert data["chart_type"] == "solar_return"

        assert "date_time" in data
        assert "solar_return_year" in data
        assert "objects" in data
        assert "houses" in data


class TestSolarReturnNumericCoordinateSchema:
    """LLMs send coordinates as JSON numbers. The tool input schemas
    (generated from the function type hints) must accept numbers as well as
    strings, or the whole call is rejected with a parse error before the
    tool body ever runs ('params.latitude is not any of [subschema 0]...')."""

    @staticmethod
    def _registered_tool():
        from mcp.server.mcpserver import MCPServer
        from astro_mcp.tools import solar_return

        mcp = MCPServer(name="test")
        solar_return.register(mcp)
        return mcp._tool_manager._tools["create_solar_return"]

    def test_accepts_numeric_coordinates(self):
        args = self._registered_tool().fn_metadata.validate_arguments({
            "date_time": "1984-05-10 20:44",
            "latitude": 34.0211,
            "longitude": -118.3968,
            "year": 2025,
        })
        assert args["latitude"] == 34.0211
        assert args["longitude"] == -118.3968

    def test_numeric_coordinates_end_to_end(self):
        import json
        from astro_mcp.tools.solar_return import create_solar_return

        data = json.loads(create_solar_return(
            date_time="1984-05-10 20:44",
            latitude=34.0211,
            longitude=-118.3968,
            year=2025,
        ))
        assert data["chart_type"] == "solar_return"
        assert data["solar_return_year"] == 2025
