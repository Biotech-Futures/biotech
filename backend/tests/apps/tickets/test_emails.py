import json
import re
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import TestCase, override_settings

from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketCategory,
    TicketChannel,
    TicketMessageType,
    TicketPriority,
    TicketStatus,
)
from apps.tickets.services import emails, lifecycle

User = get_user_model()


def visible_text(body: str) -> str:
    """What a person actually reads, as nearly as a test can get to it.

    Assertions about wording have to run against this and not the raw source.
    Three separate things hid the DEC-021 sentence from a substring check on
    the raw string, and only the first was found the first time:

    * whitespace — a sentence broken across two template lines is one
      sentence once the mail client collapses it;
    * markup — "you do not <strong>need</strong> to do anything" reads as one
      phrase and contains none of it as a substring;
    * case — "You do not need..." is the same sentence to a reader.

    So: strip tags, collapse whitespace, lowercase. Callers compare against
    lowercase needles.
    """
    without_tags = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", without_tags).lower()


def fold(body: str) -> str:
    """Deprecated alias, kept so existing assertions read unchanged."""
    return visible_text(body)


# The two tags that make up the "Open this enquiry" button: a VML rectangle
# for Outlook and an anchor for everything else.
CTA_TAG = re.compile(r'<(?:a\b[^>]*class="cta-link"|v:roundrect\b)[^>]*>', re.I)
HREF = re.compile(r'href="([^"]*)"', re.I)


def cta_hrefs(html: str) -> list:
    """Every address the button itself carries, read off the attribute.

    Reading the attribute rather than the document is the whole point. The
    same address is printed lower down as text a reader can copy, so
    `assertIn("/#/support/tickets/", html)` stayed green with the button's own
    href replaced by any URL at all.

    Both tags are returned, because a check that only finds the anchor says
    nothing about where Outlook sends the reader.
    """
    return [
        match.group(1)
        for tag in CTA_TAG.findall(html)
        for match in [HREF.search(tag)]
        if match
    ]


# Delimiters that mean the template engine did not consume something.
SOURCE_TOKENS = ("{#", "#}", "{%", "{{", "endcomment")

# Words that only ever appear in notes addressed to whoever maintains this.
#
# Deliberately narrow. "pending user" and "requester" were in the first draft
# and had to come out: both are user-facing vocabulary — the status label in
# the meta block of every email is literally "Pending user". A leak-detector
# that fires on legitimate copy gets loosened by the next person until it
# catches nothing, so this list only holds strings that have no business in an
# email under any wording.
INTERNAL_WORDS = ("dec-0", "deliberately", "agent who", "todo:", "fixme", "xxx")


class TicketEmailTestCase(TestCase):
    """Emails go out on transaction commit, which a TestCase never reaches on
    its own — hence captureOnCommitCallbacks around anything that should send.
    """

    def setUp(self):
        self.requester = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson",
        )
        self.agent = User.objects.create_user(
            email="agent@example.com", password="pass1234",
            first_name="Sam", last_name="Reid",
        )
        SupportScope.objects.create(user=self.agent)
        mail.outbox = []

    def make_ticket(self, **overrides):
        # Defaults rather than fixed arguments, so a subclass can raise the
        # ticket the same way with a subject or a body of its own.
        fields = {
            "category": TicketCategory.HELP_STUDENT_GROUP,
            "subject": "Cannot access group workspace",
            "body": "I get an error opening my group.",
            **overrides,
        }
        with self.captureOnCommitCallbacks(execute=True):
            ticket = lifecycle.create_ticket(user=self.requester, **fields)
        return ticket

    def quiet_ticket(self):
        """A ticket whose creation email has been cleared from the outbox."""
        ticket = self.make_ticket()
        mail.outbox = []
        return ticket

    def ticket_of(self, message):
        """The ticket an email is about, found through its subject line."""
        return Ticket.objects.get(
            ticket_number=message.subject.split("(")[1].rstrip(")")
        )

    def expected_url(self, message) -> str:
        """Where that email should point, rebuilt here rather than imported.

        Asking the module under test for the address it wrote would pass on
        any address it chose to write.
        """
        base = settings.FRONTEND_BASE_URL.rstrip("/")
        return f"{base}/#/support/tickets/{self.ticket_of(message).pk}"
    def each_email(self):
        """(label, EmailMultiAlternatives) for E1, E2 and E3."""
        mail.outbox = []
        ticket = self.make_ticket()
        yield "E1 submitted", mail.outbox[0]

        mail.outbox = []
        lifecycle.claim(ticket=ticket, actor=self.agent)
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent, body="Have a look please.",
            )
        yield "E2 reply", mail.outbox[0]

        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.resolve(ticket=ticket, actor=self.agent)
        yield "E3 resolved", mail.outbox[0]



