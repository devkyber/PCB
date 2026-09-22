# Human Sign-Off — gnss-neom9n

> Legacy checklist for old scripts only. The current `pcb-copilot review`
> reads `review-profile.yaml` and hash-bound `review-signoff.yaml`, not these
> boxes. Ticking this file does not approve the current design.

Claude can get a board to *"every automated gate passes."* It cannot get it to
*"correct."* Checking a box here records that the step was **performed** — not
that it was performed correctly. That distinction is real and is not hidden.

Sign by changing `- [ ]` to `- [x]` and appending your initials and a
`YYYY-MM-DD` date. The date is **checked** by `run_gates.py` — a tick with
no date does not count:

    - [x] **Board opened in KiCad and looked at.**  — TL 2026-08-26

- [ ] **Module socket pinouts verified against the vendor card, module in hand.**
      Highest-stakes item; no tool here can check it. A sequentially-assigned
      header netlist passes ERC, passes DRC, routes cleanly, fabricates — and
      then puts a power rail into a 3.3V GPIO. Both of TMS V3's module sockets
      were wrong in exactly this way.
- [ ] **Hand-authored footprints checked against the real part.** Print 1:1 and
      offer the component to it.
- [ ] **Passive values confirmed against the part actually bought**, not the
      generic value. Crystal load caps especially.
- [ ] **`DEVIATIONS.md` reviewed** — every declared deviation agreed or rejected.
- [ ] **Board opened in KiCad and looked at.** 3D view for mechanical fit,
      silkscreen legibility, pin-1 markers.
- [ ] **Connectors are the real connector.** A part labelled "XT60" that is a
      2.54mm header passes every automated gate in this workspace.
- [ ] **Current-carrying nets sized for actual current**, not default width.
- [ ] **Mounting holes and outline checked against the mechanical assembly.**
- [ ] **BOM sourceable** — every line has an LCSC number and stock.
