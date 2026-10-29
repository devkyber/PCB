# USB-C power entry example

Follow the root CLAUDE.md, WORKFLOW.md and DESIGN_RULES.md. This new educational
example is an unbuilt DRAFT. Native CAD becomes authoritative after authoring;
never replay a construction recipe over subsequent owner edits. No human
fabrication approval is recorded. Preserve exact archived manufacturer evidence.

Scope is a bench-only 5 V power sink with independent CC resistors. No USB data,
PD negotiation, source-current detection, reverse protection or regulated output
is implemented. The externally guaranteed source/load budget is at most 500 mA;
the PPTC is not a 500 mA current limiter. A TVS is not a 5 V overvoltage regulator.
Do not advertise USB certification, hardware qualification or sensitive-load
protection from clean machine checks.