class NoEmailLeaksItsSourceTests(TicketEmailTestCase):
    """All three emails, both parts, checked for unrendered source.

    The first version of this scanned only E2, because that is where the leak
    was found. Injecting the same multi-line ``{# #}`` into the other two
    templates showed both rendering it verbatim with the suite still green:
    one third of a critical defect covered. What went wrong is a property of
    Django's comment syntax, not of one template, so the guard has to be too.
    """

    def test_no_email_carries_template_syntax_or_developer_notes(self):
        for label, message in self.each_email():
            parts = [("text", message.body)]
            parts += [("html", body) for body, _ in message.alternatives]
            for part_name, raw in parts:
                # Folded *and* lowercased *and* stripped of tags: a mail client
                # collapses whitespace, a reader does not care about case, and
                # a banned phrase split by <strong> is still one phrase on the
                # screen. Checking the raw string misses all three.
                readable = visible_text(raw)
                with self.subTest(email=label, part=part_name):
                    for token in SOURCE_TOKENS:
                        self.assertNotIn(
                            token, readable,
                            f"unrendered template syntax {token!r} in {label} ({part_name})",
                        )
                    for word in INTERNAL_WORDS:
                        self.assertNotIn(
                            word, readable,
                            f"developer-facing wording {word!r} in {label} ({part_name})",
                        )

    def test_no_template_uses_the_single_line_comment_across_lines(self):
        """Caught at the source, before any send path has to exist.

        The render checks above only cover templates something already mails.
        This one covers the mistake itself: ``{# #}`` is single-line, Django's
        lexer does not span newlines, and a block comment written that way is
        emitted as text. ``{% comment %}`` is the multi-line form.
        """
        template_dir = Path(settings.BASE_DIR) / "apps" / "tickets" / "templates"
        offenders = []
        for path in sorted(template_dir.rglob("*.html")):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                for match in re.finditer(r"\{#", line):
                    if "#}" not in line[match.end():]:
                        offenders.append(f"{path.name}:{number}")

        self.assertEqual(
            offenders, [],
            "{# #} opened without closing on the same line — Django renders "
            f"the whole block as text. Use {{% comment %}}. Found at: {offenders}",
        )


class EveryEmailAddressesAPersonTests(TicketEmailTestCase):
    """The three emails read like a message from a team, in both halves.

    Not cosmetic. The audience is 14-to-18 year olds and the guardians who
    read over their shoulder, and three things were missing: the plain-text
    half never used the recipient's name while the HTML half did, neither half
    was signed by anybody, and the only route back to the conversation was a
    line of 12px grey text under the fold.
    """

    def test_both_halves_of_every_email_greet_the_requester_by_name(self):
        for label, message in self.each_email():
            html = message.alternatives[0][0]
            for part, raw in (("text", message.body), ("html", html)):
                with self.subTest(email=label, part=part):
                    self.assertIn("hi mia,", visible_text(raw))

    def test_a_requester_with_no_first_name_is_greeted_anyway(self):
        """An account an administrator invited and nobody completed has no
        first name at all, and "Hi ," at the top of an email reads as broken.

        The HTML half had a |default filter for this; the plain-text half
        interpolated the raw value and would have printed the empty string.
        """
        self.requester.first_name = ""
        self.requester.save(update_fields=["first_name"])
        for label, message in self.each_email():
            html = message.alternatives[0][0]
            for part, raw in (("text", message.body), ("html", html)):
                with self.subTest(email=label, part=part):
                    readable = visible_text(raw)
                    self.assertIn("hi there,", readable)
                    self.assertNotIn("hi ,", readable)

    def test_both_halves_of_every_email_are_signed_with_the_brand(self):
        """Asserts the resolved brand name, not the phrase around it.

        The first version of this test asked for "support team" as a substring
        and passed on the literal text "The {BRAND_NAME} support team" — which
        is what actually went out, because `str.format` does not recurse and
        the sign-off was a constant carrying its own placeholder. A substring
        assertion cannot tell a rendered sign-off from an unrendered one.
        """
        from apps.services.email_branding import brand_context

        brand = brand_context()["BRAND_NAME"]
        for label, message in self.each_email():
            html = message.alternatives[0][0]
            for part, raw in (("text", message.body), ("html", html)):
                with self.subTest(email=label, part=part):
                    self.assertIn(
                        f"the {brand.lower()} support team", visible_text(raw)
                    )

    def test_no_half_of_any_email_carries_an_unexpanded_placeholder(self):
        """The general form of the bug above, so the next one is caught too.

        Every context key is checked as `{KEY}` against both halves. This is
        broader than the SOURCE_TOKENS scan, which looks for template syntax:
        `{BRAND_NAME}` is not template syntax, it is a str.format field that
        nothing formatted, and it renders as ordinary text a reader sees.
        """
        from apps.tickets.services import emails as email_module

        for label, message in self.each_email():
            ticket = Ticket.objects.get(ticket_number=message.subject.split("(")[1].rstrip(")"))
            keys = email_module._context(ticket).keys()
            html = message.alternatives[0][0]
            for part, raw in (("text", message.body), ("html", html)):
                for key in keys:
                    with self.subTest(email=label, part=part, key=key):
                        self.assertNotIn(
                            "{" + key + "}", raw,
                            f"{key} was never substituted in {label} ({part})",
                        )

    def test_no_email_signs_off_with_an_agent_name(self):
        """DEC-017: nothing sent to a requester names the person handling
        their ticket. They are minors, and the portal shows support replies as
        "Support" for the same reason."""
        self.agent.first_name = "Zebediah"
        self.agent.save(update_fields=["first_name"])
        for label, message in self.each_email():
            html = message.alternatives[0][0]
            for part, raw in (("text", message.body), ("html", html)):
                with self.subTest(email=label, part=part):
                    self.assertNotIn("zebediah", visible_text(raw))

    def test_every_email_offers_the_link_as_a_button_not_as_small_print(self):
        """The anchor must carry the button styling, not the 12px grey rule
        the footnote used. Checked on the raw HTML on purpose: visible_text
        strips exactly the attributes that are the point here.

        The href is compared whole, and both tags of the button are read. The
        first version of this asked whether "/#/support/tickets/" appeared
        anywhere in the document, which the printed copy of the address under
        the button satisfies on its own: every one of these emails could have
        sent its readers to another site with the suite green.
        """
        for label, message in self.each_email():
            expected = self.expected_url(message)
            html = message.alternatives[0][0]
            with self.subTest(email=label):
                self.assertIn('class="cta-link"', html)
                hrefs = cta_hrefs(html)
                self.assertEqual(
                    len(hrefs), 2,
                    "the Outlook rectangle and the anchor should both carry "
                    f"the link, found {hrefs}",
                )
                for href in hrefs:
                    self.assertEqual(href, expected)

    def test_the_plain_text_half_still_spells_the_link_out(self):
        """A text-only client renders no button. The URL itself has to be in
        the words, or that reader has no way back to the conversation."""
        for label, message in self.each_email():
            with self.subTest(email=label):
                self.assertIn(self.expected_url(message), message.body)


