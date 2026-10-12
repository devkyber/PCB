# Frozen regression inputs

The barometer, IMU and GNSS projects were retired on 2026-10-07. These fixed
inputs remain only because tests exercise native KiCad export, pin/net parity,
power-glyph geometry, footprint resolution, source hashing and failure recovery
against them. They are not active designs or manufacturing deliverables.

Tests resolve them through `tests.board_fixtures.board_source` and perform writes
only in temporary copies. Do not develop boards here or restore them under
`projects/`. Unused 3D models, local editor settings and the GNSS evaluation
document were omitted. Indexed manufacturer/reference evidence retains its exact
bytes and provenance; the tests deliberately detect changed archives.

Current owner designs live in `projects/rover-pdb` and `projects/tms-v3`.
