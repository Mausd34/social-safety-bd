"""Tests for the hotel safety directory and its moderated review queue.

Two properties matter more than anything else here, because a hotel safety
rating is a serious claim about a named business: an unverified listing must
never be readable, and an unmoderated review must never reach the public.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase

from api.models import City, Hotel, HotelReview


def post_json(client, path, payload):
    return client.post(path, data=json.dumps(payload), content_type="application/json")


def get_json(client, path):
    return json.loads(client.get(path).content)


class HotelFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dhaka = City.objects.create(
            name="Dhaka", slug="dhaka", division="Dhaka Division",
            latitude=23.8103, longitude=90.4125, reported_cases=300,
        )
        cls.chattogram = City.objects.create(
            name="Chattogram", slug="chattogram", division="Chattogram Division",
            latitude=22.3569, longitude=91.7832, reported_cases=120,
        )
        cls.verified_hotel = Hotel.objects.create(
            name="Verified Lodge", city=cls.dhaka, area="Uttara", address="Road 5",
            price_range="MID", has_24h_front_desk=True, has_cctv=True, verified=True,
        )
        cls.unverified_hotel = Hotel.objects.create(
            name="Unverified Lodge", city=cls.dhaka, verified=False,
        )
        cls.safer_hotel = Hotel.objects.create(
            name="Safer Lodge", city=cls.dhaka, area="Gulshan", price_range="PREMIUM",
            verified=True,
        )

    def add_review(self, hotel=None, **overrides):
        # ``hotel`` accepts a Hotel instance or a raw id, so a test can also aim
        # at a row that does not exist.
        target = self.verified_hotel if hotel is None else hotel
        data = {
            "hotel": getattr(target, "id", target),
            "author_name": "Asha", "rating": 5, "safety_rating": 5,
            "solo_traveller": True, "body": "I walked back to the hotel at midnight safely.",
        }
        data.update(overrides)
        return post_json(self.client, "/api/hotels/reviews/", data)

    def verify_last_review(self, **fields):
        review = HotelReview.objects.latest("id")
        for name, value in fields.items():
            setattr(review, name, value)
        review.save()
        return review

    def make_staff(self):
        return User.objects.create_user(
            username="staff@example.com", email="staff@example.com",
            password="supersecret", is_staff=True,
        )


class HotelListingTests(HotelFixture):
    def test_unverified_hotels_are_never_listed(self):
        """An unverified listing is a defamatory claim waiting to happen."""
        names = [h["name"] for h in get_json(self.client, "/api/hotels/")]
        self.assertNotIn("Unverified Lodge", names)
        self.assertIn("Verified Lodge", names)

    def test_unverified_hotel_detail_is_not_readable(self):
        response = self.client.get(f"/api/hotels/{self.unverified_hotel.id}/")
        self.assertEqual(response.status_code, 404)

    def test_unknown_hotel_returns_404(self):
        self.assertEqual(self.client.get("/api/hotels/999999/").status_code, 404)

    def test_filters_by_city(self):
        Hotel.objects.create(name="Chattogram Stay", city=self.chattogram, verified=True)
        names = [h["name"] for h in get_json(self.client, "/api/hotels/?city=chattogram")]
        self.assertEqual(names, ["Chattogram Stay"])

    def test_search_matches_name_or_area(self):
        self.assertEqual(
            [h["name"] for h in get_json(self.client, "/api/hotels/?search=Safer")],
            ["Safer Lodge"],
        )
        self.assertEqual(
            [h["name"] for h in get_json(self.client, "/api/hotels/?search=Gulshan")],
            ["Safer Lodge"],
        )

    def test_filters_by_price_range(self):
        names = [h["name"] for h in get_json(self.client, "/api/hotels/?price=premium")]
        self.assertEqual(names, ["Safer Lodge"])

    def test_an_unknown_price_filter_is_ignored(self):
        self.assertEqual(len(get_json(self.client, "/api/hotels/?price=gold-plated")), 2)

    def test_payload_carries_the_amenities_and_district(self):
        payload = get_json(self.client, f"/api/hotels/{self.verified_hotel.id}/")
        self.assertEqual(payload["city"], "Dhaka")
        self.assertEqual(payload["area"], "Uttara")
        self.assertTrue(payload["amenities"]["front_desk_24h"])
        self.assertTrue(payload["amenities"]["cctv"])
        self.assertFalse(payload["amenities"]["women_only_floor"])

    def test_a_hotel_without_a_photo_reports_none(self):
        """The UI falls back to a placeholder, so the key must be present."""
        payload = get_json(self.client, f"/api/hotels/{self.verified_hotel.id}/")
        self.assertIsNone(payload["photo"])

    def test_an_uploaded_photo_is_served_back_in_the_payload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00"
            b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        self.verified_hotel.photo.save("shot.png", SimpleUploadedFile("shot.png", png), save=True)
        payload = get_json(self.client, f"/api/hotels/{self.verified_hotel.id}/")
        self.assertTrue(payload["photo"].startswith("/media/hotel-photos/"))


class HotelReviewModerationTests(HotelFixture):
    def test_a_new_review_is_held_for_moderation(self):
        response = self.add_review()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], HotelReview.PENDING)
        self.assertEqual(HotelReview.objects.get().status, HotelReview.PENDING)

    def test_a_pending_review_never_reaches_the_public(self):
        self.add_review()
        payload = get_json(self.client, f"/api/hotels/{self.verified_hotel.id}/")
        self.assertEqual(payload["reviews"], [])
        self.assertEqual(payload["review_count"], 0)
        self.assertIsNone(payload["rating"])
        self.assertIsNone(payload["safety_rating"])

    def test_a_rejected_review_never_reaches_the_public(self):
        self.add_review()
        self.verify_last_review(status=HotelReview.REJECTED)
        payload = get_json(self.client, f"/api/hotels/{self.verified_hotel.id}/")
        self.assertEqual(payload["reviews"], [])
        self.assertEqual(payload["review_count"], 0)

    def test_verified_reviews_are_published_with_averages(self):
        self.add_review(rating=4, safety_rating=5, solo_traveller=True)
        self.verify_last_review(status=HotelReview.VERIFIED)
        self.add_review(rating=4, safety_rating=3, solo_traveller=False)
        self.verify_last_review(status=HotelReview.VERIFIED)

        payload = get_json(self.client, f"/api/hotels/{self.verified_hotel.id}/")
        self.assertEqual(payload["review_count"], 2)
        self.assertEqual(payload["rating"], 4.0)
        self.assertEqual(payload["safety_rating"], 4.0)
        self.assertEqual(payload["solo_reviews"], 1)
        self.assertEqual(len(payload["reviews"]), 2)

    def test_detail_reports_the_safety_star_breakdown(self):
        self.add_review(safety_rating=5)
        self.verify_last_review(status=HotelReview.VERIFIED)
        self.add_review(safety_rating=2)
        self.verify_last_review(status=HotelReview.VERIFIED)

        payload = get_json(self.client, f"/api/hotels/{self.verified_hotel.id}/")
        breakdown = {row["stars"]: row["count"] for row in payload["safety_breakdown"]}
        self.assertEqual(breakdown[5], 1)
        self.assertEqual(breakdown[2], 1)
        self.assertEqual([row["stars"] for row in payload["safety_breakdown"]], [5, 4, 3, 2, 1])

    def test_the_safest_stays_sort_to_the_front(self):
        self.add_review(hotel=self.verified_hotel, safety_rating=2)
        self.verify_last_review(status=HotelReview.VERIFIED)
        self.add_review(hotel=self.safer_hotel, safety_rating=5)
        self.verify_last_review(status=HotelReview.VERIFIED)

        names = [h["name"] for h in get_json(self.client, "/api/hotels/")]
        self.assertEqual(names, ["Safer Lodge", "Verified Lodge"])

    def test_min_rating_filters_out_the_unsafe_stays(self):
        self.add_review(hotel=self.verified_hotel, safety_rating=2)
        self.verify_last_review(status=HotelReview.VERIFIED)
        self.add_review(hotel=self.safer_hotel, safety_rating=5)
        self.verify_last_review(status=HotelReview.VERIFIED)

        names = [h["name"] for h in get_json(self.client, "/api/hotels/?min_rating=4")]
        self.assertEqual(names, ["Safer Lodge"])


class HotelReviewSubmissionTests(HotelFixture):
    def test_a_review_needs_a_name_body_and_both_ratings(self):
        response = self.add_review(author_name="", body="", rating=0, safety_rating=0)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(HotelReview.objects.count(), 0)

    def test_ratings_outside_one_to_five_are_refused(self):
        for bad in (0, 6, -1, "not-a-number"):
            with self.subTest(rating=bad):
                self.assertEqual(self.add_review(rating=bad).status_code, 400)

    def test_a_body_over_the_limit_is_refused(self):
        self.assertEqual(self.add_review(body="x" * 2001).status_code, 400)

    def test_an_anonymous_visitor_may_still_review(self):
        self.assertEqual(self.add_review().status_code, 201)
        self.assertIsNone(HotelReview.objects.get().user)

    def test_reviewing_an_unknown_hotel_returns_404(self):
        self.assertEqual(self.add_review(hotel=999999).status_code, 404)

    def test_reviewing_an_unverified_hotel_returns_404(self):
        self.assertEqual(self.add_review(hotel=self.unverified_hotel).status_code, 404)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get("/api/hotels/reviews/").status_code, 405)

    def test_a_signed_in_traveller_may_only_review_once(self):
        User.objects.create_user(
            username="asha@example.com", email="asha@example.com", password="supersecret"
        )
        self.client.login(username="asha@example.com", password="supersecret")
        self.assertEqual(self.add_review().status_code, 201)
        self.assertEqual(self.add_review().status_code, 409)
        self.assertEqual(HotelReview.objects.count(), 1)


class HotelModerationQueueTests(HotelFixture):
    def test_the_queue_is_closed_to_anonymous_visitors(self):
        self.assertEqual(self.client.get("/api/admin/hotels/reviews/").status_code, 403)

    def test_the_queue_is_closed_to_normal_users(self):
        User.objects.create_user(
            username="traveller@example.com", email="traveller@example.com",
            password="supersecret",
        )
        self.client.login(username="traveller@example.com", password="supersecret")
        self.assertEqual(self.client.get("/api/admin/hotels/reviews/").status_code, 403)

    def test_staff_see_pending_reviews(self):
        self.add_review()
        self.make_staff()
        self.client.login(username="staff@example.com", password="supersecret")

        queue = json.loads(self.client.get("/api/admin/hotels/reviews/").content)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["hotel"], "Verified Lodge")
        self.assertEqual(queue[0]["status"], HotelReview.PENDING)

    def test_staff_can_verify_a_review(self):
        review = self.add_review().json()["review"]
        self.make_staff()
        self.client.login(username="staff@example.com", password="supersecret")

        response = self.client.patch(
            "/api/admin/hotels/reviews/",
            data=json.dumps({"id": review["id"], "status": "VERIFIED"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(HotelReview.objects.get(pk=review["id"]).status, HotelReview.VERIFIED)

    def test_staff_cannot_set_an_unknown_status(self):
        review = self.add_review().json()["review"]
        self.make_staff()
        self.client.login(username="staff@example.com", password="supersecret")

        response = self.client.patch(
            "/api/admin/hotels/reviews/",
            data=json.dumps({"id": review["id"], "status": "SPAM"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(HotelReview.objects.get(pk=review["id"]).status, HotelReview.PENDING)

    def test_patching_an_unknown_review_returns_404(self):
        self.make_staff()
        self.client.login(username="staff@example.com", password="supersecret")
        response = self.client.patch(
            "/api/admin/hotels/reviews/",
            data=json.dumps({"id": 999999, "status": "VERIFIED"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
