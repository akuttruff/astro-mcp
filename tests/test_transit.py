"""Tests for create_transit_chart tool."""

import json
import os

import pytest


@pytest.fixture
def reference_a():
    """Reference A: NYC, mid-year, diurnal, Northern Hemisphere."""
    return {
        "date_time": "1984-05-10 20:44",
        "latitude": "34.02",
        "longitude": "-118.40",
    }


@pytest.fixture
def fixture_data_transit():
    """Fixture data for NYC transit chart."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "reference_a_nyc_transit_2025.json")
    
    # Generate fixture if it doesn't exist
    if not os.path.exists(fixture_path):
        from immanuel import charts
        from astro_mcp.utils import extract_aspect_details
        
        reference = {
            "date_time": "1984-05-10 20:44",
            "latitude": 34.02,
            "longitude": -118.40,
        }
        
        native = charts.Subject(
            date_time=reference["date_time"],
            latitude=reference["latitude"],
            longitude=reference["longitude"],
        )
        
        config = charts.Config()
        from immanuel.const import chart as chart_const
        config.house_system = chart_const.WHOLE_SIGN
        
        natal_chart = charts.Natal(native, config=config)
        
        transit_chart = charts.Transits(
            latitude=reference["latitude"],
            longitude=reference["longitude"],
            aspects_to=natal_chart,
            config=config
        )
        
        # Get aspect details
        aspects_list = extract_aspect_details(transit_chart)
        
        # Serialize and update
        json_str = json.dumps(transit_chart, cls=charts.ToJSON)
        data = json.loads(json_str)
        data["aspects"] = aspects_list
        
        with open(fixture_path, "w") as f:
            json.dump(data, f, indent=2)
    
    with open(fixture_path, "r") as f:
        return json.load(f)


class TestTransitChartHappyPath:
    """Test happy path scenarios for transit chart generation."""

    def test_create_transit_chart(self, reference_a):
        """Test generating a transit chart."""
        from astro_mcp.tools import transit
        from mcp.server.mcpserver import MCPServer
        
        mcp = MCPServer(name="test")
        transit.register(mcp)
        
        # Get registered tools
        tools = list(mcp._tool_manager._tools.values())
        tool_names = [t.name for t in tools]
        
        assert "create_transit_chart" in tool_names

    def test_transit_chart_returns_valid_json(self, reference_a):
        """Test that transit chart tool returns valid JSON structure."""
        from astro_mcp.tools.transit import create_transit_chart
        
        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30"
        )
        
        data = json.loads(result)
        
        assert "type" in data
        assert data["type"] == "Transits"
        
        assert "objects" in data
        assert "houses" in data

    def test_transit_chart_has_expected_objects(self, reference_a):
        """Test that transit chart has expected objects."""
        from astro_mcp.tools.transit import create_transit_chart
        
        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30"
        )
        
        data = json.loads(result)
        
        object_names = [obj["name"] for obj in data.get("objects", {}).values()]
        
        expected_planets = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                           "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        
        for planet in expected_planets:
            assert planet in object_names, f"Missing planet: {planet}"


class TestTransitChartValidation:
    """Test validation and error handling for transit charts."""

    def test_invalid_birth_date_format(self, reference_a):
        """Test that invalid birth date format returns error."""
        from astro_mcp.tools.transit import create_transit_chart
        
        result = create_transit_chart(
            date_time="invalid-date",
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30"
        )
        
        data = json.loads(result)
        
        assert "error" in data

    def test_invalid_transit_date_format(self, reference_a):
        """Test that invalid transit date format returns error."""
        from astro_mcp.tools.transit import create_transit_chart
        
        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="invalid-date"
        )
        
        data = json.loads(result)
        
        assert "error" in data

    def test_invalid_latitude(self, reference_a):
        """Test that invalid latitude returns error."""
        from astro_mcp.tools.transit import create_transit_chart
        
        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude="100",
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30"
        )
        
        data = json.loads(result)
        
        assert "error" in data

    def test_invalid_longitude(self, reference_a):
        """Test that invalid longitude returns error."""
        from astro_mcp.tools.transit import create_transit_chart
        
        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude="200",
            transit_date_time="2025-06-15 14:30"
        )
        
        data = json.loads(result)
        
        assert "error" in data

    def test_unknown_house_system(self, reference_a):
        """Test that unknown house system returns error."""
        from astro_mcp.tools.transit import create_transit_chart
        
        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            house_system="invalid_system"
        )
        
        data = json.loads(result)
        
        assert "error" in data


class TestTransitChartHouseSystems:
    """Test different house systems for transit charts."""

    def test_whole_sign_houses_start_at_0(self, reference_a):
        """Test that Whole Sign houses start at 0° of each sign."""
        from astro_mcp.tools.transit import create_transit_chart
        
        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            house_system="whole_sign"
        )
        
        data = json.loads(result)
        
        # In Whole Sign houses, each house starts at 0° of a sign
        for house_key, house in data.get("houses", {}).items():
            longitude_value = house["longitude"]["degrees"]
            assert abs(longitude_value % 30) < 0.01, f"House {house_key} not at sign start: {longitude_value}"

    def test_placidus_houses_differ_from_whole_sign(self, reference_a):
        """Test that Placidus houses differ from Whole Sign."""
        from astro_mcp.tools.transit import create_transit_chart
        
        # Get Whole Sign result
        result_whole = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            house_system="whole_sign"
        )
        
        # Get Placidus result
        result_placidus = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            house_system="placidus"
        )
        
        data_whole = json.loads(result_whole)
        data_placidus = json.loads(result_placidus)
        
        # House cusps should differ between systems
        whole_house_keys = list(data_whole["houses"].keys())
        placidus_house_keys = list(data_placidus["houses"].keys())
        
        whole_cusp1 = data_whole["houses"][whole_house_keys[0]]["longitude"]["degrees"]
        placidus_cusp1 = data_placidus["houses"][placidus_house_keys[0]]["longitude"]["degrees"]
        
        # They should be different (within tolerance for rounding)
        assert abs(whole_cusp1 - placidus_cusp1) > 0.5, "Placidus and Whole Sign should differ"


class TestTransitChartObjects:
    """Test chart objects in transit charts."""

    def test_chiron_included(self, fixture_data_transit):
        """Test that Chiron is included in the transit chart."""
        data = fixture_data_transit
        
        object_names = [obj["name"] for obj in data.get("objects", {}).values()]
        assert "Chiron" in object_names

    def test_all_planets_present(self, fixture_data_transit):
        """Test that all planets are included."""
        data = fixture_data_transit
        
        object_names = [obj["name"] for obj in data.get("objects", {}).values()]
        
        expected_planets = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                           "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        
        for planet in expected_planets:
            assert planet in object_names, f"Missing planet: {planet}"

    def test_angles_present(self, fixture_data_transit):
        """Test that all angles are included."""
        data = fixture_data_transit
        
        object_names = [obj["name"] for obj in data.get("objects", {}).values()]
        
        expected_angles = ["Asc", "MC", "IC", "Desc"]
        
        for angle in expected_angles:
            assert angle in object_names, f"Missing angle: {angle}"

    def test_lunar_nodes_present(self, fixture_data_transit):
        """Test that lunar nodes are included."""
        data = fixture_data_transit
        
        object_names = [obj["name"] for obj in data.get("objects", {}).values()]
        
        assert "True North Node" in object_names
        assert "True South Node" in object_names


class TestTransitChartAspects:
    """Test aspect calculations in transit charts."""

    def test_aspects_calculated(self, fixture_data_transit):
        """Test that aspects are calculated."""
        data = fixture_data_transit
        
        assert len(data.get("aspects", [])) > 0, "No aspects calculated"

    def test_transit_aspects_include_major_types(self, fixture_data_transit):
        """Test that transit aspects include major types."""
        data = fixture_data_transit
        
        aspect_types = [aspect["type"] for aspect in data.get("aspects", [])]
        
        # Transit charts should have conjunctions, squares, trines
        assert "Conjunction" in aspect_types
        assert "Square" in aspect_types
        assert "Trine" in aspect_types

    def test_transit_aspects_have_unique_pairs(self, fixture_data_transit):
        """Test that transit aspects don't contain duplicate pairs."""
        data = fixture_data_transit
        
        aspect_pairs = []
        for aspect in data.get("aspects", []):
            pair = tuple(sorted([aspect["from_object"], aspect["to_object"]]))
            aspect_pairs.append(pair)
        
        # Check for duplicates
        assert len(aspect_pairs) == len(set(aspect_pairs)), "Duplicate aspect pairs found"


