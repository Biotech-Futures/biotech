"""P17-5 — directional-scope controls must not survive into stored ticket text.

The defect these cover: a requester pastes U+202E RIGHT-TO-LEFT OVERRIDE into a
subject, the queue row renders in an order the database does not hold, and the
agent who reads the row and types it into the search box gets an empty queue.

Two of these tests are generated rather than hand-picked, which is deliberate.
A list of example characters is exactly the kind of test that passes while
being incomplete, so the coverage claim here is made over the whole of Unicode
and the expected answer is derived from the standard library's Unicode tables,
never from the module under test.
"""

import unicodedata

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from apps.tickets.bidi import BIDI_SCOPE_CONTROLS, strip_bidi_controls
from apps.tickets.models import SupportScope, Ticket, TicketMessage

User = get_user_model()

LIST_URL = "/api/v1/tickets/"
QUEUE = "/api/v1/admin/tickets/"

# The nine code points this filter is allowed to touch, written out here as a
# literal so that the expectation does not come from the code being tested.
# LRE, RLE, PDF, LRO, RLO, LRI, RLI, FSI, PDI.
EXPECTED_REMOVED = {
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
    0x2066, 0x2067, 0x2068, 0x2069,
}

# Bidi_Class values that open or close a directional scope.
SCOPE_CLASSES = {"LRE", "RLE", "PDF", "LRO", "RLO", "LRI", "RLI", "FSI", "PDI"}

RLO = "\u202e"   # RIGHT-TO-LEFT OVERRIDE
POP = "\u202c"   # POP DIRECTIONAL FORMATTING

# A subject shaped like the one measured on the live stack: stored as
# "…invoice<RLO>gnp.pdf<PDF> please", displayed as "…invoicefdp.png please".
ATTACK_SUBJECT = f"P17 invoice{RLO}gnp.pdf{POP} please"
CLEANED_SUBJECT = "P17 invoicegnp.pdf please"


class StripBidiControlsTests(APITestCase):
    """The pure function, checked against the whole of Unicode."""

    def test_the_unicode_tables_agree_that_exactly_nine_code_points_open_a_scope(self):
        """Guards the derivation the next test relies on."""
        derived = {
            code_point
            for code_point in range(0x110000)
            if unicodedata.bidirectional(chr(code_point)) in SCOPE_CLASSES
        }
        self.assertEqual(derived, EXPECTED_REMOVED)

    def test_every_code_point_in_unicode_survives_except_those_nine(self):
        """Generated, not hand-picked: all 1,114,112 code points, one at a time.

        This is the test that makes the "legitimate non-English text is not
        mangled" claim honest. It is not a sample of Vietnamese, Portuguese and
        Chinese characters; it is every character there is.
        """
        removed = set()
        for code_point in range(0x110000):
            character = chr(code_point)
            result = strip_bidi_controls(character)
            if result != character:
                self.assertEqual(result, "", f"U+{code_point:04X} was altered, not removed")
                removed.add(code_point)
        self.assertEqual(removed, EXPECTED_REMOVED)

    def test_the_whole_of_unicode_in_one_string_loses_exactly_those_nine(self):
        """The same claim again, on one long string rather than 1.1M short ones.

        A character-at-a-time filter and a context-sensitive one behave the same
        on single characters and differently in a sentence, so both shapes are
        checked.
        """
        everything = "".join(chr(code_point) for code_point in range(0x110000))
        survived = set(map(ord, strip_bidi_controls(everything)))
        self.assertEqual(set(range(0x110000)) - survived, EXPECTED_REMOVED)

    def test_the_characters_a_legitimate_requester_needs_are_kept(self):
        """Illustrative on top of the exhaustive test above, and a named guard.

        Each of these is a character that the obvious "strip categories
        Cc/Cf/Cs/Co/Cn" rule in apps/common/filenames.py would delete. That
        rule is right for a filename and wrong for a sentence, and this is the
        list a future refactor towards it would break.
        """
        keepers = {
            "U+200D ZERO WIDTH JOINER (family emoji)": "help \U0001F468\u200d\U0001F469\u200d\U0001F467 please",
            "U+200D + variation selector (rainbow flag)": "\U0001F3F3\ufe0f\u200d\U0001F308",
            "U+200C ZERO WIDTH NON-JOINER (Persian)": "می\u200cخواهم",
            "U+200E LEFT-TO-RIGHT MARK (mixed Hebrew)": "שלום\u200e world",
            "U+200F RIGHT-TO-LEFT MARK": "world \u200fשלום",
            "U+061C ARABIC LETTER MARK": "مرحبا\u061c 2026",
            "Vietnamese": "Xin chào, tôi cần trợ giúp",
            "Portuguese": "Não consigo aceder à minha conta",
            "Chinese": "你好，我无法登录",
        }
        for label, text in keepers.items():
            with self.subTest(label):
                self.assertEqual(strip_bidi_controls(text), text)

    def test_none_becomes_an_empty_string_and_a_non_string_is_refused(self):
        self.assertEqual(strip_bidi_controls(None), "")
        with self.assertRaises(TypeError):
            strip_bidi_controls(7)

    def test_every_occurrence_goes_not_just_the_first(self):
        """The generated sweeps above cannot see this, by construction.

        They vary WHICH code point appears, never HOW MANY times: the attack
        strings are one override plus one pop, the exhaustive test feeds one
        character at a time, and the whole-of-Unicode string holds each code
        point exactly once. So a rule that removed only the first occurrence of
        each control passed all fifteen tests while the filed defect came
        straight back — a subject pasted as "one<RLO>two<RLO>gnp.pdf<POP>"
        still reached the queue reversed and still could not be searched for.

        This is failure shape (c) from the project notes: the sample list was
        complete along the axis its author was thinking about and empty along
        the one that mattered.
        """
        rlo, pop = "\u202e", "\u202c"
        self.assertEqual(strip_bidi_controls(rlo + "a" + rlo + "b" + rlo), "ab")
        self.assertEqual(strip_bidi_controls(f"x{pop}{pop}y{pop}"), "xy")
        for control in sorted(BIDI_SCOPE_CONTROLS):
            with self.subTest(f"U+{ord(control):04X} five times"):
                self.assertEqual(strip_bidi_controls(control * 5 + "z"), "z")


