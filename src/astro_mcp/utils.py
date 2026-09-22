"""Utility functions for astro-mcp."""

import json
import logging
import math
import sys
from datetime import datetime
from typing import Any, Optional, Tuple

try:
    from immanuel import charts
except ImportError:
    # Fallback for development before immanuel is installed
    charts = None

logger = logging.getLogger("astro-mcp")
# CRITICAL: All log output goes to stderr, never stdout.
handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


def get_current_datetime() -> dict:
    """Get current date and time for LLM context awareness.
    
    Returns:
        Dict with current datetime information including ISO format, 
        local time, and date components
    """
    now = datetime.now()
    return {
        "current_datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "hour": now.hour,
        "minute": now.minute,
        "second": now.second,
        "weekday": now.strftime("%A")
    }


def add_datetime_context(error_msg: str) -> str:
    """Add current datetime context to error messages.
    
    Args:
        error_msg: The error message to enhance
        
    Returns:
        Error message with current datetime appended
    """
    dt = get_current_datetime()
    return f"{error_msg}\n\nCurrent datetime: {dt['current_datetime']} ({dt['weekday']})"


def chart_to_json(chart: Any) -> str:
    """Serialize a full immanuel chart to JSON string."""
    return json.dumps(chart, cls=charts.ToJSON, indent=2) if hasattr(charts, "ToJSON") else str(chart)


def object_to_json(obj: Any) -> str:
    """Serialize a single chart object to JSON string."""
    return json.dumps(obj, cls=charts.ToJSON, indent=2) if hasattr(charts, "ToJSON") else str(obj)


def error_response(message: str, detail: str = "") -> str:
    """Return a structured error as JSON (MCP tool result)."""
    err = {"error": message}
    if detail:
        err["detail"] = detail
    return json.dumps(err, indent=2)


# (JSON key, display name) for the eight moon phases, in elongation order.
# Names match immanuel's MOON_PHASES so output stays familiar.
MOON_PHASES = [
    ("new_moon", "New"),
    ("waxing_crescent", "Waxing Crescent"),
    ("first_quarter", "First Quarter"),
    ("waxing_gibbous", "Waxing Gibbous"),
    ("full_moon", "Full"),
    ("disseminating", "Disseminating"),
    ("third_quarter", "Third Quarter"),
    ("balsamic", "Balsamic"),
]


