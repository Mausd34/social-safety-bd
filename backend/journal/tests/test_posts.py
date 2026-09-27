"""Tests for publishing, reading and editing citizen-journal posts."""

import json

from django.contrib.auth.models import User
from django.test import TestCase

from api.models import City
from journal.models import Post


class JournalFixture(TestCase):
    """A small, hand-built dataset so every assertion is exact."""

    @classmethod
    def setUpTestData(cls):
        cls.dhaka = City.objects.create(name="Dhaka", slug="dhaka", division="Dhaka Division")
        cls.chattogram = City.objects.create(name="Chattogram", slug="chattogram", division="Chattogram Division")
        cls.author = User.objects.create_user(username="reporter", email="reporter@example.com",
                                              password="test-pass-123", first_name="Reza")
        cls.other = User.objects.create_user(username="nosy", email="nosy@example.com",
                                             password="test-pass-123")
        cls.staff = User.objects.create_user(username="editor", email="editor@example.com",
                                             password="test-pass-123", is_staff=True)
        cls.post = Post.objects.create(
            author=cls.author, city=cls.dhaka, category="VIOLENCE",
            title="Street light out near the school gate", body="Parents are walking children home in the dark.")
        cls.other_post = Post.objects.create(
            author=cls.other, city=cls.chattogram, category="CYBERCRIME",
            title="Parcel scam in Agrabad", body="Courier fee demand for a parcel nobody ordered.")

    def get_json(self, path):
        return json.loads(self.client.get(path).content)

    def as_user(self, user):
        self.assertTrue(self.client.login(username=user.username, password="test-pass-123"))


class PostListTests(JournalFixture):
    def test_lists_published_posts(self):
        data = self.get_json("/api/journal/posts/")
        self.assertEqual(data["count"], 2)
        self.assertEqual([p["title"] for p in data["results"]],
                         ["Parcel scam in Agrabad", "Street light out near the school gate"])

    def test_filters_by_district_slug(self):
        titles = [p["title"] for p in self.get_json("/api/journal/posts/?city=dhaka")["results"]]
        self.assertEqual(titles, ["Street light out near the school gate"])

    def test_unknown_district_returns_nothing(self):
        self.assertEqual(self.get_json("/api/journal/posts/?city=atlantis")["results"], [])

    def test_filters_by_category(self):
        results = self.get_json("/api/journal/posts/?category=cybercrime")["results"]
        self.assertEqual([p["title"] for p in results], ["Parcel scam in Agrabad"])

    def test_search_matches_title_or_body(self):
        self.assertEqual(self.get_json("/api/journal/posts/?q=parcel")["count"], 1)
        self.assertEqual(self.get_json("/api/journal/posts/?q=dark")["count"], 1)

    def test_limit_caps_the_page(self):
        self.assertEqual(len(self.get_json("/api/journal/posts/?limit=1")["results"]), 1)

    def test_rejected_posts_are_hidden_from_readers_but_not_staff(self):
        Post.objects.filter(pk=self.post.pk).update(status=Post.REJECTED)
        self.assertEqual(self.get_json("/api/journal/posts/")["count"], 1)
        self.as_user(self.staff)
        self.assertEqual(self.get_json("/api/journal/posts/")["count"], 2)


class PostCreateTests(JournalFixture):
    def post_json(self, payload):
        return self.client.post("/api/journal/posts/", data=json.dumps(payload),
                                content_type="application/json")

    def test_requires_a_signed_in_user(self):
        self.assertEqual(self.post_json(
            {"title": "Hi", "body": "There", "city": "dhaka"}).status_code, 401)

    def test_publishes_a_post(self):
        self.as_user(self.author)
        response = self.post_json({"title": "Broken footbridge", "body": "A plank is missing over the canal.",
                                   "city": "dhaka", "category": "GENERAL"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Post.objects.filter(title="Broken footbridge").exists())

    def test_records_the_district_from_its_name(self):
        self.as_user(self.author)
        self.post_json({"title": "By name", "body": "Filed by district name.", "city": "Chattogram"})
        self.assertEqual(Post.objects.get(title="By name").city, self.chattogram)

    def test_rejects_an_unknown_district(self):
        self.as_user(self.author)
        self.assertEqual(self.post_json(
            {"title": "Nowhere", "body": "Filed nowhere.", "city": "atlantis"}).status_code, 400)

    def test_rejects_an_unknown_category(self):
        self.as_user(self.author)
        self.assertEqual(self.post_json(
            {"title": "Odd", "body": "Bad category.", "city": "dhaka", "category": "ALIEN"}).status_code, 400)

    def test_requires_a_title_and_body(self):
        self.as_user(self.author)
        self.assertEqual(self.post_json({"city": "dhaka"}).status_code, 400)


class PostEditTests(JournalFixture):
    def patch_json(self, post, payload):
        return self.client.patch(f"/api/journal/posts/{post.pk}/", data=json.dumps(payload),
                                 content_type="application/json")

    def test_author_can_edit_their_own_post(self):
        self.as_user(self.author)
        response = self.patch_json(self.post, {"title": "Street light still out near the school gate"})
        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Street light still out near the school gate")

    def test_a_stranger_cannot_edit_someone_elses_post(self):
        self.as_user(self.other)
        self.assertEqual(self.patch_json(self.post, {"title": "Hijacked"}).status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Street light out near the school gate")

    def test_an_author_cannot_reject_their_own_post(self):
        self.as_user(self.author)
        self.assertEqual(self.patch_json(self.post, {"status": "REJECTED"}).status_code, 403)

    def test_staff_can_reject_a_post_and_hide_it_from_readers(self):
        self.as_user(self.staff)
        self.assertEqual(self.patch_json(self.post, {"status": "REJECTED"}).status_code, 200)
        self.client.logout()
        self.assertEqual(self.get_json("/api/journal/posts/")["count"], 1)

    def test_author_can_delete_their_own_post(self):
        self.as_user(self.author)
        self.assertEqual(self.client.delete(f"/api/journal/posts/{self.post.pk}/").status_code, 200)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_missing_post_returns_404(self):
        self.assertEqual(self.client.get("/api/journal/posts/9999/").status_code, 404)


class FeedAndTrendingTests(JournalFixture):
    def test_feed_shows_the_requested_district(self):
        self.as_user(self.author)
        data = self.get_json("/api/journal/feed/?city=dhaka")
        self.assertEqual(data["city"], "dhaka")
        self.assertEqual([p["title"] for p in data["results"]],
                         ["Street light out near the school gate"])

    def test_trending_ranks_the_most_liked_post_first(self):
        self.as_user(self.other)
        for _ in range(3):
            self.client.post(f"/api/journal/posts/{self.post.pk}/like/")
        titles = [p["title"] for p in self.get_json("/api/journal/posts/trending/")["results"]]
        self.assertEqual(titles[0], "Street light out near the school gate")

