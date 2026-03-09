from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection
from django.test import TestCase
from django.urls import reverse

from .models import BookStation, Item


class BookStationModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="model-user",
            password="StrongPass123",
        )

    def test_string_representation_includes_name_and_readable_id(self):
        station = BookStation(
            name="Central Park Station",
            readable_id="central-park",
            description="Near the fountain",
            latitude=40.785091,
            longitude=-73.968285,
            location="Central Park, New York",
            added_by=self.user,
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
            added_by=self.user,
        )

        with self.assertRaises(ValidationError):
            station.full_clean()

    def test_save_generates_readable_id_when_missing(self):
        station = BookStation.objects.create(
            name="Generated Slug Station",
            description="",
            location="Somewhere",
            added_by=self.user,
        )

        self.assertEqual(station.readable_id, "generated-slug-station")


class BookStationViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="station-owner",
            password="StrongPass123",
        )
        self.station = BookStation.objects.create(
            name="Riverside Box",
            readable_id="riverside-box",
            description="Community shelf by the riverside path",
            picture="book_stations/images/photos/riverside-box-lowres.svg",
            latitude=51.507351,
            longitude=-0.127758,
            location="Riverside Walk, London",
            added_by=self.user,
        )
        Item.objects.create(
            title="Counted Inventory Item",
            author="Author",
            description="",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )
        Item.objects.create(
            title="Taken Out Should Not Count",
            author="Author",
            description="",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.TAKEN_OUT,
            current_book_station=None,
            added_by=self.user,
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
        self.assertEqual(payload[0]["added_by"], "station-owner")

    def test_browse_stations_renders_html_list(self):
        response = self.client.get(reverse("book_stations:bookstation-list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "book_stations/bookstation_list.html")
        self.assertContains(response, "Browse Book Stations")
        self.assertContains(response, "Riverside Box")
        self.assertContains(response, "1 item")
        self.assertContains(
            response,
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": self.station.readable_id},
            ),
        )

    def test_browse_stations_supports_location_sorting(self):
        BookStation.objects.create(
            name="Cedar Shelf",
            readable_id="cedar-shelf",
            description="Shaded corner cabinet",
            latitude=51.500000,
            longitude=-0.090000,
            location="Alpha Avenue",
            added_by=self.user,
        )

        response = self.client.get(
            reverse("book_stations:bookstation-list"), {"sort": "location"}
        )

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
        self.assertContains(
            response,
            "/static/book_stations/images/photos/riverside-box-lowres.svg",
        )

    def test_get_detail_page_handles_station_without_picture(self):
        station_without_picture = BookStation.objects.create(
            name="No Photo Shelf",
            readable_id="no-photo-shelf",
            description="A station still waiting for a photo",
            location="Elm Street",
            added_by=self.user,
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

    def test_post_requires_authentication(self):
        payload = {
            "name": "Library Corner",
            "description": "Take one leave one shelf",
            "location": "Rue de Rivoli, Paris",
        }

        response = self.client.post(
            reverse("book_stations:bookstation-list-create"),
            data=payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_post_creates_bookstation_for_logged_in_user(self):
        self.client.login(username="station-owner", password="StrongPass123")
        payload = {
            "name": "Library Corner",
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
        created_station = BookStation.objects.get(name="Library Corner")
        self.assertEqual(created_station.readable_id, "library-corner")
        self.assertEqual(created_station.added_by, self.user)
        self.assertEqual(
            response.json()["picture"],
            "book_stations/images/photos/city-corner-lowres.svg",
        )

    def test_post_rejects_invalid_coordinates(self):
        self.client.login(username="station-owner", password="StrongPass123")
        payload = {
            "name": "Broken Place",
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
        self.client.login(username="station-owner", password="StrongPass123")
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
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="migration-owner",
            password="StrongPass123",
        )

    def test_item_table_exists_and_inventory_views_render(self):
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
            added_by=self.user,
        )

        detail_response = self.client.get(
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": station.readable_id},
            )
        )
        inventory_response = self.client.get(
            reverse(
                "book_stations:bookstation-inventory",
                kwargs={"readable_id": station.readable_id},
            )
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(inventory_response.status_code, 200)


class ItemModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="item-model-owner",
            password="StrongPass123",
        )
        self.station = BookStation.objects.create(
            name="Harbor Shelf",
            readable_id="harbor-shelf",
            description="",
            latitude=51.500000,
            longitude=-0.090000,
            location="Harbor Road",
            added_by=self.user,
        )

    def test_requires_current_station_when_status_is_at_book_station(self):
        item = Item(
            title="The Long Way Home",
            author="A. Writer",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            added_by=self.user,
        )

        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_database_constraint_requires_current_station_when_at_book_station(self):
        with self.assertRaises(IntegrityError):
            Item.objects.create(
                title="Constraint Check",
                author="A. Writer",
                item_type=Item.ItemType.BOOK,
                status=Item.Status.AT_BOOK_STATION,
                added_by=self.user,
            )

    def test_save_defaults_last_seen_and_last_activity(self):
        item = Item.objects.create(
            title="Neighborhood Almanac",
            item_type=Item.ItemType.MAGAZINE,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )

        self.assertEqual(item.last_seen_at, self.station)
        self.assertEqual(item.last_activity, date.today())

    def test_author_required_for_books(self):
        item = Item(
            title="Needs Author",
            author="",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.UNKNOWN,
            added_by=self.user,
        )

        with self.assertRaises(ValidationError):
            item.full_clean()


class ItemViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="item-owner",
            password="StrongPass123",
        )
        self.station = BookStation.objects.create(
            name="South Park Box",
            readable_id="south-park-box",
            description="Near the playground",
            latitude=51.510000,
            longitude=-0.110000,
            location="South Park",
            added_by=self.user,
        )
        self.other_station = BookStation.objects.create(
            name="North Corner Shelf",
            readable_id="north-corner-shelf",
            description="",
            latitude=51.520000,
            longitude=-0.120000,
            location="North Corner",
            added_by=self.user,
        )
        self.item_here = Item.objects.create(
            title="Clean Code",
            author="Robert C. Martin",
            description="Programming book",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            last_activity=date(2026, 2, 5),
            added_by=self.user,
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
            added_by=self.user,
        )
        self.item_other_station = Item.objects.create(
            title="Bird Atlas",
            author="C. Reader",
            description="",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.other_station,
            last_activity=date(2026, 1, 20),
            added_by=self.user,
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
            added_by=self.user,
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

    def test_post_items_api_requires_authentication(self):
        payload = {
            "title": "Gardening Weekly",
            "author": "Garden Club",
            "item_type": Item.ItemType.MAGAZINE,
        }

        response = self.client.post(
            reverse("book_stations:item-list-create"),
            data=payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_post_items_api_creates_item(self):
        self.client.login(username="item-owner", password="StrongPass123")
        payload = {
            "title": "Gardening Weekly",
            "author": "Garden Club",
            "description": "Issue #12",
            "item_type": Item.ItemType.MAGAZINE,
            "status": Item.Status.AT_BOOK_STATION,
            "current_book_station": self.station.readable_id,
            "thumbnail_url": "https://example.com/thumb.jpg",
            "last_activity": "2026-03-01",
        }

        response = self.client.post(
            reverse("book_stations:item-list-create"),
            data=payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        created_item = Item.objects.get(title="Gardening Weekly")
        self.assertEqual(created_item.added_by, self.user)
        self.assertTrue(Item.objects.filter(title="Gardening Weekly").exists())
        self.assertEqual(response.json()["current_book_station"], "south-park-box")

    def test_post_items_api_rejects_at_station_without_station(self):
        self.client.login(username="item-owner", password="StrongPass123")
        payload = {
            "title": "Broken Item",
            "author": "Some Author",
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


class CreateFormViewTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123"
        self.user = get_user_model().objects.create_user(
            username="form-user",
            password=self.password,
        )
        self.station = BookStation.objects.create(
            name="Form Station",
            location="Downtown",
            added_by=self.user,
        )

    def test_bookstation_create_view_requires_login(self):
        response = self.client.get(reverse("book_stations:bookstation-create"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_bookstation_create_form_uploads_picture_and_assigns_owner(self):
        self.client.login(username="form-user", password=self.password)
        upload = SimpleUploadedFile("station.jpg", b"test-bytes", content_type="image/jpeg")

        response = self.client.post(
            reverse("book_stations:bookstation-create"),
            data={
                "name": "River Walk Station",
                "location": "River Walk",
                "description": "A new shelf",
                "latitude": "",
                "longitude": "",
                "picture_upload": upload,
            },
        )

        created_station = BookStation.objects.get(name="River Walk Station")
        self.assertRedirects(
            response,
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": created_station.readable_id},
            ),
        )
        self.assertEqual(created_station.added_by, self.user)
        self.assertEqual(created_station.readable_id, "river-walk-station")
        self.assertTrue(
            created_station.picture.startswith("/media/book_stations/images/photos/")
        )

    def test_item_create_view_requires_login(self):
        response = self.client.get(reverse("book_stations:item-create"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_item_create_form_requires_author_for_book(self):
        self.client.login(username="form-user", password=self.password)

        response = self.client.post(
            reverse("book_stations:item-create"),
            data={
                "title": "Anonymous Book",
                "author": "",
                "item_type": Item.ItemType.BOOK,
                "status": Item.Status.UNKNOWN,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Author is required when the item type is BOOK.")

    def test_item_create_form_accepts_non_book_without_author(self):
        self.client.login(username="form-user", password=self.password)

        response = self.client.post(
            reverse("book_stations:item-create"),
            data={
                "title": "Monthly Digest",
                "author": "",
                "item_type": Item.ItemType.MAGAZINE,
                "status": Item.Status.UNKNOWN,
                "current_book_station": "",
                "last_seen_at": "",
                "last_activity": "",
                "thumbnail_url": "https://example.com/digest.jpg",
            },
        )

        created_item = Item.objects.get(title="Monthly Digest")
        self.assertRedirects(
            response,
            reverse("book_stations:item-detail", kwargs={"item_id": created_item.id}),
        )
        self.assertEqual(created_item.added_by, self.user)
        self.assertEqual(created_item.thumbnail_url, "https://example.com/digest.jpg")
