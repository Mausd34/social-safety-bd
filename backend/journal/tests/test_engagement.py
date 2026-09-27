"""Tests for likes, shares, comments and the view counter."""

import json

from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.test import TestCase

from api.models import City
from journal.models import Comment, Like, Post, PostAnalytics, Share


class EngagementFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dhaka = City.objects.create(name="Dhaka", slug="dhaka", division="Dhaka Division")
        cls.reader = User.objects.create_user(username="reader", email="reader@example.com",
                                              password="test-pass-123", first_name="Rina")
        cls.friend = User.objects.create_user(username="friend", email="friend@example.com",
                                              password="test-pass-123")
        cls.post = Post.objects.create(author=cls.reader, city=cls.dhaka,
                                       title="Canal footbridge missing a plank",
                                       body="The middle plank is gone after the flood.")
        cls.comment = Comment.objects.create(post=cls.post, author=cls.reader,
                                             body="I walked it this morning, it is unsafe.")

    def as_user(self, user):
        self.assertTrue(self.client.login(username=user.username, password="test-pass-123"))

    def get_json(self, path):
        return json.loads(self.client.get(path).content)


class LikeTests(EngagementFixture):
    def test_liking_requires_a_signed_in_user(self):
        self.assertEqual(self.client.post(f"/api/journal/posts/{self.post.pk}/like/").status_code, 401)

    def test_liking_twice_still_leaves_one_like(self):
        self.as_user(self.friend)
        self.client.post(f"/api/journal/posts/{self.post.pk}/like/")
        self.client.post(f"/api/journal/posts/{self.post.pk}/like/")
        self.assertEqual(Like.objects.filter(post=self.post).count(), 1)

    def test_a_second_click_removes_the_like(self):
        self.as_user(self.friend)
        self.client.post(f"/api/journal/posts/{self.post.pk}/like/")
        response = self.client.delete(f"/api/journal/posts/{self.post.pk}/like/")
        self.assertEqual(json.loads(response.content)["like_count"], 0)
        self.assertEqual(Like.objects.filter(post=self.post).count(), 0)

    def test_two_different_people_can_both_like(self):
        self.as_user(self.friend)
        self.client.post(f"/api/journal/posts/{self.post.pk}/like/")
        self.as_user(self.reader)
        self.client.post(f"/api/journal/posts/{self.post.pk}/like/")
        self.assertEqual(Like.objects.filter(post=self.post).count(), 2)

    def test_the_list_tells_the_reader_what_they_liked(self):
        self.as_user(self.friend)
        self.client.post(f"/api/journal/posts/{self.post.pk}/like/")
        post = self.get_json("/api/journal/posts/?q=footbridge")["results"][0]
        self.assertTrue(post["liked"])
        self.assertEqual(post["like_count"], 1)

    def test_a_like_cannot_target_a_post_and_a_comment_at_once(self):
        with self.assertRaises(IntegrityError):
            Like.objects.create(user=self.friend, post=self.post, comment=self.comment)

    def test_a_like_must_target_something(self):
        with self.assertRaises(IntegrityError):
            Like.objects.create(user=self.friend)


class CommentTests(EngagementFixture):
    def post_json(self, payload):
        return self.client.post("/api/journal/comments/", data=json.dumps(payload),
                                content_type="application/json")

    def test_commenting_requires_a_signed_in_user(self):
        self.assertEqual(self.post_json(
            {"post": self.post.pk, "body": "Not signed in."}).status_code, 401)

    def test_adds_a_comment(self):
        self.as_user(self.friend)
        response = self.post_json({"post": self.post.pk, "body": "Reported it to the ward office."})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Comment.objects.filter(post=self.post).count(), 2)

    def test_replies_must_belong_to_the_same_post(self):
        self.as_user(self.friend)
        other = Post.objects.create(author=self.reader, city=self.dhaka,
                                    title="Another report", body="Filed elsewhere.")
        response = self.post_json({"post": other.pk, "parent": self.comment.pk,
                                   "body": "Cross-posted reply."})
        self.assertEqual(response.status_code, 400)

    def test_rejects_an_empty_comment(self):
        self.as_user(self.friend)
        self.assertEqual(self.post_json({"post": self.post.pk, "body": "   "}).status_code, 400)

    def test_a_stranger_cannot_edit_someone_elses_comment(self):
        self.as_user(self.friend)
        response = self.client.patch(f"/api/journal/comments/{self.comment.pk}/",
                                     data=json.dumps({"body": "Rewritten."}),
                                     content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_the_author_can_delete_their_own_comment(self):
        self.as_user(self.reader)
        self.assertEqual(self.client.delete(f"/api/journal/comments/{self.comment.pk}/").status_code, 200)
        self.assertEqual(Comment.objects.filter(pk=self.comment.pk).count(), 0)

    def test_the_comment_count_ignores_hidden_comments(self):
        Comment.objects.create(post=self.post, author=self.friend, body="Spam.", status="HIDDEN")
        self.assertEqual(self.get_json(f"/api/journal/posts/{self.post.pk}/comments/")["count"], 1)


class ShareAndViewTests(EngagementFixture):
    def test_an_anonymous_reader_can_share(self):
        response = self.client.post(f"/api/journal/posts/{self.post.pk}/share/", data="{}",
                                    content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Share.objects.filter(post=self.post).count(), 1)

    def test_rejects_an_unknown_channel(self):
        response = self.client.post(f"/api/journal/posts/{self.post.pk}/share/",
                                    data=json.dumps({"channel": "CARRIER_PIGEON"}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_views_accumulate(self):
        for expected in (1, 2, 3):
            self.client.post(f"/api/journal/posts/{self.post.pk}/view/")
            self.assertEqual(PostAnalytics.objects.get(post=self.post).views, expected)

    def test_viewing_a_missing_post_returns_404(self):
        self.assertEqual(self.client.post("/api/journal/posts/9999/view/").status_code, 404)

