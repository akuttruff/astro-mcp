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


_MISSING_LOCALES: set[str] = set()


def cache_missing_locales() -> None:
    """immanuel caches a locale it finds but not one it does not, and 'en_US'
    (the source language) has no catalog, so every localized string re-walked
    the locales directory through gettext: forty million stat calls in a
    24-year transit scan, two thirds of its running time. Remember the
    misses too. Idempotent; wraps the function the module's localize() calls
    by name, so the cache applies to every chart."""
    from immanuel.support import localize as localize_module

    original = localize_module.load_locale
    if getattr(original, "_astro_mcp_cached", False):
        return

    def load_locale(lcid: str) -> bool:
        if lcid in _MISSING_LOCALES:
            return False
        found = original(lcid)
        if not found:
            _MISSING_LOCALES.add(lcid)
        return found

    load_locale._astro_mcp_cached = True  # type: ignore[attr-defined]
    localize_module.load_locale = load_locale


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

    cache_missing_locales()
    config = charts.Config()
    config.house_system = chart.WHOLE_SIGN
    config.locale = ServerConfig().locale
    for obj in ServerConfig().extra_objects():
        config.objects.append(obj)
    return config
