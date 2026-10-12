"""Prepare authentic PSpice decks; never run a simulator or write owner CAD.

Run from the PCB workspace: uv run python projects/rover-pdb/simulation/pspice/generate.py
The frozen CAD hash guard deliberately fails after an owner schematic edit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

import sexpdata

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
ARCHIVE = PROJECT / "evidence/files/LMR51450SDRRR_SNVMCB2_e1fd811f3bcb.zip"
ARCHIVE_SHA256 = "e1fd811f3bcb494bf528772421a5af4dd37b37f50461caaa5e834d3256ac1a40"
VENDOR = HERE / "vendor"
MODEL = VENDOR / "LMR51450_PSPICE_TRANS/LMR51450_TRANS.lib"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def native_parts() -> dict:
    parts = {}
    for path in sorted(PROJECT.glob("*.kicad_sch")):
        tree = sexpdata.loads(path.read_text(encoding="utf-8"))
        for node in tree:
            if not isinstance(node, list) or not node or str(node[0]) != "symbol":
                continue
            props = {str(n[1]): str(n[2]) for n in node
                     if isinstance(n, list) and n and str(n[0]) == "property"}
            if props.get("Reference", "").startswith("#"):
                continue
            if "Reference" in props:
                parts[props["Reference"]] = {"sheet": path.name, **props}
    return parts


def extract_exact_vendor() -> list:
    if sha256(ARCHIVE.read_bytes()) != ARCHIVE_SHA256:
        raise ValueError("TI archive bytes differ from the reviewed SNVMCB2 package")
    manifest = []
    with zipfile.ZipFile(ARCHIVE) as archive:
        for info in archive.infolist():
            rel = PurePosixPath(info.filename)
            if rel.is_absolute() or ".." in rel.parts or ":" in info.filename or "\\" in info.filename:
                raise ValueError(f"Unsafe archive path: {info.filename}")
            if info.is_dir():
                continue
            dest = VENDOR.joinpath(*rel.parts)
            if not dest.resolve().is_relative_to(VENDOR.resolve()):
                raise ValueError(f"Archive path escapes vendor directory: {dest}")
            payload = archive.read(info)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.read_bytes() != payload:
                raise ValueError(f"Vendor file changed; preserve it and investigate: {dest}")
            if not dest.exists():
                dest.write_bytes(payload)
            manifest.append({"path": dest.relative_to(HERE).as_posix(),
                             "sha256": sha256(payload), "bytes": len(payload)})
    return manifest


RAILS = {
    "12v": dict(ic="U2", in_caps=["C10", "C11"], hf="C30", boot="C33",
                lref="L1", l="6.8u", dcr="11.5m", rtop="R10", rbot="R17",
                rbot_value="7.15k", enable="R13", ff_c="C39", ff_r="R21",
                out_caps=["C20", "C21", "C22", "C23"], ceff="8.95u",
                bulk=None, iout=3.0, vout=0.8*(1+100/7.15)),
    "5v": dict(ic="U3", in_caps=["C12", "C13"], hf="C31", boot="C34",
               lref="L2", l="4.7u", dcr="8.4m", rtop="R11", rbot="R16",
               rbot_value="19.1k", enable="R14", ff_c="C40", ff_r="R22",
               out_caps=["C24", "C25", "C26", "C27", "C28"], ceff="17.51u",
               bulk=("C2", "470u", "56m"), iout=2.4, vout=0.8*(1+100/19.1)),
    "motor": dict(ic="U4", in_caps=["C14", "C15"], hf="C32", boot="C35",
                  lref="L3", l="3.3u", dcr="6.8m", rtop="R12", rbot="R18",
                  rbot_value="3.74k", enable=None, ff_c="C41", ff_r="R23",
                  out_caps=["C16", "C17", "C18", "C19"], ceff="6.4u",
                  bulk=("C5", "220u", "30m"), iout=3.5, vout=0.8*(1+100/3.74)),
}


def capacitor(ref: str, node: str, capacitance: str, esr: str) -> list[str]:
    return [f"R_ESR_{ref} {node} {ref}_ESR {esr}",
            f"C_{ref} {ref}_ESR 0 {capacitance}"]


def deck(rail: str, kind: str) -> str:
    r = RAILS[rail]
    lines = [f"Rover PDB A9 {rail} {kind} -- PREPARED, NOT RUN",
             "* Authentic encrypted TI LMR51450 model. PSpice required.",
             "* Component/model assumptions and limitations: ../README.md",
             '.LIB "../vendor/LMR51450_PSPICE_TRANS/LMR51450_TRANS.lib"',
             f".PARAM VIN_POINT=25.2 I_FULL={r['iout']} V_TARGET={r['vout']:.9f}",
             "* Sensitivity parameters; defaults are approximate, not production bounds.",
             ".PARAM C_SCALE=1 CER_ESR=5m BULK_SCALE=1 BULK_ESR_SCALE=1",
             ".PARAM SOURCE_R=50m L_SCALE=1"]
    if kind == "vin_sweep":
        source = "PWL(0 0 1m 25.2 12m 25.2 18m 19.8 22m 19.8 28m 25.2 35m 25.2)"
        tstop = "35m"
    else:
        source = "PWL(0 0 1m {VIN_POINT} 30m {VIN_POINT})"
        tstop = "28m" if kind == "enable" else "25m"
    lines += [f"V_BAT SOURCE 0 {source}",
              "* Single-rail upstream source approximation; other rails and C1 omitted.",
              "R_SOURCE SOURCE VIN {SOURCE_R}"]
    for ref in r["in_caps"]:
        lines += capacitor(ref, "VIN", "{5.75u*C_SCALE}", "{CER_ESR}")
    lines += capacitor(r["hf"], "VIN", "100n", "{CER_ESR}")
    if rail == "motor":
        lines += ["R_R19 VIN SW_SUPPLY 100k", "R_R24 SW_SUPPLY 0 22k", "R_R15 EN 0 100k"]
        if kind == "enable":
            lines += ["V_SWITCH CONTROL 0 PWL(0 0 2m 0 2.001m 1 12m 1 12.001m 0 16m 0 16.001m 1 28m 1)",
                      "S_SW1 SW_SUPPLY EN CONTROL 0 SW_MODEL",
                      ".MODEL SW_MODEL VSWITCH(RON=0.05 ROFF=1e12 VON=0.9 VOFF=0.1)"]
        else:
            lines += ["* SW1 closed; 50m contact resistance is an assumed testbench parasitic.",
                      "R_SW1 SW_SUPPLY EN 50m"]
    else:
        lines += [f"R_{r['enable']} VIN EN 100k"]
    lines += ["* Model pin order: AGND BOOT EN FB GND PGOOD RT SW1 SW2 SW3 VIN1 VIN2 VIN3",
              "* Both ground domains tied at 0 per TI model; cannot evaluate return layout.",
              "* RT_NC and PG_NC intentionally have no external parts, matching A9.",
              f"X_{r['ic']} 0 BOOT EN FB 0 PG_NC RT_NC SW SW SW VIN VIN VIN LMR51450_TRANS PARAMS: MODE=0",
              f"C_{r['boot']} BOOT SW 100n",
              f"L_{r['lref']} SW L_DCR {{{r['l']}*L_SCALE}}",
              f"R_DCR L_DCR VOUT {r['dcr']}",
              f"R_{r['rtop']} VOUT FB 100k",
              f"R_{r['rbot']} FB 0 {r['rbot_value']}",
              f"C_{r['ff_c']} VOUT FF 33p",
              f"R_{r['ff_r']} FF FB 1k"]
    for ref in r["out_caps"]:
        lines += capacitor(ref, "VOUT", "{" + r["ceff"] + "*C_SCALE}", "{CER_ESR}")
    if r["bulk"]:
        ref, value, esr = r["bulk"]
        lines += ["* Bulk ESR approximates published 100kHz impedance; not a guaranteed ESR model."]
        lines += capacitor(ref, "VOUT", "{"+value+"*BULK_SCALE}", "{"+esr+"*BULK_ESR_SCALE}")
    if rail == "motor":
        lines += ["* D2/R20 indicator is excluded; about 5mA must be added to actual motor load."]
    if kind == "load_step":
        lines += ["* Unloaded startup, then 0 -> planning load -> 0; 10us edges are assumed.",
                  "I_LOAD VOUT 0 PWL(0 0 12m 0 12.01m {I_FULL} 18m {I_FULL} 18.01m 0 25m 0)",
                  ".MEAS TRAN STEP_UP_MIN MIN V(VOUT) FROM=12m TO=17m",
                  ".MEAS TRAN STEP_UP_MAX MAX V(VOUT) FROM=12m TO=17m",
                  ".MEAS TRAN STEP_DOWN_MAX MAX V(VOUT) FROM=18m TO=23m",
                  ".MEAS TRAN LOADED_AVG AVG V(VOUT) FROM=16m TO=17m",
                  ".MEAS TRAN LOADED_RIPPLE PP V(VOUT) FROM=16m TO=17m"]
    else:
        lines += ["* Resistive planning load: full rated planning current only at target voltage.",
                  "R_LOAD VOUT 0 {V_TARGET/I_FULL}"]
    lines += ["R_NUMERICAL VOUT 0 1G", f".TRAN 0 {tstop} 0 20n", ".OPTIONS ADVCONV",
              ".OPTIONS ITL4=20", ".PROBE64 V(VIN) V(VOUT) V(EN) V(BOOT) V(SW) V(FB)",
              f"+ I(L_{r['lref']}) I(V_BAT)",
              ".MEAS TRAN VOUT_MAX MAX V(VOUT)",
              f".MEAS TRAN IL_MAX MAX I(L_{r['lref']})"]
    if kind == "startup":
        lines += [".STEP PARAM VIN_POINT LIST 19.8 22.2 25.2",
                  ".MEAS TRAN VOUT_SETTLED AVG V(VOUT) FROM=23m TO=24m",
                  ".MEAS TRAN RIPPLE_SETTLED PP V(VOUT) FROM=23m TO=24m"]
    lines += [".END", ""]
    return "\n".join(lines)


def main() -> None:
    expected = json.loads((HERE / "cad_snapshot.json").read_text(encoding="utf-8"))["sha256"]
    actual = {p.name: sha256(p.read_bytes()) for p in sorted(PROJECT.glob("*.kicad_sch"))}
    if actual != expected:
        raise SystemExit("Owner CAD changed. Reconcile the testbench explicitly; do not refresh hashes blindly.")
    parts = native_parts()
    for rail in RAILS.values():
        assert parts[rail["ic"]]["MPN"] == "LMR51450SDRRR"
        refs = rail["in_caps"] + rail["out_caps"] + [rail[k] for k in ("hf", "boot", "lref", "rtop", "rbot", "ff_c", "ff_r")]
        assert all(ref in parts for ref in refs)
    entries = extract_exact_vendor()
    interface = MODEL.read_text(encoding="utf-8").replace("\r", "")
    assert re.search(r"\.SUBCKT LMR51450_TRANS AGND BOOT EN FB GND PGOOD RT SW1 SW2 SW3 VIN1 VIN2 VIN3\s*\+\s*PARAMS: MODE=0", interface)
    cases = []
    (HERE / "cases").mkdir(exist_ok=True)
    for rail in RAILS:
        for kind in ("startup", "load_step", "vin_sweep"):
            path = HERE / "cases" / f"{rail}_{kind}.cir"
            path.write_text(deck(rail, kind), encoding="ascii", newline="\n")
            cases.append({"path": path.relative_to(HERE).as_posix(), "status": "NOT RUN",
                          "sha256": sha256(path.read_bytes())})
    path = HERE / "cases/motor_enable.cir"
    path.write_text(deck("motor", "enable"), encoding="ascii", newline="\n")
    cases.append({"path": path.relative_to(HERE).as_posix(), "status": "NOT RUN", "sha256": sha256(path.read_bytes())})
    provenance = {"status": "PREPARED_NOT_RUN", "source_url": "https://www.ti.com/lit/zip/SNVMCB2",
                  "archive": str(ARCHIVE.relative_to(PROJECT)), "archive_sha256": sha256(ARCHIVE.read_bytes()),
                  "model_sha256": sha256(MODEL.read_bytes()), "cad_sha256": actual,
                  "vendor_files": entries, "cases": cases,
                  "note": "Vendor .out files are bundled TI historical examples, not results from this project."}
    (HERE / "provenance.json").write_text(json.dumps(provenance, indent=2)+"\n", encoding="utf-8")
    selected = {ref: data for ref, data in parts.items()
                if data["sheet"] in ("buck-12v.kicad_sch", "buck-5v.kicad_sch", "buck-motor.kicad_sch") or ref == "C2"}
    (HERE / "native_component_snapshot.json").write_text(json.dumps(selected, indent=2)+"\n", encoding="utf-8")
    print(f"Prepared {len(cases)} decks. Simulator not invoked; all statuses NOT RUN.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vendor-only', action='store_true',
                        help='Restore exact vendor example from the archive; do not rewrite Rover decks')
    args = parser.parse_args()
    if args.vendor_only:
        entries = extract_exact_vendor()
        print(f"Restored {len(entries)} archived vendor files. No simulation or Rover deck update.")
    else:
        main()
