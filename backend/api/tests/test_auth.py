"""Tests for authentication and staff-only report moderation boundaries."""

import json

from django.contrib.auth.models import User
from django.test import TestCase

from api.models import SafetyReport

CREDENTIALS = {"email": "asha@example.com", "password": "supersecret"}


def post_json(client, path, payload):
    return client.post(path, data=json.dumps(payload), content_type="application/json")


class AuthTests(TestCase):
    def setUp(self):
        User.objects.create_user(
            username="asha@example.com", email="asha@example.com", password="supersecret"
        )

    def me(self):
        return json.loads(self.client.get("/api/me/").content)

    def test_me_is_unauthenticated_by_default(self):
        self.assertFalse(self.me()["authenticated"])

    def test_register_creates_an_account_and_logs_the_user_in(self):
        response = post_json(self.client, "/api/register/", {
            "name": "Asha", "email": "new@example.com", "password": "supersecret",
        })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.me()["authenticated"])

    def test_register_rejects_a_short_password(self):
        response = post_json(self.client, "/api/register/", {
            "name": "Asha", "email": "new@example.com", "password": "short",
        })
        self.assertEqual(response.status_code, 400)

    def test_register_rejects_a_duplicate_email(self):
        response = post_json(self.client, "/api/register/", {
            "name": "Asha", "email": CREDENTIALS["email"], "password": "supersecret",
        })
        self.assertEqual(response.status_code, 409)

    def test_register_rejects_malformed_json(self):
        response = self.client.post(
            "/api/register/", data="{not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_login_with_valid_credentials_succeeds(self):
        response = post_json(self.client, "/api/login/", CREDENTIALS)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.me()["authenticated"])

    def test_login_with_a_wrong_password_is_rejected(self):
        response = post_json(self.client, "/api/login/", {**CREDENTIALS, "password": "wrong"})
        self.assertEqual(response.status_code, 401)

    def test_login_with_an_unknown_email_is_rejected(self):
        response = post_json(self.client, "/api/login/", {**CREDENTIALS, "email": "nobody@example.com"})
        self.assertEqual(response.status_code, 401)

    def test_login_rejects_a_get_request(self):
        self.assertEqual(self.client.get("/api/login/").status_code, 405)

    def test_logout_clears_the_session(self):
        post_json(self.client, "/api/login/", CREDENTIALS)
        self.client.post("/api/logout/")
        self.assertFalse(self.me()["authenticated"])


class ReportModerationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.report = SafetyReport.objects.create(
            location="Uttara", category="Harassment", description="Test report"
        )

    def make_staff(self):
        return User.objects.create_user(
            username="staff@example.com", email="staff@example.com",
            password="supersecret", is_staff=True,
        )

    def submit(self, **overrides):
        data = {"location": "Gulshan", "category": "Harassment", "description": "Test"}
        data.update(overrides)
        return self.client.post("/api/reports/", data)

    def test_anonymous_visitor_can_submit_a_report(self):
        response = self.submit(location="Uttara", description="Repeated follow-up.")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SafetyReport.objects.filter(location="Uttara").count(), 2)

    def test_submitted_reports_start_as_pending(self):
        self.submit()
        self.assertEqual(SafetyReport.objects.get(location="Gulshan").status, "PENDING")

    def test_missing_fields_are_rejected(self):
        self.assertEqual(self.client.post("/api/reports/", {"location": "Uttara"}).status_code, 400)

    def test_an_oversized_description_is_rejected(self):
        self.assertEqual(self.submit(description="x" * 5001).status_code, 400)

    def test_get_is_rejected(self):
        self.assertEqual(self.client.get("/api/reports/").status_code, 405)

    def test_moderation_list_is_closed_to_anonymous_visitors(self):
        self.assertEqual(self.client.get("/api/admin/reports/").status_code, 403)

    def test_moderation_list_is_closed_to_normal_users(self):
        User.objects.create_user(
            username="asha@example.com", email="asha@example.com", password="supersecret"
        )
        self.client.force_login(User.objects.get(username="asha@example.com"))
        self.assertEqual(self.client.get("/api/admin/reports/").status_code, 403)

    def test_staff_can_read_reports(self):
        self.client.force_login(self.make_staff())
        payload = json.loads(self.client.get("/api/admin/reports/").content)
        self.assertEqual(len(payload), 1)

    def test_staff_can_moderate_a_report(self):
        self.client.force_login(self.make_staff())
        response = self.client.patch(
            "/api/admin/reports/",
            data=json.dumps({"id": self.report.id, "status": "VERIFIED"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "VERIFIED")

    def test_staff_cannot_set_an_invalid_status(self):
        self.client.force_login(self.make_staff())
        response = self.client.patch(
            "/api/admin/reports/",
            data=json.dumps({"id": self.report.id, "status": "BANANA"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "PENDING")

    def test_moderating_an_unknown_report_returns_404(self):
        self.client.force_login(self.make_staff())
        response = self.client.patch(
            "/api/admin/reports/",
            data=json.dumps({"id": 9999, "status": "VERIFIED"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
