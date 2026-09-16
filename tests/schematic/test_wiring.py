"""Local wire routing must avoid non-electrical visual obstacles."""

from itertools import pairwise

import pytest

from pcb_copilot.schematic import wiring


def _obstacle(x_min, y_min, x_max, y_max, *, owner="fixture"):
    return wiring.VisualObstacle(
        x_min, y_min, x_max, y_max, kind="text", owner=owner,
    )


class ObstacleEditor:
    def __init__(self, *, obstacles=(), expose_obstacles=True):
        self.positions = {
            ("A", "1"): (0.0, 0.0),
            ("B", "1"): (10.0, 0.0),
        }
        self.segments = []
        if expose_obstacles:
            self.obstacles = list(obstacles)

    def pin_position(self, pin):
        return self.positions[(pin.ref, pin.pin)]

    def add_segment(self, segment):
        self.segments.append(segment)


def _segment_hits(segment, obstacle):
    return not (
        max(segment.start[0], segment.end[0]) < obstacle.x_min
        or min(segment.start[0], segment.end[0]) > obstacle.x_max
        or max(segment.start[1], segment.end[1]) < obstacle.y_min
        or min(segment.start[1], segment.end[1]) > obstacle.y_max
    )


def _serialized_segment(segment):
    return wiring.WireSegment(
        tuple(round(value, 4) for value in segment.start),
        tuple(round(value, 4) for value in segment.end),
        segment.net,
    )


@pytest.mark.parametrize(
    "obstacle",
    [
        _obstacle(4.0, -0.5, 6.0, 0.5, owner="crossing"),
        _obstacle(4.0, 0.0, 6.0, 2.0, owner="touching-edge"),
        _obstacle(4.0, -0.5, 6.0, 0.5, owner="same-net-value"),
    ],
    ids=("crossing", "touching-edge", "same-net-visual-text"),
)
def test_local_connection_detours_around_inclusive_visual_obstacle(obstacle):
    editor = ObstacleEditor(obstacles=[obstacle])

    route = wiring.connect_local(
        editor,
        wiring.PinRef("A", "1"),
        wiring.PinRef("B", "1"),
        wiring.WireCorridor(0.0, -2.0, 10.0, 2.0),
        net="DATA",
    )

    assert route == tuple(editor.segments)
    assert not any(_segment_hits(segment, obstacle) for segment in route)


def test_local_connection_rejects_segment_wholly_inside_visual_obstacle():
    obstacle = _obstacle(-1.0, -1.0, 11.0, 1.0, owner="containing-text")
    editor = ObstacleEditor(obstacles=[obstacle])

    with pytest.raises(wiring.StubCrossingError, match="no clear local wire path"):
        wiring.connect_local(
            editor,
            wiring.PinRef("A", "1"),
            wiring.PinRef("B", "1"),
            wiring.WireCorridor(0.0, -2.0, 10.0, 2.0),
            net="DATA",
        )

    assert editor.segments == []


def test_visual_obstacle_blocking_corridor_fails_without_partial_mutation():
    obstacle = _obstacle(4.0, -1.0, 6.0, 1.0, owner="wall")
    editor = ObstacleEditor(obstacles=[obstacle])

    with pytest.raises(wiring.StubCrossingError, match="no clear local wire path"):
        wiring.connect_local(
            editor,
            wiring.PinRef("A", "1"),
            wiring.PinRef("B", "1"),
            wiring.WireCorridor(0.0, 0.0, 10.0, 0.0),
            net="DATA",
        )

    assert editor.segments == []


def test_editor_without_visual_obstacle_collection_remains_compatible():
    editor = ObstacleEditor(expose_obstacles=False)

    route = wiring.connect_local(
        editor,
        wiring.PinRef("A", "1"),
        wiring.PinRef("B", "1"),
        wiring.WireCorridor(0.0, 0.0, 10.0, 0.0),
        net="DATA",
    )

    assert route == (wiring.WireSegment((0.0, 0.0), (10.0, 0.0), "DATA"),)


def test_local_connection_uses_bounded_multi_bend_fallback_when_one_lane_is_trapped():
    editor = ObstacleEditor(obstacles=[
        _obstacle(9.5, 5.0, 10.8, 8.0, owner="source-column-text"),
        _obstacle(2.0, 5.0, 3.0, 7.0, owner="target-column-text"),
    ])
    editor.positions = {
        ("A", "1"): (10.16, 10.16),
        ("B", "1"): (2.54, 2.54),
    }
    editor.segments = [
        wiring.WireSegment((6.35, 8.89), (6.35, 11.43), "body:A"),
        wiring.WireSegment((5.08, 1.27), (5.08, 3.81), "body:B"),
    ]
    foreign_segments = list(editor.segments)

    route = wiring.connect_local(
        editor,
        wiring.PinRef("A", "1"),
        wiring.PinRef("B", "1"),
        wiring.WireCorridor(0.0, 0.0, 15.24, 15.24),
        net="DATA",
    )

    assert len(route) >= 4
    assert route[0].start == (10.16, 10.16)
    assert route[-1].end == (2.54, 2.54)
    assert all(first.end == second.start for first, second in pairwise(route))
    assert all(segment.start[0] == segment.end[0]
               or segment.start[1] == segment.end[1]
               for segment in route)
    assert not any(_segment_hits(segment, obstacle)
                   for segment in route for obstacle in editor.obstacles)
    assert not any(wiring._touches(_serialized_segment(segment),
                                   _serialized_segment(existing))
                   for segment in route for existing in foreign_segments)


def test_multi_bend_fallback_rejects_off_lattice_target_without_partial_mutation():
    editor = ObstacleEditor(obstacles=[
        _obstacle(9.5, 5.0, 10.8, 8.0, owner="source-column-text"),
        _obstacle(2.0, 5.0, 3.0, 7.0, owner="target-column-text"),
    ])
    editor.positions = {
        ("A", "1"): (10.16, 10.16),
        ("B", "1"): (2.541, 2.54),
    }
    editor.segments = [
        wiring.WireSegment((6.35, 8.89), (6.35, 11.43), "body:A"),
        wiring.WireSegment((5.08, 1.27), (5.08, 3.81), "body:B"),
    ]
    before = list(editor.segments)

    with pytest.raises(wiring.StubCrossingError, match="no clear local wire path"):
        wiring.connect_local(
            editor,
            wiring.PinRef("A", "1"),
            wiring.PinRef("B", "1"),
            wiring.WireCorridor(0.0, 0.0, 15.24, 15.24),
            net="DATA",
        )

    assert editor.segments == before


def test_multi_bend_fallback_rejects_endpoints_backend_cannot_preserve():
    editor = ObstacleEditor(obstacles=[
        _obstacle(9.5, 5.0, 10.8, 8.0, owner="source-column-text"),
        _obstacle(2.0, 5.0, 3.0, 7.0, owner="target-column-text"),
    ])
    source = (10.1600004, 10.1600004)
    target = (2.5400004, 2.5400004)
    editor.positions = {("A", "1"): source, ("B", "1"): target}
    editor.segments = [
        wiring.WireSegment((6.35, 8.89), (6.35, 11.43), "body:A"),
        wiring.WireSegment((5.08, 1.27), (5.08, 3.81), "body:B"),
    ]
    before = list(editor.segments)

    with pytest.raises(wiring.StubCrossingError, match="no clear local wire path"):
        wiring.connect_local(
            editor,
            wiring.PinRef("A", "1"),
            wiring.PinRef("B", "1"),
            wiring.WireCorridor(0.0, 0.0, 15.24, 15.24),
            net="DATA",
        )

    assert editor.segments == before
