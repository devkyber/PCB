"""Orthogonal, grid-preserving local schematic wiring."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise


class StubCrossingError(RuntimeError):
    """Raised before two different nets are drawn through the same point."""


@dataclass(frozen=True)
class PinRef:
    ref: str
    pin: str


@dataclass(frozen=True)
class WireCorridor:
    left: float
    top: float
    right: float
    bottom: float

    def contains(self, point: tuple[float, float]) -> bool:
        return self.left <= point[0] <= self.right and self.top <= point[1] <= self.bottom


@dataclass(frozen=True)
class WireSegment:
    start: tuple[float, float]
    end: tuple[float, float]
    net: str


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _touches(first: WireSegment, second: WireSegment) -> bool:
    a, b, c, d = first.start, first.end, second.start, second.end
    return (
        min(a[0], b[0]) <= max(c[0], d[0])
        and min(c[0], d[0]) <= max(a[0], b[0])
        and min(a[1], b[1]) <= max(c[1], d[1])
        and min(c[1], d[1]) <= max(a[1], b[1])
        and _orientation(a, b, c) == 0
        and _orientation(a, b, d) == 0
    ) or (
        min(a[0], b[0]) <= max(c[0], d[0])
        and min(c[0], d[0]) <= max(a[0], b[0])
        and min(a[1], b[1]) <= max(c[1], d[1])
        and min(c[1], d[1]) <= max(a[1], b[1])
        and _orientation(a, b, c) * _orientation(a, b, d) <= 0
        and _orientation(c, d, a) * _orientation(c, d, b) <= 0
    )


def connect_local(
    editor,
    source: PinRef,
    target: PinRef,
    corridor: WireCorridor,
    *,
    net: str,
) -> tuple[WireSegment, ...]:
    start = editor.pin_position(source)
    end = editor.pin_position(target)
    if not corridor.contains(start) or not corridor.contains(end):
        raise ValueError("pin lies outside its functional-block wire corridor")
    candidates = [
        [start, (end[0], start[1]), end],
        [start, (start[0], end[1]), end],
    ]
    # Search parallel grid lanes when either simple elbow would cross a pin
    # or a prior wire. Validate the whole path before adding any segment.
    for step in range(1, 220):
        for sign in (-1, 1):
            x = round(start[0] + sign * step * 1.27, 6)
            y = round(start[1] + sign * step * 1.27, 6)
            candidates.append([start, (x, start[1]), (x, end[1]), end])
            candidates.append([start, (start[0], y), (end[0], y), end])
    for points in candidates:
        if not all(corridor.contains(point) for point in points):
            continue
        segments = tuple(WireSegment(a, b, net) for a, b in pairwise(points) if a != b)
        if any(existing.net != net and _touches(existing, segment)
               for segment in segments for existing in editor.segments):
            continue
        for segment in segments:
            editor.add_segment(segment)
        return segments
    raise StubCrossingError(f"no clear local wire path for {net} inside its block")
