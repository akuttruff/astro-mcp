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
    """Fixture data for transit chart at a fixed 2025 date."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "reference_a_nyc_transit_2025.json")

    # Generate fixture if it doesn't exist
    if not os.path.exists(fixture_path):
        from immanuel import charts
        from astro_mcp.config import get_config
        from astro_mcp.tools.transit import _transits_for_date
        from astro_mcp.utils import (
            assign_natal_houses_to_transit_objects,
            calculate_transit_to_natal_aspects,
            compact_chart_json,
        )

        reference = {
            "date_time": "1984-05-10 20:44",
            "latitude": 34.02,
            "longitude": -118.40,
        }

        config = get_config("whole_sign")

        native = charts.Subject(
            date_time=reference["date_time"],
            latitude=reference["latitude"],
            longitude=reference["longitude"],
        )

        natal_chart = charts.Natal(native, config=config)

        transit_chart = _transits_for_date(
            "2025-06-15 14:30", reference["latitude"], reference["longitude"], natal_chart, config
        )

        natal_positions = {
            o.name: o.longitude.raw % 360
            for o in natal_chart.objects.values()
            if o.name in ["Sun", "Moon", "Mercury", "Venus", "Mars",
                          "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Chiron"]
        }
        aspects_list = calculate_transit_to_natal_aspects(transit_chart, natal_positions)

        with open(fixture_path, "w") as f:
            f.write(compact_chart_json(
                transit_chart,
                chart_type="transit",
                date_time="2025-06-15 14:30",
                house_system="whole_sign",
                house_overrides=assign_natal_houses_to_transit_objects(transit_chart, natal_chart, "whole_sign"),
                houses_chart=natal_chart,
                aspects=aspects_list,
            ))

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

        assert "chart_type" in data
        assert data["chart_type"] == "transit"

        assert "date_time" in data
        assert "objects" in data
        assert "houses" in data

    def test_transit_chart_note_points_to_timing_tool(self, reference_a):
        """The single-moment output must steer the LLM to the range-scanning
        tool instead of estimating transit timing itself."""
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30"
        )

        data = json.loads(result)

        assert "note" in data
        assert "list_upcoming_transits with" in data["note"]

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

        object_names = list(data.get("objects", {}).keys())

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
            longitude_value = house["cusp"]
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
        
        whole_cusp1 = data_whole["houses"][whole_house_keys[0]]["cusp"]
        placidus_cusp1 = data_placidus["houses"][placidus_house_keys[0]]["cusp"]
        
        # They should be different (within tolerance for rounding)
        assert abs(whole_cusp1 - placidus_cusp1) > 0.5, "Placidus and Whole Sign should differ"


class TestTransitChartObjects:
    """Test chart objects in transit charts."""

    def test_chiron_included(self, fixture_data_transit):
        """Test that Chiron is included in the transit chart."""
        data = fixture_data_transit

        object_names = list(data.get("objects", {}).keys())
        assert "Chiron" in object_names

    def test_all_planets_present(self, fixture_data_transit):
        """Test that all planets are included."""
        data = fixture_data_transit

        object_names = list(data.get("objects", {}).keys())

        expected_planets = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                           "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        
        for planet in expected_planets:
            assert planet in object_names, f"Missing planet: {planet}"

    def test_angles_present(self, fixture_data_transit):
        """Test that all angles are included."""
        data = fixture_data_transit

        object_names = list(data.get("objects", {}).keys())

        expected_angles = ["Asc", "MC", "IC", "Desc"]
        
        for angle in expected_angles:
            assert angle in object_names, f"Missing angle: {angle}"

    def test_lunar_nodes_present(self, fixture_data_transit):
        """Test that lunar nodes are included."""
        data = fixture_data_transit

        object_names = list(data.get("objects", {}).keys())

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
        """Test that transit aspects don't contain duplicate directed pairs.

        Transit-to-natal aspects are cross-chart: (transit X, natal Y) and
        (transit Y, natal X) are different aspects that may both be present,
        so uniqueness is checked on the directed (from, to, type) triple,
        not on sorted name pairs.
        """
        data = fixture_data_transit

        aspect_pairs = []
        for aspect in data.get("aspects", []):
            aspect_pairs.append((aspect["from_object"], aspect["to_object"], aspect["type"]))

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

        assert "chart_type" in data
        assert data["chart_type"] == "transit"

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

    def test_filter_by_max_orb(self, reference_a):
        """Test filtering by maximum orb value."""
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            max_orb=2.0
        )

        data = json.loads(result)

        # All aspects should have orb <= 2.0 (tight aspects, including exact ones, kept)
        for aspect in data["aspects"]:
            assert aspect["orb"] <= 2.0, f"Expected orb <= 2.0, got {aspect['orb']}"

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
        """Test combining aspect type and max_orb filters."""
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            aspect_type="Trine",
            max_orb=1.5
        )

        data = json.loads(result)

        # All aspects should be Trines with orb <= 1.5
        for aspect in data["aspects"]:
            assert aspect["type"] == "Trine", f"Expected Trine, got {aspect['type']}"
            assert aspect["orb"] <= 1.5, f"Expected orb <= 1.5, got {aspect['orb']}"

    def test_filter_no_matches(self, reference_a):
        """Test that filtering returns empty array when no matches.

        'Quincunx' is never emitted by the transit-to-natal aspect
        calculator, so the result is deterministically empty.
        """
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time="2025-06-15 14:30",
            aspect_type="Quincunx"
        )

        data = json.loads(result)

        assert data["aspects"] == []

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
    """Test list_upcoming_transits with birth data (natal mode)."""

    def test_list_upcoming_transits_basic(self, reference_a):
        """Test basic natal-mode functionality."""
        from astro_mcp.tools.transit import list_upcoming_transits

        # Scan a short range (1 day)
        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-15"
        )

        data = json.loads(result)

        assert "transit_range" in data
        assert data["mode"] == "natal"
        assert "natal" in data
        assert "note" not in data
        assert "total_transits" in data
        assert "transits" in data

    def test_list_upcoming_transits_date_range(self, reference_a):
        """Test that date range is properly set."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-20"
        )

        data = json.loads(result)

        assert data["transit_range"]["start"] == "2025-06-15"
        assert data["transit_range"]["end"] == "2025-06-20"

    def test_list_upcoming_transits_scans_multiple_days(self, reference_a):
        """Test that scanning multiple days returns transits for each day."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17"
        )

        data = json.loads(result)

        # Should have transits starting on at least some of the 3 days
        dates = set(t["start"] for t in data["transits"])

        # Should contain at least some dates from the range
        assert len(dates) > 0

    def test_list_upcoming_transits_with_aspect_filter(self, reference_a):
        """Test list_upcoming_transits with aspect type filter."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
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

    def test_list_upcoming_transits_with_max_orb(self, reference_a):
        """Test list_upcoming_transits with maximum orb filter."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17",
            max_orb=2.0
        )

        data = json.loads(result)

        # All transits should have orb <= 2.0
        for transit in data["transits"]:
            assert transit["orb"] <= 2.0, f"Expected orb <= 2.0, got {transit['orb']}"

    def test_list_upcoming_transits_total_count(self, reference_a):
        """Test that total_transits count matches actual transits."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17"
        )

        data = json.loads(result)

        assert len(data["transits"]) == data["total_transits"]

    def test_list_upcoming_transits_sorted_by_date(self, reference_a):
        """Test that transits are sorted by date."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-20"
        )

        data = json.loads(result)

        starts = [t["start"] for t in data["transits"]]

        # Check that dates are sorted
        assert starts == sorted(starts), "Transits should be sorted by date"

    def test_list_upcoming_transits_transit_structure(self, reference_a):
        """Test that each transit span has the expected structure."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date="2025-06-17"
        )

        data = json.loads(result)

        for transit in data["transits"]:
            assert "start" in transit
            assert "end" in transit
            assert transit["start"] <= transit["end"]
            assert "from_object" in transit
            assert "to_object" in transit
            assert "type" in transit
            assert "orb" in transit

    def test_list_upcoming_transits_default_date_range(self, reference_a):
        """Test that the default range is today to +60 days."""
        from datetime import date, timedelta
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"]
        )

        data = json.loads(result)

        today = date.today()
        assert data["transit_range"]["start"] == today.isoformat()
        assert data["transit_range"]["end"] == (today + timedelta(days=60)).isoformat()

    def test_natal_span_known_aspect(self, reference_a):
        """reference_a's natal Moon (26deg15 Virgo) is exactly sextile
        transiting Mars on 2026-09-21 (12:48 local, verified against the
        user's independent ephemeris). The midnight-sampled span must cover
        2026-09-21 with a sub-degree tightest orb."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2026-09-18",
            end_date="2026-09-27"
        )

        data = json.loads(result)

        spans = [
            t for t in data["transits"]
            if t["from_object"] == "Mars" and t["to_object"] == "Moon"
            and t["type"] == "Sextile"
        ]
        assert len(spans) == 1, f"expected one Mars-Moon sextile span, got {spans}"
        assert spans[0]["start"] in ("2026-09-19", "2026-09-20")
        assert spans[0]["start"] <= "2026-09-21" <= spans[0]["end"]
        assert spans[0]["orb"] < 0.5


class TestListUpcomingTransitsValidation:
    """Test validation for list_upcoming_transits."""

    def test_invalid_birth_date(self, reference_a):
        """Test that invalid birth date returns error."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time="invalid-date",
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"]
        )

        data = json.loads(result)

        assert "error" in data

    def test_invalid_start_date(self, reference_a):
        """Test that invalid start date returns error."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="invalid-date"
        )

        data = json.loads(result)

        assert "error" in data

    def test_invalid_end_date(self, reference_a):
        """Test that invalid end date returns error."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            end_date="invalid-date"
        )

        data = json.loads(result)

        assert "error" in data

    def test_invalid_latitude(self, reference_a):
        """Test that invalid latitude returns error."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude="100",
            longitude=reference_a["longitude"]
        )

        data = json.loads(result)

        assert "error" in data

    def test_invalid_longitude(self, reference_a):
        """Test that invalid longitude returns error."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude="200"
        )

        data = json.loads(result)

        assert "error" in data

    def test_partial_birth_data_date_only(self, reference_a):
        """Birth data must be all-or-nothing: date_time alone is rejected."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(date_time=reference_a["date_time"])

        data = json.loads(result)
        assert "error" in data

    def test_partial_birth_data_missing_longitude(self, reference_a):
        """Birth data must be all-or-nothing: missing longitude is rejected."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"]
        )

        data = json.loads(result)
        assert "error" in data


