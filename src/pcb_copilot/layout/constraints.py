"""Evidence-backed estimates and native constraints for published layout drafts.

This prepares a human-reviewable proposal; it never routes or approves a board.
Board-wide minima come from the draft's existing companion project, not a fab
preset inferred from missing physical inputs.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from kicad_claude.adapters import dsn_keepouts
from kicad_claude.adapters import project_settings as ps
from kicad_claude.utils.geometry import mcp_to_kicad_xy

from pcb_copilot.accept import assert_draft_base_current, load_draft
from pcb_copilot.drafts import _project_root
from pcb_copilot.evidence.checks import Finding
from pcb_copilot.layout.models import LayoutIntent
from pcb_copilot.models import DraftKind
from pcb_copilot.project import load_project
from pcb_copilot.state import file_digest
from pcb_copilot.toolchain import discover_toolchain

CURRENT_SOURCE = "https://raw.githubusercontent.com/KiCad/kicad-source-mirror/10.0.6/pcb_calculator/calculator_panels/panel_track_width.cpp"
MICROSTRIP_SOURCE = "https://www.ti.com/lit/an/sprabi2d/sprabi2d.pdf"


@dataclass(frozen=True)
class ConstraintReport:
    net_classes: dict[str, str]
    calculated_widths_mm: dict[str, float]
    findings: list[Finding]
    calculations: dict[str, dict] = field(default_factory=dict)
    base_project_sha256: str | None = None
    effective_rules_mm: dict[str, dict] = field(default_factory=dict)


def _positive(**values):
    for name, value in values.items():
        if (
            not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{name} must be finite and positive")


def calculate_current_width(
    current_a: float,
    rise_c: float,
    copper_oz: float,
    layer: Literal["external", "internal"],
) -> float:
    """IPC-2221 steady-state estimate in mm; nominal 1 oz = 0.035 mm.

    I = k * rise**0.44 * area_mil2**0.725 (KiCad 10.0.6 source above).
    This empirical model cannot validate pulse duration, duty cycle, ambient
    conditions or measured plated thickness.
    """
    _positive(current_a=current_a, rise_c=rise_c, copper_oz=copper_oz)
    if layer not in ("external", "internal"):
        raise ValueError("layer must be external or internal")
    k = 0.048 if layer == "external" else 0.024
    try:
        width = (
            (current_a / (k * rise_c**0.44)) ** (1 / 0.725)
            * 0.0254**2
            / (0.035 * copper_oz)
        )
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("current model exceeds numeric domain") from exc
    _positive(result_width_mm=width)
    return width


def calculate_microstrip_width(
    impedance_ohm: float,
    dielectric_height_mm: float,
    er: float,
    copper_mm: float,
) -> float:
    """Invert TI SPRABI2D p95 Eq10; restricted to its best-accuracy 50–100 Ω range.

    Z = 87/sqrt(er+1.41) * ln(5.98*H/(0.8*W+T)). Static approximation for
    an external microstrip over a reference plane; no soldermask, frequency,
    roughness or fabrication-tolerance correction, and not a field solver.
    """
    _positive(
        impedance_ohm=impedance_ohm,
        dielectric_height_mm=dielectric_height_mm,
        er=er,
        copper_mm=copper_mm,
    )
    if not 50 <= impedance_ohm <= 100 or er <= 1:
        raise ValueError("TI approximation supports 50–100 ohm and er > 1 only")
    width = (
        5.98
        * dielectric_height_mm
        * math.exp(-impedance_ohm * math.sqrt(er + 1.41) / 87)
        - copper_mm
    ) / 0.8
    _positive(result_width_mm=width)
    return width


_NATIVE = r"""
import json, sys, pcbnew
r = json.load(sys.stdin)
b = pcbnew.LoadBoard(r['pcb'])
if b is None:
    raise ValueError('native board could not be loaded')
if r.get('zones') is not None:
    for z in list(b.Zones()):
        if z.GetZoneName().startswith('Copilot:'):
            b.Remove(z)
    for spec in r['zones']:
        net = b.FindNet(spec['net'])
        if net is None:
            raise ValueError('zone references missing native net')
        z = pcbnew.ZONE(b)
        z.SetNet(net)
        layers = pcbnew.LSET()
        layers.AddLayer(b.GetLayerID(spec['layer']))
        z.SetLayerSet(layers)
        z.SetZoneName(spec['name'])
        z.SetLocalClearance(pcbnew.FromMM(spec['clearance']))
        p = z.Outline()
        p.NewOutline()
        for x,y in spec['points']:
            p.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        b.Add(z)
    if not pcbnew.SaveBoard(r['pcb'], b, True):
        raise ValueError('native save failed')
    b = pcbnew.LoadBoard(r['pcb'])
