"""Orthogonal, grid-preserving local schematic wiring."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from itertools import pairwise

GRID_MM = 1.27
MAX_GRID_STATES = 250_000


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


@dataclass(frozen=True)
class VisualObstacle:
    """Inclusive rectangular keepout for non-electrical sheet graphics."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float
    kind: str
    owner: str


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


def _intersects_obstacle(segment: WireSegment, obstacle: VisualObstacle) -> bool:
    """Return whether an orthogonal segment intersects an inclusive box."""
    return not (
        max(segment.start[0], segment.end[0]) < obstacle.x_min
        or min(segment.start[0], segment.end[0]) > obstacle.x_max
        or max(segment.start[1], segment.end[1]) < obstacle.y_min
        or min(segment.start[1], segment.end[1]) > obstacle.y_max
    )


def _route_is_clear(editor, segments: tuple[WireSegment, ...], net: str) -> bool:
    if any(_intersects_obstacle(segment, obstacle)
           for segment in segments for obstacle in getattr(editor, "obstacles", ())):
        return False
    return not any(existing.net != net and _touches(existing, segment)
                   for segment in segments for existing in editor.segments)


def _grid_fallback(editor, start, end, corridor, net) -> tuple[WireSegment, ...] | None:
    """Find a minimum-bend grid path after all one-lane routes are blocked."""
    end_index = (
        round((end[0] - start[0]) / GRID_MM),
        round((end[1] - start[1]) / GRID_MM),
    )
    snapped_end = (
        start[0] + end_index[0] * GRID_MM,
        start[1] + end_index[1] * GRID_MM,
    )
    if any(abs(a - b) > 0.002 for a, b in zip(end, snapped_end)):
        return None

    ix_min = math.ceil((corridor.left - start[0]) / GRID_MM - 1e-9)
    ix_max = math.floor((corridor.right - start[0]) / GRID_MM + 1e-9)
    iy_min = math.ceil((corridor.top - start[1]) / GRID_MM - 1e-9)
    iy_max = math.floor((corridor.bottom - start[1]) / GRID_MM + 1e-9)
    possible_states = (ix_max - ix_min + 1) * (iy_max - iy_min + 1) * 4
    if possible_states <= 0 or possible_states > MAX_GRID_STATES:
        return None

    directions = ((1, 0), (-1, 0), (0, 1), (0, -1))

    def point(index):
        return (
            round(start[0] + index[0] * GRID_MM, 6),
            round(start[1] + index[1] * GRID_MM, 6),
        )

    start_state = (0, 0, -1)
    costs = {start_state: (0, 0)}
    parents = {}
    pending = [(0, 0, *start_state)]
    goal = None
    while pending:
        turns, steps, ix, iy, direction = heapq.heappop(pending)
        state = (ix, iy, direction)
        if costs.get(state) != (turns, steps):
            continue
        if (ix, iy) == end_index:
            goal = state
            break
        for next_direction, (dx, dy) in enumerate(directions):
            nx, ny = ix + dx, iy + dy
            if not (ix_min <= nx <= ix_max and iy_min <= ny <= iy_max):
                continue
            segment = WireSegment(point((ix, iy)), point((nx, ny)), net)
            if not _route_is_clear(editor, (segment,), net):
                continue
            next_state = (nx, ny, next_direction)
            next_cost = (turns + int(direction not in (-1, next_direction)), steps + 1)
            if next_cost >= costs.get(next_state, (math.inf, math.inf)):
                continue
            costs[next_state] = next_cost
            parents[next_state] = state
            heapq.heappush(pending, (*next_cost, *next_state))
    if goal is None:
        return None

    indexes = []
    state = goal
    while state != start_state:
        indexes.append((state[0], state[1]))
        state = parents[state]
    indexes.append((0, 0))
    points = [point(index) for index in reversed(indexes)]
    compressed = [points[0]]
    for candidate in points[1:]:
        if (len(compressed) >= 2
                and ((compressed[-2][0] == compressed[-1][0] == candidate[0])
                     or (compressed[-2][1] == compressed[-1][1] == candidate[1]))):
            compressed[-1] = candidate
        else:
            compressed.append(candidate)
    return tuple(WireSegment(a, b, net) for a, b in pairwise(compressed))


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
        if not _route_is_clear(editor, segments, net):
            continue
        for segment in segments:
            editor.add_segment(segment)
        return segments
    segments = _grid_fallback(editor, start, end, corridor, net)
    if segments is not None:
        for segment in segments:
            editor.add_segment(segment)
        return segments
    raise StubCrossingError(f"no clear local wire path for {net} inside its block")