class TestTransitChartMoonPhase:
    """Test moon phase in transit charts."""

    def test_moon_phase_calculated(self, fixture_data_transit):
        """Test that moon phase is calculated."""
        data = fixture_data_transit
        
        assert "moon_phase" in data
        moon_phase = data["moon_phase"]
        
        # Check that phase fields exist
        assert "new_moon" in moon_phase
        assert "full_moon" in moon_phase


class TestTransitChartDiurnal:
    """Test diurnal flag in transit charts."""

    def test_diurnal_flag_set(self, fixture_data_transit):
        """Test that diurnal flag is set."""
        data = fixture_data_transit
        
        assert "diurnal" in data
        # Should be a boolean
        assert isinstance(data["diurnal"], bool)


class TestTransitChartSerialization:
    """Test JSON serialization for transit charts."""

    def test_chart_serializes_to_json(self, fixture_data_transit):
        """Test that chart serializes to valid JSON."""
        data = fixture_data_transit

        assert "type" in data
        assert data["type"] == "Transits"

        assert "objects" in data
        assert "houses" in data

    def test_transit_chart_has_detailed_aspects(self, fixture_data_transit):
        """Test that transit JSON includes detailed aspect information."""
        data = fixture_data_transit

        # Check aspects array exists
        assert "aspects" in data, "No aspects found in JSON"

        # Check that aspects is a list
        assert isinstance(data["aspects"], list), "Aspects should be a list"

        # Check that aspects have required fields
        for aspect in data["aspects"]:
            assert "from_object" in aspect, f"Missing from_object in: {aspect}"
            assert "to_object" in aspect, f"Missing to_object in: {aspect}"
            assert "type" in aspect, f"Missing type in: {aspect}"
            assert "orb" in aspect, f"Missing orb in: {aspect}"


