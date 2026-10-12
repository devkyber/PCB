# Design Basis — template

Every key part's circuit should name what it was learned from. PCB design,
like code, is mostly reading how credible people solved the same problem and
then justifying each departure. A departure nobody wrote down is
indistinguishable from an oversight — that is the whole reason this file
exists.

Fill one row per key part (any IC >=8 pins, or any plug-in module socket).
Archive the source first so the citation points at a file you still have:

    uv run pcb-copilot research PROJECT --search-plan <PART>
    uv run pcb-copilot research PROJECT --add <PART> <URL> --role datasheet

| Ref | Part | Aspect | Ours | Reference says | Source | Verdict |
|---|---|---|---|---|---|---|
| <U1> | <PART> | decoupling | <100nF> | <10uF + 100nF> | <evidence/files/FILE + url> | <Match / Deviate: reason> |

Verdict must be `Match` or `Deviate: <reason>`. "Deviate" with a real reason
is a good outcome — this file is not here to make you copy the EVM, it is
here to make the choice explicit and re-checkable.

Rules and lectures count as sources too: a `docs/DESIGN_RULES.md` rule number,
a manufacturer app note, Phil's Lab or Altium Academy layout guidance. Cite
which one.
