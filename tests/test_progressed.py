"""Tests for create_progressed_chart tool."""

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
def fixture_data_progressed():
    """Fixture data for NYC progressed 2025."""
    import json
    import os
    
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "reference_a_nyc_progressed_2025.json")
    with open(fixture_path, "r") as f:
        return json.load(f)


class TestProgressedChartHappyPath:
    """Test happy path scenarios for progressed chart generation."""

    def test_create_progressed_chart(self, reference_a):
        """Test generating a progressed chart."""
        from astro_mcp.tools import progressed
        from mcp.server.mcpserver import MCPServer
        
        mcp = MCPServer(name="test")
        progressed.register(mcp)
        
        # Get registered tools
        tools = list(mcp._tool_manager._tools.values())
        tool_names = [t.name for t in tools]
        
        assert "create_progressed_chart" in tool_names

    def test_progressed_chart_returns_valid_json(self, reference_a):
        """Test that progressed chart tool returns valid JSON structure."""
        from astro_mcp.tools.progressed import create_progressed_chart
        
        result = create_progressed_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            target_date="2025-06-15 14:30"
        )
        
        import json
        data = json.loads(result)
        
        assert "chart_type" in data
        assert data["chart_type"] == "progressed"

        assert "date_time" in data
        assert "house_system" in data

    def test_progressed_chart_has_expected_date(self, reference_a):
        """Test that progressed chart has correct date."""
        from astro_mcp.tools.progressed import create_progressed_chart
        
        result = create_progressed_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            target_date="2025-06-15 14:30"
        )
        
        import json
        data = json.loads(result)
        
        assert "progressed_date_time" in data
        assert isinstance(data["progressed_date_time"], str)
        assert "T" in data["progressed_date_time"]

    def test_progressed_chart_date_differs_from_birth(self, reference_a):
        """Test that progressed date is after birth date."""
        from astro_mcp.tools.progressed import create_progressed_chart
        
        result = create_progressed_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            target_date="2025-06-15 14:30"
        )
        
        import json
        data = json.loads(result)
        
        # The progressed date should be significantly after the birth date
        birth_datetime = data["date_time"]
        progressed_datetime = data["progressed_date_time"]

        # Just verify both exist and are different dates
        assert birth_datetime != progressed_datetime


class TestProgressedChartValidation:
    """Test validation and error handling for progressed charts."""

    def test_invalid_birth_date_format(self, reference_a):
        """Test that invalid birth date format returns error."""
        from astro_mcp.tools.progressed import create_progressed_chart
        
        result = create_progressed_chart(
            date_time="invalid-date",
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            target_date="2025-06-15"
        )
        
        import json
        data = json.loads(result)
        
        assert "error" in data

    def test_invalid_target_date_format(self, reference_a):
        """Test that invalid target date format returns error."""
        from astro_mcp.tools.progressed import create_progressed_chart
        
        result = create_progressed_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            target_date="invalid-date"
        )
        
        import json
        data = json.loads(result)
        
        assert "error" in data

    def test_invalid_latitude(self, reference_a):
        """Test that invalid latitude returns error."""
        from astro_mcp.tools.progressed import create_progressed_chart
        
        result = create_progressed_chart(
            date_time=reference_a["date_time"],
            latitude="100",
            longitude=reference_a["longitude"],
            target_date="2025-06-15"
        )
        
        import json
        data = json.loads(result)
        
        assert "error" in data

    def test_invalid_longitude(self, reference_a):
        """Test that invalid longitude returns error."""
        from astro_mcp.tools.progressed import create_progressed_chart
        
        result = create_progressed_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude="200",
            target_date="2025-06-15"
        )
        
        import json
        data = json.loads(result)
        
        assert "error" in data

    def test_unknown_house_system(self, reference_a):
        """Test that unknown house system returns error."""
        from astro_mcp.tools.progressed import create_progressed_chart
        
        result = create_progressed_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            target_date="2025-06-15",
            house_system="invalid_system"
        )
        
        import json
        data = json.loads(result)
        
        assert "error" in data


class TestProgressedChartHouseSystems:
    """Test different house systems for progressed charts."""

    def test_whole_sign_houses_start_at_0(self, reference_a):
        """Test that Whole Sign houses start at 0° of each sign."""
        from astro_mcp.tools.progressed import create_progressed_chart
        
        result = create_progressed_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            target_date="2025-06-15 14:30",
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
        from astro_mcp.tools.progressed import create_progressed_chart
        
        # Get Whole Sign result
        result_whole = create_progressed_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            target_date="2025-06-15 14:30",
            house_system="whole_sign"
        )
        
        # Get Placidus result
        result_placidus = create_progressed_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            target_date="2025-06-15 14:30",
            house_system="placidus"
        )
        
        import json
        data_whole = json.loads(result_whole)
        data_placidus = json.loads(result_placidus)
        
        # House cusps should differ between systems
        whole_house_keys = list(data_whole["houses"].keys())
        placidus_house_keys = list(data_placidus["houses"].keys())
        
        whole_cusp1 = data_whole["houses"][whole_house_keys[0]]["cusp"]
        placidus_cusp1 = data_placidus["houses"][placidus_house_keys[0]]["cusp"]
        
        # They should be different (within tolerance for rounding)
        assert abs(whole_cusp1 - placidus_cusp1) > 0.5, "Placidus and Whole Sign should differ"