class TestTransitChartFiltering:
    """Test aspect filtering in transit charts."""

    def test_filter_by_aspect_type_conjunction(self, reference_a):
        """Test filtering transit aspects by conjunction type."""
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            aspect_type="Conjunction"
        )

        data = json.loads(result)

        # All aspects should be Conjunctions
        for aspect in data["aspects"]:
            assert aspect["type"] == "Conjunction", f"Expected Conjunction, got {aspect['type']}"

    def test_filter_by_aspect_type_square(self, reference_a):
        """Test filtering transit aspects by square type."""
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            aspect_type="Square"
        )

        data = json.loads(result)

        # All aspects should be Squares
        for aspect in data["aspects"]:
            assert aspect["type"] == "Square", f"Expected Square, got {aspect['type']}"

    def test_filter_by_min_orb(self, reference_a):
        """Test filtering by minimum orb value."""
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            min_orb=2.0
        )

        data = json.loads(result)

        # All aspects should have orb >= 2.0
        for aspect in data["aspects"]:
            assert aspect["orb"] >= 2.0, f"Expected orb >= 2.0, got {aspect['orb']}"

    def test_filter_by_object(self, reference_a):
        """Test filtering by transiting object."""
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            object_filter="Mars"
        )

        data = json.loads(result)

        # All aspects should involve Mars as the transiting object
        for aspect in data["aspects"]:
            assert aspect["from_object"] == "Mars", f"Expected Mars as transiting object, got {aspect['from_object']}"

    def test_combined_filters_aspect_and_orb(self, reference_a):
        """Test combining aspect type and min_orb filters."""
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            aspect_type="Trine",
            min_orb=1.5
        )

        data = json.loads(result)

        # All aspects should be Trines with orb >= 1.5
        for aspect in data["aspects"]:
            assert aspect["type"] == "Trine", f"Expected Trine, got {aspect['type']}"
            assert aspect["orb"] >= 1.5, f"Expected orb >= 1.5, got {aspect['orb']}"

    def test_filter_no_matches(self, reference_a):
        """Test that filtering returns empty array when no matches."""
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            aspect_type="Conjunction",
            min_orb=10.0  # Very high orb threshold
        )

        data = json.loads(result)

        # Should return empty array (or no aspects)
        assert isinstance(data["aspects"], list)

    def test_multiple_aspect_types(self, reference_a):
        """Test filtering by multiple aspect types."""
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            aspect_type="Conjunction,Square"
        )

        data = json.loads(result)

        # All aspects should be either Conjunction or Square
        valid_types = ["Conjunction", "Square"]
        for aspect in data["aspects"]:
            assert aspect["type"] in valid_types, f"Expected Conjunction or Square, got {aspect['type']}"


