"""Server configuration for astro-mcp."""

from dataclasses import dataclass, field


@dataclass
class ServerConfig:
    """Server-wide configuration defaults."""
    locale: str = "en_US"
    aspect_orb_default: float = 8.0  # degrees; immanuel's default

    def extra_objects(self) -> list[int]:
        from immanuel.const import chart
        return [chart.CHIRON]


def get_config():
    """A fresh immanuel Config for each chart call.

    Houses are always whole sign. Other systems were offered once, but the
    transit tools place transiting planets by the natal chart's cusps, and
    only the whole-sign placement was ever right -- so the choice was
    removed rather than left half-working. (Horary keeps its own traditional
    settings; see tools/horary.py.)
    """
    try:
        from immanuel import charts
        from immanuel.const import chart
    except ImportError as e:
        raise RuntimeError(f"immanuel library not installed: {e}")

    config = charts.Config()
    config.house_system = chart.WHOLE_SIGN
    config.locale = ServerConfig().locale
    for obj in ServerConfig().extra_objects():
        config.objects.append(obj)
    return config