class PlacesThatPrint(HTMLParser):
    """Where an email prints a string, and every style rule enclosing it.

    overflow-wrap and word-break are inherited, so a rule on any enclosing
    element counts and the whole stack of open tags is what matters. Walking
    the document is also what makes this a search for places rather than a
    check of the one place somebody wrote down: the version before it named
    two locations by hand and missed a third that had been there all along.

    Text nodes only. The address is in the button's href as well, and an
    attribute is not something a layout can be too wide for.
    """

    VOID = {"area", "base", "br", "col", "hr", "img", "input", "link", "meta"}

    def __init__(self, needle):
        super().__init__(convert_charrefs=True)
        self.needle = needle
        self.open = []
        self.places = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.open.append((tag, dict(attrs).get("style", "")))

    def handle_endtag(self, tag):
        for index in range(len(self.open) - 1, -1, -1):
            if self.open[index][0] == tag:
                del self.open[index:]
                return

    def handle_data(self, data):
        if self.needle in data:
            styles = " ".join(style for _, style in self.open)
            self.places.append(styles.replace(" ", "").lower())


class NothingInAnEmailIsWiderThanTheScreenTests(TicketEmailTestCase):
    """A string that arrives as one unbreakable word widens the whole card.

    A table is never narrower than the longest word it holds, so the 600px
    card runs off the side of a phone. Measured in Chromium at 320px: a
    requester who pasted a link into the subject took the card to 1361px and
    pushed the button's own label off the screen, and the address printed
    under the button took every email to 393px as soon as the production
    domain replaced localhost.

    Which strings those are is found and not listed. Every field a requester
    can type into is filled with one long word of its own, and the tests
    below look for wherever those words come out. The first version named the
    subject and the address by hand, and the greeting missed the cut: it is
    the account holder's own first name, a field of the same 255 characters
    the subject has, printed at the top of all three emails.

    A Django test cannot measure a layout, so it asserts the rule that was
    measured to fix it. Only these two properties shrink the intrinsic
    minimum width of the text; overflow-wrap:break-word and the legacy
    word-wrap move the line break without moving the table, which is why
    neither counts.
    """

    BREAKS_A_LONG_WORD = ("overflow-wrap:anywhere", "word-break:break-all")

    # One long word per field, each one its own so a value can be traced back
    # to where it was typed. Letters only: an escaped character would reach
    # the parser as a reference and could be handed over in two pieces.
    TYPED_BY_THE_USER = {
        "first_name": "Firstname" + "a" * 180,
        "last_name": "Lastname" + "b" * 180,
    }
    TYPED_INTO_THE_TICKET = {
        "subject": "Subject" + "c" * 180,
        "body": "Body" + "d" * 180,
    }

    def setUp(self):
        super().setUp()
        for field, word in self.TYPED_BY_THE_USER.items():
            setattr(self.requester, field, word)
        self.requester.save(update_fields=list(self.TYPED_BY_THE_USER))

    def make_ticket(self, **overrides):
        for field, word in self.TYPED_INTO_THE_TICKET.items():
            overrides.setdefault(field, word)
        return super().make_ticket(**overrides)

    def carried_from_user_input(self, ticket):
        """{context key: value} for every string a template is handed that
        holds something the requester typed.

        Read back from the database rather than from the ticket in hand, the
        way the mail does.
        """
        typed = set(self.TYPED_BY_THE_USER.values()) | set(
            self.TYPED_INTO_THE_TICKET.values()
        )
        context = emails._context(Ticket.objects.get(pk=ticket.pk))
        return {
            key: value
            for key, value in context.items()
            if isinstance(value, str) and any(word in value for word in typed)
        }

    def places_of(self, html, text):
        parser = PlacesThatPrint(text)
        parser.feed(html)
        return parser.places

    def assertBreaks(self, style, what):
        self.assertTrue(
            any(rule in style for rule in self.BREAKS_A_LONG_WORD),
            f"{what} has no rule that lets a long word break: {style!r}",
        )

    def test_the_strings_an_email_carries_from_user_input_are_still_these(self):
        """Not a list anyone has to remember to extend. Every free-text field
        is filled with a word of its own, and this is which of them reach a
        template at all. A fourth turns this red, and the test below is then
        the one that has to be made to pass.
        """
        ticket = self.make_ticket()
        self.assertEqual(
            set(self.carried_from_user_input(ticket)),
            {"TICKET_SUBJECT", "FIRST_NAME", "GREETING_NAME"},
        )

    def test_every_place_an_email_prints_one_of_them_can_break_it(self):
        """Reporting "this page will not open" by pasting the link into the
        subject is the most natural thing a student can do, and the subject
        is printed as typed. A name is stranger to paste a link into, but the
        field is the account holder's own and just as long.
        """
        for label, message in self.each_email():
            html = message.alternatives[0][0]
            carried = self.carried_from_user_input(self.ticket_of(message))
            for key, value in sorted(carried.items()):
                for style in self.places_of(html, value):
                    with self.subTest(email=label, key=key):
                        self.assertBreaks(style, f"{key} in {label}")

            # The loop above passes an email that prints none of them, so the
            # two that are on the card are named here. This list is for
            # emptiness and not for coverage: a fourth string is caught by the
            # test above, which is what sends the next person back here.
            for key in ("TICKET_SUBJECT", "GREETING_NAME"):
                with self.subTest(email=label, key=key):
                    self.assertTrue(
                        self.places_of(html, carried[key]),
                        f"{label} no longer prints {key}, so this checks nothing",
                    )

    def test_every_place_an_email_prints_the_address_can_break_it(self):
        """Nobody types this one and it still needs the rule. Every ticket
        email prints the address under the button for a reader to copy, it is
        one word by definition, and a real
        https://<subdomain>.biotechfutures.org address is long enough on its
        own.
        """
        for label, message in self.each_email():
            html = message.alternatives[0][0]
            places = self.places_of(html, self.expected_url(message))
            with self.subTest(email=label):
                self.assertTrue(places, f"{label} does not print the address")
            for style in places:
                with self.subTest(email=label):
                    self.assertBreaks(style, f"the copyable address in {label}")


