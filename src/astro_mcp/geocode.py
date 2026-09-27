"""Geocoding utilities for converting city/state/country to coordinates."""

from functools import lru_cache
from typing import Optional, Tuple

# Try to import geopy, but don't fail if it's not available
try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False


class LocationNotFoundError(Exception):
    """Raised when a location cannot be found."""
    pass


def geocode_location(
    city: str,
    state: Optional[str] = None,
    country: Optional[str] = None
) -> Tuple[float, float]:
    """Coordinates only. See resolve_location for what was matched."""
    latitude, longitude, _ = resolve_location(city, state, country)
    return latitude, longitude


# Birth places repeat constantly -- the same person's chart, over and over --
# and Nominatim asks for at most one request a second. Caching makes the
# common case free and keeps us inside their usage policy.
@lru_cache(maxsize=256)
def resolve_location(
    city: str,
    state: Optional[str] = None,
    country: Optional[str] = None
) -> Tuple[float, float, str]:
    """
    Convert city/state/country to latitude and longitude.
    
    Args:
        city: City name (required)
        state: State/province code or name (optional, e.g., 'NY' or 'New York')
        country: Country code or name (optional, defaults to US if not specified)
    
    Returns:
        Tuple of (latitude, longitude)
    
    Raises:
        LocationNotFoundError: If the location cannot be resolved
        RuntimeError: If geopy is not installed
    
    Examples:
        >>> geocode_location("New York", "NY", "USA")
        (40.7128, -74.006)
        
        >>> geocode_location("Sydney", "NSW", "Australia")
        (-33.8688, 151.2093)
    """
    if not GEOPY_AVAILABLE:
        raise RuntimeError(
            "Geocoding requires the 'geopy' package. "
            "Install it with: pip install geopy"
        )
    
    # Build location string
    parts = [city.strip()]
    if state:
        parts.append(state.strip())
    if country:
        parts.append(country.strip())
    
    location_str = ", ".join(parts)
    
    # Initialize geocoder with a unique user agent
    geolocator = Nominatim(user_agent="astro-mcp-geo-1.0")
    
    try:
        # Try to geocode the location
        location = geolocator.geocode(
            location_str,
            exactly_one=True,
            timeout=10
        )
        
        if location is None:
            raise LocationNotFoundError(
                f"Could not find coordinates for: {location_str}"
            )
        
        return (location.latitude, location.longitude, str(location.address))
    
    except GeocoderTimedOut:
        raise LocationNotFoundError(
            "Geocoding service timed out. Please try again."
        )
    except GeocoderServiceError as e:
        raise LocationNotFoundError(
            f"Geocoding service error: {e}"
        )


def validate_coordinates(latitude: float, longitude: float) -> Tuple[bool, str]:
    """
    Validate that coordinates are within valid ranges.
    
    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not -90 <= latitude <= 90:
        return False, f"Latitude must be between -90 and 90. Got: {latitude}"
    
    if not -180 <= longitude <= 180:
        return False, f"Longitude must be between -180 and 180. Got: {longitude}"
    
    return True, ""
