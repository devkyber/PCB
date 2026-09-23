"""Supplier CAD conversion adapted from BeckhamLabs kicad-jlcpcb (MIT).

See THIRD_PARTY_LICENSE.txt for the retained copyright and license.
"""

from pathlib import Path
import subprocess

from pcb_copilot.toolchain import discover_toolchain


class PartLibraryError(RuntimeError):
    """Supplier CAD conversion failed."""


def _safe_name(name):
    if not name or name in {'.', '..'} or any(c in name for c in '/\\:'):
        raise PartLibraryError(f'invalid supplier library name: {name!r}')


def convert(cad: dict, lcsc: str, libs: Path, *, want_3d: bool = True) -> dict:
    """Convert supplier CAD; conversion failure never generates placeholders."""
    try:
        from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
        from easyeda2kicad.easyeda.easyeda_importer import (
            Easyeda3dModelImporter,
            EasyedaFootprintImporter,
            EasyedaSymbolImporter,
        )
        from easyeda2kicad.kicad.export_kicad_3d_model import Exporter3dModelKicad
        from easyeda2kicad.kicad.export_kicad_footprint import ExporterFootprintKicad
        from easyeda2kicad.kicad.export_kicad_symbol import ExporterSymbolKicad
    except ImportError as e:  # pragma: no cover - depends on install state
        raise PartLibraryError(
            f"easyeda2kicad is not installed ({e}); cannot build real libraries"
        ) from e

    api = EasyedaApi()
    library_name = 'lcsc_' + lcsc
    model_ref = '${KIPRJMOD}/libs/' + library_name + '.3dshapes'
    libs.mkdir(parents=True, exist_ok=True)
    sym_path = libs / f"{library_name}.kicad_sym"
    pretty = libs / f"{library_name}.pretty"
    shapes = libs / f"{library_name}.3dshapes"

    # Seed the symbol library at the newest format version. Once it
    # exists, easyeda2kicad reads the version back out and matches it.
    if not sym_path.exists():
        sym_path.write_text(
            f"(kicad_symbol_lib\n  (version {20251024})\n"
            f"  (generator kicad_jlcpcb_mcp)\n)",
            encoding="utf-8",
        )

    try:
        ee_symbol = EasyedaSymbolImporter(easyeda_cp_cad_data=cad).get_symbol()
        _safe_name(ee_symbol.info.name)
        ExporterSymbolKicad(symbol=ee_symbol, lib_path=str(sym_path)).save_to_lib(
            lib_path=str(sym_path), footprint_lib_name=library_name, overwrite=True
        )

        ee_footprint = EasyedaFootprintImporter(easyeda_cp_cad_data=cad).get_footprint()
        _safe_name(ee_footprint.info.name)
        pretty.mkdir(parents=True, exist_ok=True)
        fp_path = pretty / f"{ee_footprint.info.name}.kicad_mod"
        ExporterFootprintKicad(footprint=ee_footprint).export(
            footprint_full_path=str(fp_path),
            model_3d_path=model_ref,
        )
    except PartLibraryError:
        raise
    except Exception as e:
        raise PartLibraryError(f"easyeda2kicad conversion failed for {lcsc}: {e}") from e

    toolchain = discover_toolchain(Path(__file__).resolve().parents[2])
    if toolchain.kipython is None:
        raise PartLibraryError('KiCad Python is required to normalize the imported footprint')
    normalized = subprocess.run(
        [str(toolchain.kipython), '-I', '-c',
         'import pcbnew,sys; fp=pcbnew.FootprintLoad(sys.argv[1],sys.argv[2]); '
         'assert fp is not None; pcbnew.FootprintSave(sys.argv[1],fp)', str(pretty), fp_path.stem],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60,
    )
    if normalized.returncode:
        raise PartLibraryError(f'KiCad footprint normalization failed: {normalized.stderr}')

    warnings: list[str] = []
    model_path: Path | None = None
    if want_3d:
        try:
            model = Easyeda3dModelImporter(
                easyeda_cp_cad_data=cad, download_raw_3d_model=True, api=api
            ).output
            if model is not None:
                _safe_name(model.name)
            if model is not None and Exporter3dModelKicad(model_3d=model).export(
                output_dir=str(shapes)
            ):
                # export() writes <name>.step and <name>.wrl; report the
                # STEP since that is what mechanical CAD consumes.
                candidate = shapes / f"{model.name}.step"
                model_path = candidate if candidate.exists() else None
            else:
                warnings.append(f"No 3D model available on EasyEDA for {lcsc}")
        except Exception as e:
            warnings.append(f"3D model fetch failed for {lcsc}: {e}")

    return {
        "symbol_path": sym_path,
        "footprint_path": fp_path,
        "model_3d_path": model_path,
        "symbol_name": ee_symbol.info.name,
        "footprint_name": ee_footprint.info.name,
        "pin_count": len(ee_footprint.pads),
        "warnings": warnings,
    }
