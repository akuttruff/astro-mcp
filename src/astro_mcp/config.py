"""Server configuration for astro-mcp."""

from dataclasses import dataclass, field
from typing import Optional

try:
    from immanuel.const import chart
except ImportError:
    # Fallback for development before immanuel is installed
    WHOLE_SIGN = 0
    PLACIDUS = 1
    EQUAL = 2
    KOCH = 3
    CAMPANUS = 4
    REGIOMONTANUS = 5
    PORPHYRIUS = 6
    MORINUS = 7
    POLICH_PAGE = 8
    ALCABITUS = 9
    AZIMUTHAL = 10
    MERIDIAN = 11
    VEHLOW_EQUAL = 12
    
    HOUSE_SYSTEM_MAP = {
        "placidus": PLACIDUS,
        "whole_sign": WHOLE_SIGN,
        "equal": EQUAL,
        "koch": KOCH,
        "campanus": CAMPANUS,
        "regiomontanus": REGIOMONTANUS,
        "porphyrius": PORPHYRIUS,
        "morinus": MORINUS,
        "polich_page": POLICH_PAGE,
        "alcabitus": ALCABITUS,
        "azimuthal": AZIMUTHAL,
        "meridian": MERIDIAN,
        "vehlow_equal": VEHLOW_EQUAL,
    }
else:
    HOUSE_SYSTEM_MAP = {
        "placidus": chart.PLACIDUS,
        "whole_sign": chart.WHOLE_SIGN,
        "equal": chart.EQUAL,
        "koch": chart.KOCH,
        "campanus": chart.CAMPANUS,
        "regiomontanus": chart.REGIOMONTANUS,
        "porphyrius": chart.PORPHYRIUS,
        "morinus": chart.MORINUS,
        "polich_page": chart.POLICH_PAGE,
        "alcabitus": chart.ALCABITUS,
        "azimuthal": chart.AZIMUTHAL,
        "meridian": chart.MERIDIAN,
        "vehlow_equal": chart.VEHLOW_EQUAL,
    }
    
    HOUSE_SYSTEMS_INFO = {
        "placidus": "Time-based; divides ecliptic by diurnal/nocturnal semi-arcs. Most common in Western astrology.",
        "whole_sign": "Each house equals one complete zodiac sign. Oldest house system.",
        "equal": "Twelve equal 30° divisions starting from the Ascendant.",
        "koch": "Time-based system using the upper semicircle. Popular in German astrology.",
        "campanus": "Space-based; divides the prime vertical. Used in medieval astrology.",
        "regiomontanus": "Space-based; divides the celestial equator.",
        "porphyrius": "Ancient trisection of the horizon. Also called Porphyry.",
        "morinus": "Uses the equator rather than the ecliptic for house divisions.",
        "polich_page": "Also known as Topocentric.",
        "alcabitus": "Semi-arc system from Arabic astrology.",
        "azimuthal": "Based on azimuth divisions of the local horizon.",
        "meridian": "Based on meridian divisions.",
        "vehlow_equal": "Equal house with a 15° shift.",
    }


@dataclass
class ServerConfig:
    """Server-wide configuration defaults."""
    house_system: str = "whole_sign"  # Default: Whole Sign
    locale: str = "en_US"
    aspect_orb_default: float = 8.0  # degrees; immanuel's default
    extra_objects: list[int] = field(default_factory=lambda: [chart.CHIRON] if 'chart' in dir() else [])


def get_config(house_system_override: Optional[str] = None) -> "charts.Config":
    """Build a fresh immanuel Config for each chart call."""
    try:
        from immanuel import charts
    except ImportError as e:
        raise RuntimeError(f"immanuel library not installed: {e}")
    
    config = charts.Config()
    house_sys = house_system_override or ServerConfig().house_system
    config.house_system = HOUSE_SYSTEM_MAP.get(house_sys, chart.WHOLE_SIGN)
    config.locale = ServerConfig().locale
    for obj in ServerConfig().extra_objects:
        config.objects.append(obj)
    return config


def get_house_system_constant(house_system: str) -> int:
    """Convert house system string to immanuel constant."""
    if house_system not in HOUSE_SYSTEM_MAP:
        raise ValueError(f"Unknown house system: {house_system}. Valid options: {list(HOUSE_SYSTEM_MAP.keys())}")
    return HOUSE_SYSTEM_MAP[house_system]