class SubmissionEmailTests(TicketEmailTestCase):
    def test_submitting_sends_exactly_one_email_to_the_requester(self):
        self.make_ticket()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["mia@example.com"])

    def test_the_subject_carries_the_ticket_number(self):
        ticket = self.make_ticket()
        self.assertIn(ticket.ticket_number, mail.outbox[0].subject)

    def test_it_says_where_the_ticket_stands_whose_move_it_is_and_when_to_expect_us(self):
        ticket = self.make_ticket()
        message = mail.outbox[0]
        html = message.alternatives[0][0]
        for element in (ticket.ticket_number, "Open", "do not need to do anything",
                        "one business day"):
            self.assertIn(element, html)

    def test_there_is_a_plain_text_body_as_well_as_the_html(self):
        self.make_ticket()
        message = mail.outbox[0]
        self.assertTrue(message.body.strip())
        self.assertEqual(message.alternatives[0][1], "text/html")

    def test_nothing_is_sent_before_the_transaction_commits(self):
        # Without the commit hook the requester could hold a receipt for a
        # ticket that a rollback erased.
        lifecycle.create_ticket(
            user=self.requester,
            category=TicketCategory.ACCOUNT_ACCESS,
            subject="Uncommitted",
            body="Nothing should go out yet.",
        )
        self.assertEqual(mail.outbox, [])


class ReplyEmailTests(TicketEmailTestCase):
    def test_a_support_reply_notifies_the_requester(self):
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Looking into it.")
        self.assertEqual(len(mail.outbox), 1)

    def test_an_internal_note_notifies_nobody(self):
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_internal_note(ticket=ticket, actor=self.agent, body="Internal only.")
        self.assertEqual(mail.outbox, [])

    def test_when_we_are_waiting_on_them_the_email_says_so(self):
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        lifecycle.mark_pending(ticket=ticket, actor=self.agent)
        mail.outbox = []

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent, body="Could you send a screenshot?"
            )

        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("waiting on your answer", html)

    def test_a_reply_never_tells_the_requester_there_is_nothing_to_do(self):
        """The branch that knows nothing about what the reply asked for.

        An agent can ask a question without ticking the box, and this is the
        email that goes out when they do: the status has not moved and nothing
        was passed down, so the copy has to be true either way. It used to say
        "You do not need to do anything", which is the opposite of what those
        replies were asking for.

        Written when the admin app wrote the reply and changed the status as
        two requests, which put every "please send us X" here. That is now one
        action and those land on the pending branch, but this one still
        renders on the reply that asks in passing.
        """
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        mail.outbox = []

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent, body="Could you send a screenshot?"
            )

        html = mail.outbox[0].alternatives[0][0]
        text = mail.outbox[0].body
        # Folded, not raw. The banned sentence was already going out when this
        # assertion was written against the raw string: it sat inside a
        # multi-line {# #} block that Django does not treat as a comment, so
        # the words were split by a newline and 17 spaces and assertNotIn
        # matched nothing. A mail client collapses that whitespace, so what
        # the student read was the whole sentence. Compare what they see.
        self.assertNotIn("do not need to do anything", fold(html))
        self.assertNotIn("do not need to do anything", fold(text))
        self.assertIn("if we have asked you for anything", fold(html))

    def test_no_reply_email_leaks_template_syntax_or_developer_notes(self):
        """Both branches of E2, both parts, checked for unrendered source.

        The multi-line {# #} above did not just leak one banned sentence. It
        put the delimiters and a paragraph of internal workflow notes into a
        live email to a school student. Nothing in the suite looked at the
        rendered body for template syntax, so the only signal was reading the
        email by hand.
        """
        for pending_first in (False, True):
            with self.subTest(waiting_on_requester=pending_first):
                ticket = self.quiet_ticket()
                lifecycle.claim(ticket=ticket, actor=self.agent)
                if pending_first:
                    lifecycle.mark_pending(ticket=ticket, actor=self.agent)
                mail.outbox = []

                with self.captureOnCommitCallbacks(execute=True):
                    lifecycle.add_support_reply(
                        ticket=ticket, actor=self.agent, body="Have a look please.",
                    )

                html = fold(mail.outbox[0].alternatives[0][0])
                text = fold(mail.outbox[0].body)
                for part_name, part in (("html", html), ("text", text)):
                    for token in SOURCE_TOKENS:
                        self.assertNotIn(
                            token, part,
                            f"unrendered template syntax {token!r} in the {part_name} part",
                        )
                    for token in INTERNAL_WORDS:
                        self.assertNotIn(
                            token, part,
                            f"developer-facing wording {token!r} in the {part_name} part",
                        )

    def test_moving_a_ticket_to_pending_does_not_send_a_second_email(self):
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.mark_pending(ticket=ticket, actor=self.agent)
        self.assertEqual(mail.outbox, [])


