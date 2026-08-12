


"""i18n service — Accept-Language based locale detection with gettext .mo fallback."""

from __future__ import annotations

import gettext
import os
from pathlib import Path

from core.logging import get_logger

logger = get_logger("i18n")

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
SUPPORTED_LOCALES = {"en": "en_US", "pt": "pt_BR", "pt-BR": "pt_BR", "en-US": "en_US"}

_translations: dict[str, gettext.NullTranslations] = {}


def _load_translations() -> None:
    """Preload .mo files for all supported locales."""
    for locale_tag, locale_dir in SUPPORTED_LOCALES.items():
        try:
            path = LOCALES_DIR / locale_dir / "LC_MESSAGES" / "messages.mo"
            if path.exists():
                with open(path, "rb") as f:
                    t = gettext.GNUTranslations(f)
                    _translations[locale_tag] = t
            else:
                _translations[locale_tag] = gettext.NullTranslations()
        except Exception:
            _translations[locale_tag] = gettext.NullTranslations()


def get_locale(lang_header: str | None) -> str:
    """Parse Accept-Language header and return the best locale."""
    if not lang_header:
        return "en"
    # Simplistic: take the first language with highest quality
    for segment in lang_header.replace(" ", "").split(","):
        lang_tag = segment.split(";")[0]
        simple = lang_tag.split("-")[0].lower()
        if lang_tag in SUPPORTED_LOCALES:
            return lang_tag
        if simple in SUPPORTED_LOCALES:
            return simple
    return "en"


def translate(key: str, locale: str = "en", **kwargs) -> str:
    """Translate a key to the given locale, with optional interpolation."""
    t = _translations.get(locale, _translations.get("en"))
    if t is None:
        return key
    msg = t.gettext(key)
    if kwargs:
        try:
            msg = msg % kwargs
        except Exception:
            pass
    return msg


# Lazy-load at import time via app startup
def init_i18n() -> None:
    _load_translations()
    logger.info("i18n_loaded", locales=list(_translations.keys()))