def classify_moon_phase(sun_longitude: float, moon_longitude: float) -> dict:
    """Classify the moon phase from Sun and Moon ecliptic longitudes.

    immanuel's moon_phase_from() uses the principal elongations themselves
    (0°, 45°, 90°, ...) as bin edges, so any Moon between 90° and 135° from
    the Sun is labeled 'First Quarter' — but a Moon at 119° is ~74%
    illuminated, i.e. a waxing gibbous Moon. This reclassifies with the
    standard equal-width bins centered on each principal phase (edges at
    22.5° + 45°·k), keeping immanuel's phase names and boolean output
    shape, and adds the elongation and illumination fraction.
    """
    elongation = (moon_longitude - sun_longitude) % 360
    index = int((elongation + 22.5) // 45) % 8
    phase = {key: False for key, _ in MOON_PHASES}
    phase[MOON_PHASES[index][0]] = True
    phase["formatted"] = MOON_PHASES[index][1]
    phase["elongation"] = round(elongation, 2)
    phase["illumination"] = round((1 - math.cos(math.radians(elongation))) / 2, 3)
    return phase


def corrected_moon_phase(chart: Any) -> dict | None:
    """Recompute a chart's moon_phase with corrected phase boundaries.

    Args:
        chart: An immanuel chart object with Sun and Moon in .objects

    Returns:
        Corrected moon_phase dict, or None if the chart has no Sun and
        Moon to measure.
    """
    longitudes = {}
    for obj in getattr(chart, "objects", {}).values():
        if obj.name in ("Sun", "Moon"):
            longitudes[obj.name] = obj.longitude.raw
    if "Sun" not in longitudes or "Moon" not in longitudes:
        return None
    return classify_moon_phase(longitudes["Sun"], longitudes["Moon"])


def validate_date_string(date_str: str) -> tuple[bool, str]:
    """Validate date string format and range.

    Returns:
        Tuple of (is_valid, error_message if invalid)
    """
    import re
    from datetime import datetime

    # Try ISO 8601 formats
    patterns = [
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$",  # YYYY-MM-DD HH:MM
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$",  # YYYY-MM-DDTHH:MM
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",  # YYYY-MM-DD HH:MM:SS
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$",  # YYYY-MM-DDTHH:MM:SS
    ]

    for pattern in patterns:
        if re.match(pattern, date_str):
            try:
                # Parse and validate range
                dt = datetime.strptime(date_str.replace("T", " "), "%Y-%m-%d %H:%M")
                if dt.year < 1200 or dt.year > 4799:
                    return False, f"Date out of range. Supported range: 1200-01-01 to 4799-12-31"
                return True, ""
            except ValueError as e:
                return False, f"Invalid date: {e}"

    return False, "Invalid date format. Expected 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'"


def validate_latitude(latitude_str: str) -> tuple[bool, str]:
    """Validate latitude string.

    Returns:
        Tuple of (is_valid, error_message if invalid)
    """
    import re

    # Try decimal degrees
    try:
        lat = float(latitude_str)
        if -90 <= lat <= 90:
            return True, ""
        return False, f"Latitude must be between -90 and 90. Got: {latitude_str}"
    except ValueError:
        pass

    # Try DMS format (e.g., 34n03, 34N03, 34°N)
    dms_pattern = r"^([+-]?\d+(?:\.\d+)?)\s*([nNsS])$"
    match = re.match(dms_pattern, latitude_str.strip())
    if match:
        degrees = float(match.group(1))
        direction = match.group(2).upper()
        if direction in ("S", "N"):
            lat = degrees if direction == "N" else -degrees
            if -90 <= lat <= 90:
                return True, ""

    return False, f"Invalid latitude format. Use decimal degrees (e.g., '34.05') or DMS (e.g., '34n03')."


def validate_longitude(longitude_str: str) -> tuple[bool, str]:
    """Validate longitude string.

    Returns:
        Tuple of (is_valid, error_message if invalid)
    """
    import re

    # Try decimal degrees
    try:
        lon = float(longitude_str)
        if -180 <= lon <= 180:
            return True, ""
        return False, f"Longitude must be between -180 and 180. Got: {longitude_str}"
    except ValueError:
        pass

    # Try DMS format (e.g., 118w15, 118W15, 118°W)
    dms_pattern = r"^([+-]?\d+(?:\.\d+)?)\s*([eEwW])$"
    match = re.match(dms_pattern, longitude_str.strip())
    if match:
        degrees = float(match.group(1))
        direction = match.group(2).upper()
        if direction in ("W", "E"):
            lon = degrees if direction == "E" else -degrees
            if -180 <= lon <= 180:
                return True, ""

    return False, f"Invalid longitude format. Use decimal degrees (e.g., '-118.24') or DMS (e.g., '118w15')."


def validate_house_system(house_system: str | None) -> tuple[bool, str]:
    """Validate house system string.

    Returns:
        Tuple of (is_valid, error_message if invalid)
    """
    from astro_mcp.config import HOUSE_SYSTEM_MAP

    if house_system is None:
        return True, ""

    if house_system not in HOUSE_SYSTEM_MAP:
        valid = ", ".join(sorted(HOUSE_SYSTEM_MAP.keys()))
        return False, f"Unknown house system: {house_system}. Valid options: {valid}"

    return True, ""


def geocode_location(
    city: str,
    state: Optional[str] = None,
    country: Optional[str] = None
) -> Tuple[float, float]:
    """
    Convert city/state/country to latitude and longitude.

    Args:
        city: City name (required)
        state: State/province code or name (optional, e.g., 'NY' or 'New York')
        country: Country code or name (optional, defaults to US if not specified)

    Returns:
        Tuple of (latitude, longitude)

    Raises:
        RuntimeError: If geopy is not installed
    """
    try:
        from astro_mcp.geocode import geocode_location as geo_func
        return geo_func(city, state, country)
    except ImportError:
        raise RuntimeError(
            "Geocoding requires the 'geopy' package. "
            "Install it with: pip install geopy"
        )


def get_coordinates(
    latitude: Optional[str],
    longitude: Optional[str],
    city: Optional[str],
    state: Optional[str] = None,
    country: Optional[str] = None
) -> Tuple[float, float]:
    """
    Get coordinates from either provided values or geocoding.

    Args:
        latitude: Latitude string (if None, will use geocoding)
        longitude: Longitude string (if None, will use geocoding)
        city: City name for geocoding
        state: State/province (optional)
        country: Country (optional)

    Returns:
        Tuple of (latitude, longitude) as floats
    """
    if latitude is not None and longitude is not None:
        # Use provided coordinates
        lat_val = float(latitude)
        lon_val = float(longitude)
    elif city is not None:
        # Geocode the location
        lat_val, lon_val = geocode_location(city, state, country)
    else:
        raise ValueError("Must provide either coordinates or city/state/country")

    return lat_val, lon_val


def extract_aspect_details(chart: Any) -> list[dict]:
    """Extract aspect details from an immanuel chart.

    This function uses immanuel's internal Aspect objects to extract
    meaningful aspect information (type, orb, distance, etc.) without
    making any calculations itself.

    Args:
        chart: An immanuel chart object (Natal, SolarReturn, etc.)

    Returns:
        List of aspect dictionaries with full details
    """
    import immanuel.charts

    if not hasattr(chart, 'aspects'):
        return []

    # Build object index to name mapping
    obj_map = {}
    for obj in chart.objects.values():
        obj_map[obj.index] = obj.name

    aspects_list = []
    seen_pairs = set()  # Track unique aspect pairs to avoid duplicates

    # In a natal (same-chart) aspect list each pair appears twice, as
    # A->B and B->A. In a synastry/aspects_to chart (e.g. Transits against a
    # Natal) every entry is a unique cross-chart pair: (transit X, natal Y)
    # and (transit Y, natal X) are different aspects and must both be kept —
    # but they share the same object indices/names, so name-based dedup would
    # wrongly drop one of them.
    is_synastry = getattr(chart, '_aspects_to', None) is not None

    # Iterate through aspect relationships
    for obj_id, relationships in chart.aspects.items():
        if isinstance(relationships, dict):
            for rel_obj_id, aspect in relationships.items():
                # Get object names
                from_name = obj_map.get(getattr(aspect, 'active', None), str(obj_id))
                to_name = obj_map.get(getattr(aspect, 'passive', None), str(rel_obj_id))

                # Create a unique pair key. Same-chart aspects collapse the
                # A->B / B->A duplicates; synastry aspects do not.
                if is_synastry:
                    pair_key = (obj_id, rel_obj_id)
                else:
                    pair_key = (min(obj_id, rel_obj_id), max(obj_id, rel_obj_id))

                # Skip if we've already seen this pair
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Get aspect details
                condition_val = getattr(aspect, 'condition', None)
                movement_val = getattr(aspect, 'movement', None)

                # Convert condition and movement to strings if they're objects
                condition_str = str(condition_val) if condition_val else None
                movement_str = str(movement_val) if movement_val else None

                # immanuel's Aspect.orb is the configured (maximum) orb for the
                # pair; the actual deviation from the exact angle is
                # Aspect.difference (signed). Report the magnitude of that.
                difference_val = getattr(aspect, 'difference', None)
                actual_orb = abs(difference_val.raw) if difference_val is not None else None

                aspect_info = {
                    "from_object": from_name,
                    "to_object": to_name,
                    "type": str(getattr(aspect, 'type', None)),
                    "orb": actual_orb,
                    "distance": str(getattr(aspect, 'distance', '')),
                    "condition": condition_str,
                    "movement": movement_str
                }

                # Clean up any None values
                aspect_info = {k: v for k, v in aspect_info.items() if v is not None}

                aspects_list.append(aspect_info)

    return aspects_list


def calculate_transit_to_natal_aspects(transit_chart: Any, natal_positions: dict) -> list[dict]:
    """Calculate transit-to-natal aspects for a transit chart.
    
    Args:
        transit_chart: An immanuel Transit chart object
        natal_positions: Dict of {object_name: longitude_degrees} from natal chart
        
    Returns:
        List of aspect dictionaries with transit-to-natal aspects
    """
    import immanuel.charts
    
    # Get transiting planet positions (Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron)
    # NOTE: use longitude.raw (full-precision float). The .degrees attribute is only
    # the integer degree part of the DMS value and would quantize every orb to 1°.
    transit_positions = {}
    for obj in transit_chart.objects.values():
        if obj.name in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron']:
            transit_positions[obj.name] = obj.longitude.raw % 360
    
    # Define aspect orbs
    aspects = {
        'Conjunction': 10,
        'Opposition': 10,
        'Square': 10,
        'Trine': 8,
        'Sextile': 6
    }
    
    found_aspects = []

    for transiting, t_pos in transit_positions.items():
        for natal_name, n_pos in natal_positions.items():
            # Calculate diff
            diff = abs(t_pos - n_pos)
            if diff > 180:
                diff = 360 - diff

            # Check for aspects
            for aspect_name, orb in aspects.items():
                expected = {'Opposition': 180, 'Square': 90, 'Trine': 120, 'Sextile': 60}.get(aspect_name, 0)
                distance = abs(diff - expected)

                if distance <= orb:
                    # Each (transiting, natal) combination is visited exactly
                    # once, so no deduplication is needed. Deduping by object
                    # names would wrongly drop transiting X to natal Y whenever
                    # transiting Y to natal X also aspects (same name pair).
                    found_aspects.append({
                        "from_object": transiting,
                        "to_object": natal_name,
                        "type": aspect_name,
                        "orb": distance
                    })
    
    # Sort by orb (tightest first)
    found_aspects.sort(key=lambda x: x['orb'])
    
    return found_aspects


def filter_aspects(aspects: list[dict],
                   aspect_type: str | None = None,
                   max_orb: float | None = None,
                   object_filter: list[str] | None = None) -> list[dict]:
    """Filter aspects based on criteria.

    Args:
        aspects: List of aspect dictionaries to filter
        aspect_type: Filter by specific aspect type (e.g., "Conjunction", "Square")
        max_orb: Maximum orb threshold (aspects with orb <= this value are kept,
            so tighter/exact aspects are always included)
        object_filter: List of transiting object names to include

    Returns:
        Filtered list of aspects
    """
    if not aspects:
        return []

    filtered = []

    for aspect in aspects:
        # Filter by aspect type
        if aspect_type:
            if isinstance(aspect_type, str):
                if aspect.get("type", "") != aspect_type:
                    continue
            elif isinstance(aspect_type, list):
                if aspect.get("type", "") not in aspect_type:
                    continue

        # Filter by maximum orb (keep aspects tighter than or equal to the threshold)
        if max_orb is not None:
            aspect_orb = aspect.get("orb")
            if aspect_orb is None or aspect_orb > max_orb:
                continue
        
        # Filter by transiting objects
        if object_filter:
            from_obj = aspect.get("from_object", "")
            to_obj = aspect.get("to_object", "")
            
            # For transit charts, from_object is the transiting planet
            if from_obj not in object_filter:
                continue
        
        filtered.append(aspect)

    return filtered


def assign_natal_houses_to_transit_objects(transit_chart: Any, natal_chart: Any, house_system: str) -> dict:
    """Assign transit objects to houses based on natal chart's house cusps.
    
    For transit charts, we want to know which houses the transiting planets fall into
    relative to the natal chart's house system, not the transit chart's houses.
    
    Args:
        transit_chart: An immanuel Transit chart object
        natal_chart: The natal chart (source of house cusps)
        house_system: The house system being used
        
    Returns:
        Dict mapping object names to their natal house numbers
    """
    # Get natal house cusps (longitude of each house cusp)
    natal_house_longitudes = {}
    for house in natal_chart.houses.values():
        natal_house_longitudes[house.number] = house.longitude.degrees
    
    # For Whole Sign houses, the sign of the Ascendant is house 1. Determine
    # which sign each transit object is in and number the houses relative to
    # the Ascendant's sign.
    if house_system == 'whole_sign':
        asc = next((o for o in natal_chart.objects.values() if o.name == 'Asc'), None)
        if asc is None:
            return {}
        asc_sign_index = int((asc.longitude.raw % 360) // 30)  # 0 = Aries, 11 = Pisces

        assigned_houses = {}
        for obj in transit_chart.objects.values():
            if hasattr(obj, 'longitude') and hasattr(obj, 'sign'):
                longitude = obj.longitude.raw % 360
                sign_index = int(longitude // 30)  # Each sign is 30 degrees
                assigned_houses[obj.name] = (sign_index - asc_sign_index) % 12 + 1

        return assigned_houses
    
    # For other house systems, use the transit chart's house assignments
    # (This is a limitation - proper house cusp calculation would be needed)
    assigned_houses = {}
    for obj in transit_chart.objects.values():
        if hasattr(obj, 'house') and obj.house:
            assigned_houses[obj.name] = obj.house.number
    
    return assigned_houses
