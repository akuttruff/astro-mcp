"""Integration tests for natal chart generation."""

import pytest


@pytest.fixture
def reference_nyc():
    """Reference A: NYC, mid-year, diurnal, Northern Hemisphere."""
    return {
        "date_time": "1990-06-15 14:30",
        "latitude": "40.74",
        "longitude": "-73.99",
    }


@pytest.mark.asyncio
async def test_natal_chart_generation(reference_nyc):
    """Test generating a natal chart with immanuel directly."""
    from immanuel import charts
    
    native = charts.Subject(
        date_time=reference_nyc["date_time"].replace("T", " "),
        latitude=float(reference_nyc["latitude"]),
        longitude=float(reference_nyc["longitude"]),
    )
    
    config = charts.Config()
    config.house_system = charts.chart.WHOLE_SIGN
    
    natal = charts.Natal(native, config=config)
    
    # Verify chart was created
    assert natal is not None
    assert hasattr(natal, "objects")
    
    # Check for key objects (objects is a dict)
    object_values = list(natal.objects.values())
    assert len(object_values) > 0
    
    # Check for Sun
    sun_found = False
    for obj in object_values:
        if hasattr(obj, 'name') and obj.name == "Sun":
            sun_found = True
            break
    
    assert sun_found, "Sun not found in chart"


@pytest.mark.asyncio
async def test_natal_chart_whole_sign(reference_nyc):
    """Test that Whole Sign houses are used correctly."""
    from immanuel import charts
    
    native = charts.Subject(
        date_time=reference_nyc["date_time"].replace("T", " "),
        latitude=float(reference_nyc["latitude"]),
        longitude=float(reference_nyc["longitude"]),
    )
    
    config = charts.Config()
    config.house_system = charts.chart.WHOLE_SIGN
    
    natal = charts.Natal(native, config=config)
    
    # In Whole Sign houses, each house starts at 0° of a sign
    for house in natal.houses.values():
        # Check that the house longitude is at 0° (or very close)
        # house.longitude has a degrees property
        if hasattr(house, 'longitude'):
            longitude_value = house.longitude.degrees
            assert abs(longitude_value % 30) < 0.01, f"House not at sign start"


@pytest.mark.asyncio
async def test_natal_chart_chiron(reference_nyc):
    """Test that Chiron is included in the chart."""
    from immanuel import charts
    
    native = charts.Subject(
        date_time=reference_nyc["date_time"].replace("T", " "),
        latitude=float(reference_nyc["latitude"]),
        longitude=float(reference_nyc["longitude"]),
    )
    
    config = charts.Config()
    config.house_system = charts.chart.WHOLE_SIGN
    
    natal = charts.Natal(native, config=config)
    
    # Check for Chiron
    object_values = list(natal.objects.values())
    chiron_found = False
    for obj in object_values:
        if hasattr(obj, 'name') and "Chiron" in obj.name:
            chiron_found = True
            break
    
    assert chiron_found, "Chiron not found in chart"


@pytest.mark.asyncio
async def test_natal_chart_aspects(reference_nyc):
    """Test that aspects are calculated."""
    from immanuel import charts
    
    native = charts.Subject(
        date_time=reference_nyc["date_time"].replace("T", " "),
        latitude=float(reference_nyc["latitude"]),
        longitude=float(reference_nyc["longitude"]),
    )
    
    config = charts.Config()
    config.house_system = charts.chart.WHOLE_SIGN
    
    natal = charts.Natal(native, config=config)
    
    # Check for aspects
    assert hasattr(natal, "aspects")
    assert len(natal.aspects) > 0, "No aspects calculated"


@pytest.mark.asyncio
async def test_natal_chart_moon_phase(reference_nyc):
    """Test that moon phase is calculated."""
    from immanuel import charts
    
    native = charts.Subject(
        date_time=reference_nyc["date_time"].replace("T", " "),
        latitude=float(reference_nyc["latitude"]),
        longitude=float(reference_nyc["longitude"]),
    )
    
    config = charts.Config()
    config.house_system = charts.chart.WHOLE_SIGN
    
    natal = charts.Natal(native, config=config)
    
    # Check for moon phase
    assert hasattr(natal, "moon_phase")
    assert natal.moon_phase is not None


@pytest.mark.asyncio
async def test_natal_chart_serialization(reference_nyc):
    """Test that the chart can be serialized to JSON."""
    from immanuel import charts
    import json
    
    native = charts.Subject(
        date_time=reference_nyc["date_time"].replace("T", " "),
        latitude=float(reference_nyc["latitude"]),
        longitude=float(reference_nyc["longitude"]),
    )
    
    config = charts.Config()
    config.house_system = charts.chart.WHOLE_SIGN
    
    natal = charts.Natal(native, config=config)
    
    # Serialize to JSON
    json_str = json.dumps(natal, cls=charts.ToJSON)
    
    # Parse it back
    data = json.loads(json_str)
    
    assert "type" in data
    assert data["type"] == "Natal"
    assert "objects" in data
