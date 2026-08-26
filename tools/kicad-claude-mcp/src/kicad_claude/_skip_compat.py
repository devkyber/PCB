"""Compatibility shims for kicad-skip 0.2.5 parsing gaps.

kicad-skip 0.2.5 (latest on PyPI, no newer release available) has two gaps
that break loading real-world boards:

1. It cannot parse ``(fp_text user "..." ...)`` blocks — the footprint
   text variant used for the "${REFERENCE}" auto-substitution field that
   easyeda2kicad and most real vendor footprints put on F.Fab. Its
   FootprintWrapper.__init__ assumes every ``fp_text`` child is a full
   parsed list, but for the "user" variant the underlying parser hands
   back a bare ``Symbol('user')`` instead, and ``FootprintText.__init__``
   blows up with ``AttributeError: 'Symbol' object has no attribute
   '_base_coords'`` (or an ``IndexError`` from the same code path).

2. ``FootprintCollection.__init__`` keys footprints by
   ``s.Reference.value`` unconditionally — but footprints with no
   reference designator (mounting holes, fiducials without silkscreen
   refs) legitimately have ``Reference is None``, so it crashes with
   ``AttributeError: 'NoneType' object has no attribute 'value'`` instead
   of falling back the way ``NamedElementCollection._cleanse_key``
   already does for other missing-name cases.

Both break loading any board with real fetched footprints or mounting
holes — i.e. every board in this workspace. There's no newer kicad-skip
release to pick up a fix from, so both are patched at import time to
degrade gracefully instead of crashing the whole PCB load. Reference/
Value text (the fields skip's own API depends on) are unaffected — only
the inert "user" display text and the naming of refless footprints
change behavior.

Call ``apply()`` once, before any ``skip.PCB``/``skip.Schematic`` is
constructed (server.py does this before importing the tool modules).
"""

from __future__ import annotations

import logging

logger = logging.getLogger("kicad-claude.skip_compat")

_applied = False


def apply() -> None:
    global _applied
    if _applied:
        return
    _applied = True

    from skip.pcbnew import footprint as fp_mod
    from skip.collection import NamedElementCollection

    original_init = fp_mod.FootprintWrapper.__init__

    def patched_init(self, pv):
        from skip.pcbnew.footprint import FootprintText

        # Re-run ElementWithPropertiesWrapper.__init__ + layer handler setup
        # via the original, but with a tolerant fp_text loop. Easiest way to
        # stay in sync with upstream: call original_init, then just repair
        # self.fp_text if it's missing entries due to a raised exception —
        # but original_init raises before finishing, so instead we inline
        # the same steps here with a try/except around FootprintText().
        from skip.property import ElementWithPropertiesWrapper
        from skip.pcbnew.layer import LayerPropertyHandler

        ElementWithPropertiesWrapper.__init__(self, pv)

        footprint_text = []
        for fptxt in pv.fp_text:
            try:
                footprint_text.append(FootprintText(fptxt))
            except (AttributeError, IndexError):
                logger.debug(
                    "skipping unparseable fp_text entry in footprint (skip 0.2.5 gap)"
                )

        self.fp_text = NamedElementCollection(
            self, footprint_text, lambda fptxt: fptxt.name
        )
        self._layer_handler = LayerPropertyHandler(pv.layer, self.parent)

    fp_mod.FootprintWrapper.__init__ = patched_init

    def patched_collection_init(self, parent, elements):
        from skip.collection import NamedElementCollection

        def namefetcher(s):
            ref = s.Reference
            if ref is None:
                return None
            return ref.value

        NamedElementCollection.__init__(self, parent, elements, namefetcher)

    fp_mod.FootprintCollection.__init__ = patched_collection_init

    logger.info("applied kicad-skip fp_text/reference compat patches")
