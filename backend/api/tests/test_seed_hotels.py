"""Tests for the hotel rows in the synthetic seed.

A hotel safety rating is a claim about a named business, so these lock in the
same guarantees the rest of the demo data has: invented names, verified
listings, published reviews, and a stable spread of scores.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from api.models import City, Hotel, HotelReview


def seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


class SeedHotelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()

    def test_hotels_and_reviews_are_seeded(self):
        self.assertGreater(Hotel.objects.count(), 0)
        self.assertGreater(HotelReview.objects.count(), 0)

    def test_every_seeded_hotel_is_verified(self):
        """An unverified hotel is invisible, so seeding it half-done is a bug."""
        for hotel in Hotel.objects.all():
            with self.subTest(hotel=hotel.name):
                self.assertTrue(hotel.verified)

    def test_every_seeded_review_is_already_moderated(self):
        """Otherwise the directory would render empty to a first-time visitor."""
        self.assertEqual(
            HotelReview.objects.filter(status=HotelReview.PENDING).count(), 0
        )

    def test_seeded_reviews_have_no_owner_account(self):
        """They are invented, so they must not be attributed to a real login."""
        for review in HotelReview.objects.all():
            with self.subTest(review=review.pk):
                self.assertIsNone(review.user)

    def test_ratings_stay_inside_the_one_to_five_range(self):
        for review in HotelReview.objects.all():
            with self.subTest(review=review.pk):
                self.assertGreaterEqual(review.rating, 1)
                self.assertLessEqual(review.rating, 5)
                self.assertGreaterEqual(review.safety_rating, 1)
                self.assertLessEqual(review.safety_rating, 5)

    def test_every_hotel_sits_in_a_real_district(self):
        for hotel in Hotel.objects.all():
            with self.subTest(hotel=hotel.name):
                self.assertIsNotNone(hotel.city_id)
                self.assertIn(hotel.city.slug, {c.slug for c in City.objects.all()})

    def test_hotel_names_are_unique_within_a_district(self):
        keys = list(Hotel.objects.values_list("city__slug", "name"))
        self.assertEqual(len(keys), len(set(keys)))

    def test_re_running_the_seed_does_not_duplicate_hotels(self):
        before = (Hotel.objects.count(), HotelReview.objects.count())
        seed()
        after = (Hotel.objects.count(), HotelReview.objects.count())
        self.assertEqual(before, after)

    def test_re_running_the_seed_is_deterministic(self):
        fields = ("name", "city__slug", "price_range", "has_24h_front_desk")
        before = list(Hotel.objects.order_by("pk").values_list(*fields))
        seed()
        after = list(Hotel.objects.order_by("pk").values_list(*fields))
        self.assertEqual(before, after)

    def test_safety_scores_are_not_all_identical(self):
        """If every hotel tied, the safety-first sort would be meaningless."""
        spread = {h.summary()["safety_rating"] for h in Hotel.objects.all()}
        self.assertGreater(len(spread), 1)

    def test_some_hotels_are_rated_by_solo_travellers(self):
        """The solo flag is the point of the feature, so it must appear."""
        self.assertGreater(HotelReview.objects.filter(solo_traveller=True).count(), 0)


class SeedHotelResetTests(TestCase):
    def test_reset_restores_hotels_after_deleting_cities(self):
        """--reset clears City, which cascades to Hotel and its reviews."""
        seed()
        self.assertGreater(Hotel.objects.count(), 0)
        seed("--reset")
        self.assertGreater(Hotel.objects.count(), 0)
        self.assertGreater(HotelReview.objects.count(), 0)
        self.assertEqual(HotelReview.objects.filter(status=HotelReview.PENDING).count(), 0)
