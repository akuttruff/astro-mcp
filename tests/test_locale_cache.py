"""immanuel's locale lookup must not hit the filesystem again for a locale it already failed to find."""
import gettext

from astro_mcp.config import cache_missing_locales


def test_missing_locale_is_looked_up_once(monkeypatch):
    from immanuel.support import localize as localize_module

    cache_missing_locales()
    calls = []
    real = gettext.translation

    def counting(*args, **kwargs):
        calls.append(kwargs.get("languages"))
        return real(*args, **kwargs)

    monkeypatch.setattr(gettext, "translation", counting)
    for _ in range(5):
        assert localize_module.localize("Sun", "xx_NOWHERE") == "Sun"
    assert len(calls) == 1


def test_wrapping_is_idempotent():
    from immanuel.support import localize as localize_module

    cache_missing_locales()
    first = localize_module.load_locale
    cache_missing_locales()
    assert localize_module.load_locale is first
