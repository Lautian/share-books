from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import BookStation


class BookStationModelTests(TestCase):
	def test_string_representation_includes_name_and_readable_id(self):
		station = BookStation(
			name="Central Park Station",
			readable_id="central-park",
			description="Near the fountain",
			latitude=40.785091,
			longitude=-73.968285,
			location="Central Park, New York",
		)

		self.assertEqual(str(station), "Central Park Station (central-park)")

	def test_latitude_and_longitude_validation(self):
		station = BookStation(
			name="Out of Bounds",
			readable_id="out-of-bounds",
			description="",
			latitude=120,
			longitude=-220,
			location="Nowhere",
		)

		with self.assertRaises(ValidationError):
			station.full_clean()


class BookStationViewTests(TestCase):
	def setUp(self):
		self.station = BookStation.objects.create(
			name="Riverside Box",
			readable_id="riverside-box",
			description="Community shelf by the riverside path",
			latitude=51.507351,
			longitude=-0.127758,
			location="Riverside Walk, London",
		)

	def test_get_list_returns_bookstations(self):
		response = self.client.get(reverse("book_stations:bookstation-list-create"))

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(len(payload), 1)
		self.assertEqual(payload[0]["readable_id"], "riverside-box")

	def test_browse_stations_renders_html_list(self):
		response = self.client.get(reverse("book_stations:bookstation-list"))

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, "book_stations/bookstation_list.html")
		self.assertContains(response, "Browse Book Stations")
		self.assertContains(response, "Riverside Box")

	def test_browse_stations_supports_location_sorting(self):
		BookStation.objects.create(
			name="Cedar Shelf",
			readable_id="cedar-shelf",
			description="Shaded corner cabinet",
			latitude=51.500000,
			longitude=-0.090000,
			location="Alpha Avenue",
		)

		response = self.client.get(reverse("book_stations:bookstation-list"), {"sort": "location"})

		self.assertEqual(response.status_code, 200)
		stations = list(response.context["stations"])
		self.assertEqual(stations[0].readable_id, "cedar-shelf")

	def test_get_detail_returns_single_bookstation(self):
		response = self.client.get(
			reverse(
				"book_stations:bookstation-detail",
				kwargs={"readable_id": self.station.readable_id},
			)
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload["name"], "Riverside Box")
		self.assertEqual(payload["location"], "Riverside Walk, London")

	def test_post_creates_bookstation(self):
		payload = {
			"name": "Library Corner",
			"readable_id": "library-corner",
			"description": "Take one leave one shelf",
			"latitude": 48.856613,
			"longitude": 2.352222,
			"location": "Rue de Rivoli, Paris",
		}

		response = self.client.post(
			reverse("book_stations:bookstation-list-create"),
			data=payload,
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 201)
		self.assertTrue(BookStation.objects.filter(readable_id="library-corner").exists())

	def test_post_rejects_invalid_coordinates(self):
		payload = {
			"name": "Broken Place",
			"readable_id": "broken-place",
			"description": "",
			"latitude": 1000,
			"longitude": 2.352222,
			"location": "Unknown",
		}

		response = self.client.post(
			reverse("book_stations:bookstation-list-create"),
			data=payload,
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("latitude", response.json()["errors"])

	def test_post_rejects_duplicate_readable_id(self):
		payload = {
			"name": "Another Riverside",
			"readable_id": "riverside-box",
			"description": "duplicate id",
			"latitude": 51.500000,
			"longitude": -0.120000,
			"location": "London",
		}

		response = self.client.post(
			reverse("book_stations:bookstation-list-create"),
			data=payload,
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("readable_id", response.json()["errors"])
