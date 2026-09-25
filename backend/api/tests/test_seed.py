"""Tests for the synthetic demo seed data.

These lock in the guarantees the README makes about the demo dataset: that
seeding is deterministic and idempotent, that every district sits inside
Bangladesh's bounding box, and that ``--reset`` leaves a *complete* database
rather than a half-deleted one.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from api.management.commands.seed_demo import DISTRICTS
from api.management.commands.seed_upazilas import UPAZILAS
from api.models import Area, Case, City, Upazila

# Bounding box of Bangladesh, with a small margin of tolerance.
LAT_RANGE = (20.5, 26.7)
LON_RANGE = (87.9, 92.8)


def seed(*args):
    """Run the demo seeder with its output captured."""
    call_command("seed_demo", *args, stdout=StringIO())


class SeedDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()

    def test_seeds_all_64_districts(self):
        self.assertEqual(City.objects.count(), 64)
        self.assertEqual(City.objects.count(), len(DISTRICTS))

    def test_covers_all_eight_divisions(self):
        divisions = {c.division for c in City.objects.all()}
        self.assertEqual(len(divisions), 8)

    def test_every_district_has_valid_coordinates(self):
        for city in City.objects.all():
            with self.subTest(city=city.name):
                self.assertIsNotNone(city.latitude)
                self.assertIsNotNone(city.longitude)
                self.assertTrue(LAT_RANGE[0] <= city.latitude <= LAT_RANGE[1])
                self.assertTrue(LON_RANGE[0] <= city.longitude <= LON_RANGE[1])

    def test_district_slugs_are_unique(self):
        slugs = [c.slug for c in City.objects.all()]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_areas_and_cases_are_seeded(self):
        self.assertGreater(Area.objects.count(), 0)
        self.assertGreater(Case.objects.count(), 0)

    def test_every_case_is_labelled_synthetic(self):
        """Synthetic figures must never be mistakable for real statistics."""
        for case in Case.objects.all():
            with self.subTest(case=case.case_id):
                self.assertIn("synthetic", case.source_name.lower())

    def test_re_running_the_seed_does_not_duplicate_rows(self):
        before = (City.objects.count(), Area.objects.count(), Case.objects.count())
        seed()
        after = (City.objects.count(), Area.objects.count(), Case.objects.count())
        self.assertEqual(before, after)

    def test_re_running_the_seed_is_deterministic(self):
        before = dict(City.objects.values_list("slug", "reported_cases"))
        seed()
        after = dict(City.objects.values_list("slug", "reported_cases"))
        self.assertEqual(before, after)


class SeedResetTests(TestCase):
    """``--reset`` must leave a complete database, not a stripped one.

    Regression guard: resetting deletes every City row, which cascades to
    Upazila. The seeder reloads upazilas afterwards so the chat picker is
    never left empty.
    """

    def test_reset_restores_upazilas_after_deleting_cities(self):
        seed("--reset")
        self.assertEqual(
            Upazila.objects.count(),
            sum(len(names) for names in UPAZILAS.values()),
        )

    def test_reset_leaves_a_fully_populated_database(self):
        seed("--reset")
        self.assertEqual(City.objects.count(), 64)
        self.assertGreater(Area.objects.count(), 0)
        self.assertGreater(Case.objects.count(), 0)
        self.assertGreater(Upazila.objects.count(), 0)

    def test_reset_is_idempotent(self):
        seed("--reset")
        before = (
            City.objects.count(),
            Area.objects.count(),
            Case.objects.count(),
            Upazila.objects.count(),
        )
        seed("--reset")
        after = (
            City.objects.count(),
            Area.objects.count(),
            Case.objects.count(),
            Upazila.objects.count(),
        )
        self.assertEqual(before, after)


class SeedUpazilaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()
        call_command("seed_upazilas", stdout=StringIO())

    def test_upazilas_are_attached_to_a_district(self):
        self.assertGreater(Upazila.objects.count(), 0)
        for upazila in Upazila.objects.all():
            with self.subTest(upazila=upazila.name):
                self.assertIsNotNone(upazila.district_id)

    def test_upazila_slugs_are_unique(self):
        slugs = [u.slug for u in Upazila.objects.all()]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_running_twice_does_not_duplicate(self):
        before = Upazila.objects.count()
        call_command("seed_upazilas", stdout=StringIO())
        self.assertEqual(Upazila.objects.count(), before)
