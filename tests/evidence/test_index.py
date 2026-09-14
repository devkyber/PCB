from datetime import date

import pytest

from pcb_copilot.evidence.index import (
    EvidenceFormatError,
    load_evidence_index,
    save_evidence_index,
)
from pcb_copilot.evidence.models import (
    EvidenceIndex,
    EvidenceRecord,
    EvidenceRole,
    TrustTier,
)


def _record(**overrides) -> EvidenceRecord:
    fields = {
        "id": "sha256:abc123",
        "manufacturer": "Digi",
        "part_numbers": ["XBee 3"],
        "title": "XBee 3 Hardware Reference",
        "revision": "90001543",
        "source_url": "https://example.test/xbee.pdf",
        "retrieved_on": date(2026, 8, 25),
        "path": "files/xbee3_hardware_ref.pdf",
        "sha256": "abc123",
        "media_type": "application/pdf",
        "roles": {EvidenceRole.DATASHEET, EvidenceRole.MODULE_PINOUT},
        "trust_tier": TrustTier.MANUFACTURER,
        "component_refs": {"J9"},
    }
    fields.update(overrides)
    return EvidenceRecord(**fields)


def test_one_document_can_fill_multiple_roles(tmp_path):
    record = _record()
    path = tmp_path / "index.yaml"

    save_evidence_index(EvidenceIndex(schema_version=1, records=[record]), path)
    loaded = load_evidence_index(path)

    assert loaded.records[0].roles == record.roles
    assert loaded.records[0].component_refs == frozenset({"J9"})
    assert loaded.for_part("xbee 3") == (loaded.records[0],)


def test_repeated_save_is_byte_identical_and_sorted(tmp_path):
    path = tmp_path / "index.yaml"
    index = EvidenceIndex(
        schema_version=1,
        records=[
            _record(id="sha256:fff", sha256="fff", part_numbers=["Z", "A"]),
            _record(id="sha256:aaa", sha256="aaa"),
        ],
    )

    save_evidence_index(index, path)
    first = path.read_bytes()
    save_evidence_index(index, path)

    assert path.read_bytes() == first
    assert first.index(b"sha256:aaa") < first.index(b"sha256:fff")
    assert first.index(b"- A") < first.index(b"- Z")


@pytest.mark.parametrize(
    "document, message",
    [
        (
            {
                "schema_version": 1,
                "records": [
                    _record().model_dump(mode="json"),
                    _record().model_dump(mode="json"),
                ],
            },
            "duplicate evidence id",
        ),
        (
            {
                "schema_version": 1,
                "records": [{**_record().model_dump(mode="json"), "path": "/tmp/a.pdf"}],
            },
            "relative",
        ),
        (
            {
                "schema_version": 1,
                "records": [{**_record().model_dump(mode="json"), "path": "../a.pdf"}],
            },
            "escape",
        ),
        (
            {
                "schema_version": 1,
                "records": [
                    {k: v for k, v in _record().model_dump(mode="json").items() if k != "sha256"}
                ],
            },
            "sha256",
        ),
        (
            {
                "schema_version": 1,
                "records": [
                    {
                        **_record().model_dump(mode="json"),
                        "roles": ["datasheet", "marketing_claim"],
                    }
                ],
            },
            "role",
        ),
    ],
)
def test_invalid_indexes_raise_evidence_format_error(tmp_path, document, message):
    import yaml

    path = tmp_path / "index.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    with pytest.raises(EvidenceFormatError, match=message):
        load_evidence_index(path)
