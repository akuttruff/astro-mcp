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
