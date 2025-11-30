from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from unittest.mock import patch

from rest_framework.test import APIClient
from rest_framework import status

from .models import NewsletterSubscription
from apps.groups.models import Countries, CountryStates, Tracks
from apps.users.models import StudentProfile
from apps.resources.models import Roles, RoleAssignmentHistory


class NewsletterModelTests(TestCase):
    def test_email_normalization_and_uniqueness(self):
        # Create with uppercase email -> stored as lowercase
        sub = NewsletterSubscription.objects.create(email="USER@TEST.COM")
        self.assertEqual(sub.email, "user@test.com")

        # Using subscribe() with different casing should return same record
        obj, changed = NewsletterSubscription.subscribe("User@Test.com")
        self.assertEqual(obj.id, sub.id)
        self.assertFalse(changed)

    def test_subscribe_links_user_and_sets_timestamps(self):
        User = get_user_model()
        u = User.objects.create_user(email="member@test.com", password="x")
        sub, changed = NewsletterSubscription.subscribe(email=u.email, user=u)
        self.assertTrue(changed)
        self.assertTrue(sub.is_subscribed)
        self.assertIsNotNone(sub.subscribed_at)
        self.assertIsNone(sub.unsubscribed_at)
        self.assertEqual(sub.user, u)

        # Second call is idempotent; still linked
        sub2, changed2 = NewsletterSubscription.subscribe(email=u.email)
        self.assertEqual(sub2.id, sub.id)
        self.assertFalse(changed2)
        self.assertEqual(sub2.user, u)

    def test_unsubscribe_by_email_and_idempotence(self):
        sub, _ = NewsletterSubscription.subscribe("unsub@test.com")
        self.assertTrue(sub.is_subscribed)

        obj, changed = NewsletterSubscription.unsubscribe(
            email="unsub@test.com")
        self.assertTrue(changed)
        self.assertFalse(obj.is_subscribed)
        self.assertIsNotNone(obj.unsubscribed_at)

        # Idempotent second call
        obj2, changed2 = NewsletterSubscription.unsubscribe(
            email="unsub@test.com")
        self.assertEqual(obj2.id, obj.id)
        self.assertFalse(changed2)

    def test_unsubscribe_by_token(self):
        sub, _ = NewsletterSubscription.subscribe("bytoken@test.com")
        token = sub.unsubscribe_token
        self.assertTrue(bool(token))

        obj, changed = NewsletterSubscription.unsubscribe(token=token)
        self.assertTrue(changed)
        self.assertEqual(obj.id, sub.id)
        self.assertFalse(obj.is_subscribed)

        # Idempotent
        obj2, changed2 = NewsletterSubscription.unsubscribe(token=token)
        self.assertEqual(obj2.id, sub.id)
        self.assertFalse(changed2)

    def test_resubscribe_sets_flags(self):
        sub, _ = NewsletterSubscription.subscribe("re@test.com")
        NewsletterSubscription.unsubscribe(email=sub.email)
        sub.refresh_from_db()
        self.assertFalse(sub.is_subscribed)
        self.assertIsNotNone(sub.unsubscribed_at)

        sub2, changed = NewsletterSubscription.subscribe(sub.email)
        self.assertTrue(changed)
        self.assertTrue(sub2.is_subscribed)
        self.assertIsNone(sub2.unsubscribed_at)

    def test_unsubscribe_requires_email_or_token_raises(self):
        with self.assertRaises(Exception):
            NewsletterSubscription.unsubscribe()

    def test_unsubscribe_unknown_email_returns_none_false(self):
        obj, changed = NewsletterSubscription.unsubscribe(
            email="nope@nowhere.com")
        self.assertIsNone(obj)
        self.assertFalse(changed)

    def test_unsubscribe_token_collision_retries(self):
        # First subscription generates a token
        sub1, _ = NewsletterSubscription.subscribe("first@t.com")
        existing_token = sub1.unsubscribe_token
        self.assertTrue(existing_token)
        # Next subscribe will attempt to generate the same token then a new one
        with patch("apps.newsletter.models.get_random_string", side_effect=[existing_token, "new-unique-token"]):
            sub2, created2 = NewsletterSubscription.subscribe("second@t.com")
        self.assertTrue(created2)
        self.assertEqual(sub2.unsubscribe_token, "new-unique-token")


class NewsletterApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.admin = User.objects.create_user(
            email="admin@test.com", password="x", is_staff=True
        )
        self.user = User.objects.create_user(
            email="user@test.com", password="x", is_staff=False
        )

        # Geography and track for region derivation
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(
            country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(
            track_name="AUS-NSW", state=self.state)

        # Attach region/track to user
        self.user.state = self.state
        self.user.track = self.track
        self.user.first_name = "Alice"
        self.user.last_name = "Doe"
        self.user.save(
            update_fields=["state", "track", "first_name", "last_name"])

        # Student profile for school name
        StudentProfile.objects.create(
            user=self.user,
            pg_first_name="PG",
            pg_last_name="One",
            parent_guardian_flag=True,
            school_name="River High",
            year_lvl="10",
        )

        # Roles for active role derivation
        self.role_student, _ = Roles.objects.get_or_create(role_name="Student")
        now = timezone.now()
        RoleAssignmentHistory.objects.create(
            user=self.user,
            role=self.role_student,
            valid_from=now - timedelta(days=1),
            valid_to=None,
        )

        self.subscribe_url = reverse("newsletter-subscribe")
        self.unsubscribe_url = reverse("newsletter-unsubscribe")
        self.resubscribe_url = reverse("newsletter-resubscribe")
        self.list_url = reverse("newsletter-subscribers")

    def test_subscribe_unauthenticated_with_email(self):
        resp = self.client.post(self.subscribe_url, {
                                "email": "CAPS@EXAMPLE.COM"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(body["email"], "caps@example.com")
        self.assertTrue(body["is_subscribed"])
        self.assertTrue(body["created_or_updated"])  # created on first call

        # Idempotent second call
        resp2 = self.client.post(self.subscribe_url, {
                                 "email": "caps@example.com"}, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertFalse(resp2.json()["created_or_updated"])  # unchanged

    def test_subscribe_authenticated_without_email_uses_user_email(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(self.subscribe_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(body["email"], self.user.email)
        self.assertEqual(body["user_id"], self.user.id)

    def test_subscribe_unauthenticated_missing_email_returns_400(self):
        resp = self.client.post(self.subscribe_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsubscribe_by_email_and_token(self):
        # subscribe first
        self.client.post(self.subscribe_url, {
                         "email": "removeme@test.com"}, format="json")
        sub = NewsletterSubscription.objects.get(email="removeme@test.com")

        # By email
        r1 = self.client.post(self.unsubscribe_url, {
                              "email": "removeme@test.com"}, format="json")
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        sub.refresh_from_db()
        self.assertFalse(sub.is_subscribed)
        # Idempotent
        r1b = self.client.post(self.unsubscribe_url, {
                               "email": "removeme@test.com"}, format="json")
        self.assertEqual(r1b.status_code, status.HTTP_200_OK)

        # Resubscribe, then by token
        self.client.post(self.resubscribe_url, {
                         "email": "removeme@test.com"}, format="json")
        sub.refresh_from_db()
        self.assertTrue(sub.is_subscribed)
        r2 = self.client.post(self.unsubscribe_url, {
                              "token": sub.unsubscribe_token}, format="json")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        sub.refresh_from_db()
        self.assertFalse(sub.is_subscribed)

    def test_resubscribe_endpoint(self):
        self.client.post(self.subscribe_url, {
                         "email": "again@test.com"}, format="json")
        self.client.post(self.unsubscribe_url, {
                         "email": "again@test.com"}, format="json")
        sub = NewsletterSubscription.objects.get(email="again@test.com")
        self.assertFalse(sub.is_subscribed)

        r = self.client.post(self.resubscribe_url, {
                             "email": "again@test.com"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        sub.refresh_from_db()
        self.assertTrue(sub.is_subscribed)

    def test_resubscribe_unauthenticated_missing_email_returns_400(self):
        resp = self.client.post(self.resubscribe_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_requires_admin_and_returns_computed_fields(self):
        # Unauthenticated
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # Non-admin
        self.client.force_authenticate(self.user)
        resp2 = self.client.get(self.list_url)
        self.assertEqual(resp2.status_code, status.HTTP_403_FORBIDDEN)

        # Create records: one linked to user, one email-only
        NewsletterSubscription.subscribe(self.user.email, user=self.user)
        NewsletterSubscription.subscribe("anon@test.com")

        # Admin listing
        self.client.force_authenticate(self.admin)
        resp3 = self.client.get(self.list_url)
        self.assertEqual(resp3.status_code, status.HTTP_200_OK)
        data = resp3.json()
        # Handle paginated response (DRF generics typically paginate if set globally)
        items = data["results"] if isinstance(
            data, dict) and "results" in data else data
        emails = {row["email"] for row in items}
        self.assertIn(self.user.email, emails)
        self.assertIn("anon@test.com", emails)

        # Verify computed fields for linked user
        linked = next(r for r in items if r["email"] == self.user.email)
        self.assertEqual(linked["first_name"], "Alice")
        self.assertEqual(linked["school"], "River High")
        self.assertEqual(linked["region"], "NSW")
        self.assertIn("Student", linked.get("roles", []))

        # Email-only subscriber should have null/empty derived fields
        anon = next(r for r in items if r["email"] == "anon@test.com")
        self.assertIsNone(anon.get("first_name"))
        self.assertIsNone(anon.get("school"))
        self.assertIsNone(anon.get("region"))
        self.assertEqual(anon.get("roles"), [])

    def test_serializer_fallback_roles_query_and_region_track_fallback(self):
        # Linked user with active role exists in setUp. Remove prefetched attribute and serialize directly.
        NewsletterSubscription.subscribe(self.user.email, user=self.user)
        sub = NewsletterSubscription.objects.get(email=self.user.email)

        # Temporarily remove user.state to force region fallback via track.state
        self.user.state = None
        self.user.save(update_fields=["state"])

        data = __import__(
            "apps.newsletter.serializers", fromlist=["NewsletterSubscriptionSerializer"]
        ).NewsletterSubscriptionSerializer(sub).data
        # from track.state fallback
        self.assertEqual(data.get("region"), "NSW")
        # fallback query path should populate
        self.assertIn("Student", data.get("roles", []))

    def test_list_filters_status_and_search(self):
        # Two subs: one subscribed, one unsubscribed
        NewsletterSubscription.subscribe("keep@test.com")
        NewsletterSubscription.subscribe("drop@test.com")
        NewsletterSubscription.unsubscribe(email="drop@test.com")

        self.client.force_authenticate(self.admin)
        # Filter subscribed
        r1 = self.client.get(self.list_url + "?status=subscribed")
        items1 = (r1.json()["results"] if isinstance(
            r1.json(), dict) and "results" in r1.json() else r1.json())
        emails1 = {r["email"] for r in items1}
        self.assertIn("keep@test.com", emails1)
        self.assertNotIn("drop@test.com", emails1)

        # Filter unsubscribed
        r2 = self.client.get(self.list_url + "?status=unsubscribed")
        items2 = (r2.json()["results"] if isinstance(
            r2.json(), dict) and "results" in r2.json() else r2.json())
        emails2 = {r["email"] for r in items2}
        self.assertIn("drop@test.com", emails2)
        self.assertNotIn("keep@test.com", emails2)

        # Search by q
        r3 = self.client.get(self.list_url + "?q=keep@")
        items3 = (r3.json()["results"] if isinstance(
            r3.json(), dict) and "results" in r3.json() else r3.json())
        emails3 = {r["email"] for r in items3}
        self.assertEqual(emails3, {"keep@test.com"})

    def test_unsubscribe_endpoint_requires_email_or_token(self):
        resp = self.client.post(self.unsubscribe_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
