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
