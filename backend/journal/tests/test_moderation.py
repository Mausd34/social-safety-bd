"""Tests for reader reports, the staff queue and journalist verification."""

import json

from django.contrib.auth.models import User
from django.test import TestCase

from api.models import City
from journal.models import Comment, JournalistVerification, ModerationFlag, Post


class ModerationFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dhaka = City.objects.create(name="Dhaka", slug="dhaka", division="Dhaka Division")
        cls.reader = User.objects.create_user(username="reader", email="reader@example.com",
                                              password="test-pass-123", first_name="Rina")
        cls.staff = User.objects.create_user(username="editor", email="editor@example.com",
                                             password="test-pass-123", is_staff=True)
        cls.post = Post.objects.create(author=cls.reader, city=cls.dhaka,
                                       title="Unverified rumour about a local school",
                                       body="A parent shared this in a group. It may be wrong.")

    def as_user(self, user):
        self.assertTrue(self.client.login(username=user.username, password="test-pass-123"))

    def post_json(self, path, payload):
        return self.client.post(path, data=json.dumps(payload), content_type="application/json")

    def get_json(self, path):
        return json.loads(self.client.get(path).content)


class FlagTests(ModerationFixture):
    def test_an_anonymous_reader_can_report_a_post(self):
        response = self.post_json("/api/journal/flags/",
                                  {"post": self.post.pk, "reason": "MISINFORMATION",
                                   "email": "tip@example.com"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ModerationFlag.objects.count(), 1)

    def test_needs_a_reason_the_platform_recognises(self):
        self.assertEqual(self.post_json("/api/journal/flags/",
                                        {"post": self.post.pk, "reason": "BECAUSE"}).status_code, 400)

    def test_needs_something_to_report(self):
        self.assertEqual(self.post_json("/api/journal/flags/", {"reason": "SPAM"}).status_code, 400)

    def test_the_same_reader_cannot_report_twice(self):
        self.as_user(self.reader)
        payload = {"post": self.post.pk, "reason": "SPAM"}
        self.post_json("/api/journal/flags/", payload)
        self.assertEqual(self.post_json("/api/journal/flags/", payload).status_code, 200)
        self.assertEqual(ModerationFlag.objects.count(), 1)

    def test_the_queue_is_staff_only(self):
        self.assertEqual(self.client.get("/api/journal/admin/flags/").status_code, 403)
        self.as_user(self.reader)
        self.assertEqual(self.client.get("/api/journal/admin/flags/").status_code, 403)

    def test_staff_can_resolve_a_report(self):
        self.as_user(self.reader)
        self.post_json("/api/journal/flags/", {"post": self.post.pk, "reason": "SPAM"})
        self.as_user(self.staff)
        response = self.client.patch("/api/journal/admin/flags/", data=json.dumps(
            {"id": ModerationFlag.objects.get().pk, "status": "RESOLVED",
             "resolution": "Asked the author for a source."}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        flag = ModerationFlag.objects.get()
        self.assertEqual(flag.handled_by, self.staff)
        self.assertIsNotNone(flag.handled_at)

    def test_a_report_cannot_be_parked_back_in_the_queue(self):
        self.as_user(self.reader)
        self.post_json("/api/journal/flags/", {"post": self.post.pk, "reason": "SPAM"})
        self.as_user(self.staff)
        response = self.client.patch("/api/journal/admin/flags/", data=json.dumps(
            {"id": ModerationFlag.objects.get().pk, "status": "PENDING"}),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ModerationFlag.objects.get().status, "PENDING")


class JournalistTests(ModerationFixture):
    def apply_json(self, payload):
        return self.post_json("/api/journal/journalist/apply/", payload)

    def test_applying_requires_a_signed_in_user(self):
        self.assertEqual(self.apply_json({"statement": "I report on transport."}).status_code, 401)

    def test_creates_a_pending_application(self):
        self.as_user(self.reader)
        response = self.apply_json({"statement": "I report on transport.", "outlet": "District Daily"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(JournalistVerification.objects.get().status, "PENDING")

    def test_only_one_application_per_account(self):
        self.as_user(self.reader)
        self.apply_json({"statement": "First application."})
        self.assertEqual(self.apply_json({"statement": "Second application."}).status_code, 409)

    def test_needs_a_statement(self):
        self.as_user(self.reader)
        self.assertEqual(self.apply_json({"outlet": "District Daily"}).status_code, 400)

    def test_approval_is_staff_only_and_adds_the_badge(self):
        self.as_user(self.reader)
        self.apply_json({"statement": "I report on transport."})
        application = JournalistVerification.objects.get()

        self.assertEqual(self.client.patch("/api/journal/admin/journalists/", data=json.dumps(
            {"id": application.pk, "status": "APPROVED"}),
            content_type="application/json").status_code, 403)

        self.as_user(self.staff)
        self.assertEqual(self.client.patch("/api/journal/admin/journalists/", data=json.dumps(
            {"id": application.pk, "status": "APPROVED", "notes": "Press card seen."}),
            content_type="application/json").status_code, 200)

        application.refresh_from_db()
        self.assertTrue(application.is_approved)
        self.assertEqual(application.reviewed_by, self.staff)
        self.post.refresh_from_db()
        self.assertTrue(self.post.author_is_verified)

    def test_posts_from_an_unverified_author_are_not_badged(self):
        self.post.refresh_from_db()
        self.assertFalse(self.post.author_is_verified)

    def test_a_brand_new_author_is_not_badged(self):
        fresh = User.objects.create_user(username="fresh", email="fresh@example.com",
                                         password="test-pass-123")
        post = Post(author=fresh, city=self.dhaka, title="Hello", body="First post.")
        self.assertFalse(post.author_is_verified)


class SearchAndStatsTests(ModerationFixture):
    def test_search_needs_at_least_two_characters(self):
        self.assertEqual(self.client.get("/api/journal/search/?q=a").status_code, 400)

    def test_search_returns_posts_and_comments(self):
        Comment.objects.create(post=self.post, author=self.reader, body="Not about the school.")
        data = self.get_json("/api/journal/search/?q=school")
        self.assertEqual([p["title"] for p in data["posts"]], [self.post.title])
        self.assertEqual(len(data["comments"]), 1)

    def test_stats_count_only_published_posts(self):
        self.post.status = "REJECTED"
        self.post.save()
        self.assertEqual(self.get_json("/api/journal/stats/")["posts"], 0)

    def test_my_analytics_requires_a_signed_in_user(self):
        self.assertEqual(self.client.get("/api/journal/me/analytics/").status_code, 401)

    def test_my_analytics_reports_the_authors_own_posts(self):
        self.as_user(self.reader)
        data = self.get_json("/api/journal/me/analytics/")
        self.assertEqual(data["posts"], 1)
        self.assertEqual(data["published"], 1)
        self.assertFalse(data["journalist_badge"])

    def test_my_posts_still_lists_a_rejected_post_for_its_author(self):
        Post.objects.filter(pk=self.post.pk).update(status="REJECTED")
        self.as_user(self.reader)
        self.assertEqual(self.get_json("/api/journal/me/posts/")["count"], 1)

