"""Basic tests for astro-mcp functionality."""

import pytest


def test_imports():
    """Test that all modules can be imported."""
    from astro_mcp import config
    from astro_mcp import utils
    from astro_mcp import schemas
    from astro_mcp.server import mcp
    
    assert config is not None
    assert utils is not None
    assert schemas is not None
    assert mcp is not None


def test_server_has_tools():
    """Test that the server has tools registered."""
    from astro_mcp.server import mcp
    
    assert hasattr(mcp, "name")
    assert mcp.name == "astro-mcp"


def test_config_module():
    """Test config module functions."""
    from astro_mcp.config import get_config, HOUSE_SYSTEM_MAP
    
    assert "whole_sign" in HOUSE_SYSTEM_MAP
    assert "placidus" in HOUSE_SYSTEM_MAP


def test_utils_module():
    """Test utils module functions."""
    from astro_mcp.utils import (
        error_response,
        validate_date_string,
        validate_latitude,
        validate_longitude,
    )
    
    # Test error_response
    err = error_response("Test error", "Detail")
    assert '"error":' in err
    
    # Test date validation
    valid, msg = validate_date_string("1990-06-15 14:30")
    assert valid is True

    valid, msg = validate_date_string("invalid-date")
    assert valid is False


def test_validate_date_string_formats():
    """The validator must accept every shape get_current_datetime() can
    return (datetime.isoformat(): 'T' separator, seconds, microseconds) as
    well as the classic minute-precision formats."""
    from astro_mcp.utils import validate_date_string

    # Classic formats (space or T, minutes or seconds)
    for valid_date in [
        "1990-06-15 14:30",
        "1990-06-15T14:30",
        "1990-06-15 14:30:05",
        "1990-06-15T14:30:05",
        # get_current_datetime() shape: isoformat() with microseconds
        "2026-09-23T15:04:05.123456",
        "2026-09-23 15:04:05.123456",
        # Fractional without seconds, short and long fractions
        "1990-06-15 14:30.5",
        "1990-06-15T14:30:05.123",
        "1990-06-15T14:30:05.123456789",
    ]:
        assert validate_date_string(valid_date) == (True, ""), valid_date

    # Still rejected: garbage, impossible dates, out-of-range years
    for invalid_date in [
        "invalid-date",
        "1990-13-15 14:30",   # month 13
        "1990-06-31 14:30",   # June 31
        "1990-06-15 25:30",   # hour 25
        "1990-06-15 14:30:",  # trailing colon
        " 1990-06-15 14:30",  # leading space
        "1000-06-15 14:30",   # before ephemeris range
        "5000-06-15 14:30",   # after ephemeris range
    ]:
        valid, msg = validate_date_string(invalid_date)
        assert valid is False, invalid_date
        assert msg, invalid_date

    # Natural-language dates are rejected (strict ISO contract), and the
    # error must echo the rejected value and state the expected format so
    # the calling LLM can convert and retry.
    valid, msg = validate_date_string("May 10, 1984 8:44 PM")
    assert valid is False
    assert "May 10, 1984 8:44 PM" in msg
    assert "YYYY-MM-DD HH:MM" in msg


def test_date_params_publish_format_in_schema():
    """LLMs only see the published input schema, so every date parameter
    must carry its format contract as a parameter description."""
    from mcp.server.mcpserver import MCPServer
    from astro_mcp.tools import natal, solar_return, progressed, transit, synastry

    mcp = MCPServer(name="test")
    for mod in (natal, solar_return, progressed, transit, synastry):
        mod.register(mcp)

    date_params = {
        "create_natal_chart": ["date_time"],
        "create_transit_chart": ["date_time", "transit_date_time"],
        "list_upcoming_transits": ["start_date", "end_date", "date_time"],
        "create_solar_return": ["date_time"],
        "create_progressed_chart": ["date_time", "target_date"],
        "create_synastry": ["date_time_a", "date_time_b"],
    }
    for tool_name, params in date_params.items():
        schema = mcp._tool_manager._tools[tool_name].fn_metadata.arg_model.model_json_schema()
        for param in params:
            desc = schema["properties"][param].get("description", "")
            assert desc, f"{tool_name}.{param} has no schema description"
            assert "YYYY-MM-DD" in desc, f"{tool_name}.{param} description lacks the date format: {desc!r}"


def test_schemas():
    """Test schema models."""
    from astro_mcp.schemas import (
        NatalChartParams,
        SolarReturnParams,
        ProgressedParams,
        TransitParams,
        SynastryParams,
    )
    
    # Test NatalChartParams
    params = NatalChartParams(
        date_time="1990-06-15 14:30",
        latitude="40.74",
        longitude="-73.99"
    )
    
    assert params.date_time == "1990-06-15 14:30"


def test_tools_registered():
    """Test that all tool modules have register functions."""
    from astro_mcp.tools import natal, solar_return, progressed, transit, synastry
    
    assert hasattr(natal, "register")
    assert hasattr(solar_return, "register")
    assert hasattr(progressed, "register")
    assert hasattr(transit, "register")
    assert hasattr(synastry, "register")