class TestListUpcomingTransitsGeneralMode:
    """Test list_upcoming_transits without birth data (transits as-is)."""

    PLANETS = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter",
               "Saturn", "Uranus", "Neptune", "Pluto", "Chiron"}
    MAJOR_TYPES = {"Conjunction", "Opposition", "Square", "Trine", "Sextile"}

    def test_general_mode_basic(self):
        """No birth data: major aspects among the transiting planets."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            start_date="2025-06-15",
            end_date="2025-06-17"
        )

        data = json.loads(result)

        assert data["mode"] == "general"
        assert "natal" not in data
        assert "note" in data
        assert data["total_transits"] == len(data["transits"])

    def test_general_mode_entries(self):
        """Entries must be major aspects among the 11 transiting planets."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            start_date="2025-06-15",
            end_date="2025-07-15"
        )

        data = json.loads(result)

        assert data["transits"], "expected transiting-planet aspects in a 30-day range"
        for transit in data["transits"]:
            assert transit["from_object"] in self.PLANETS
            assert transit["to_object"] in self.PLANETS
            assert transit["type"] in self.MAJOR_TYPES
            assert transit["orb"] <= 1.5

    def test_general_mode_max_orb(self):
        """max_orb applies in general mode too."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            start_date="2025-06-15",
            end_date="2025-07-15",
            max_orb=0.5
        )

        data = json.loads(result)

        for transit in data["transits"]:
            assert transit["orb"] <= 0.5, f"Expected orb <= 0.5, got {transit['orb']}"

    def test_general_mode_default_date_range(self):
        """Default range (today to +60 days) works without birth data."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits()

        data = json.loads(result)

        assert data["mode"] == "general"
        assert "transit_range" in data
        assert "total_transits" in data

    def test_general_mode_consecutive_days_form_one_span(self):
        """A slow aspect in orb across the whole window is listed once, as a
        span covering the window - not one entry per sampled day."""
        from astro_mcp.tools.transit import list_upcoming_transits

        result = list_upcoming_transits(
            start_date="2026-09-20",
            end_date="2026-09-30"
        )

        data = json.loads(result)

        spans = [
            t for t in data["transits"]
            if t["from_object"] == "Neptune" and t["to_object"] == "Pluto"
            and t["type"] == "Sextile"
        ]
        assert len(spans) == 1, f"expected one Neptune-Pluto sextile span, got {spans}"
        span = spans[0]
        assert span["start"] == "2026-09-20"
        assert span["end"] == "2026-09-30"
        assert span["orb"] <= 0.11