outline = pcbnew.SHAPE_POLY_SET()
if not b.GetBoardPolygonOutlines(outline, False):
    raise ValueError('native board outline is unavailable')
box = outline.BBox()
netrules = {}
for name,n in b.GetNetsByName().items():
    if not name:
        continue
    c = n.GetNetClassSlow()
    netrules[str(name)] = dict(name=str(c.GetName()), width=pcbnew.ToMM(c.GetTrackWidth()),
        clearance=pcbnew.ToMM(c.GetClearance()), via=pcbnew.ToMM(c.GetViaDiameter()),
        drill=pcbnew.ToMM(c.GetViaDrill()))
print('RESULT=' + json.dumps(dict(nets=netrules,
    layers=[b.GetLayerName(i) for i in range(pcbnew.PCB_LAYER_ID_COUNT)
            if pcbnew.IsCopperLayer(i) and b.IsLayerEnabled(i)],
    bounds=[pcbnew.ToMM(v) for v in (box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom())],
    rectangular=(outline.OutlineCount()==1 and outline.HoleCount(0)==0 and
        abs(abs(outline.COutline(0).Area())-box.GetWidth()*box.GetHeight()) < 1),
    pads=sorted((fp.GetReference(),p.GetNumber(),p.GetNetname(),
        int(p.GetLocalClearance() or 0), int(fp.GetLocalClearance() or 0))
        for fp in b.GetFootprints() for p in fp.Pads()),
    tracks=len(list(b.GetTracks())), zones=len(list(b.Zones())))))