class InternalActionsSendNothingTests(TicketEmailTestCase):
    """The three actions a requester must never be emailed about (DEC-009).

    These were on the manual checklist and nowhere else, which meant nothing
    checked them when the code changed. Making any of the three send is a
    one-line mistake, and the person it lands on is a school student who did
    not ask to hear about our internal bookkeeping.
    """

    def setUp(self):
        super().setUp()
        self.other_agent = User.objects.create_user(
            email="agent2@example.com", password="pass1234",
            first_name="Dana", last_name="Okafor",
        )
        SupportScope.objects.create(user=self.other_agent)
        self.ticket = self.quiet_ticket()
        mail.outbox = []

    def test_claiming_a_ticket_emails_nobody(self):
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.claim(ticket=self.ticket, actor=self.agent)
        self.assertEqual(mail.outbox, [])

    def test_handing_a_ticket_to_a_colleague_emails_nobody(self):
        lifecycle.claim(ticket=self.ticket, actor=self.agent)
        mail.outbox = []

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.assign(
                ticket=self.ticket, actor=self.agent, assignee=self.other_agent
            )

        self.assertEqual(mail.outbox, [])

    def test_changing_priority_emails_nobody(self):
        """Driven through the endpoint, not through ``_touch``.

        ``_touch`` is a private ORM helper; asserting on it would test a path
        no agent ever takes and would miss an email added to the priority
        branch of the PATCH view — the same trap ``mark_pending`` fell into.
        """
        SupportScope.objects.get_or_create(user=self.agent)
        self.client.force_login(self.agent)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f"/api/v1/admin/tickets/{self.ticket.pk}/",
                data=json.dumps({"priority": TicketPriority.HIGH}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.priority, TicketPriority.HIGH)
        self.assertEqual(mail.outbox, [])

    def test_deleting_a_ticket_emails_nobody(self):
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.soft_delete(ticket=self.ticket, actor=self.agent)
        self.assertEqual(mail.outbox, [])


class ResolutionEmailTests(TicketEmailTestCase):
    def test_resolving_sends_exactly_one_email(self):
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.resolve(ticket=ticket, actor=self.agent)
        self.assertEqual(len(mail.outbox), 1)

    def test_resolving_twice_still_sends_only_one(self):
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.resolve(ticket=ticket, actor=self.agent)
            lifecycle.resolve(ticket=ticket, actor=self.agent)
        self.assertEqual(len(mail.outbox), 1)

    def test_it_tells_them_replying_will_reopen_it(self):
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.resolve(ticket=ticket, actor=self.agent)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("Resolved", html)
        self.assertIn("reopen automatically", html)


class NoRecipientTests(TicketEmailTestCase):
    def test_a_ticket_with_no_requester_is_skipped_rather_than_failing(self):
        # Screening raises tickets with no requester at all. Every email in
        # the system has to step over those for their whole life, not just at
        # creation.
        ticket = self.quiet_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(
            created_by=None, channel=TicketChannel.AI_SCREENING
        )
        ticket.refresh_from_db()

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body="Reviewed.")
            lifecycle.resolve(ticket=ticket, actor=self.agent)

        self.assertEqual(mail.outbox, [])
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.RESOLVED)


class SupportSideEmailTests(TicketEmailTestCase):
    def test_agents_are_never_emailed_about_their_own_queue(self):
        # E4 and E5 in the design: deliberately not built. Agents work from
        # the queue, so mail to them would be noise nobody reads.
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.claim(ticket=ticket, actor=self.agent)
            lifecycle.assign(ticket=ticket, actor=self.agent, assignee=self.agent)
            lifecycle.add_user_reply(
                ticket=ticket, user=self.requester, body="Any news?"
            )
        recipients = [address for message in mail.outbox for address in message.to]
        self.assertNotIn("agent@example.com", recipients)


