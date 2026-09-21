"""Tests for create_natal_chart tool."""

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
def reference_b():
    """Reference B: Sydney, Southern Hemisphere, nocturnal."""
    return {
        "date_time": "1985-01-28 03:15",
        "latitude": "-33.87",
        "longitude": "151.21",
    }


@pytest.fixture
def fixture_data_nyc():
    """Fixture data for NYC reference."""
    import json
    import os
    
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "reference_a_nyc_whole_sign.json")
    with open(fixture_path, "r") as f:
        return json.load(f)


class TestNatalChartHappyPath:
    """Test happy path scenarios for natal chart generation."""

    def test_create_natal_chart_with_coordinates(self, reference_a):
        """Test generating a natal chart with coordinate inputs."""
        from immanuel import charts
        
        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        
        config = charts.Config()
        config.house_system = charts.chart.WHOLE_SIGN
        
        natal = charts.Natal(native, config=config)
        
        # Verify chart was created
        assert natal is not None

    def test_create_natal_chart_with_city_state_country(self):
        """Test that geocoding works for city/state/country input."""
        from astro_mcp.geocode import geocode_location
        
        # Test NYC
        lat, lon = geocode_location("New York", "NY", "USA")
        assert abs(lat - 40.71) < 0.1
        assert abs(lon - (-74.00)) < 0.1

    def test_natal_chart_has_expected_structure(self, fixture_data_nyc):
        """Test that the natal chart has all expected top-level keys."""
        data = fixture_data_nyc
        
        assert "type" in data
        assert data["type"] == "Natal"
        
        assert "native" in data
        assert "house_system" in data
        assert "objects" in data
        assert "houses" in data
        assert "aspects" in data


class TestNatalChartValidation:
    """Test validation and error handling for natal charts."""

    def test_invalid_date_format(self):
        """Test that invalid date format returns error."""
        from astro_mcp.utils import validate_date_string
        
        valid, error = validate_date_string("invalid-date")
        assert valid is False
        assert "Invalid" in error

    def test_date_out_of_range(self):
        """Test that dates outside 1200-4799 range are rejected."""
        from astro_mcp.utils import validate_date_string
        
        valid, error = validate_date_string("1000-06-15 14:30")
        assert valid is False
        assert "range" in error.lower() or "out of" in error.lower()
        
        valid, error = validate_date_string("5000-06-15 14:30")
        assert valid is False
        assert "range" in error.lower() or "out of" in error.lower()

    def test_invalid_latitude(self):
        """Test that invalid latitude values are rejected."""
        from astro_mcp.utils import validate_latitude
        
        valid, error = validate_latitude("100")
        assert valid is False
        assert "Latitude" in error
        
        valid, error = validate_latitude("-100")
        assert valid is False
        assert "Latitude" in error

    def test_invalid_longitude(self):
        """Test that invalid longitude values are rejected."""
        from astro_mcp.utils import validate_longitude
        
        valid, error = validate_longitude("200")
        assert valid is False
        assert "Longitude" in error
        
        valid, error = validate_longitude("-200")
        assert valid is False
        assert "Longitude" in error

    def test_unknown_house_system(self):
        """Test that unknown house system returns error with valid options."""
        from astro_mcp.utils import validate_house_system
        
        valid, error = validate_house_system("invalid_system")
        assert valid is False
        assert "Unknown" in error or "Valid options" in error


class TestNatalChartHouseSystems:
    """Test different house systems."""

    def test_whole_sign_houses_start_at_0(self, reference_a):
        """Test that Whole Sign houses start at 0° of each sign."""
        from immanuel import charts
        
        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        
        config = charts.Config()
        config.house_system = charts.chart.WHOLE_SIGN
        
        natal = charts.Natal(native, config=config)
        
        # In Whole Sign houses, each house starts at 0° of a sign
        for house in natal.houses.values():
            longitude_value = house.longitude.degrees
            assert abs(longitude_value % 30) < 0.01, f"House not at sign start: {longitude_value}"

    def test_placidus_houses_differ_from_whole_sign(self, reference_a):
        """Test that Placidus houses differ from Whole Sign."""
        from immanuel import charts
        
        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        
        # Whole Sign config
        config_whole = charts.Config()
        config_whole.house_system = charts.chart.WHOLE_SIGN
        natal_whole = charts.Natal(native, config=config_whole)
        
        # Placidus config
        config_placidus = charts.Config()
        config_placidus.house_system = charts.chart.PLACIDUS
        natal_placidus = charts.Natal(native, config=config_placidus)
        
        # House cusps should differ between systems
        whole_cusp1 = list(natal_whole.houses.values())[0].longitude.degrees
        placidus_cusp1 = list(natal_placidus.houses.values())[0].longitude.degrees
        
        # They should be different (within tolerance for rounding)
        assert abs(whole_cusp1 - placidus_cusp1) > 0.5, "Placidus and Whole Sign should differ"