class TicketBidiWritePathTests(APITestCase):
    """Every path that writes ticket text a person will later read."""

    def setUp(self):
        cache.clear()
        self.requester = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson",
        )
        self.agent = User.objects.create_user(
            email="agent@example.com", password="pass1234",
            first_name="Sam", last_name="Reid",
        )
        SupportScope.objects.create(user=self.agent)

    def create(self, subject=ATTACK_SUBJECT, body="body"):
        self.client.force_login(self.requester)
        response = self.client.post(LIST_URL, {
            "category": "help_student_group", "subject": subject, "body": body,
        })
        return response

    def test_a_pasted_override_does_not_reach_the_stored_subject(self):
        response = self.create()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ticket = Ticket.objects.get(pk=response.json()["data"]["id"])
        self.assertEqual(ticket.subject, CLEANED_SUBJECT)

    def test_a_pasted_override_does_not_reach_the_first_message_body(self):
        response = self.create(body=f"line {RLO}reversed{POP} end")
        ticket = Ticket.objects.get(pk=response.json()["data"]["id"])
        first = TicketMessage.objects.filter(ticket=ticket).order_by("id").first()
        self.assertEqual(first.body, "line reversed end")

    def test_a_pasted_override_does_not_reach_a_requesters_reply(self):
        ticket_id = self.create().json()["data"]["id"]
        response = self.client.post(
            f"{LIST_URL}{ticket_id}/messages/", {"body": f"reply {RLO}flipped{POP} end"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        last = TicketMessage.objects.filter(ticket_id=ticket_id).order_by("-id").first()
        self.assertEqual(last.body, "reply flipped end")

    def test_a_pasted_override_does_not_reach_an_agents_reply_or_internal_note(self):
        ticket_id = self.create().json()["data"]["id"]
        self.client.force_login(self.agent)
        for message_type in ("support_reply", "internal_note"):
            with self.subTest(message_type):
                response = self.client.post(
                    f"{QUEUE}{ticket_id}/messages/",
                    {"messageType": message_type, "body": f"note {RLO}flipped{POP} end"},
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                last = TicketMessage.objects.filter(ticket_id=ticket_id).order_by("-id").first()
                self.assertEqual(last.body, "note flipped end")

    def test_the_agent_can_find_the_ticket_by_the_text_the_row_shows_them(self):
        """The harm the finding measured, stated as a test.

        Before the fix the stored subject was "P17 invoice<RLO>gnp.pdf<PDF>
        please" while the row read "P17 invoicefdp.png please", and a search for
        anything in the reversed run returned nothing.
        """
        self.create()
        self.client.force_login(self.agent)
        for term in ("invoicegnp.pdf", "gnp.pdf", CLEANED_SUBJECT):
            with self.subTest(term):
                total = self.client.get(QUEUE, {"search": term}).json()["data"]["total"]
                self.assertEqual(total, 1)

    def test_a_subject_made_only_of_overrides_is_refused_rather_than_stored_empty(self):
        """The sibling defect this fix could have introduced.

        Stripping after DRF's blank check would leave an empty subject in the
        database, which is a worse row than the flipped one.
        """
        response = self.create(subject=f"{RLO}{POP}\u2066\u2069")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Asserted two ways: the literal message, and equality with the
        # answer a genuinely empty subject already gets, so the two cases
        # cannot drift apart.
        self.assertEqual(response.json()["code"], "blank")
        self.assertEqual(
            response.json()["fields"], {"subject": ["This field may not be blank."]}
        )
        self.assertEqual(response.json()["fields"], self.create(subject="").json()["fields"])
        self.assertEqual(Ticket.objects.count(), 0)

    def test_a_numeric_subject_is_still_coerced_rather_than_crashing(self):
        """Pins the ``isinstance`` guard in BidiSafeCharField.run_validation.

        DRF's CharField coerces a JSON number to its string form, so a client
        that sends ``"subject": 12345`` gets a ticket called "12345" both
        before this change and after it. Drop the guard and the strip runs on
        an int instead, raising TypeError inside the serializer and turning a
        201 into a 500 — with nothing else in the suite noticing, because
        every other case here passes a string.
        """
        self.client.force_login(self.requester)
        response = self.client.post(LIST_URL, {
            "category": "help_student_group", "subject": 12345, "body": "body",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ticket = Ticket.objects.get(pk=response.json()["data"]["id"])
        self.assertEqual(ticket.subject, "12345")

    def test_the_length_cap_counts_what_is_stored_not_what_was_pasted(self):
        """255 real characters plus two invisible controls still fits."""
        response = self.create(subject="x" * 255 + RLO + POP)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ticket = Ticket.objects.get(pk=response.json()["data"]["id"])
        self.assertEqual(ticket.subject, "x" * 255)

    def test_a_subject_that_is_genuinely_too_long_is_still_refused(self):
        response = self.create(subject="x" * 256)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_english_subjects_round_trip_unchanged(self):
        for label, subject in {
            "Vietnamese": "Không thể đăng nhập",
            "Portuguese": "Não consigo aceder à conta",
            "Chinese": "无法登录我的帐户",
            "emoji": "help \U0001F468\u200d\U0001F469\u200d\U0001F467 \U0001F1E7\U0001F1F7",
            "Hebrew with LRM": "שלום\u200e help",
        }.items():
            with self.subTest(label):
                response = self.create(subject=subject)
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                ticket = Ticket.objects.get(pk=response.json()["data"]["id"])
                self.assertEqual(ticket.subject, subject)
                ticket.delete()

    def test_the_delete_audit_snapshot_of_a_new_ticket_carries_the_clean_subject(self):
        """Only for tickets raised after this change; rows already stored keep
        whatever they were stored with."""
        from apps.audit.models import AuditLog
        from apps.tickets.services import lifecycle

        ticket = Ticket.objects.get(pk=self.create().json()["data"]["id"])
        lifecycle.soft_delete(ticket=ticket, actor=self.agent)
        row = (
            AuditLog.objects.filter(entity_id=ticket.pk, action="delete")
            .order_by("-id").first()
        )
        self.assertEqual(row.before_state["subject"], CLEANED_SUBJECT)