@override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
class DeliveryFailureTests(TicketEmailTestCase):
    """DEC-012.

    Marking a ticket resolved says the requester was told. When the send
    fails that is no longer true, and a log line is not where an agent looks.
    """

    def resolve_with_a_dead_relay(self, ticket):
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=RuntimeError("smtp down")
        ):
            with self.captureOnCommitCallbacks(execute=True):
                lifecycle.resolve(ticket=ticket, actor=self.agent)

    def test_a_bounced_resolution_email_does_not_undo_the_resolution(self):
        ticket = self.quiet_ticket()
        self.resolve_with_a_dead_relay(ticket)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.RESOLVED)
        self.assertIsNotNone(ticket.resolved_at)

    def test_the_failure_is_written_onto_the_timeline_as_an_internal_note(self):
        """Support sees it; the requester does not.

        The type is the whole guard. SYSTEM messages are shown to the
        requester — views.py excludes only internal notes — so writing this
        one as SYSTEM put a sentence addressed to an agent, carrying the
        requester's own email address, on the requester's own page. Asserted
        on the type rather than on the text, because the text is identical
        either way and reads perfectly well in an agent's timeline.
        """
        ticket = self.quiet_ticket()
        self.resolve_with_a_dead_relay(ticket)

        last = ticket.messages.order_by("created_at").last()
        self.assertEqual(last.message_type, TicketMessageType.INTERNAL_NOTE)
        self.assertIn("could not be delivered", last.body)
        self.assertIn("mia@example.com", last.body)

    def test_the_bounce_notice_does_not_float_the_ticket_for_the_requester(self):
        ticket = self.quiet_ticket()
        self.resolve_with_a_dead_relay(ticket)

        after = Ticket.objects.get(pk=ticket.pk)
        # resolve() moves all three clocks together, so the requester's clock
        # is still standing exactly where the resolution left it.
        self.assertEqual(after.updated_at, after.resolved_at)
        # The bounce notice landed afterwards and moved the support clock
        # only. Strictly greater is the whole point: if these were equal, the
        # notice had touched the requester's clock too.
        self.assertGreater(after.support_updated_at, after.updated_at)
        self.assertIn(
            "could not be delivered",
            ticket.messages.order_by("created_at").last().body,
        )


class DispatchGuardTests(TicketEmailTestCase):
    """_dispatch's early exits, pinned at the layer where they act.

    The no-recipient guard used to be "covered" by a test that passed with
    the guard deleted: an email built with an empty to-list is silently not
    appended to Django's outbox, so asserting on the outbox proved Django's
    behaviour, not ours. The assertion has to sit on OUR send call.
    """

    def test_a_ticket_with_no_recipient_never_reaches_the_mailer(self):
        # AI-raised tickets have created_by=None and no other address (the
        # contact_email column was deliberately not built, DEC-019③).
        ticket = self.quiet_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(created_by=None)
        ticket.refresh_from_db()

        with patch("apps.tickets.services.emails.send_async") as send:
            from apps.tickets.services import emails
            result = emails.send_ticket_resolved(ticket)

        self.assertFalse(result)
        send.assert_not_called()

    def test_e2_and_e3_subjects_carry_the_ticket_number(self):
        # Only E1's subject was pinned. The number in the subject is how a
        # requester's inbox threads the conversation, and how a reply will
        # one day be matched back to its ticket (Phase 3a) — losing it from
        # E2 or E3 breaks both silently.
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent, body="Answer.",
            )
            lifecycle.resolve(ticket=ticket, actor=self.agent)

        self.assertEqual(len(mail.outbox), 2)
        for message in mail.outbox:
            self.assertIn(ticket.ticket_number, message.subject)

    def test_every_email_has_a_real_plain_text_body(self):
        # Only E2's text part was pinned. The text part is what a
        # screen-reader-first client and strict corporate filters read; a
        # blank one is an empty email to those readers.
        ticket = self.make_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.claim(ticket=ticket, actor=self.agent)
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent, body="Answer.",
            )
            lifecycle.resolve(ticket=ticket, actor=self.agent)

        self.assertEqual(len(mail.outbox), 3)
        for message in mail.outbox:
            body = visible_text(message.body)
            self.assertIn(ticket.ticket_number.lower(), body)
            self.assertIn("/#/support/tickets/", message.body)


class BulkAssignSendsNothingTests(TicketEmailTestCase):
    """DEC-009's fourth internal action, the one the list missed.

    Claim, hand-off and priority each had a sends-nothing test; bulk assign
    is the same promise made across many tickets at once, where breaking it
    is worse by exactly that factor.
    """

    def test_bulk_assigning_emails_nobody(self):
        SupportScope.objects.get_or_create(user=self.agent)
        tickets = [self.make_ticket() for _ in range(3)]
        mail.outbox = []
        self.client.force_login(self.agent)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/admin/tickets/bulk-assign/",
                data=json.dumps({
                    "ticketIds": [t.pk for t in tickets],
                    "assigneeId": self.agent.pk,
                }),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.outbox, [])
