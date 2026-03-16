from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection
from django.test import TestCase, override_settings
from django.urls import reverse

from items.models import Item

from .forms import BookStationCreateForm, decode_plus_code, encode_plus_code
from .models import BookStation


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

    def test_model_allows_blank_location_when_geolocation_is_present(self):
        station = BookStation(
            name="Geo Only Station",
            description="",
            latitude="40.712776",
            longitude="-74.005974",
            location="",
            added_by=self.user,
        )

        station.full_clean()

    def test_model_rejects_when_location_and_geolocation_are_missing(self):
        station = BookStation(
            name="Missing Location Data",
            description="",
            latitude=None,
            longitude=None,
            location="",
            added_by=self.user,
        )

        with self.assertRaises(ValidationError) as error_context:
            station.full_clean()

        self.assertIn("location", error_context.exception.message_dict)

    def test_database_constraint_rejects_when_location_and_geolocation_are_missing(self):
        with self.assertRaises(IntegrityError):
            BookStation.objects.create(
                name="DB Invalid Station",
                description="",
                latitude=None,
                longitude=None,
                location="",
                added_by=self.user,
            )


class BookStationCreateFormTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="plus-code-user",
            password="StrongPass123",
        )

    def test_plus_code_populates_latitude_and_longitude(self):
        plus_code = encode_plus_code(51.507351, -0.127758)
        form = BookStationCreateForm(
            data={
                "name": "Plus Code Station",
                "location": "",
                "description": "",
                "plus_code": plus_code,
                "latitude": "",
                "longitude": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        expected_latitude, expected_longitude = decode_plus_code(plus_code)
        self.assertEqual(form.cleaned_data["latitude"], expected_latitude)
        self.assertEqual(form.cleaned_data["longitude"], expected_longitude)

    def test_plus_code_overrides_manual_coordinates(self):
        plus_code = encode_plus_code(40.689247, -74.044502)
        form = BookStationCreateForm(
            data={
                "name": "Override Station",
                "location": "Liberty Island",
                "description": "",
                "plus_code": plus_code,
                "latitude": "0.000001",
                "longitude": "0.000001",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        expected_latitude, expected_longitude = decode_plus_code(plus_code)
        self.assertEqual(form.cleaned_data["latitude"], expected_latitude)
        self.assertEqual(form.cleaned_data["longitude"], expected_longitude)

    def test_invalid_plus_code_raises_form_error(self):
        form = BookStationCreateForm(
            data={
                "name": "Invalid Plus Code Station",
                "location": "Somewhere",
                "description": "",
                "plus_code": "NOT-A-CODE",
                "latitude": "",
                "longitude": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("plus_code", form.errors)

    def test_edit_form_prefills_plus_code_from_instance_coordinates(self):
        station = BookStation.objects.create(
            name="Existing Station",
            description="",
            latitude=48.858370,
            longitude=2.294481,
            location="Paris",
            added_by=self.user,
        )

        form = BookStationCreateForm(instance=station)

        self.assertEqual(
            form.initial.get("plus_code"),
            encode_plus_code(station.latitude, station.longitude),
        )

    def test_without_plus_code_manual_coordinates_remain_unchanged(self):
        form = BookStationCreateForm(
            data={
                "name": "Manual Coordinates Station",
                "location": "Manual Town",
                "description": "",
                "plus_code": "",
                "latitude": "51.500000",
                "longitude": "-0.120000",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(str(form.cleaned_data["latitude"]), "51.500000")
        self.assertEqual(str(form.cleaned_data["longitude"]), "-0.120000")

    def test_form_accepts_empty_location_if_coordinates_are_provided(self):
        form = BookStationCreateForm(
            data={
                "name": "Geo Coordinates Only",
                "location": "",
                "description": "",
                "plus_code": "",
                "latitude": "52.520008",
                "longitude": "13.404954",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_when_location_and_geolocation_are_empty(self):
        form = BookStationCreateForm(
            data={
                "name": "Missing Location Info",
                "location": "",
                "description": "",
                "plus_code": "",
                "latitude": "",
                "longitude": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("location", form.errors)
        self.assertIn("latitude", form.errors)
        self.assertIn("longitude", form.errors)


class BookStationViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="station-owner",
            password="StrongPass123",
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-station-user",
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
        # Sort controls should be a dropdown and arrow buttons, not plain links
        self.assertContains(response, 'name="sort_by"')
        self.assertContains(response, 'aria-label="Sort ascending"')
        self.assertContains(response, 'aria-label="Sort descending"')
        # "Add item" button must not appear on the overview page
        self.assertNotContains(response, "Add item")

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

    def test_browse_stations_supports_sort_by_and_sort_dir_params(self):
        BookStation.objects.create(
            name="Alpha Shelf",
            readable_id="alpha-shelf",
            description="First alphabetically",
            latitude=51.500000,
            longitude=-0.090000,
            location="Zebra Lane",
            added_by=self.user,
        )

        # sort_by=name asc: Alpha Shelf should come before Riverside Box
        response = self.client.get(
            reverse("book_stations:bookstation-list"),
            {"sort_by": "name", "sort_dir": "asc"},
        )
        self.assertEqual(response.status_code, 200)
        stations = list(response.context["stations"])
        self.assertEqual(stations[0].readable_id, "alpha-shelf")
        self.assertEqual(response.context["active_sort_by"], "name")
        self.assertEqual(response.context["active_sort_dir"], "asc")

        # sort_by=name desc: Riverside Box should come before Alpha Shelf
        response = self.client.get(
            reverse("book_stations:bookstation-list"),
            {"sort_by": "name", "sort_dir": "desc"},
        )
        stations = list(response.context["stations"])
        self.assertEqual(stations[0].readable_id, "riverside-box")
        self.assertEqual(response.context["active_sort_dir"], "desc")

        # sort_by=location asc: Riverside Walk comes before Zebra Lane
        response = self.client.get(
            reverse("book_stations:bookstation-list"),
            {"sort_by": "location", "sort_dir": "asc"},
        )
        stations = list(response.context["stations"])
        self.assertEqual(stations[0].readable_id, "riverside-box")

    def test_browse_stations_defaults_to_name_asc(self):
        response = self.client.get(reverse("book_stations:bookstation-list"))

        self.assertEqual(response.context["active_sort_by"], "name")
        self.assertEqual(response.context["active_sort_dir"], "asc")

    def test_browse_stations_rejects_invalid_sort_params(self):
        response = self.client.get(
            reverse("book_stations:bookstation-list"),
            {"sort_by": "invalid", "sort_dir": "sideways"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_sort_by"], "name")
        self.assertEqual(response.context["active_sort_dir"], "asc")

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
        self.assertContains(response, "Inventory")
        self.assertContains(response, "Full inventory")
        self.assertContains(response, "riverside-box")
        self.assertContains(response, "Photo of Riverside Box")
        self.assertContains(
            response,
            "/static/book_stations/images/photos/riverside-box-lowres.svg",
        )

    def test_inventory_page_supports_sorting_and_renders_controls(self):
        Item.objects.create(
            title="Alpha Title",
            author="Author",
            description="",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )
        Item.objects.create(
            title="Zulu Title",
            author="Author",
            description="",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )

        response = self.client.get(
            reverse(
                "book_stations:bookstation-inventory",
                kwargs={"readable_id": self.station.readable_id},
            ),
            {"sort_by": "title"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Items currently at this book station")
        self.assertContains(response, "Sort by")
        self.assertContains(response, 'value="title" selected', html=False)
        self.assertContains(
            response,
            'id="sort-dir-input" type="hidden" name="sort_dir" value="asc"',
            html=False,
        )
        self.assertEqual(response.context["active_sort_by"], "title")
        self.assertEqual(response.context["active_sort_dir"], "asc")

        inventory_items = list(response.context["items"])
        self.assertEqual(inventory_items[0].title, "Alpha Title")

    def test_detail_page_shows_owner_controls_only_for_owner(self):
        self.client.login(username="station-owner", password="StrongPass123")
        owner_response = self.client.get(
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": self.station.readable_id},
            )
        )

        self.assertContains(
            owner_response,
            reverse(
                "book_stations:bookstation-edit",
                kwargs={"readable_id": self.station.readable_id},
            ),
        )
        self.assertContains(
            owner_response,
            reverse(
                "book_stations:bookstation-delete",
                kwargs={"readable_id": self.station.readable_id},
            ),
        )

        self.client.login(username="other-station-user", password="StrongPass123")
        other_response = self.client.get(
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": self.station.readable_id},
            )
        )

        self.assertNotContains(
            other_response,
            reverse(
                "book_stations:bookstation-edit",
                kwargs={"readable_id": self.station.readable_id},
            ),
        )
        self.assertNotContains(
            other_response,
            reverse(
                "book_stations:bookstation-delete",
                kwargs={"readable_id": self.station.readable_id},
            ),
        )

    def test_owner_can_edit_station(self):
        self.client.login(username="station-owner", password="StrongPass123")

        response = self.client.post(
            reverse(
                "book_stations:bookstation-edit",
                kwargs={"readable_id": self.station.readable_id},
            ),
            data={
                "name": "Riverside Box Updated",
                "location": "Riverside Walk, London",
                "description": "Updated description",
                "latitude": "51.507351",
                "longitude": "-0.127758",
            },
        )

        self.station.refresh_from_db()
        self.assertRedirects(
            response,
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": self.station.readable_id},
            ),
        )
        self.assertEqual(self.station.name, "Riverside Box Updated")
        self.assertEqual(self.station.description, "Updated description")

    def test_non_owner_cannot_edit_or_delete_station(self):
        self.client.login(username="other-station-user", password="StrongPass123")

        edit_response = self.client.get(
            reverse(
                "book_stations:bookstation-edit",
                kwargs={"readable_id": self.station.readable_id},
            )
        )
        delete_response = self.client.post(
            reverse(
                "book_stations:bookstation-delete",
                kwargs={"readable_id": self.station.readable_id},
            )
        )

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(BookStation.objects.filter(pk=self.station.pk).exists())

    def test_owner_can_delete_station(self):
        self.client.login(username="station-owner", password="StrongPass123")

        response = self.client.post(
            reverse(
                "book_stations:bookstation-delete",
                kwargs={"readable_id": self.station.readable_id},
            )
        )

        self.assertRedirects(response, reverse("users:profile"))
        self.assertFalse(BookStation.objects.filter(pk=self.station.pk).exists())

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

    def test_owner_sees_clickable_photo_shortcut_when_no_picture(self):
        station_without_picture = BookStation.objects.create(
            name="Shortcut Test Shelf",
            readable_id="shortcut-test-shelf",
            description="A station awaiting a photo",
            location="Oak Lane",
            added_by=self.user,
        )
        self.client.login(username="station-owner", password="StrongPass123")

        response = self.client.get(
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": station_without_picture.readable_id},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No station photo yet")
        self.assertContains(response, "Click to add a photo for this station")
        self.assertContains(response, 'title="Add a photo for this station"')

    def test_non_owner_does_not_see_photo_shortcut_when_no_picture(self):
        station_without_picture = BookStation.objects.create(
            name="Non Owner Photo Shelf",
            readable_id="non-owner-photo-shelf",
            description="A station with no photo",
            location="Birch Road",
            added_by=self.user,
        )
        self.client.login(username="other-station-user", password="StrongPass123")

        response = self.client.get(
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": station_without_picture.readable_id},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No station photo yet")
        self.assertNotContains(response, "Click to add a photo for this station")
        self.assertNotContains(response, 'title="Add a photo for this station"')

    def test_anonymous_user_does_not_see_photo_shortcut_when_no_picture(self):
        station_without_picture = BookStation.objects.create(
            name="Anon Photo Shelf",
            readable_id="anon-photo-shelf",
            description="A station with no photo",
            location="Pine Street",
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
        self.assertNotContains(response, "Click to add a photo for this station")
        self.assertNotContains(response, 'title="Add a photo for this station"')

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


class BookStationCreateFormViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._temporary_media_directory = TemporaryDirectory()
        cls._media_override = override_settings(
            MEDIA_ROOT=cls._temporary_media_directory.name
        )
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        cls._temporary_media_directory.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.password = "StrongPass123"
        self.user = get_user_model().objects.create_user(
            username="form-user",
            password=self.password,
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


class BookStationQRCodeViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="qr-station-owner",
            password="StrongPass123",
        )
        self.station = BookStation.objects.create(
            name="QR Test Station",
            readable_id="qr-test-station",
            description="Station for QR code tests",
            latitude=51.5,
            longitude=-0.1,
            location="QR Test Lane",
            added_by=self.user,
        )

    def test_qr_page_returns_200(self):
        response = self.client.get(
            reverse("book_stations:bookstation-qr", kwargs={"readable_id": self.station.readable_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "book_stations/bookstation_qr.html")

    def test_qr_page_contains_station_name(self):
        response = self.client.get(
            reverse("book_stations:bookstation-qr", kwargs={"readable_id": self.station.readable_id})
        )

        self.assertContains(response, "QR Test Station")

    def test_qr_page_contains_detail_url(self):
        response = self.client.get(
            reverse("book_stations:bookstation-qr", kwargs={"readable_id": self.station.readable_id})
        )

        self.assertContains(response, "qr-test-station")

    def test_qr_page_embeds_image_data_uri(self):
        response = self.client.get(
            reverse("book_stations:bookstation-qr", kwargs={"readable_id": self.station.readable_id})
        )

        self.assertContains(response, "data:image/png;base64,")

    def test_qr_download_returns_png(self):
        response = self.client.get(
            reverse("book_stations:bookstation-qr", kwargs={"readable_id": self.station.readable_id}),
            {"download": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertIn("qr-qr-test-station.png", response["Content-Disposition"])

    def test_qr_page_404_for_unknown_station(self):
        response = self.client.get(
            reverse("book_stations:bookstation-qr", kwargs={"readable_id": "does-not-exist"})
        )

        self.assertEqual(response.status_code, 404)

    def test_qr_page_rejects_post(self):
        response = self.client.post(
            reverse("book_stations:bookstation-qr", kwargs={"readable_id": self.station.readable_id})
        )

        self.assertEqual(response.status_code, 405)

    def test_bookstation_detail_page_links_to_qr(self):
        response = self.client.get(
            reverse("book_stations:bookstation-detail", kwargs={"readable_id": self.station.readable_id})
        )

        self.assertContains(
            response,
            reverse("book_stations:bookstation-qr", kwargs={"readable_id": self.station.readable_id}),
        )


class ShelfOverflowRestSectionTests(TestCase):
    """Tests that rest-section HTML elements are rendered in the detail page
    and that the JavaScript overflow handler is included."""

    # Maximum characters to scan inside a rest-section anchor for its href.
    # An anchor tag with class, href, title, and aria-label is well under 300 chars.
    _ANCHOR_SCAN_WINDOW = 300

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rest-section-owner",
            password="StrongPass123",
        )
        self.station = BookStation.objects.create(
            name="Rest Section Station",
            readable_id="rest-section-station",
            description="",
            latitude=51.5,
            longitude=-0.1,
            location="Test Lane",
            added_by=self.user,
        )
        self.detail_url = reverse(
            "book_stations:bookstation-detail",
            kwargs={"readable_id": self.station.readable_id},
        )
        self.inventory_url = reverse(
            "book_stations:bookstation-inventory",
            kwargs={"readable_id": self.station.readable_id},
        )

    def test_book_rest_section_present_when_books_exist(self):
        Item.objects.create(
            title="A Book",
            author="An Author",
            description="",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="book-rest"')

    def test_book_rest_section_links_to_inventory(self):
        Item.objects.create(
            title="A Book",
            author="An Author",
            description="",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )

        response = self.client.get(self.detail_url)

        content = response.content.decode()
        book_rest_idx = content.find('class="book-rest"')
        self.assertNotEqual(book_rest_idx, -1, "book-rest element not found in page")
        self.assertIn(
            f'href="{self.inventory_url}"',
            content[book_rest_idx:book_rest_idx + self._ANCHOR_SCAN_WINDOW],
        )

    def test_book_rest_section_has_full_inventory_tooltip(self):
        Item.objects.create(
            title="A Book",
            author="An Author",
            description="",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )

        response = self.client.get(self.detail_url)

        self.assertContains(response, 'title="full inventory"')

    def test_dvd_rest_section_present_when_dvds_exist(self):
        Item.objects.create(
            title="A DVD",
            author="",
            description="",
            item_type=Item.ItemType.DVD,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="dvd-rest"')

    def test_dvd_rest_section_links_to_inventory(self):
        Item.objects.create(
            title="A DVD",
            author="",
            description="",
            item_type=Item.ItemType.DVD,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )

        response = self.client.get(self.detail_url)

        content = response.content.decode()
        dvd_rest_idx = content.find('class="dvd-rest"')
        self.assertNotEqual(dvd_rest_idx, -1, "dvd-rest element not found in page")
        self.assertIn(
            f'href="{self.inventory_url}"',
            content[dvd_rest_idx:dvd_rest_idx + self._ANCHOR_SCAN_WINDOW],
        )

    def test_dvd_rest_section_has_full_inventory_tooltip(self):
        Item.objects.create(
            title="A DVD",
            author="",
            description="",
            item_type=Item.ItemType.DVD,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )

        response = self.client.get(self.detail_url)

        self.assertContains(response, 'title="full inventory"')

    def test_book_rest_section_absent_when_no_items(self):
        response = self.client.get(self.detail_url)

        self.assertNotContains(response, 'class="book-rest"')

    def test_dvd_rest_section_absent_when_no_dvds(self):
        Item.objects.create(
            title="A Book Only",
            author="An Author",
            description="",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )

        response = self.client.get(self.detail_url)

        self.assertNotContains(response, 'class="dvd-rest"')

    def test_shelf_overflow_js_is_included_in_page(self):
        Item.objects.create(
            title="A Book",
            author="An Author",
            description="",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )

        response = self.client.get(self.detail_url)

        self.assertContains(response, "setupShelfOverflow")

    def test_dvd_rest_and_at_least_one_dvd_case_both_rendered(self):
        """Both a full-frontal DVD case and the dvd-rest section must appear in the
        page simultaneously so the JS overflow handler always has at least one
        visible DVD to keep in place."""
        for i in range(3):
            Item.objects.create(
                title=f"DVD {i}",
                author="",
                description="",
                item_type=Item.ItemType.DVD,
                status=Item.Status.AT_BOOK_STATION,
                current_book_station=self.station,
                added_by=self.user,
            )

        response = self.client.get(self.detail_url)

        # dvd-rest section is rendered
        self.assertContains(response, 'class="dvd-rest"')
        # At least one full-frontal DVD case is also rendered alongside it
        self.assertContains(response, 'class="dvd-case"')
