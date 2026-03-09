from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.test import TestCase
from django.urls import reverse

from .models import BookStation, Item


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
			picture="book_stations/images/photos/riverside-box-lowres.svg",
			latitude=51.507351,
			longitude=-0.127758,
			location="Riverside Walk, London",
		)
		Item.objects.create(
			title="Counted Inventory Item",
			author="",
			description="",
			item_type=Item.ItemType.BOOK,
			status=Item.Status.AT_BOOK_STATION,
			current_book_station=self.station,
		)
		Item.objects.create(
			title="Taken Out Should Not Count",
			author="",
			description="",
			item_type=Item.ItemType.BOOK,
			status=Item.Status.TAKEN_OUT,
			current_book_station=None,
		)

	def test_get_list_returns_bookstations(self):
		response = self.client.get(reverse("book_stations:bookstation-list-create"))

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(len(payload), 1)
		self.assertEqual(payload[0]["readable_id"], "riverside-box")
		self.assertEqual(
			payload[0]["picture"],
			"book_stations/images/photos/riverside-box-lowres.svg",
		)

	def test_browse_stations_renders_html_list(self):
		response = self.client.get(reverse("book_stations:bookstation-list"))

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, "book_stations/bookstation_list.html")
		self.assertContains(response, "Browse Book Stations")
		self.assertContains(response, "Riverside Box")
		self.assertContains(response, "1 item")
		self.assertContains(
			response,
			reverse("book_stations:bookstation-detail", kwargs={"readable_id": self.station.readable_id}),
		)

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

	def test_get_detail_page_renders_station_information(self):
		response = self.client.get(
			reverse(
				"book_stations:bookstation-detail",
				kwargs={"readable_id": self.station.readable_id},
			)
		)

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, "book_stations/bookstation_detail.html")
		self.assertContains(response, "Book station detail")
		self.assertContains(response, "Riverside Box")
		self.assertContains(response, "Riverside Walk, London")
		self.assertContains(response, "riverside-box")
		self.assertContains(response, "Photo of Riverside Box")
		self.assertContains(response, "/static/book_stations/images/photos/riverside-box-lowres.svg")

	def test_get_detail_page_handles_station_without_picture(self):
		station_without_picture = BookStation.objects.create(
			name="No Photo Shelf",
			readable_id="no-photo-shelf",
			description="A station still waiting for a photo",
			latitude=51.500000,
			longitude=-0.100000,
			location="Elm Street",
		)

		response = self.client.get(
			reverse(
				"book_stations:bookstation-detail",
				kwargs={"readable_id": station_without_picture.readable_id},
			)
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "No station photo yet")

	def test_get_detail_returns_single_bookstation_json(self):
		response = self.client.get(
			reverse(
				"book_stations:bookstation-detail-api",
				kwargs={"readable_id": self.station.readable_id},
			)
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload["name"], "Riverside Box")
		self.assertEqual(payload["location"], "Riverside Walk, London")
		self.assertEqual(
			payload["picture"],
			"book_stations/images/photos/riverside-box-lowres.svg",
		)

	def test_post_creates_bookstation(self):
		payload = {
			"name": "Library Corner",
			"readable_id": "library-corner",
			"description": "Take one leave one shelf",
			"picture": "book_stations/images/photos/city-corner-lowres.svg",
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
		self.assertEqual(response.json()["picture"], "book_stations/images/photos/city-corner-lowres.svg")

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


class InventoryMigrationRegressionTests(TestCase):
	def test_item_table_exists_and_inventory_views_render(self):
		# If Item migrations are missing, this assertion fails with a clear message.
		self.assertIn(
			Item._meta.db_table,
			connection.introspection.table_names(),
			msg=(
				"Missing table for Item model. Ensure Item migrations are created and applied "
				"(e.g. makemigrations + migrate)."
			),
		)

		station = BookStation.objects.create(
			name="Regression Station",
			readable_id="regression-station",
			description="",
			latitude=51.500000,
			longitude=-0.120000,
			location="Test Lane",
		)

		detail_response = self.client.get(
			reverse("book_stations:bookstation-detail", kwargs={"readable_id": station.readable_id})
		)
		inventory_response = self.client.get(
			reverse("book_stations:bookstation-inventory", kwargs={"readable_id": station.readable_id})
		)

		self.assertEqual(detail_response.status_code, 200)
		self.assertEqual(inventory_response.status_code, 200)


class ItemModelTests(TestCase):
	def setUp(self):
		self.station = BookStation.objects.create(
			name="Harbor Shelf",
			readable_id="harbor-shelf",
			description="",
			latitude=51.500000,
			longitude=-0.090000,
			location="Harbor Road",
		)

	def test_requires_current_station_when_status_is_at_book_station(self):
		item = Item(
			title="The Long Way Home",
			item_type=Item.ItemType.BOOK,
			status=Item.Status.AT_BOOK_STATION,
		)

		with self.assertRaises(ValidationError):
			item.full_clean()

	def test_database_constraint_requires_current_station_when_at_book_station(self):
		with self.assertRaises(IntegrityError):
			Item.objects.create(
				title="Constraint Check",
				item_type=Item.ItemType.BOOK,
				status=Item.Status.AT_BOOK_STATION,
			)

	def test_save_defaults_last_seen_and_last_activity(self):
		item = Item.objects.create(
			title="Neighborhood Almanac",
			item_type=Item.ItemType.MAGAZINE,
			status=Item.Status.AT_BOOK_STATION,
			current_book_station=self.station,
		)

		self.assertEqual(item.last_seen_at, self.station)
		self.assertEqual(item.last_activity, date.today())


class ItemViewTests(TestCase):
	def setUp(self):
		self.station = BookStation.objects.create(
			name="South Park Box",
			readable_id="south-park-box",
			description="Near the playground",
			latitude=51.510000,
			longitude=-0.110000,
			location="South Park",
		)
		self.other_station = BookStation.objects.create(
			name="North Corner Shelf",
			readable_id="north-corner-shelf",
			description="",
			latitude=51.520000,
			longitude=-0.120000,
			location="North Corner",
		)
		self.item_here = Item.objects.create(
			title="Clean Code",
			author="Robert C. Martin",
			description="Programming book",
			item_type=Item.ItemType.BOOK,
			status=Item.Status.AT_BOOK_STATION,
			current_book_station=self.station,
			last_activity=date(2026, 2, 5),
		)
		self.item_taken = Item.objects.create(
			title="Ocean Dreams",
			author="A. Writer",
			description="",
			item_type=Item.ItemType.OTHER,
			status=Item.Status.TAKEN_OUT,
			current_book_station=None,
			last_seen_at=self.other_station,
			last_activity=date(2025, 12, 1),
		)
		self.item_other_station = Item.objects.create(
			title="Bird Atlas",
			author="C. Reader",
			description="",
			item_type=Item.ItemType.BOOK,
			status=Item.Status.AT_BOOK_STATION,
			current_book_station=self.other_station,
			last_activity=date(2026, 1, 20),
		)

	def test_get_item_list_page_renders_html(self):
		response = self.client.get(reverse("book_stations:item-list"))

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, "book_stations/item_list.html")
		self.assertContains(response, "Browse Items")
		self.assertContains(response, "Clean Code")
		self.assertContains(response, "Ocean Dreams")

	def test_get_item_detail_page_renders_item(self):
		response = self.client.get(
			reverse("book_stations:item-detail", kwargs={"item_id": self.item_here.id})
		)

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, "book_stations/item_detail.html")
		self.assertContains(response, "Item detail")
		self.assertContains(response, "Clean Code")
		self.assertContains(response, "Robert C. Martin")

	def test_get_station_inventory_page_only_shows_items_at_station(self):
		response = self.client.get(
			reverse(
				"book_stations:bookstation-inventory",
				kwargs={"readable_id": self.station.readable_id},
			)
		)

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, "book_stations/station_inventory.html")
		self.assertContains(response, "Clean Code")
		self.assertNotContains(response, "Ocean Dreams")

	def test_get_station_inventory_page_renders_dvd_cases(self):
		Item.objects.create(
			title="Blade Runner",
			author="",
			description="",
			item_type=Item.ItemType.DVD,
			status=Item.Status.AT_BOOK_STATION,
			current_book_station=self.station,
		)

		response = self.client.get(
			reverse(
				"book_stations:bookstation-inventory",
				kwargs={"readable_id": self.station.readable_id},
			)
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'class="dvd-group"', html=False)
		self.assertContains(response, 'class="dvd-case"', html=False)
		self.assertContains(response, "DVD")
		self.assertContains(response, "Blade Runner")

	def test_get_items_api_returns_items(self):
		response = self.client.get(reverse("book_stations:item-list-create"))

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(len(payload), 3)
		self.assertEqual(payload[0]["title"], "Bird Atlas")

	def test_get_items_api_filters_by_station(self):
		response = self.client.get(
			reverse("book_stations:item-list-create"),
			{"station": self.station.readable_id},
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(len(payload), 1)
		self.assertEqual(payload[0]["title"], "Clean Code")
		self.assertEqual(payload[0]["current_book_station"], "south-park-box")

	def test_get_item_detail_api_returns_item(self):
		response = self.client.get(
			reverse("book_stations:item-detail-api", kwargs={"item_id": self.item_here.id})
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload["title"], "Clean Code")
		self.assertEqual(payload["status"], Item.Status.AT_BOOK_STATION)

	def test_post_items_api_creates_item(self):
		payload = {
			"title": "Gardening Weekly",
			"author": "Garden Club",
			"description": "Issue #12",
			"item_type": Item.ItemType.MAGAZINE,
			"status": Item.Status.AT_BOOK_STATION,
			"current_book_station": self.station.readable_id,
			"last_activity": "2026-03-01",
		}

		response = self.client.post(
			reverse("book_stations:item-list-create"),
			data=payload,
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 201)
		self.assertTrue(Item.objects.filter(title="Gardening Weekly").exists())
		self.assertEqual(response.json()["current_book_station"], "south-park-box")

	def test_post_items_api_rejects_at_station_without_station(self):
		payload = {
			"title": "Broken Item",
			"item_type": Item.ItemType.BOOK,
			"status": Item.Status.AT_BOOK_STATION,
		}

		response = self.client.post(
			reverse("book_stations:item-list-create"),
			data=payload,
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("current_book_station", response.json()["errors"])