class TestListUpcomingTransitsForecast:
    """Yearly-forecast support: the response must stay within the MCP
    client truncation budget (~25KB). This pins the compact single-line
    serialization, the object_filter param, and the self-adaptive trim of
    high-frequency Moon/Mercury spans for oversized results."""

    def _scan(self, reference_a, end="2025-06-21", **kwargs):
        from astro_mcp.tools.transit import list_upcoming_transits

        return list_upcoming_transits(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            start_date="2025-06-15",
            end_date=end,
            **kwargs
        )

    def test_output_is_single_line_compact(self, reference_a):
        result = self._scan(reference_a)
        assert "\n" not in result
        assert json.loads(result)["mode"] == "natal"

    def test_no_omission_within_budget(self, reference_a):
        """A 7-day scan fits the budget, so nothing may be auto-trimmed
        and spans stay in the readable object form."""
        data = json.loads(self._scan(reference_a))
        assert "omitted" not in data
        assert "span_fields" not in data
        assert all(isinstance(t, dict) for t in data["transits"])
        assert data["total_transits"] == len(data["transits"])

    def test_object_filter_keeps_only_listed_objects(self, reference_a):
        """Names are matched case-insensitively; the echo is normalized."""
        data = json.loads(self._scan(reference_a, object_filter="moon,mercury"))
        assert data["object_filter"] == ["Mercury", "Moon"]
        from_objects = {t["from_object"] for t in data["transits"]}
        assert from_objects <= {"Moon", "Mercury"}

    def test_object_filter_rejects_unknown_object(self, reference_a):
        data = json.loads(self._scan(reference_a, object_filter="Moon,PaleMoon"))
        assert "error" in data
        assert "PaleMoon" in data["detail"]
        assert "Chiron" in data["detail"]  # recognized objects are listed

    def test_auto_trim_when_over_budget(self, reference_a, monkeypatch):
        """When the full list exceeds the budget, Moon/Mercury spans are
        dropped, the response reports exactly what was omitted, and the
        spans fall back to the compact positional-array encoding."""
        import astro_mcp.tools.transit as transit_module

        monkeypatch.setattr(transit_module, "_MAX_RESPONSE_CHARS", 500)
        data = json.loads(self._scan(reference_a))

        assert "omitted" in data
        assert data["omitted"]["objects"] == ["Mercury", "Moon"]
        assert data["omitted"]["spans"]["Moon"] >= 1
        assert "object_filter" in data["omitted"]["hint"]
        assert data["span_fields"] == ["start", "end", "from_object", "to_object", "type", "orb"]
        assert all(isinstance(t, list) and len(t) == 6 for t in data["transits"])
        from_objects = {t[2] for t in data["transits"]}
        assert from_objects.isdisjoint({"Moon", "Mercury"})
        assert data["total_transits"] == len(data["transits"])

    def test_explicit_filter_disables_auto_trim(self, reference_a, monkeypatch):
        """An explicit object_filter (even for fast objects) is never
        auto-trimmed - explicit beats implicit - but the compact encoding
        still applies when the result is oversized."""
        import astro_mcp.tools.transit as transit_module

        monkeypatch.setattr(transit_module, "_MAX_RESPONSE_CHARS", 500)
        data = json.loads(self._scan(reference_a, object_filter="Moon"))
        assert "omitted" not in data
        assert "span_fields" in data
        from_objects = {t[2] for t in data["transits"]}
        assert from_objects <= {"Moon"}


