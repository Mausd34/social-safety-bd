"""Guard against the CSRF trap that the default test client cannot see.

Django's test client sets enforce_csrf_checks=False, so a view that forgets
@csrf_exempt passes every other test in this suite and then fails with a 403
the first time a real browser posts to it. These tests use a CSRF-enforcing
client so the browser path is actually covered.
"""

import json

from django.contrib.auth.models import User
from django.test import Client, TestCase

from api.models import City
from journal.models import Comment, Post


class CsrfSafeWriteTests(TestCase):
    """Every browser-reachable write must work without a CSRF token.

    The React client posts JSON with credentials and no token, so these views
    rely on @csrf_exempt exactly like the rest of api.views.
    """

    def setUp(self):
        self.city = City.objects.create(name="Dhaka", slug="dhaka", division="Dhaka Division")
        self.user = User.objects.create_user(username="reporter", email="reporter@example.com",
                                             password="test-pass-123")
        self.post = Post.objects.create(author=self.user, city=self.city,
                                        title="Original headline", body="Original body.")
        self.comment = Comment.objects.create(post=self.post, author=self.user, body="First comment.")
        self.client = Client(enforce_csrf_checks=True, HTTP_HOST="127.0.0.1")
        self.client.login(username="reporter", password="test-pass-123")

    def post_json(self, path, payload, method="post"):
        return getattr(self.client, method)(path, data=json.dumps(payload),
                                            content_type="application/json")

    def test_creating_a_post_survives_csrf_enforcement(self):
        response = self.post_json("/api/journal/posts/", {
            "title": "Browser written", "body": "Posted from a real browser.", "city": "dhaka"})
        self.assertEqual(response.status_code, 201)

    def test_editing_a_post_survives_csrf_enforcement(self):
        response = self.post_json(f"/api/journal/posts/{self.post.pk}/",
                                  {"title": "Edited from a browser"}, method="patch")
        self.assertEqual(response.status_code, 200)

    def test_deleting_a_post_survives_csrf_enforcement(self):
        self.assertEqual(self.client.delete(f"/api/journal/posts/{self.post.pk}/").status_code, 200)

    def test_commenting_survives_csrf_enforcement(self):
        response = self.post_json("/api/journal/comments/", {
            "post": self.post.pk, "body": "Comment from a browser."})
        self.assertEqual(response.status_code, 201)

    def test_editing_a_comment_survives_csrf_enforcement(self):
        response = self.post_json(f"/api/journal/comments/{self.comment.pk}/",
                                  {"body": "Edited comment."}, method="patch")
        self.assertEqual(response.status_code, 200)

    def test_liking_and_sharing_survive_csrf_enforcement(self):
        self.assertEqual(self.client.post(f"/api/journal/posts/{self.post.pk}/like/").status_code, 200)
        self.assertEqual(self.post_json(f"/api/journal/posts/{self.post.pk}/share/",
                                         {"channel": "LINK"}).status_code, 201)
        self.assertEqual(self.client.post(f"/api/journal/posts/{self.post.pk}/view/").status_code, 200)

    def test_view_counting_survives_csrf_enforcement_without_a_login(self):
        self.client.logout()
        self.assertEqual(self.client.post(f"/api/journal/posts/{self.post.pk}/view/").status_code, 200)

    def test_filing_a_report_survives_csrf_enforcement_without_a_login(self):
        self.client.logout()
        response = self.post_json("/api/journal/flags/", {"post": self.post.pk, "reason": "SPAM"})
        self.assertEqual(response.status_code, 201)

    def test_applying_to_be_a_journalist_survives_csrf_enforcement(self):
        response = self.post_json("/api/journal/journalist/apply/", {"statement": "I report locally."})
        self.assertEqual(response.status_code, 201)

    def test_reading_a_post_needs_no_token_either(self):
        self.client.logout()
        self.assertEqual(self.client.get(f"/api/journal/posts/{self.post.pk}/").status_code, 200)
