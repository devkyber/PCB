# PCB Copilot fault evaluation

Run: `2026-10-28T18:38:25.705763+00:00` · mode: `native`

This is a small manually selected software regression exercise. A met expectation is not a design approval or an engineering-quality score.

| Case | Interface | Expected exit | Actual exit | Outcome | Logs |
| --- | --- | ---: | ---: | --- | --- |
| control-evidence | cli | 0 | 0 | met_expectation | [stdout](logs/control-evidence.stdout.txt) · [stderr](logs/control-evidence.stderr.txt) |
| control-footprints | validator-api | 0 | 0 | met_expectation | [stdout](logs/control-footprints.stdout.txt) · [stderr](logs/control-footprints.stderr.txt) |
| missing-preview | cli | 2 | 2 | met_expectation | [stdout](logs/missing-preview.stdout.txt) · [stderr](logs/missing-preview.stderr.txt) |
| evidence-corruption | cli | 1 | 1 | met_expectation | [stdout](logs/evidence-corruption.stdout.txt) · [stderr](logs/evidence-corruption.stderr.txt) |
| footprint-geometry | validator-api | 1 | 1 | met_expectation | [stdout](logs/footprint-geometry.stdout.txt) · [stderr](logs/footprint-geometry.stderr.txt) |
| model-corruption | validator-api | 1 | 1 | met_expectation | [stdout](logs/model-corruption.stdout.txt) · [stderr](logs/model-corruption.stderr.txt) |
| selected-mpn | validator-api | 1 | 1 | met_expectation | [stdout](logs/selected-mpn.stdout.txt) · [stderr](logs/selected-mpn.stderr.txt) |
| native-preview-control | native-cli | 0 | 0 | met_expectation | [stdout](logs/native-preview-control.stdout.txt) · [stderr](logs/native-preview-control.stderr.txt) |
| changed-candidate | native-cli | 2 | 2 | met_expectation | [stdout](logs/changed-candidate.stdout.txt) · [stderr](logs/changed-candidate.stderr.txt) |

Source inputs unchanged: **True**. Implementation unchanged during run: **True**.

Exact commands, input manifests, fault descriptions, environment, durations and outcomes: [evaluation.json](evaluation.json). All workspace paths are relative to this report; raw logs and executed argv retain their actual paths.

The API cases call `pcb_copilot.layout.footprints.resolve_footprint` directly. They do not claim the whole CLI review or release ran. Native preview is optional; its successful creation is not human visual review, approval, or fabrication release.

Harness exit: `0` (0: enabled expectations met; 1: observed behavior differs; 2: execution/preservation error).