# ---------------------------------------------------------------------------
# Regression tests: exact transits must not be missed
#
# The transit tool previously (a) dropped aspects tighter than min_orb — so
# exact (orb 0) transits were systematically filtered out, (b) computed
# transit-to-natal aspects from integer-degree positions, and (c) ignored
# transit_date_time (immanuel's Transits constructor hardcodes now()).
# ---------------------------------------------------------------------------

class TestExactTransitRegression:
    """Guard against exact/tight transits being silently dropped."""

    def test_exact_aspect_survives_default_orb_filter(self):
        """An exact (orb 0) aspect must pass the default max_orb=1.5 filter."""
        from astro_mcp.utils import filter_aspects

        aspects = [
            {"from_object": "Mars", "to_object": "Moon", "type": "Sextile", "orb": 0.0},
            {"from_object": "Venus", "to_object": "Sun", "type": "Conjunction", "orb": 0.3},
            {"from_object": "Saturn", "to_object": "Mars", "type": "Square", "orb": 3.0},
        ]
        filtered = filter_aspects(aspects, max_orb=1.5)
        kept_pairs = {(a["from_object"], a["to_object"]) for a in filtered}
        assert ("Mars", "Moon") in kept_pairs, "exact transit was filtered out"
        assert ("Venus", "Sun") in kept_pairs
        assert ("Saturn", "Mars") not in kept_pairs

    def test_orb_uses_subdegree_precision(self):
        """Orbs must be computed from full-precision longitudes, not integer
        degrees. With whole-degree quantization the fake position pair below
        would report a false exact (orb 0) sextile; the true orb is 0.6."""
        from astro_mcp.utils import calculate_transit_to_natal_aspects

        class _FakeAngle:
            def __init__(self, raw):
                self.raw = raw
                self.degrees = int(raw)

        class _FakeObject:
            def __init__(self, name, lon):
                self.name = name
                self.longitude = _FakeAngle(lon)

        class _FakeChart:
            def __init__(self, objects):
                self.objects = {3000000 + i: o for i, o in enumerate(objects)}

        transit_chart = _FakeChart([_FakeObject("Mars", 116.3)])
        aspects = calculate_transit_to_natal_aspects(transit_chart, {"Moon": 176.9})
        mars_moon = [a for a in aspects if a["from_object"] == "Mars" and a["to_object"] == "Moon"]
        assert mars_moon, "Mars-Moon aspect not detected"
        assert mars_moon[0]["type"] == "Sextile"
        assert abs(mars_moon[0]["orb"] - 0.6) < 1e-6, f"orb quantized: {mars_moon[0]['orb']}"

    def test_transit_date_time_is_honored(self, reference_a):
        """create_transit_chart must build the chart at the requested moment,
        not 'now'. A transit chart at the birth moment itself must show every
        planet exactly conjunct its natal counterpart."""
        from astro_mcp.tools.transit import create_transit_chart

        result = create_transit_chart(
            date_time=reference_a["date_time"],
            latitude=reference_a["latitude"],
            longitude=reference_a["longitude"],
            transit_date_time=reference_a["date_time"],
        )
        data = json.loads(result)

        # The chart's subject must be the requested moment
        assert data["date_time"].startswith(reference_a["date_time"])

        # At the birth moment every transiting planet sits on its natal position
        conjunctions = [a for a in data["aspects"] if a["type"] == "Conjunction"]
        assert len(conjunctions) >= 10, f"expected 11 exact conjunctions, got {len(conjunctions)}"
        for aspect in conjunctions:
            assert aspect["orb"] < 0.01, f"aspect at birth moment not exact: {aspect}"

    def test_transits_for_date_uses_requested_date(self, reference_a):
        """The dated-transit helper must actually move the planets between
        days (with the old code both days repeated the same 'now' chart)."""
        from immanuel import charts
        from astro_mcp.config import get_config
        from astro_mcp.tools.transit import _transits_for_date

        config = get_config(None)
        native = charts.Subject(
            date_time=reference_a["date_time"],
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        natal = charts.Natal(native, config=config)

        t1 = _transits_for_date("2025-06-15 00:00", reference_a["latitude"], reference_a["longitude"], natal, config)
        t2 = _transits_for_date("2025-06-16 00:00", reference_a["latitude"], reference_a["longitude"], natal, config)

        assert t1._native.date_time.isoformat().startswith("2025-06-15T00:00")
        assert t2._native.date_time.isoformat().startswith("2025-06-16T00:00")

        def position(chart, name):
            return next(o for o in chart.objects.values() if o.name == name).longitude.raw

        # Moon moves ~13 deg/day, Sun ~1 deg/day
        assert abs(position(t1, "Moon") - position(t2, "Moon")) > 10.0
        assert abs(position(t1, "Sun") - position(t2, "Sun")) > 0.5

    def test_whole_sign_houses_numbered_from_ascendant(self, reference_a):
        """Whole-sign houses must number the Ascendant's sign as house 1.
        reference_a has a Sagittarius Ascendant, so a transit object in
        Sagittarius is in house 1 (the old code put it in house 10)."""
        from immanuel import charts
        from astro_mcp.config import get_config
        from astro_mcp.tools.transit import _transits_for_date
        from astro_mcp.utils import assign_natal_houses_to_transit_objects

        config = get_config("whole_sign")
        native = charts.Subject(
            date_time=reference_a["date_time"],
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        natal = charts.Natal(native, config=config)

        asc = next(o for o in natal.objects.values() if o.name == "Asc")
        asc_sign_index = int(asc.longitude.raw // 30)
        assert asc_sign_index == 8  # Sagittarius — makes this test meaningful

        # Property check against a real dated transit chart: every object's
        # house must follow the Ascendant-relative formula.
        transit = _transits_for_date("2025-06-15 14:30", reference_a["latitude"], reference_a["longitude"], natal, config)
        houses = assign_natal_houses_to_transit_objects(transit, natal, "whole_sign")

        for obj in transit.objects.values():
            sign_index = int(obj.longitude.raw // 30)
            expected = (sign_index - asc_sign_index) % 12 + 1
            assert houses[obj.name] == expected, (
                f"{obj.name} in sign {sign_index}: expected house {expected}, got {houses[obj.name]}"
            )

        # Deterministic check with known positions: with a Sagittarius
        # Ascendant, Sagittarius is house 1, Capricorn house 2, Aries house 5.
        class _StubAngle:
            def __init__(self, raw):
                self.raw = raw

        class _StubObject:
            def __init__(self, name, lon):
                self.name = name
                self.longitude = _StubAngle(lon)
                self.sign = None

        class _StubChart:
            def __init__(self, objects):
                self.objects = {3000000 + i: o for i, o in enumerate(objects)}

        stub = _StubChart([
            _StubObject("Mars", 240.0),   # Sagittarius
            _StubObject("Venus", 270.0),  # Capricorn
            _StubObject("Sun", 0.0),      # Aries
        ])
        stub_houses = assign_natal_houses_to_transit_objects(stub, natal, "whole_sign")
        assert stub_houses["Mars"] == 1, f"Ascendant sign should be house 1, got {stub_houses['Mars']}"
        assert stub_houses["Venus"] == 2
        assert stub_houses["Sun"] == 5


class TestNumericCoordinateSchema:
    """LLMs send coordinates as JSON numbers. The tool input schemas
    (generated from the function type hints) must accept numbers as well as
    strings, or the whole call is rejected with a parse error before the
    tool body ever runs ('params.latitude is not any of [subschema 0]...')."""

    @staticmethod
    def _registered_tool(name):
        from mcp.server.mcpserver import MCPServer
        from astro_mcp.tools import transit

        mcp = MCPServer(name="test")
        transit.register(mcp)
        return mcp._tool_manager._tools[name]

    def test_list_upcoming_transits_accepts_numeric_coordinates(self):
        tool = self._registered_tool("list_upcoming_transits")
        args = tool.fn_metadata.validate_arguments({
            "date_time": "1984-05-10 20:44",
            "latitude": 34.0211,
            "longitude": -118.3968,
            "start_date": "2025-06-15",
            "end_date": "2025-06-15",
        })
        assert args["latitude"] == 34.0211
        assert args["longitude"] == -118.3968

    def test_create_transit_chart_accepts_numeric_coordinates(self):
        tool = self._registered_tool("create_transit_chart")
        args = tool.fn_metadata.validate_arguments({
            "date_time": "1984-05-10 20:44",
            "latitude": 34.0211,
            "longitude": -118.3968,
            "transit_date_time": "2025-06-15 14:30",
        })
        assert args["latitude"] == 34.0211
        assert args["longitude"] == -118.3968

    def test_list_upcoming_transits_numeric_end_to_end(self):
        """Numeric coordinates must survive the tool body's str()
        normalization and come back intact in the result."""
        from astro_mcp.tools.transit import list_upcoming_transits

        data = json.loads(list_upcoming_transits(
            date_time="1984-05-10 20:44",
            latitude=34.0211,
            longitude=-118.3968,
            start_date="2025-06-15",
            end_date="2025-06-15",
        ))
        assert data["mode"] == "natal"
        assert data["natal"]["latitude"] == 34.0211
        assert data["natal"]["longitude"] == -118.3968


class TestNatalTimezoneParams:
    """timezone_offset is accepted by create_natal_chart and must actually
    reach the ephemeris (previously ignored)."""

    @staticmethod
    def _moon_longitude(**kwargs):
        from astro_mcp.tools.natal import create_natal_chart

        data = json.loads(create_natal_chart(
            date_time="1984-05-10 20:44",
            latitude="34.02",
            longitude="-118.40",
            **kwargs,
        ))
        return data["objects"]["Moon"]["longitude"]

    def test_explicit_pdt_offset_matches_geolocated(self):
        # May 1984 in Los Angeles is PDT (UTC-7); an explicit -7.0 offset must
        # reproduce the geolocated chart.
        assert abs(self._moon_longitude(timezone_offset=-7.0) - self._moon_longitude()) < 1e-6

    def test_wrong_offset_shifts_the_moon(self):
        # A deliberately wrong UTC offset shifts the Moon by several degrees.
        delta = abs(self._moon_longitude(timezone_offset=2.0) - self._moon_longitude())
        assert delta > 1.0, f"timezone_offset appears to be ignored (Moon shifted only {delta} deg)"