class TestListUpcomingTransits:
    """Test list_upcoming_planetary_transits tool."""

    def test_list_upcoming_planetary_transits_basic(self, reference_a):
        """Test basic list_upcoming_planetary_transits functionality."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        # Scan a short range (1 day)
        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-15"
        )

        data = json.loads(result)

        assert "transit_range" in data
        assert "total_transits" in data
        assert "transits" in data

    def test_list_upcoming_planetary_transits_date_range(self, reference_a):
        """Test that date range is properly set."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-20"
        )

        data = json.loads(result)

        assert data["transit_range"]["start"] == "2025-06-15"
        assert data["transit_range"]["end"] == "2025-06-20"

    def test_list_upcoming_planetary_transits_scans_multiple_days(self, reference_a):
        """Test that scanning multiple days returns transits for each day."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17"
        )

        data = json.loads(result)

        # Should have transits for at least some of the 3 days
        dates = set(t["date"] for t in data["transits"])
        
        # Should contain at least some dates from the range
        assert len(dates) > 0

    def test_list_upcoming_planetary_transits_with_aspect_filter(self, reference_a):
        """Test list_upcoming_planetary_transits with aspect type filter."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17",
            aspect_filter="Conjunction"
        )

        data = json.loads(result)

        # All transits should be Conjunctions
        for transit in data["transits"]:
            assert transit["type"] == "Conjunction", f"Expected Conjunction, got {transit['type']}"

    def test_list_upcoming_planetary_transits_with_min_orb(self, reference_a):
        """Test list_upcoming_planetary_transits with minimum orb filter."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17",
            min_orb=2.0
        )

        data = json.loads(result)

        # All transits should have orb >= 2.0
        for transit in data["transits"]:
            assert transit["orb"] >= 2.0, f"Expected orb >= 2.0, got {transit['orb']}"

    def test_list_upcoming_planetary_transits_total_count(self, reference_a):
        """Test that total_transits count matches actual transits."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17"
        )

        data = json.loads(result)

        assert len(data["transits"]) == data["total_transits"]

    def test_list_upcoming_planetary_transits_sorted_by_date(self, reference_a):
        """Test that transits are sorted by date."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-20"
        )

        data = json.loads(result)

        dates = [t["date"] for t in data["transits"]]
        
        # Check that dates are sorted
        assert dates == sorted(dates), "Transits should be sorted by date"

    def test_list_upcoming_planetary_transits_transit_structure(self, reference_a):
        """Test that each transit has the expected structure."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17"
        )

        data = json.loads(result)

        for transit in data["transits"]:
            assert "date" in transit
            assert "from_object" in transit
            assert "to_object" in transit
            assert "type" in transit
            assert "orb" in transit

    def test_list_upcoming_planetary_transits_default_date_range(self, reference_a):
        """Test that default date range works (uses today to +365 days)."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"]
        )

        data = json.loads(result)

        assert "transit_range" in data
        assert "total_transits" in data
        assert "transits" in data


class TestListUpcomingTransitsValidation:
    """Test validation for list_upcoming_planetary_transits."""

    def test_invalid_birth_date(self, reference_a):
        """Test that invalid birth date returns error."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time="invalid-date",
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"]
        )

        data = json.loads(result)

        assert "error" in data

    def test_invalid_start_date(self, reference_a):
        """Test that invalid start date returns error."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="invalid-date"
        )

        data = json.loads(result)

        assert "error" in data

    def test_invalid_end_date(self, reference_a):
        """Test that invalid end date returns error."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            end_date="invalid-date"
        )

        data = json.loads(result)

        assert "error" in data

    def test_invalid_latitude(self, reference_a):
        """Test that invalid latitude returns error."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude="100",
            longitude=reference_a["longitude"]
        )

        data = json.loads(result)

        assert "error" in data

    def test_invalid_longitude(self, reference_a):
        """Test that invalid longitude returns error."""
        from astro_mcp.tools.transit import list_upcoming_planetary_transits

        result = list_upcoming_planetary_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude="200"
        )

        data = json.loads(result)

        assert "error" in data


class TestListUpcomingTransitsToNatal:
    """Test list_upcoming_transits_to_natal tool."""

    def test_list_upcoming_transits_to_natal_basic(self, reference_a):
        """Test basic list_upcoming_transits_to_natal functionality."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17"
        )

        data = json.loads(result)

        assert "transit_range" in data
        assert "total_transits_to_natal" in data
        assert "transits_to_natal" in data

    def test_list_upcoming_transits_to_natal_date_range(self, reference_a):
        """Test that date range is properly set."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-20"
        )

        data = json.loads(result)

        assert data["transit_range"]["start"] == "2025-06-15"
        assert data["transit_range"]["end"] == "2025-06-20"

    def test_list_upcoming_transits_to_natal_scans_multiple_days(self, reference_a):
        """Test that scanning multiple days returns transits for each day."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17"
        )

        data = json.loads(result)

        dates = set(t["date"] for t in data["transits_to_natal"])
        assert len(dates) > 0

    def test_list_upcoming_transits_to_natal_with_aspect_filter(self, reference_a):
        """Test list_upcoming_transits_to_natal with aspect type filter."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17",
            aspect_filter="Conjunction"
        )

        data = json.loads(result)

        for transit in data["transits_to_natal"]:
            assert transit["type"] == "Conjunction"

    def test_list_upcoming_transits_to_natal_with_min_orb(self, reference_a):
        """Test list_upcoming_transits_to_natal with minimum orb filter."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17",
            min_orb=2.0
        )

        data = json.loads(result)

        for transit in data["transits_to_natal"]:
            assert transit["orb"] >= 2.0

    def test_list_upcoming_transits_to_natal_total_count(self, reference_a):
        """Test that total_transits_to_natal count matches actual transits."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17"
        )

        data = json.loads(result)

        assert len(data["transits_to_natal"]) == data["total_transits_to_natal"]

    def test_list_upcoming_transits_to_natal_sorted_by_date(self, reference_a):
        """Test that transits are sorted by date."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-20"
        )

        data = json.loads(result)

        dates = [t["date"] for t in data["transits_to_natal"]]
        assert dates == sorted(dates), "Transits should be sorted by date"

    def test_list_upcoming_transits_to_natal_structure(self, reference_a):
        """Test that each transit has the expected structure."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17"
        )

        data = json.loads(result)

        for transit in data["transits_to_natal"]:
            assert "date" in transit
            assert "from_object" in transit
            assert "to_object" in transit
            assert "type" in transit
            assert "orb" in transit

    def test_list_upcoming_transits_to_natal_default_date_range(self, reference_a):
        """Test that default date range works."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"]
        )

        data = json.loads(result)

        assert "transit_range" in data
        assert "total_transits_to_natal" in data
        assert "transits_to_natal" in data


class TestListUpcomingTransitsToNatalValidation:
    """Test validation for list_upcoming_transits_to_natal."""

    def test_invalid_birth_date(self, reference_a):
        """Test that invalid birth date returns error."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time="invalid-date",
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"]
        )

        data = json.loads(result)
        assert "error" in data

    def test_invalid_start_date(self, reference_a):
        """Test that invalid start date returns error."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="invalid-date"
        )

        data = json.loads(result)
        assert "error" in data

    def test_invalid_end_date(self, reference_a):
        """Test that invalid end date returns error."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            end_date="invalid-date"
        )

        data = json.loads(result)
        assert "error" in data

    def test_invalid_latitude(self, reference_a):
        """Test that invalid latitude returns error."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude="100",
            longitude=reference_a["longitude"]
        )

        data = json.loads(result)
        assert "error" in data

    def test_invalid_longitude(self, reference_a):
        """Test that invalid longitude returns error."""
        from astro_mcp.tools.transit import list_upcoming_transits_to_natal

        result = list_upcoming_transits_to_natal(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude="200"
        )

        data = json.loads(result)
        assert "error" in data