class ReplyAndMoveToPendingEmailTests(TicketEmailTestCase):
    """The point of folding T4 into the reply: making the email tell the truth.

    ``WAITING_ON_REQUESTER`` reads the status at send time. While the admin app
    wrote the reply and changed the status as two requests, the status was
    still in_progress when the email was built, so every "could you send us a
    screenshot?" rendered the branch that does *not* say we are waiting. That
    branch of ticket_reply.html could not render in production at all.
    """

    def test_it_sends_exactly_one_email_for_the_one_action(self):
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        mail.outbox = []

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent,
                body="Could you send a screenshot?", move_to_pending=True,
            )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.requester.email])

    def test_the_email_now_says_we_are_waiting_on_them(self):
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        mail.outbox = []

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent,
                body="Could you send a screenshot?", move_to_pending=True,
            )

        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("waiting on your answer", html)
        self.assertIn("nothing further will happen until you reply", html)

    def test_the_plain_text_half_says_it_too(self):
        """A text-only client renders this instead of the HTML.

        The text alternative used to be one fixed sentence for both cases, so
        fixing only the HTML would have left half the audience without the one
        fact the whole change exists to convey.
        """
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        mail.outbox = []

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent,
                body="Could you send a screenshot?", move_to_pending=True,
            )

        text = mail.outbox[0].body
        self.assertIn("waiting on your answer", text)
        self.assertIn("nothing further will happen until you reply", text)

    def test_the_plain_text_half_keeps_the_other_wording_when_not_waiting(self):
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        mail.outbox = []

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent, body="Looking into it now."
            )

        text = mail.outbox[0].body
        self.assertNotIn("waiting on your answer", text)
        self.assertIn("if we have asked you for anything", text)

    def test_a_reply_without_the_flag_still_renders_the_other_branch(self):
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        mail.outbox = []

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent, body="Looking into it now."
            )

        html = mail.outbox[0].alternatives[0][0]
        self.assertNotIn("waiting on your answer", html)
        self.assertIn("if we have asked you for anything", html)


class ASecondReplyOnAPendingTicketTests(TicketEmailTestCase):
    """An agent who answers in full on a ticket already sitting in "pending
    user" renders the same *status* as the agent who asked the question.

    The status is the same on both, and a plain reply does not move it, so
    nothing the ticket stores separates the two. This is the path that made
    the email tell a requester we had asked them for more information on the
    reply that had just given them the answer, and it is the one the
    ``asked_for_information`` flag exists to keep out of that wording.
    """

    def second_reply(self, body):
        """The email from a plain reply sent after a "reply and move" one."""
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent,
                body="Could you send a screenshot?", move_to_pending=True,
            )
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(ticket=ticket, actor=self.agent, body=body)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        return mail.outbox[0]

    def halves(self, message):
        return (("text", message.body), ("html", message.alternatives[0][0]))

    def test_it_does_not_tell_them_we_asked_for_something(self):
        message = self.second_reply("Found it. Here is the whole answer.")
        for part, raw in self.halves(message):
            with self.subTest(part=part):
                self.assertNotIn("we have asked you", visible_text(raw))
                self.assertNotIn("more information", visible_text(raw))

    def test_it_still_says_where_the_ticket_stands(self):
        """The other half of DEC-021: this branch may not go quiet either. The
        ticket really is stopped, and nobody will pick it up until they
        reply."""
        message = self.second_reply("Found it. Here is the whole answer.")
        for part, raw in self.halves(message):
            with self.subTest(part=part):
                self.assertIn("waiting on your answer", visible_text(raw))


