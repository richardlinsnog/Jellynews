
"""HTML sanitization and text extraction — centralized for all endpoints."""

from __future__ import annotations

import re

import nh3

_ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "strong", "em", "b", "i", "u", "s", "sub", "sup",
    "a", "img",
    "ul", "ol", "li",
    "blockquote", "pre", "code",
    "table", "thead", "tbody", "tr", "th", "td",
    "div", "span",
}

_ALLOWED_ATTRS = {
    "a": {"href", "title", "rel", "target"},
    "img": {"src", "alt", "width", "height"},
    "*": {"class", "style"},
}


def sanitize_html(html: str) -> str:
    """Sanitize HTML, keeping only safe tags and attributes for newsletter content.

    ``link_rel=None`` disables nh3's automatic ``rel="nofollow noreferrer"``
    injection, allowing our allowlist to control the ``rel`` attribute directly.
    """
    return nh3.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, link_rel=None)


def html_to_text(html: str) -> str:
    """Extract plain text from HTML for non-HTML channels (e.g. Telegram, plain-text email)."""
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"</p>", "\n\n", text)
    text = re.sub(r"</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
