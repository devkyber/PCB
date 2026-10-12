"""Restore archived model bytes without overwriting a locally modified model."""
import importlib.util
import zipfile
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'projects/rover-pdb/simulation/pspice/generate.py'
spec = importlib.util.spec_from_file_location('rover_vendor', MODULE)
vendor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vendor)


@pytest.fixture
def extraction(tmp_path, monkeypatch):
    archive = tmp_path / 'source.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('model/model.lib', b'original model\r\n')
    monkeypatch.setattr(vendor, 'HERE', tmp_path)
    monkeypatch.setattr(vendor, 'ARCHIVE', archive)
    monkeypatch.setattr(vendor, 'ARCHIVE_SHA256', vendor.sha256(archive.read_bytes()))
    monkeypatch.setattr(vendor, 'VENDOR', tmp_path / 'vendor')
    return archive, tmp_path / 'vendor/model/model.lib'


def test_restores_exact_model_and_reuses_unchanged_extraction(extraction):
    _, model = extraction
    assert len(vendor.extract_exact_vendor()) == 1
    assert model.read_bytes() == b'original model\r\n'
    assert len(vendor.extract_exact_vendor()) == 1


def test_rejects_changed_archive_before_extraction(extraction):
    archive, model = extraction
    archive.write_bytes(archive.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='archive bytes differ'):
        vendor.extract_exact_vendor()
    assert not model.exists()


def test_preserves_modified_extracted_model(extraction):
    _, model = extraction
    model.parent.mkdir(parents=True)
    model.write_bytes(b'owner modification')
    with pytest.raises(ValueError, match='Vendor file changed'):
        vendor.extract_exact_vendor()
    assert model.read_bytes() == b'owner modification'
