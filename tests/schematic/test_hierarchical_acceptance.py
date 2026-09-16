"""Acceptance retains KiCad's qualified local names without rewriting the PCB."""

import importlib
import json

import pytest

from pcb_copilot.accept import accept_schematic, load_draft
from pcb_copilot.project import load_project
from pcb_copilot.schematic.commands import draft_schematic
from pcb_copilot.schematic.io import load_schematic_intent, save_schematic_intent
from pcb_copilot.schematic.models import PinConnection


@pytest.mark.slow
def test_accept_retains_real_local_sheet_net_names(project_copy, repo_root, tmp_path):
    project = load_project(project_copy)
    assert project.root.is_relative_to(tmp_path)
    pcb_before = project.pcb_path.read_bytes()
    intent = load_schematic_intent(repo_root / 'tests/fixtures/schematic/parent-child.yaml')
    connector = next(component for component in intent.components if component.ref == 'J1')
    # Keep the existing cross-sheet DATA_READY fixture and add a distinct,
    # two-pin local net on its child sheet. KiCad must qualify only the latter.
    local_connectors = tuple(connector.model_copy(update={
        'ref': ref, 'value': ref, 'block': 'sensor-io',
        'pin_map_evidence_id': None,
        'pin_map_review_note': 'Temporary integration-test connector fixture.',
        'pins': {'1': PinConnection(net='LOCAL_MONITOR', style='wire')},
    }) for ref in ('J2', 'J3'))
    intent = intent.model_copy(update={'components': (*intent.components, *local_connectors)})
    intent_path = tmp_path / 'local-and-hierarchical-intent.yaml'
    save_schematic_intent(intent, intent_path)

    report = draft_schematic(project, intent_path)
    assert report['exit_code'] == 0, report['findings']
    draft = load_draft(project, report['draft_id'])
    exported = importlib.import_module('extract_netmap').extract(
        draft.root / project.schematic_path.name
    )
    assert exported['nets'] == {
        'J1': {'1': 'DATA_READY'},
        'J2': {'1': 'Sensor/LOCAL_MONITOR'},
        'J3': {'1': 'Sensor/LOCAL_MONITOR'},
        'U1': {'7': 'DATA_READY'},
    }

    accept_schematic(project, draft)

    accepted = json.loads(project.netmap_path.read_text(encoding='utf-8'))
    assert accepted['nets'] == exported['nets']
    assert accepted['nets']['J2']['1'] != 'LOCAL_MONITOR'
    assert project.pcb_path.read_bytes() == pcb_before
    # Re-export the installed root and child to ensure the saved contract
    # represents the accepted KiCad hierarchy, not just a draft-side report.
    installed = importlib.import_module('extract_netmap').extract(project.schematic_path)
    assert accepted['nets'] == installed['nets']