"""


def _native(pcb, python, *, zones=None):
    result = subprocess.run(
        [str(python), "-I", "-c", _NATIVE],
        input=json.dumps({"pcb": str(pcb), "zones": zones}),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            f"native constraint inspection failed: {result.stderr or result.stdout}"
        )
    return json.loads(
        next(
            line.removeprefix("RESULT=")
            for line in result.stdout.splitlines()
            if line.startswith("RESULT=")
        )
    )


def _draft_boundary(pcb):
    pcb = Path(pcb).resolve()
    roots = [
        p
        for p in pcb.parents
        if p.parent.name == "drafts" and p.parent.parent.name == ".pcb-copilot"
    ]
    if not roots:
        raise ValueError("constraints require a published layout draft")
    root = roots[0]
    project = load_project(root.parent.parent.parent)
    try:
        record = load_draft(project, root.name)
    except (OSError, KeyError, ValueError) as exc:
        raise ValueError(f"invalid published draft: {exc}") from exc
    if record.kind != DraftKind.LAYOUT or _project_root(record) != project.root:
        raise ValueError("constraints require a layout draft")
    if pcb != (root / project.pcb_path.relative_to(project.root)).resolve():
        raise ValueError("PCB is not the declared draft board")
    for path in (pcb, pcb.with_suffix(".kicad_pro"), root / "constraints-report.json"):
        if not path.resolve().is_relative_to(root):
            raise ValueError("draft artifact escapes its workspace")
    metadata = json.loads((root / "draft.json").read_text(encoding="utf-8"))
    assert_draft_base_current(project, record, metadata)
    return pcb, root, project


def _publish(staged: dict[Path, Path], temp: Path):
    """Rollback-safe PCB/project/report publication; not a crash-atomic DB commit."""
    backups = {}
    for i, target in enumerate(staged):
        backup = temp / f"rollback-{i}"
        if target.exists():
            shutil.copy2(target, backup)
            backups[target] = backup
        else:
            backups[target] = None
    changed = []
    try:
        for target, source in staged.items():
            source.replace(target)
            changed.append(target)
    except Exception:
        for target in reversed(changed):
            if backups[target] is None:
                target.unlink(missing_ok=True)
            else:
                backups[target].replace(target)
        raise


def apply_constraints(pcb_path: Path, intent: LayoutIntent) -> ConstraintReport:
    """Apply constraints to a validated published draft and its companion project.

    Blocking validation findings leave both files untouched. Native failures raise
    before publication. Failed publication restores prior bytes. The report is
    persisted with a successful proposal and contains all physical inputs.
    """
    pcb, root, project = _draft_boundary(pcb_path)
    pro_path = pcb.with_suffix(".kicad_pro")
    findings = list(intent.unresolved_decisions)
    widths, calculations, assigned = {}, {}, {}
    base_hash = file_digest(project.pcb_path.with_suffix(".kicad_pro"))
    report = ConstraintReport(assigned, widths, findings, calculations, base_hash)

    def block(message, code="constraints.invalid"):
        findings.append(Finding(code, message))

    metadata = json.loads((root / "draft.json").read_text(encoding="utf-8"))
    companion_relative = (
        project.pcb_path.with_suffix(".kicad_pro").relative_to(project.root).as_posix()
    )
    if companion_relative not in metadata.get("base_files", {}):
        findings.append(
            Finding(
                "constraints.project_snapshot_unverified",
                "Draft creation metadata does not hash the companion .kicad_pro. Its currency at draft creation is unverified; this report records the current accepted project digest for subsequent checks. Review/acceptance must include the companion settings.",
                severity="review",
            )
        )
    if not pro_path.is_file():
        block(
            "Draft companion .kicad_pro is required; no generic board rules substituted"
        )
        return report
    previous_path = root / "constraints-report.json"
    if (
        previous_path.exists()
        and json.loads(previous_path.read_text(encoding="utf-8")).get(
            "base_project_sha256"
        )
        != base_hash
    ):
        block(
            "Accepted companion project changed since constraint preparation",
            "constraints.stale_project",
        )
        return report
    python = discover_toolchain(project.root).kipython
    if python is None:
        raise ValueError("native KiCad Python is required for constraints")
    before = _native(pcb, python)
    aliases = {}
    for name in before["nets"]:
        aliases.setdefault(name.lstrip("/"), []).append(name)

    def resolve(name):
        if name in before["nets"]:
            return name
        matches = aliases.get(name.lstrip("/"), [])
        if len(matches) == 1:
            return matches[0]
        raise ValueError(f"unknown or ambiguous native net: {name}")

    pro = ps.load_pro(pro_path)
    rules = ps.get_design_rules(pro)
    default = ps.find_net_class(pro, "Default")
    if not default:
        block("Companion project has no explicit Default net class")
        return report
    requested = {}
    try:
        for cls in intent.net_classes:
            for net in cls.nets:
                actual = resolve(net)
                requested[net] = {
                    "actual": actual,
                    "label": cls.name,
                    "width": cls.width_mm,
                    "clearance": cls.clearance_mm,
                    "via": cls.via_diameter_mm,
                    "drill": cls.via_drill_mm,
                }
        for critical in intent.critical_nets:
            actual = resolve(critical.net)
            names = (
                ("current_a", "duration_s", "rise_c", "copper_oz", "layer")
                if critical.kind == "power"
                else ("impedance_ohm", "dielectric_height_mm", "er", "copper_mm")
            )
            missing = [name for name in names if getattr(critical, name) is None]
            if missing:
                raise ValueError(
                    f"{critical.net}: missing physical inputs: {', '.join(missing)}"
                )
            inputs = {name: getattr(critical, name) for name in names}
            if critical.kind == "power":
                width = calculate_current_width(
                    critical.current_a,
                    critical.rise_c,
                    critical.copper_oz,
                    critical.layer,
                )
                source, model = (
                    CURRENT_SOURCE,
                    "IPC-2221 steady-state empirical estimate",
                )
                limitation = "Steady-state estimate: pulse duration/duty-cycle behavior is not validated; nominal copper conversion is 0.035 mm/oz, not measured plating."
            else:
                width = calculate_microstrip_width(**inputs)
                source, model = (
                    MICROSTRIP_SOURCE,
                    "TI SPRABI2D p95 Eq10 static microstrip approximation",
                )
                limitation = "50–100 ohm approximation over a reference plane; no frequency, soldermask, copper roughness or fabrication tolerance correction; fabricator validation required."
            widths[critical.net] = width
            calculations[critical.net] = {
                "inputs": inputs,
                "width_mm": width,
                "model": model,
                "source": source,
                "limitations": limitation,
            }
            findings.append(
                Finding(
                    "constraints.estimate",
                    f"{critical.net}: {limitation}",
                    severity="review",
                )
            )
            spec = requested.setdefault(
                critical.net,
                {
                    "actual": actual,
                    "label": "Critical",
                    "width": 0,
                    "clearance": None,
                    "via": None,
                    "drill": None,
                },
            )
            if critical.kind == "rf":
                spec["rf"] = True
                existing = max(
                    before["nets"][actual]["width"], rules.get("min_track_width", 0)
                )
                if existing > width + 1e-6 or (
                    spec["width"]
                    and not math.isclose(spec["width"], width, abs_tol=1e-6)
                ):
                    block(
                        f"{critical.net}: RF target {width:.6g} mm conflicts with explicit/existing width {max(existing, spec['width']):.6g} mm",
                        "constraints.impedance_conflict",
                    )
                spec["width"] = width
            else:
                spec["width"] = max(spec["width"], width)
        # Globs cannot safely encode arbitrary exact net membership without a
        # verified KiCad-specific escape contract. Fail rather than broaden.
        for net, spec in requested.items():
            if any(c in spec["actual"] for c in "*?[]\\"):
                raise ValueError(
                    f"{net}: wildcard net names require verified literal assignment support"
                )
        if len({v["actual"] for v in requested.values()}) != len(requested):
            raise ValueError("multiple intent names resolve to the same native net")
        zone_specs = []
        x0, y0, x1, y1 = before["bounds"]
        if intent.zones and (
            not before["rectangular"]
            or not math.isclose(x1 - x0, intent.outline.width_mm, abs_tol=0.01)
            or not math.isclose(y1 - y0, intent.outline.height_mm, abs_tol=0.01)
        ):
            raise ValueError("zones require matching rectangular native outline")
        regions = {r.id: r for r in intent.regions}
        for zone in intent.zones:
            actual = resolve(zone.net)
            region = regions.get(zone.region)
            x, y, w, h = (
                (region.x_mm, region.y_mm, region.width_mm, region.height_mm)
                if region
                else (0, 0, x1 - x0, y1 - y0)
            )
            points = [
                mcp_to_kicad_xy(x0 + a, b, page_height_mm=y1)
                for a, b in [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            ]
            clearance = max(
                zone.clearance_mm or 0,
                before["nets"][actual]["clearance"],
                rules.get("min_clearance", 0),
            )
            for layer in zone.layers:
                if layer not in before["layers"]:
                    raise ValueError(
                        f"zone layer is not enabled native copper: {layer}"
                    )
                zone_specs.append(
                    {
                        "net": actual,
                        "layer": layer,
                        "name": f"Copilot:{actual}:{layer}:{zone.region or 'board'}",
                        "clearance": clearance,
                        "points": points,
                    }
                )
    except ValueError as exc:
        block(str(exc))
    if any(f.severity == "block" for f in findings):
        return report
    # Each derived class owns one exact native net. Existing user classes and
    # their relative priorities remain intact, including broad pattern rules.
    expected = {}
    original_classes = list(ps.get_net_classes(pro))
    created_class = False

    def minimum_on_grid(value):
        # KiCad stores dimensions in integer nanometres. Round minima up so a
        # repeated native round trip neither shrinks them nor creates new IDs.
        return math.ceil(value * 1_000_000 - 1e-7) / 1_000_000

    for net, spec in requested.items():
        old = before["nets"][spec["actual"]]
        width = max(spec["width"], old["width"], rules.get("min_track_width", 0))
        width = round(width, 6) if spec.get("rf") else minimum_on_grid(width)
        clearance = max(
            spec["clearance"] or 0, old["clearance"], rules.get("min_clearance", 0)
        )
        clearance = minimum_on_grid(clearance)
        drill = minimum_on_grid(
            max(spec["drill"] or 0, old["drill"], rules.get("min_via_drill", 0))
        )
        annulus = max(
            (old["via"] - old["drill"]) / 2,
            rules.get("min_via_annular_width", 0),
            ((spec["via"] or 0) - (spec["drill"] or 0)) / 2,
        )
        via = max(
            spec["via"] or 0,
            old["via"],
            rules.get("min_via_diameter", 0),
            drill + 2 * annulus,
        )
        via = minimum_on_grid(via)
        payload = json.dumps(
            [spec["actual"], spec["label"], width, clearance, via, drill],
            sort_keys=True,
        )
        name = (
            "Copilot_"
            + spec["label"]
            + "_"
            + hashlib.sha256(payload.encode()).hexdigest()[:12]
        )
        existing = ps.find_net_class(pro, name)
        if (
            existing is not None
            and existing.get("description") != "PCB Copilot draft constraint"
        ):
            block(f"Derived class name collides with user class: {name}")
            return report
        created_class |= existing is None
        cls = ps.add_or_update_net_class(
            pro,
            name,
            track_width_mm=width,
            clearance_mm=clearance,
            via_diameter_mm=via,
            via_drill_mm=drill,
            description="PCB Copilot draft constraint",
        )
        # add_or_update supplies generic defaults for new classes. Omit all
        # unrelated fields so KiCad inherits existing differential/microvia/etc.
        # values through its effective composite class instead of masking them.
        for key in list(cls):
            if key not in {
                "name",
                "description",
                "priority",
                "track_width",
                "clearance",
                "via_diameter",
                "via_drill",
            }:
                del cls[key]
        cls["priority"] = 0
        ps.assign_pattern(pro, netclass=name, pattern=spec["actual"])
        expected[net] = {
            "name": name,
            "width": width,
            "clearance": clearance,
            "via": via,
            "drill": drill,
        }
    if created_class:
        active_names = {v["name"] for v in expected.values()}
        for cls in original_classes:
            if cls.get("name") != "Default" and cls.get("name") not in active_names:
                cls["priority"] = cls.get("priority", 0) + 1
    with tempfile.TemporaryDirectory(prefix=".constraints-", dir=root) as directory:
        temp = Path(directory)
        staged_pcb, staged_pro = temp / pcb.name, temp / pro_path.name
        shutil.copy2(pcb, staged_pcb)
        ps.save_pro(staged_pro, pro)
        dru = pcb.with_suffix(".kicad_dru")
        accepted_dru = project.pcb_path.with_suffix(".kicad_dru")
        if accepted_dru.exists() or dru.exists():
            block(
                "Custom .kicad_dru rules require separate effective-rule review; constraints not applied",
                "constraints.custom_rules",
            )
            return report
        after = _native(staged_pcb, python, zones=zone_specs if intent.zones else None)
        if before["pads"] != after["pads"] or before["tracks"] != after["tracks"]:
            raise ValueError(
                "native constraints changed pad connectivity/local overrides or routed copper"
            )
        for net, wanted in expected.items():
            actual = after["nets"][requested[net]["actual"]]
            if wanted["name"] not in actual["name"].split(",") or any(
                not math.isclose(actual[k], wanted[k], abs_tol=1e-6)
                for k in ("width", "clearance", "via", "drill")
            ):
                block(
                    f"{net}: native effective net class conflicts with requested rules",
                    "constraints.effective_conflict",
                )
        targeted = {s["actual"] for s in requested.values()}
        for net, old in before["nets"].items():
            if net not in targeted and after["nets"].get(net) != old:
                block(
                    f"Unintended net class change: {net}",
                    "constraints.membership_conflict",
                )
        if any(f.severity == "block" for f in findings):
            return report

        def runner(script, *args):
            result = subprocess.run(
                [str(python), "-I", "-c", script, *args],
                text=True,
                capture_output=True,
                timeout=60,
                check=True,
            )
            return result.stdout

        try:
            pads = dsn_keepouts.collect(staged_pcb, runner)
            if pads:
                findings.append(
                    Finding(
                        "constraints.dsn_limitation",
                        "Local-clearance DSN keepouts are conservative for netless pads only. Freerouting via enforcement is unverified; emitted via_keepout is not proof. Connected-pad overrides require manual routing/DRC review.",
                        severity="review",
                    )
                )
        except (ValueError, RuntimeError, OSError) as exc:
            findings.append(
                Finding(
                    "constraints.dsn_limitation",
                    f"DSN local-clearance inspection unavailable: {exc}",
                    severity="review",
                )
            )
        findings.append(
            Finding(
                "constraints.review_required",
                "Draft rules and unfilled zone outlines require human review; existing copper was not rerouted or validated.",
                severity="review",
            )
        )
        assigned.update({net: spec["name"] for net, spec in expected.items()})
        report.effective_rules_mm.update(
            {net: after["nets"][requested[net]["actual"]] for net in expected}
        )
        staged_report = temp / "constraints-report.json"
        staged_report.write_text(
            json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8"
        )
        _draft_boundary(pcb)  # Recheck accepted inputs before publication.
        if file_digest(project.pcb_path.with_suffix(".kicad_pro")) != base_hash:
            raise ValueError(
                "accepted companion project changed during constraint preparation"
            )
        _publish(
            {
                pcb: staged_pcb,
                pro_path: staged_pro,
                root / "constraints-report.json": staged_report,
            },
            temp,
        )
    return report
