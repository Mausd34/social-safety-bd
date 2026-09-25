"""Tests for the public read API: health, districts, areas, cases and statistics."""

import json

from django.test import TestCase

from api.models import Area, Case, City

SYNTHETIC = "SYNTHETIC demo record - fabricated for prototyping, not real data"


class ApiFixture(TestCase):
    """A small, hand-built dataset so every assertion is exact."""

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
        cls.uttara = Area.objects.create(city=cls.dhaka, name="Uttara", reported_cases=50)
        cls.agrabad = Area.objects.create(city=cls.chattogram, name="Agrabad", reported_cases=20)

        cls.convicted = Case.objects.create(
            case_id="BD-DHK-DEMO-001", city=cls.dhaka, area=cls.uttara,
            category="SEXUAL_OFFENCE", offence_section="Section 376",
            status="CONVICTED", court_status="Judgment delivered",
            incident_date="2025-01-10", source_name=SYNTHETIC, verified=True,
        )
        cls.reported = Case.objects.create(
            case_id="BD-CTG-DEMO-001", city=cls.chattogram, area=cls.agrabad,
            category="CYBERCRIME", offence_section="Section 63",
            status="REPORTED", court_status="Investigation",
            incident_date="2025-06-01", source_name=SYNTHETIC, verified=True,
        )
        cls.unverified = Case.objects.create(
            case_id="BD-DHK-DEMO-999", city=cls.dhaka,
            category="GENERAL", status="REPORTED", court_status="Investigation",
            source_name=SYNTHETIC, verified=False,
        )

    def get_json(self, path):
        return json.loads(self.client.get(path).content)


class HealthTests(ApiFixture):
    def test_health_endpoint_reports_ok(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


class CitiesTests(ApiFixture):
    def test_lists_all_cities_with_coordinates(self):
        data = self.get_json("/api/cities/")
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["name"], "Chattogram")
        self.assertIn("latitude", data[0])
        self.assertIn("reported", data[0])


class AreasTests(ApiFixture):
    def test_returns_every_area_without_a_filter(self):
        self.assertEqual(len(self.get_json("/api/areas/")), 2)

    def test_filters_by_city_slug(self):
        self.assertEqual([a["name"] for a in self.get_json("/api/areas/?city=dhaka")], ["Uttara"])

    def test_filters_by_city_name(self):
        self.assertEqual([a["name"] for a in self.get_json("/api/areas/?city=Chattogram")], ["Agrabad"])

    def test_unknown_city_returns_an_empty_list(self):
        self.assertEqual(self.get_json("/api/areas/?city=nowhere"), [])


class CasesTests(ApiFixture):
    def test_list_hides_unverified_cases(self):
        ids = [c["case_id"] for c in self.get_json("/api/cases/")]
        self.assertIn(self.convicted.case_id, ids)
        self.assertNotIn(self.unverified.case_id, ids)

    def test_filters_by_status(self):
        data = self.get_json("/api/cases/?status=CONVICTED")
        self.assertEqual([c["case_id"] for c in data], [self.convicted.case_id])

    def test_filters_by_category(self):
        data = self.get_json("/api/cases/?category=CYBERCRIME")
        self.assertEqual([c["case_id"] for c in data], [self.reported.case_id])

    def test_filters_by_city(self):
        data = self.get_json("/api/cases/?city=dhaka")
        self.assertEqual([c["case_id"] for c in data], [self.convicted.case_id])

    def test_search_matches_offence_section(self):
        data = self.get_json("/api/cases/?search=376")
        self.assertEqual([c["case_id"] for c in data], [self.convicted.case_id])

    def test_search_matches_area_name(self):
        data = self.get_json("/api/cases/?search=Agrabad")
        self.assertEqual([c["case_id"] for c in data], [self.reported.case_id])

    def test_listing_includes_a_human_readable_category_label(self):
        labels = {c["case_id"]: c["category_label"] for c in self.get_json("/api/cases/")}
        self.assertEqual(labels[self.convicted.case_id], "Sexual offence")

    def test_results_are_ordered_newest_incident_first(self):
        dates = [c["incident_date"] for c in self.get_json("/api/cases/")]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_an_unknown_filter_value_returns_an_empty_list(self):
        self.assertEqual(self.get_json("/api/cases/?status=NOPE"), [])


class CaseDetailTests(ApiFixture):
    def test_returns_a_verified_case(self):
        response = self.client.get(f"/api/cases/{self.convicted.case_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["city"], "Dhaka")

    def test_unverified_case_is_not_readable(self):
        self.assertEqual(self.client.get(f"/api/cases/{self.unverified.case_id}/").status_code, 404)

    def test_unknown_case_returns_404(self):
        self.assertEqual(self.client.get("/api/cases/NOPE/").status_code, 404)

    def test_detail_never_exposes_personal_identifying_fields(self):
        """Case records are offence data, not people. Guard the payload shape."""
        payload = self.client.get(f"/api/cases/{self.convicted.case_id}/").json()
        for forbidden in ("name", "victim", "photo", "address", "phone"):
            self.assertNotIn(forbidden, payload)


class StatisticsTests(ApiFixture):
    def test_case_status_breakdown_counts_only_verified_cases(self):
        data = self.get_json("/api/statistics/")
        total = sum(row["count"] for row in data["case_status"])
        self.assertEqual(total, Case.objects.filter(verified=True).count())

    def test_reports_city_totals(self):
        data = self.get_json("/api/statistics/")
        self.assertEqual(data["cities"], 2)
        self.assertEqual(data["reported"], 420)
