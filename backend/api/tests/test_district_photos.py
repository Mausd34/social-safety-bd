"""Tests for the generated district artwork and the photo it is served on."""

import io
import json
import shutil
import tempfile

from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from PIL import Image

from api.models import City

# Generated files must never land in the real media directory, so the whole
# command runs against a throwaway MEDIA_ROOT.
TEMP_MEDIA = tempfile.mkdtemp(prefix="ssbd-test-media-")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class DistrictArtworkTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def make(self, slug="dhaka", name="Dhaka", **kwargs):
        return City.objects.create(name=name, slug=slug, division="Dhaka Division",
                                   latitude=kwargs.pop("latitude", 23.81),
                                   longitude=kwargs.pop("longitude", 90.41), **kwargs)

    def test_generates_one_image_per_district(self):
        for slug in ("dhaka", "chattogram", "sylhet"):
            self.make(slug, slug.title())
        call_command("seed_district_photos", verbosity=0)
        self.assertEqual(City.objects.filter(photo__isnull=False).count(), 3)

    def test_rerunning_is_idempotent(self):
        self.make()
        call_command("seed_district_photos", verbosity=0)
        first = City.objects.get().photo.name
        call_command("seed_district_photos", verbosity=0)
        self.assertEqual(City.objects.get().photo.name, first)
        self.assertEqual(City.objects.filter(photo__isnull=False).count(), 1)

    def test_force_regenerates(self):
        self.make()
        call_command("seed_district_photos", verbosity=0)
        call_command("seed_district_photos", force=True, verbosity=0)
        self.assertTrue(City.objects.get().photo)

    def test_can_limit_to_a_single_district(self):
        self.make("dhaka", "Dhaka")
        self.make("sylhet", "Sylhet")
        call_command("seed_district_photos", only="sylhet", verbosity=0)
        self.assertTrue(City.objects.get(slug="sylhet").photo)
        self.assertFalse(City.objects.get(slug="dhaka").photo)

    def test_image_is_a_readable_jpeg_of_the_expected_size(self):
        self.make()
        call_command("seed_district_photos", verbosity=0)
        with Image.open(City.objects.get().photo.path) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (800, 500))

    def test_district_without_coordinates_still_renders(self):
        City.objects.create(name="Nowhere", slug="nowhere", division="Test")
        call_command("seed_district_photos", verbosity=0)
        city = City.objects.get()
        self.assertTrue(city.photo)
        with Image.open(city.photo.path) as image:
            self.assertEqual(image.size, (800, 500))

    def test_output_is_deterministic_for_the_same_district(self):
        self.make()
        call_command("seed_district_photos", verbosity=0)
        field = City.objects.get().photo
        first = field.read()
        field.close()  # FieldFile caches its handle; release it for the rewrite
        call_command("seed_district_photos", force=True, verbosity=0)
        second = City.objects.get().photo
        self.assertEqual(first, second.read())
        second.close()

    def test_no_districts_is_a_warning_not_a_crash(self):
        out = io.StringIO()
        call_command("seed_district_photos", stdout=out, verbosity=0)
        self.assertIn("No districts found", out.getvalue())


class DistrictPhotoApiTests(TestCase):
    def first_city(self):
        return json.loads(Client().get("/api/cities/").content)[0]

    def test_photo_is_null_when_missing(self):
        City.objects.create(name="Dhaka", slug="dhaka", division="Dhaka Division")
        self.assertIsNone(self.first_city()["photo"])

    def test_cities_still_return_the_rest_of_the_payload(self):
        City.objects.create(name="Dhaka", slug="dhaka", division="Dhaka Division",
                            latitude=23.81, longitude=90.41, reported_cases=300)
        row = self.first_city()
        self.assertEqual(row["name"], "Dhaka")
        self.assertEqual(row["reported"], 300)
        self.assertEqual(row["latitude"], 23.81)
        self.assertEqual(row["division"], "Dhaka Division")