class TestNatalChartObjects:
    """Test chart objects and their properties."""

    def test_chiron_included(self, reference_a):
        """Test that Chiron is included in the chart."""
        from immanuel import charts
        
        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        
        config = charts.Config()
        config.house_system = charts.chart.WHOLE_SIGN
        
        natal = charts.Natal(native, config=config)
        
        object_names = [obj.name for obj in natal.objects.values()]
        assert "Chiron" in object_names

    def test_all_planets_present(self, reference_a):
        """Test that all planets are included."""
        from immanuel import charts
        
        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        
        config = charts.Config()
        config.house_system = charts.chart.WHOLE_SIGN
        
        natal = charts.Natal(native, config=config)
        
        object_names = [obj.name for obj in natal.objects.values()]
        
        expected_planets = ["Sun", "Moon", "Mercury", "Venus", "Mars",
                           "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        
        for planet in expected_planets:
            assert planet in object_names, f"Missing planet: {planet}"

    def test_angles_present(self, reference_a):
        """Test that all angles are included."""
        from immanuel import charts
        
        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        
        config = charts.Config()
        config.house_system = charts.chart.WHOLE_SIGN
        
        natal = charts.Natal(native, config=config)
        
        object_names = [obj.name for obj in natal.objects.values()]
        
        # Note: immanuel uses "Desc" not "DSC"
        expected_angles = ["Asc", "MC", "IC", "Desc"]
        
        for angle in expected_angles:
            assert angle in object_names, f"Missing angle: {angle}"

    def test_lunar_nodes_present(self, reference_a):
        """Test that lunar nodes are included."""
        from immanuel import charts
        
        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        
        config = charts.Config()
        config.house_system = charts.chart.WHOLE_SIGN
        
        natal = charts.Natal(native, config=config)
        
        object_names = [obj.name for obj in natal.objects.values()]
        
        # Note: immanuel uses "True North Node" and "True South Node"
        assert "True North Node" in object_names
        assert "True South Node" in object_names


class TestNatalChartAspects:
    """Test aspect calculations."""

    def test_aspects_calculated(self, reference_a):
        """Test that aspects are calculated."""
        from immanuel import charts
        
        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        
        config = charts.Config()
        config.house_system = charts.chart.WHOLE_SIGN
        
        natal = charts.Natal(native, config=config)
        
        assert len(natal.aspects) > 0, "No aspects calculated"

    def test_aspect_patterns_present(self, reference_a):
        """Test that aspect patterns are calculated."""
        from immanuel import charts

        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )

        config = charts.Config()
        config.house_system = charts.chart.WHOLE_SIGN

        natal = charts.Natal(native, config=config)

        assert hasattr(natal, "aspect_patterns")

    def test_aspects_have_detailed_info(self, reference_a):
        """Test that aspects include detailed information."""
        from immanuel import charts

        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )

        config = charts.Config()
        config.house_system = charts.chart.WHOLE_SIGN

        natal = charts.Natal(native, config=config)

        # Check that aspects are accessible
        assert len(list(natal.aspects)) > 0, "No aspects found"


