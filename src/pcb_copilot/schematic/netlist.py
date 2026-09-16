"""Compare KiCad net groups before removing an intent net's sheet prefix."""

from __future__ import annotations

from collections import defaultdict

from pcb_copilot.schematic.models import SchematicIntent


def normalize_intent_netmap(
    intent: SchematicIntent,
    extracted_nets: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Return declared names only after exact physical pin-group agreement.

    The extractor preserves internal sheet paths, deliberately. A suffix alone
    cannot establish equivalence: two disconnected local nets may have the
    same label. Each extracted group must equal the complete intended group,
    and its name must be that declared name or a slash-delimited extension.
    No input object is modified. Schematic-only pseudo references are ignored
    on both sides, consistently with the existing KiCad extractor.
    """
    expected = {
        (component.ref, pin): connection.net
        for component in intent.components if not component.ref.startswith('#')
        for pin, connection in component.pins.items()
    }
    actual = {
        (ref, pin): net
        for ref, pins in extracted_nets.items() if not ref.startswith('#')
        for pin, net in pins.items()
    }
    if actual.keys() != expected.keys():
        missing = sorted(expected.keys() - actual.keys())
        extra = sorted(actual.keys() - expected.keys())
        raise ValueError(f'KiCad pin inventory differs from intent: missing={missing}, extra={extra}')

    expected_groups: dict[str, set[tuple[str, str]]] = defaultdict(set)
    actual_groups: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for pin, net in expected.items():
        expected_groups[net].add(pin)
    for pin, net in actual.items():
        actual_groups[net].add(pin)

    names = {}
    for actual_name, members in actual_groups.items():
        intended_names = {expected[pin] for pin in members}
        if len(intended_names) != 1:
            raise ValueError(
                f'KiCad net {actual_name!r} shorts intended nets {sorted(intended_names)}'
            )
        intended_name = next(iter(intended_names))
        if members != expected_groups[intended_name]:
            raise ValueError(
                f'KiCad net {actual_name!r} contains only part of intended net {intended_name!r}'
            )
        if actual_name != intended_name and not actual_name.endswith('/' + intended_name):
            raise ValueError(
                f'KiCad net {actual_name!r} does not retain declared name {intended_name!r}'
            )
        names[actual_name] = intended_name

    normalized: dict[str, dict[str, str]] = {}
    for (ref, pin), actual_name in sorted(actual.items()):
        normalized.setdefault(ref, {})[pin] = names[actual_name]
    return normalized
