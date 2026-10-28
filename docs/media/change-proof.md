# Recorded native-change proof

On 2026-10-29 KST, the native-candidate workflow completed a revision-only
schematic change on an external copy of
[the GPIO indicator](../../examples/gpio-indicator/README.md). The repository
example and its PCB stayed unchanged. The exact input, candidate, render,
inventory and original-log hashes are in [the public record](change-proof.json).

| Step | Actual exit code | Observed result |
| --- | ---: | --- |
| Initial preview | 0 | Previewed title revision `A1 DRAFT` → `DEMO-P1`. |
| Apply after changing the candidate | 2 | Rejected the stale preview after the candidate revision changed to `DEMO-P2`. |
| Fresh preview | 0 | Checked the current candidate and exported its schematic PDF. |
| Apply after author inspection | 0 | Installed that candidate into the disposable snapshot. |

The stale attempt returned `No successful matching unconsumed preview` and
requested a fresh preview. The final apply occurred only after the author
inspected the exact one-sheet PDF at page and circuit scale and resumed with
its SHA-256. The inspected sheet was `gpio-indicator.kicad_sch`; the recorded
reviewer was `Codex author visual review`. This was author inspection, not owner
sign-off.

The native before/candidate inventories matched: 11 physical parts and nine
nets, including the same component values, footprints, pin membership and
schematic identity paths. The edit also preserved every other schematic byte.
Only `gpio-indicator.kicad_sch` changed in the disposable project's declared
inputs. All 42 source input entries matched before/after, and the PCB hash
remained unchanged.

| Artifact | SHA-256 |
| --- | --- |
| Reviewed PDF | `c851d75a6a605b8058d269924d2c9db5ff0cdacb90f9818b316d349690fdd473` |
| Applied candidate schematic | `3932a952e4cb5a46324e454d7e400582572297341e07caabb7f857e465703fb0` |
| Before/candidate native inventory | `7ed29469f297d709ed55516aaa04a53c2f1e94a36283cf00f751f7f33cd8f102` |
| Unchanged source/snapshot PCB | `aa4811a06c27b7d529da161f004cf5e5c1d192e04515ebd6aa9e8716a8536c71` |

The JSON is a public summary of the captured run. Its source root is normalized
to `examples/gpio-indicator`; it identifies the original transcript and each
unedited stdout/stderr file by hash. Machine-local paths and raw logs are not
embedded. Artifact paths in that record describe the captured packet.

Reproduce from the repository root after [toolchain setup](../QUICKSTART.md):

```sh
uv run python tools/demo_change.py
```

The command stops at the final preview. Inspect your own PDF, then follow the
printed resume flags with its exact hash and your author-review identity. A
new run can have different export bytes; the values above identify this capture.

No owner decisions or fabrication release were created. The unbuilt example
retains its assembly rotation and human-review blockers. This proof establishes
the scoped preview/rejection/apply behavior and preservation checks for this
case; hardware behavior, physical fit and manufacturing still need qualification.