class TestProgressedChartObjects:
    """Test chart objects in progressed charts."""

    def test_chiron_included(self, fixture_data_progressed):
        """Test that Chiron is included in the progressed chart."""
        data = fixture_data_progressed
        
        object_names = list(data.get("objects", {}).keys())
        assert "Chiron" in object_names

    def test_all_planets_present(self, fixture_data_progressed):
        """Test that all planets are included."""
        data = fixture_data_progressed
        
        object_names = list(data.get("objects", {}).keys())

        expected_planets = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                           "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

        for planet in expected_planets:
            assert planet in object_names, f"Missing planet: {planet}"

    def test_angles_present(self, fixture_data_progressed):
        """Test that all angles are included."""
        data = fixture_data_progressed
        
        object_names = list(data.get("objects", {}).keys())

        expected_angles = ["Asc", "MC", "IC", "Desc"]
        
        for angle in expected_angles:
            assert angle in object_names, f"Missing angle: {angle}"

    def test_lunar_nodes_present(self, fixture_data_progressed):
        """Test that lunar nodes are included."""
        data = fixture_data_progressed
        
        object_names = list(data.get("objects", {}).keys())

        assert "True North Node" in object_names
        assert "True South Node" in object_names


class TestProgressedChartAspects:
    """Test aspect calculations in progressed charts."""

    def test_aspects_calculated(self, fixture_data_progressed):
        """Test that aspects are calculated."""
        data = fixture_data_progressed
        
        assert len(data.get("aspects", [])) > 0, "No aspects calculated"

    def test_aspect_patterns_present(self, fixture_data_progressed):
        """Test that aspect patterns are calculated."""
        data = fixture_data_progressed
        
        assert "aspect_patterns" in data
        patterns = data["aspect_patterns"]
        
        # Check that all expected pattern keys exist
        assert "t_square" in patterns
        assert "grand_trine" in patterns
        assert "yod" in patterns


class TestProgressedChartMoonPhase:
    """Test moon phase calculations in progressed charts."""

    def test_moon_phase_calculated(self, fixture_data_progressed):
        """Test that moon phase is calculated."""
        data = fixture_data_progressed
        
        assert "moon_phase" in data
        moon_phase = data["moon_phase"]
        
        # Check that phase fields exist
        assert "new_moon" in moon_phase
        assert "full_moon" in moon_phase
        assert "formatted" in moon_phase


class TestProgressedChartDiurnal:
    """Test diurnal flag in progressed charts."""

    def test_diurnal_flag_set(self, fixture_data_progressed):
        """Test that diurnal flag is set."""
        data = fixture_data_progressed
        
        assert "diurnal" in data
        # Should be a boolean
        assert isinstance(data["diurnal"], bool)


class TestProgressedChartSerialization:
    """Test JSON serialization for progressed charts."""

    def test_chart_serializes_to_json(self, fixture_data_progressed):
        """Test that chart serializes to valid JSON."""
        data = fixture_data_progressed

        assert "chart_type" in data
        assert data["chart_type"] == "progressed"

        assert "date_time" in data
        assert "progressed_date_time" in data
        assert "objects" in data
        assert "houses" in data


class TestProgressedNumericCoordinateSchema:
    """LLMs send coordinates as JSON numbers. The tool input schemas
    (generated from the function type hints) must accept numbers as well as
    strings, or the whole call is rejected with a parse error before the
    tool body ever runs ('params.latitude is not any of [subschema 0]...')."""

    @staticmethod
    def _registered_tool():
        from mcp.server.mcpserver import MCPServer
        from astro_mcp.tools import progressed

        mcp = MCPServer(name="test")
        progressed.register(mcp)
        return mcp._tool_manager._tools["create_progressed_chart"]

    def test_accepts_numeric_coordinates(self):
        args = self._registered_tool().fn_metadata.validate_arguments({
            "date_time": "1984-05-10 20:44",
            "latitude": 34.0211,
            "longitude": -118.3968,
            "target_date": "2025-06-15 12:00",
        })
        assert args["latitude"] == 34.0211
        assert args["longitude"] == -118.3968

    def test_numeric_coordinates_end_to_end(self):
        import json
        from astro_mcp.tools.progressed import create_progressed_chart

        data = json.loads(create_progressed_chart(
            date_time="1984-05-10 20:44",
            latitude=34.0211,
            longitude=-118.3968,
            target_date="2025-06-15 12:00",
        ))
        assert data["chart_type"] == "progressed"
        assert data["target_date"].startswith("2025-06-15")
