# Dynamics.py
"""
Standard dynamic markings (pp, mf, ff, ...) and hairpins ("pp-mp",
"pp<mp", "ff>mp") expressed as MIDI velocity (1-127).

Used by Phonon so a dynamic can be written the way a score notates it,
instead of only as a raw number.

    Phonon(0, 1, 60, dynamic="mp")        # flat dynamic
    Phonon(0, 1, 60, dynamic="pp-mp")     # crescendo across the note
    Phonon(0, 1, 60, dynamic="mf>pp")     # diminuendo across the note

A hairpin's separator ('-', '<', '>', '~') is cosmetic — direction is
always read left-to-right, so "pp-mp" and "pp<mp" are identical.
"""

import re

# MIDI velocity (1-127) assigned to each standard dynamic marking.
# Loosely follows the mapping used by common notation software.
DYNAMIC_MARKINGS: dict[str, int] = {
    "pppp": 8,
    "ppp":  16,
    "pp":   33,
    "p":    49,
    "mp":   64,
    "mf":   80,
    "f":    96,
    "ff":   112,
    "fff":  120,
    "ffff": 127,
}

# Longest names first, so "ppp" isn't mis-split into "pp" + "p".
_MARKING_NAMES = sorted(DYNAMIC_MARKINGS, key=len, reverse=True)
_MARKING_ALT   = "|".join(_MARKING_NAMES)

_HAIRPIN_RE = re.compile(
    rf"^\s*({_MARKING_ALT})\s*[-<>~]\s*({_MARKING_ALT})\s*$",
    re.IGNORECASE,
)


def dynamicMarkingToVelocity(marking: str) -> float:
    """Convert a single standard dynamic marking ('pp', 'mf', ...) to MIDI velocity."""
    key = marking.strip().lower()
    if key not in DYNAMIC_MARKINGS:
        raise ValueError(
            f"Dynamics: unknown dynamic marking {marking!r}. "
            f"Known markings: {', '.join(DYNAMIC_MARKINGS)}"
        )
    return float(DYNAMIC_MARKINGS[key])


def parseDynamicMarking(text: str) -> float | tuple[float, float]:
    """
    Parse a dynamic marking or hairpin into MIDI velocity.

    A plain marking ('mf') returns a single float velocity.
    A hairpin ('pp-mp', 'pp<mp', 'ff>mp') returns a
    (startVelocity, endVelocity) tuple.
    """
    m = _HAIRPIN_RE.match(text)
    if m:
        start, end = m.groups()
        return (
            dynamicMarkingToVelocity(start),
            dynamicMarkingToVelocity(end),
        )
    return dynamicMarkingToVelocity(text)


def splitHairpin(text: str) -> tuple[str, str] | None:
    """
    Return (startMarking, endMarking) as lowercase text if *text* is a
    hairpin ('pp-mp', 'ff>mp', ...), or None if it's a plain marking.
    Used by MusicXmlExporter to label the two ends of a crescendo/
    diminuendo wedge with the actual marking text, not just its velocity.
    """
    m = _HAIRPIN_RE.match(text)
    if not m:
        return None
    start, end = m.groups()
    return start.strip().lower(), end.strip().lower()


def isDynamicMarkingText(text) -> bool:
    """True if *text* looks like a dynamic marking or hairpin GreasyPidgin understands."""
    if not isinstance(text, str):
        return False
    if _HAIRPIN_RE.match(text):
        return True
    return text.strip().lower() in DYNAMIC_MARKINGS
