"""Unicode bidirectional-control stripping for ticket text.

Single Responsibility: this module owns one question — which code points may a
person put into a ticket subject or a message body, given that a support agent
reads those strings off a screen and then types what they read into the queue
search box.

Why this exists
---------------
U+202E RIGHT-TO-LEFT OVERRIDE and its siblings open a directional scope that
runs to the end of the paragraph, so the text after one of them is laid out in
an order that has nothing to do with the order it is stored in. A subject
stored as ``P17RTL invoice<U+202E>gnp.pdf<U+202C> please`` reaches the queue as
the row "P17RTL invoicefdp.png please". The agent reads the row, types
"invoicefdp.png" into the search box, and gets an empty queue, because the
search is a ``subject__icontains`` against the stored bytes. The ticket is
still there; nothing on screen says why it cannot be found.

Why not CSS
-----------
The obvious remedy — render inside ``unicode-bidi: isolate`` — does nothing,
and that was measured rather than assumed. ``unicode-bidi`` governs how an
element's own run sits among its siblings; it cannot neutralise an override
embedded inside the text. All six values of the property render the string
above as "P17RTL invoicefdp.png please", and Chrome's UA stylesheet already
computes ``isolate`` on these elements anyway.

Why these nine code points, and not "every format character"
------------------------------------------------------------
``apps/common/filenames.py`` strips whole Unicode categories (Cc/Cf/Cs/Co/Cn).
That is right for a filename and wrong for a sentence a person wrote: the same
rule also deletes U+200D ZERO WIDTH JOINER, so a family emoji falls apart into
three separate people and the rainbow flag becomes a white flag beside a
rainbow; it deletes the ZERO WIDTH NON-JOINER that Persian needs; and it
deletes the LEFT-TO-RIGHT MARK that makes mixed Hebrew/Latin read correctly.
This platform has students in Vietnam, Brazil and China, and a support form is
the last place a distressed person's words should be quietly rearranged.

So the rule here is narrower: drop exactly the code points whose Unicode
Bidi_Class opens or closes a directional scope — the embeddings, the overrides
and the isolates. The directional *marks* (U+200E, U+200F, U+061C) are kept.
Their Bidi_Class is L, R and AL, the same classes ordinary letters carry, and
inserting one shifts neighbouring neutrals exactly as inserting an ordinary
letter does; they cannot reverse a run.

U+202C and U+2069 close a scope rather than open one, and on their own they
change nothing on screen — measured. They are in the set anyway, so that the
invariant this module offers is a simple one to state and to test: stored
ticket text holds no directional-scope control at all.

What this costs, and it is not nothing
--------------------------------------
Dropping the isolates and embeddings is not free for legitimate text, and the
docstring above reads as though only the *marks* carried a cost. Measured: over
168 generated strings mixing a Latin island into Hebrew, Arabic and Persian
host text, the strip changed the rendering of 72, and only 27 of those carried
an override (the attack class). The other 45 were legitimate scope controls —
the canonical ``<LRI>ID-2026<PDI>`` wrapper around an order number changes the
rendering of 3 cases in 4. A worked example: stored ``shalom <LRI>ID-2026<PDI>
olam toda`` renders left-to-right as ``הדות םלוע ID-2026 םולש`` before the strip
and ``םולש ID-2026 הדות םלוע`` after it — the first stored word moves from the
right end of the line to the left, and one right-to-left run becomes two.

That is a trade-off taken deliberately, not an oversight: a support agent has
to be able to find a ticket by the text on their screen, and no subset of these
nine can be kept without leaving a way to reverse a run. It is written down
because the suite cannot see it — every legitimate-text case in test_bidi.py
uses directional MARKS, never scope controls.

What this does not do
---------------------
It runs on the way in, so it protects rows written from now on. Rows already
in the database keep whatever they were stored with, including the subject
copied into ``audit_log.before_state`` when a ticket was soft-deleted. Cleaning
those is a data migration, and a separate decision.

It also covers only the text a ticket serializer writes. Two arms of the same
queue search are still open and are NOT closed by this module, both measured:
the requester's name and email are searched by services/queue.py and rendered
raw in the queue row, and they are written by ``POST /api/v1/registration``
(apps/users/views.py, ``AllowAny``, no serializer), which is byte-identical on
``origin/main`` and therefore not this branch's code to change. A requester who
registers as ``Minh<RLO>gnp.pdf<POP>`` produces a row that cannot be found by
the name on screen. Filed rather than fixed.

``services/handoff.py`` writes a subject and body straight onto the model for
AI-screening tickets, bypassing every serializer here. It has no caller in the
repository today (``grep -rn create_ticket_from_screening`` finds only the
definition) and the screening module is explicitly out of scope for this round,
so it is named here rather than patched.
"""

from __future__ import annotations

from rest_framework import serializers

# The nine code points whose Unicode Bidi_Class is LRE, RLE, PDF, LRO, RLO,
# LRI, RLI, FSI or PDI. Written out rather than derived from ``unicodedata`` at
# import time: the set is fixed by the standard, it is worth being able to read
# in review, and a per-character category lookup on every subject and body is a
# cost with no payer. The test suite re-derives it from ``unicodedata`` and
# fails if the two ever disagree.
BIDI_SCOPE_CONTROLS: frozenset[str] = frozenset(
    "\u202a"  # LEFT-TO-RIGHT EMBEDDING
    "\u202b"  # RIGHT-TO-LEFT EMBEDDING
    "\u202c"  # POP DIRECTIONAL FORMATTING
    "\u202d"  # LEFT-TO-RIGHT OVERRIDE
    "\u202e"  # RIGHT-TO-LEFT OVERRIDE
    "\u2066"  # LEFT-TO-RIGHT ISOLATE
    "\u2067"  # RIGHT-TO-LEFT ISOLATE
    "\u2068"  # FIRST STRONG ISOLATE
    "\u2069"  # POP DIRECTIONAL ISOLATE
)

_TRANSLATION = {ord(character): None for character in BIDI_SCOPE_CONTROLS}


def strip_bidi_controls(text: str | None) -> str:
    """Return ``text`` with every directional-scope control removed.

    Pure function: deterministic, no I/O, no settings. ``None`` is coerced to
    ``""`` so callers do not have to special-case a missing value. Non-string
    input raises ``TypeError`` rather than passing through silently, which is
    the contract ``apps.common.text.sanitize_text`` already sets in this repo.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        raise TypeError(
            f"strip_bidi_controls expects str | None, got {type(text).__name__}"
        )
    return text.translate(_TRANSLATION)


class BidiSafeCharField(serializers.CharField):
    """``CharField`` that drops directional-scope controls before validating.

    The strip runs before ``CharField.run_validation``, not after, and that
    order is the whole point. ``run_validation`` is where DRF tests for blank
    and where ``max_length`` is applied, so stripping first means a subject
    consisting only of overrides is refused with the ordinary "may not be
    blank" message instead of being saved as an empty string — which is what
    stripping in a ``validate_<field>`` hook would have done.
    """

    def run_validation(self, data=serializers.empty):
        if isinstance(data, str):
            data = strip_bidi_controls(data)
        return super().run_validation(data)