class TheEmailSaysWhetherThisReplyAskedForSomethingTests(TicketEmailTestCase):
    """D7-3, the whole fix rather than the half of it that stopped the bleeding.

    The "we have asked you for some more information" sentence is the point of
    the main flow: an agent ticks "I have asked them for something", and the
    student needs to know a question is waiting for them. It was taken out
    because the only input the email had was the status, and the status is the
    same on a reply that asked nothing. ``add_support_reply`` now hands the
    action down, so both sentences can be true.

    Three paths, because the third is the one that broke it: a plain reply on
    a ticket that is *already* waiting on the requester.
    """

    def halves(self, message):
        return (("text", message.body), ("html", message.alternatives[0][0]))

    def reply(self, *, body, move_to_pending=False, already_pending=False):
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        if already_pending:
            with self.captureOnCommitCallbacks(execute=True):
                lifecycle.add_support_reply(
                    ticket=ticket, actor=self.agent,
                    body="Could you send a screenshot?", move_to_pending=True,
                )
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent, body=body,
                move_to_pending=move_to_pending,
            )
        return ticket, mail.outbox[0]

    def test_asking_for_something_says_so_in_both_halves(self):
        ticket, message = self.reply(
            body="Could you send a screenshot?", move_to_pending=True,
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        for part, raw in self.halves(message):
            with self.subTest(part=part):
                readable = visible_text(raw)
                self.assertIn("we have asked you for some more information", readable)
                # The status half of the paragraph is still there. Telling
                # them a question is waiting without telling them the ticket
                # has stopped leaves out the half that says what happens next.
                self.assertIn("waiting on your answer", readable)
                self.assertIn("nothing further will happen until you reply", readable)

    def test_a_plain_reply_on_a_pending_ticket_says_no_such_thing(self):
        """The path the earlier fix could not tell apart from the one above.

        Same status, opposite action. Nothing was asked, so the email may not
        say anything was, and it still has to say the ticket is stopped —
        because it is, from the question that came before.
        """
        ticket, message = self.reply(
            body="Found it. Here is the whole answer.", already_pending=True,
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        for part, raw in self.halves(message):
            with self.subTest(part=part):
                readable = visible_text(raw)
                self.assertNotIn("we have asked you for some more information", readable)
                self.assertIn("waiting on your answer", readable)
                self.assertIn("nothing further will happen until you reply", readable)

    def test_an_ordinary_reply_says_no_such_thing_either(self):
        _, message = self.reply(body="Looking into it now.")
        for part, raw in self.halves(message):
            with self.subTest(part=part):
                readable = visible_text(raw)
                self.assertNotIn("we have asked you for some more information", readable)
                self.assertNotIn("waiting on your answer", readable)

    def test_the_wording_follows_the_action_and_not_the_ticket(self):
        """Two emails, one ticket, one status, two different paragraphs.

        The pair is what proves the branch. Asserting each email on its own
        passes with both rendering the same paragraph, which is the state of
        things this change ends. One ticket rather than two, because two
        emails about two tickets differ in their number and their link
        whatever the paragraph says, and comparing those would pass with the
        wording identical.
        """
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent,
                body="Could you send a screenshot?", move_to_pending=True,
            )
        asked = mail.outbox[-1]

        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.add_support_reply(
                ticket=ticket, actor=self.agent,
                body="Found it. Here is the whole answer.",
            )
        answered = mail.outbox[-1]

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, TicketStatus.PENDING_USER)
        self.assertNotEqual(visible_text(asked.body), visible_text(answered.body))
        self.assertNotEqual(
            visible_text(asked.alternatives[0][0]),
            visible_text(answered.alternatives[0][0]),
        )

    def test_the_status_still_has_the_last_word_on_the_stopped_sentence(self):
        """A flag on its own may not claim the ticket is waiting on anybody.

        The email is built after the transaction commits, so the requester can
        have replied in between and handed the ball back. The status is read
        at send time and is the outer test for that reason: with it moved on,
        the wording falls back to the paragraph that needs no status.
        """
        ticket = self.quiet_ticket()
        lifecycle.claim(ticket=ticket, actor=self.agent)
        mail.outbox = []

        emails.send_ticket_reply(ticket, asked_for_information=True)

        for part, raw in self.halves(mail.outbox[0]):
            with self.subTest(part=part):
                readable = visible_text(raw)
                self.assertNotIn("we have asked you for some more information", readable)
                self.assertNotIn("nothing further will happen until you reply", readable)


class SystemMessageStyleTests(TicketEmailTestCase):
    """The requester-visible strings follow the team's English style note.

    Comments in that module are not covered: they are for us, not for a
    fourteen-year-old reading a support email.
    """

    def test_no_requester_visible_system_message_uses_an_em_dash(self):
        from apps.tickets.services import system_messages

        offenders = [
            name
            for name in dir(system_messages)
            if not name.startswith("_")
            and isinstance(getattr(system_messages, name), str)
            and "—" in getattr(system_messages, name)
        ]
        self.assertEqual(
            offenders, [],
            f"em-dash parentheticals left in requester-visible copy: {offenders}",
        )


class ExpectedResponseTests(TicketEmailTestCase):
    """p51 R51-4: every notification carries status, next action and expected
    response. The third of those reached E1 only.

    Both halves of every email are checked. The plain-text body is what a
    text-only client renders and it is a separate string from the template,
    which is exactly how E2's "we are waiting on you" sentence came to exist
    in one half and not the other.
    """

    def halves(self):
        message = mail.outbox[-1]
        return message.body, message.alternatives[0][0]

    def test_e1_says_when_to_expect_a_reply(self):
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.create_ticket(
                user=self.requester,
                category=TicketCategory.HELP_STUDENT_GROUP,
                subject="A new one",
                body="Something is wrong.",
            )
        for half in self.halves():
            self.assertIn(emails.EXPECTED_REPLY, half)

    def test_e2_says_when_to_expect_a_reply_on_both_branches(self):
        for move_to_pending in (False, True):
            with self.subTest(waiting_on_requester=move_to_pending):
                ticket = self.quiet_ticket()
                with self.captureOnCommitCallbacks(execute=True):
                    lifecycle.add_support_reply(
                        ticket=ticket, actor=self.agent,
                        body="Could you send us a screenshot?",
                        move_to_pending=move_to_pending,
                    )
                for half in self.halves():
                    self.assertIn(emails.EXPECTED_REPLY, half)

    def test_e3_says_when_to_expect_a_reply_if_it_is_reopened(self):
        ticket = self.quiet_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            lifecycle.resolve(ticket=ticket, actor=self.agent)
        for half in self.halves():
            self.assertIn(emails.EXPECTED_REPLY, half)

    def test_the_three_emails_quote_one_shared_wait(self):
        """The guard against drift, which is the real risk here.

        Six bodies quoting the wait is six places to change it. They all read
        one constant, so a reviewer changing the promise changes it once. A
        literal here rather than the constant compared to itself: comparing
        the constant to itself would pass for any value it is ever given.
        """
        self.assertEqual(emails.EXPECTED_REPLY, "one business day")