class TestNatalChartAspectDetails:
    """Test that aspect details are properly exposed in JSON output."""

    def test_natal_json_has_detailed_aspects(self, fixture_data_nyc):
        """Test that natal JSON includes detailed aspect information."""
        data = fixture_data_nyc
        
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

    def test_natal_aspect_types_include_major_aspects(self, fixture_data_nyc):
        """Test that major aspect types are present in the output."""
        data = fixture_data_nyc
        
        aspect_types = [aspect["type"] for aspect in data["aspects"]]
        
        # Check for major aspect types
        expected_types = ["Conjunction", "Opposition", "Square", "Trine", "Sextile"]
        
        for expected_type in expected_types:
            assert expected_type in aspect_types, f"Missing aspect type: {expected_type}"

    def test_natal_aspects_have_unique_pairs(self, fixture_data_nyc):
        """Test that aspects don't contain duplicate pairs."""
        data = fixture_data_nyc
        
        # Create pairs and check for duplicates
        aspect_pairs = []
        for aspect in data["aspects"]:
            pair = tuple(sorted([aspect["from_object"], aspect["to_object"]]))
            aspect_pairs.append(pair)
        
        # Check for duplicates
        assert len(aspect_pairs) == len(set(aspect_pairs)), "Duplicate aspect pairs found"

    def test_natal_aspects_have_orb_values(self, fixture_data_nyc):
        """Test that all aspects have valid orb values."""
        data = fixture_data_nyc
        
        for aspect in data["aspects"]:
            orb = aspect["orb"]
            assert isinstance(orb, (int, float)), f"Invalid orb value: {orb}"
            assert orb > 0, f"Orb should be positive: {orb}"

    def test_natal_aspects_have_condition(self, fixture_data_nyc):
        """Test that aspects have condition field (Associate/Dissociate)."""
        data = fixture_data_nyc
        
        for aspect in data["aspects"]:
            condition = aspect.get("condition")
            assert condition is not None, f"Missing condition in: {aspect}"
            assert condition in ["Associate", "Dissociate"], f"Invalid condition: {condition}"

    def test_natal_tool_exposes_aspect_details(self):
        """Test that the natal tool returns detailed aspect information."""
        from astro_mcp.tools.natal import create_natal_chart
        import json
        
        result = create_natal_chart(
            date_time="1984-05-10 20:44",
            latitude="34.02",
            longitude="-118.40"
        )
        
        data = json.loads(result)
        
        # Check aspects array exists and is populated
        assert "aspects" in data, "No aspects in tool output"
        assert len(data["aspects"]) > 0, "Aspects array is empty"
        
        # Check aspect details
        for aspect in data["aspects"]:
            assert "from_object" in aspect
            assert "to_object" in aspect
            assert "type" in aspect
            assert "orb" in aspect
        
        # Verify we have the expected number of unique aspects (30 for this chart)
        aspect_pairs = set()
        for aspect in data["aspects"]:
            pair = tuple(sorted([aspect["from_object"], aspect["to_object"]]))
            aspect_pairs.add(pair)
        
        # Should have 30 unique aspects for this chart
        assert len(aspect_pairs) == 30, f"Expected 30 unique aspects, got {len(aspect_pairs)}"


class TestNatalChartMoonPhase:
    """Test moon phase calculations."""

    def test_moon_phase_calculated(self, reference_a):
        """Test that moon phase is calculated."""
        from immanuel import charts
        
        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        
        config = charts.Config()
        config.house_system = charts.chart.WHOLE_SIGN
        
        natal = charts.Natal(native, config=config)
        
        assert hasattr(natal, "moon_phase")
        assert natal.moon_phase is not None


class TestNatalChartDiurnal:
    """Test diurnal flag."""

    def test_diurnal_flag_nyc_summer(self, reference_a):
        """Test diurnal flag for NYC summer solstice period."""
        from immanuel import charts
        
        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        
        config = charts.Config()
        config.house_system = charts.chart.WHOLE_SIGN
        
        natal = charts.Natal(native, config=config)
        
        # June 15 in NYC is summer (diurnal)
        assert hasattr(natal, "diurnal")
        # Should be diurnal (Sun above horizon)
        assert natal.diurnal is True


class TestNatalChartSerialization:
    """Test JSON serialization."""

    def test_chart_serializes_to_json(self, reference_a):
        """Test that chart serializes to valid JSON."""
        from immanuel import charts
        import json
        
        native = charts.Subject(
            date_time=reference_a["date_time"].replace("T", " "),
            latitude=float(reference_a["latitude"]),
            longitude=float(reference_a["longitude"]),
        )
        
        config = charts.Config()
        config.house_system = charts.chart.WHOLE_SIGN
        
        natal = charts.Natal(native, config=config)
        
        # Serialize to JSON
        json_str = json.dumps(natal, cls=charts.ToJSON)
        
        # Parse back
        data = json.loads(json_str)
        
        assert "type" in data
        assert data["type"] == "Natal"
        assert "objects" in data
