"""The crown: a never-miss sentence becomes watchd conditions through the sentry's lockwork.

One sentence in, whole watches out:

    never miss in Denver                     -> air (US AQI over 150) + quakes (M4.5, 120 km)
    never miss air in Lisbon over 90         -> only the air row, your number honoured
    never miss quakes near Fresno within 50 mi, every 5 minutes
                                             -> one quakes row, 80.5 km, every 300 s
    never miss the river gauge at EADM7      -> one flood row (its published stage)

Rules, not vibes:

  - a sentence that names NO kind installs the full crown (air + quakes); "no air" or
    "no quakes" trims it;
  - a sentence that names a kind installs exactly that kind (flood requires an explicit
    gauge id — the crown never mints a river from a bare place);
  - quakes answer only to over/above floors ("under 3" is a noise machine, refused);
  - every number, schedule and radius is re-parsed by guards.py (the sentry's lockwork),
    so the file's field shapes are exactly what the watchd runtime in the sibling repo
    (mrfentmen/awesome-servers) obeys — same format the sentry writes, no private channel.
"""

from __future__ import annotations

import re

import guards

_NEgated = re.compile(r"\b(?:no|not|without)\s+(air|quakes?|flood|rivers?|gauge)\b", re.I)


def _unnegate(text: str) -> str:
    """Kinds mentioned only as exclusions ("no quakes") are trims, not named kinds."""
    return _NEgated.sub(" ", str(text or ""))


def crown_place(text: str) -> str | None:
    return guards.place_of(str(text or ""))


def _every_phrase(every_s: int) -> str:
    if every_s < 60:
        return f" every {every_s} seconds"
    return f" every {max(1, every_s // 60)} minutes"


def _quake_mag(text: str) -> tuple[float, str]:
    thr = guards.threshold_of(text)
    if thr is None:
        return 4.5, "above"
    number, direction = thr
    if direction != "above":
        raise ValueError("the crown yells when a floor is crossed - quakes take over/above "
                         "(e.g. ... over 4.5); under-ratings just make noise")
    return float(number), "above"


def _air_clause(place: str, thr: tuple[float, str] | None, every_s: int) -> str:
    number, direction = thr if thr else (150.0, "above")
    word = "over" if direction == "above" else "under"
    return f"watch air quality in {place} {word} {number:g}" + _every_phrase(every_s)


def _quake_clause(place: str, radius_km: float, mag_text: str, every_s: int) -> str:
    radius = float(radius_km if radius_km else 120.0)
    mag, direction = _quake_mag(mag_text)
    word = "over" if direction == "above" else "under"
    return (f"watch quakes within {radius:g} km of {place} {word} {mag:g}"
            + _every_phrase(every_s))


def crown_entries(text: str) -> list[dict]:
    """The rows that stand for this order. ValueError carries the exact missing words."""
    raw = str(text or "")
    every_s = guards.every_of(raw, default=300)
    kind = guards.kind_of(_unnegate(raw))
    if kind == "flood":  # a flood order locates the river by its gauge, not by a place
        gauge = guards.gauge_of(raw)
        if not gauge:
            raise ValueError("the flood watch needs an explicit gauge id - say it like: "
                             "never miss the river gauge at EADM7")
        return [guards.build_entry(f"watch the river gauge at {gauge}" + _every_phrase(every_s))]
    place = crown_place(raw)
    if not place:
        raise ValueError("never-miss needs a place: never miss in <place>")
    if kind == "air":
        return [guards.build_entry(_air_clause(place, guards.threshold_of(raw), every_s))]
    if kind == "quakes":
        return [guards.build_entry(
            _quake_clause(place, guards.radius_of(raw), raw, every_s))]
    low = raw.lower()
    entries: list[dict] = []
    if "no air" not in low:
        entries.append(guards.build_entry(_air_clause(place, guards.threshold_of(raw), every_s)))
    if "no quakes" not in low:
        entries.append(guards.build_entry(
            _quake_clause(place, guards.radius_of(raw), "", every_s)))
    if not entries:
        raise ValueError("a crown without air and without quakes misses nothing; name what "
                         "should stand, e.g. never miss the river gauge at EADM7")
    return entries


def install(existing: str, entries: list[dict], now: str) -> tuple[str, str]:
    """Merge every crown row into one conditions file; (json, changed) back."""
    merged = existing or "{}"
    changed = "added"
    for entry in entries:
        merged, changed = guards.merge_into(merged, entry, now)
    return merged, changed


def describe(doc: dict) -> str:
    """The whole crown, row by row, in the words a watchd operator recognises."""
    checks = doc.get("checks") or []
    if not checks:
        return "  (the crown is empty)"
    rows = []
    for row in checks:
        target = row.get("place") or row.get("gauge") or "?"
        if row.get("kind") == "air":
            rule = f"US AQI {row.get('threshold')} {row.get('when')}"
        elif row.get("kind") == "quakes":
            rule = (f"M{row.get('magnitude', 4)} {row.get('when')} within "
                    f"{row.get('radius_km', 120)} km")
        else:
            rule = "at or over its published flood stage"
        rows.append(f"  - {row.get('name')}: watch {row.get('kind')} at {target} ({rule}), "
                    f"polls every {int(row.get('every_s', 300)) // 60} min")
    return "\n".join(rows)
