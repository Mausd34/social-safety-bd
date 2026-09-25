"""Tests for the upazila picker and the anonymous help-chat lifecycle."""

import json

from django.contrib.auth.models import User
from django.test import TestCase

from api.models import ChatMessage, ChatThread, City, Upazila


def post_json(client, path, payload):
    return client.post(path, data=json.dumps(payload), content_type="application/json")


class ChatFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dhaka = City.objects.create(name="Dhaka", slug="dhaka", division="Dhaka Division")
        cls.chattogram = City.objects.create(
            name="Chattogram", slug="chattogram", division="Chattogram Division"
        )
        cls.dhanmondi = Upazila.objects.create(
            district=cls.dhaka, name="Dhanmondi", slug="dhaka-dhanmondi"
        )
        cls.panchlaish = Upazila.objects.create(
            district=cls.chattogram, name="Panchlaish", slug="chattogram-panchlaish"
        )

    def start_thread(self, **overrides):
        data = {"upazila": self.dhanmondi.id, "message": "I need help.", "subject": "Help"}
        data.update(overrides)
        return post_json(self.client, "/api/chat/threads/", data)

    def make_staff(self):
        return User.objects.create_user(
            username="staff@example.com", email="staff@example.com",
            password="supersecret", is_staff=True,
        )


class UpazilaTests(ChatFixture):
    def test_lists_upazilas(self):
        self.assertEqual(len(json.loads(self.client.get("/api/upazilas/").content)), 2)

    def test_filters_by_district(self):
        data = json.loads(self.client.get("/api/upazilas/?district=dhaka").content)
        self.assertEqual([u["name"] for u in data], ["Dhanmondi"])

    def test_search_matches_upazila_or_district_name(self):
        by_upazila = json.loads(self.client.get("/api/upazilas/?search=Panchlaish").content)
        by_district = json.loads(self.client.get("/api/upazilas/?search=Chattogram").content)
        self.assertEqual([u["name"] for u in by_upazila], ["Panchlaish"])
        self.assertEqual([u["name"] for u in by_district], ["Panchlaish"])

    def test_payload_includes_the_parent_district(self):
        data = json.loads(self.client.get("/api/upazilas/?search=Dhanmondi").content)
        self.assertEqual(data[0]["district"], "Dhaka")


class ChatLifecycleTests(ChatFixture):
    def test_anonymous_visitor_can_open_a_thread(self):
        response = self.start_thread()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["thread"]["status"], "OPEN")

    def test_the_first_message_is_recorded_as_a_user_message(self):
        self.start_thread()
        thread = ChatThread.objects.get()
        self.assertEqual(thread.messages.count(), 1)
        self.assertEqual(thread.messages.first().sender, "USER")

    def test_an_invalid_upazila_is_rejected(self):
        self.assertEqual(self.start_thread(upazila=9999).status_code, 400)

    def test_an_empty_first_message_is_rejected(self):
        self.assertEqual(self.start_thread(message="   ").status_code, 400)

    def test_an_oversized_message_is_rejected(self):
        self.assertEqual(self.start_thread(message="x" * 2001).status_code, 400)

    def test_get_returns_the_thread_with_its_messages(self):
        self.start_thread()
        payload = json.loads(
            self.client.get(f"/api/chat/threads/{ChatThread.objects.get().id}/").content
        )
        self.assertEqual(len(payload["thread"]["messages"]), 1)
        self.assertEqual(payload["thread"]["district"], "Dhaka")

    def test_an_unknown_thread_returns_404(self):
        self.assertEqual(self.client.get("/api/chat/threads/9999/").status_code, 404)

    def test_a_visitor_can_add_a_follow_up_message(self):
        self.start_thread()
        thread = ChatThread.objects.get()
        post_json(self.client, f"/api/chat/threads/{thread.id}/", {"message": "Any update?"})
        self.assertEqual(thread.messages.count(), 2)
        self.assertEqual(thread.messages.last().sender, "USER")

    def test_an_empty_follow_up_is_rejected(self):
        self.start_thread()
        thread = ChatThread.objects.get()
        response = post_json(self.client, f"/api/chat/threads/{thread.id}/", {"message": ""})
        self.assertEqual(response.status_code, 400)

    def test_messages_are_kept_in_chronological_order(self):
        self.start_thread()
        thread = ChatThread.objects.get()
        post_json(self.client, f"/api/chat/threads/{thread.id}/", {"message": "Second"})
        post_json(self.client, f"/api/chat/threads/{thread.id}/", {"message": "Third"})
        self.assertEqual(
            [m.body for m in thread.messages.all()], ["I need help.", "Second", "Third"]
        )

    def test_a_staff_reply_moves_the_thread_to_answered(self):
        self.start_thread()
        thread = ChatThread.objects.get()
        self.client.force_login(self.make_staff())
        post_json(self.client, f"/api/chat/threads/{thread.id}/", {"message": "We will call you."})
        thread.refresh_from_db()
        self.assertEqual(thread.status, "ANSWERED")
        self.assertEqual(thread.messages.last().sender, "STAFF")

    def test_a_closed_thread_rejects_further_messages(self):
        self.start_thread()
        thread = ChatThread.objects.get()
        self.client.force_login(self.make_staff())
        post_json(self.client, "/api/admin/chat/", {"id": thread.id, "status": "CLOSED"})
        self.client.logout()
        response = post_json(self.client, f"/api/chat/threads/{thread.id}/", {"message": "Hello?"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(ChatMessage.objects.count(), 1)


class StaffInboxTests(ChatFixture):
    def test_the_inbox_is_closed_to_anonymous_visitors(self):
        self.assertEqual(self.client.get("/api/admin/chat/").status_code, 403)

    def test_the_inbox_is_closed_to_normal_users(self):
        User.objects.create_user(
            username="asha@example.com", email="asha@example.com", password="supersecret"
        )
        self.client.force_login(User.objects.get(username="asha@example.com"))
        self.assertEqual(self.client.get("/api/admin/chat/").status_code, 403)

    def test_staff_can_list_open_threads(self):
        self.start_thread()
        self.client.force_login(self.make_staff())
        self.assertEqual(len(json.loads(self.client.get("/api/admin/chat/").content)), 1)

    def test_staff_can_reply_and_the_thread_becomes_answered(self):
        self.start_thread()
        thread = ChatThread.objects.get()
        self.client.force_login(self.make_staff())
        post_json(self.client, "/api/admin/chat/", {"id": thread.id, "message": "An officer will call."})
        thread.refresh_from_db()
        self.assertEqual(thread.status, "ANSWERED")
        self.assertEqual(thread.messages.last().sender, "STAFF")

    def test_staff_can_close_a_thread(self):
        self.start_thread()
        thread = ChatThread.objects.get()
        self.client.force_login(self.make_staff())
        post_json(self.client, "/api/admin/chat/", {"id": thread.id, "status": "CLOSED"})
        thread.refresh_from_db()
        self.assertEqual(thread.status, "CLOSED")

    def test_replying_to_an_unknown_thread_returns_404(self):
        self.client.force_login(self.make_staff())
        response = post_json(self.client, "/api/admin/chat/", {"id": 9999, "message": "Hi"})
        self.assertEqual(response.status_code, 404)
