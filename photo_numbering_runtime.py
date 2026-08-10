"""Fix photo suffix numbering beyond z without rewriting report layout code."""

from __future__ import annotations

import builtins

import inspection_bot as bot


def _alpha_suffix(index: int) -> str:
    """0 -> a, 25 -> z, 26 -> aa, 27 -> ab, ..."""
    if index < 0:
        return ""
    value = index + 1
    chars: list[str] = []
    while value:
        value, remainder = divmod(value - 1, 26)
        chars.append(builtins.chr(ord("a") + remainder))
    return "".join(reversed(chars))


def _report_chr(codepoint: int) -> str:
    """Preserve normal chr(), except the photo-letter sequence starting at a."""
    offset = codepoint - ord("a")
    if offset >= 0:
        return _alpha_suffix(offset)
    return builtins.chr(codepoint)


def install_photo_numbering() -> None:
    # inspection_bot.insert_photo_groups resolves chr from its module globals.
    # Providing this module-level implementation upgrades the existing
    # a..z logic to a..z, aa..az, ba.. without touching document layout.
    bot.chr = _report_chr
