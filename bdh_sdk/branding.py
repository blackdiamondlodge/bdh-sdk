"""The hub's brand: its name, subtitle and monogram.

The hub sets ``settings.HUB_BRAND`` from its site's ``site.toml``. Any key a
site leaves out falls back to the Black Diamond Hub defaults shipped here, so
apps get a monogram even outside the hub (in tests, say).

This module does not import Django at import time.
"""
from functools import lru_cache
from pathlib import Path

__all__ = ["DEFAULT_NAME", "brand", "monogram_svg"]

DEFAULT_NAME = "Black Diamond Hub"
_HERE = Path(__file__).parent
_DEFAULTS = {
    "monogram": _HERE / "bdh-monogram.svg",  # dark diamond, for light backgrounds (QR codes)
    "monogram_light": _HERE / "bdh-monogram-light.svg",  # light diamond, for the dark navbar
}


def _conf():
    try:
        from django.conf import settings
    except ImportError:
        return {}
    if not settings.configured:
        return {}
    return getattr(settings, "HUB_BRAND", None) or {}


def brand():
    """The site's brand: ``name``, ``subtitle`` and the ``monogram`` and
    ``monogram_light`` SVG file paths."""
    conf = _conf()
    return {
        "name": conf.get("name") or DEFAULT_NAME,
        "subtitle": conf.get("subtitle") or "",
        **{key: Path(conf.get(key) or default) for key, default in _DEFAULTS.items()},
    }


def monogram_svg(light=False):
    """The site's monogram as SVG text, 100x100 viewBox. ``light`` picks the
    version for dark backgrounds."""
    return _read(str(brand()["monogram_light" if light else "monogram"]))


@lru_cache(maxsize=8)
def _read(path):
    return Path(path).read_text(encoding="utf-8")
