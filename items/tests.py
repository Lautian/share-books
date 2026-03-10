from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from book_stations.models import BookStation
from movements.models import Movement

from .models import Item


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

    def test_requires_empty_current_station_when_status_is_not_at_book_station(self):
        item = Item(
            title="Wrong Station Status",
            author="A. Writer",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.TAKEN_OUT,
            current_book_station=self.station,
            added_by=self.user,
        )

        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_database_constraint_rejects_current_station_when_not_at_book_station(self):
        with self.assertRaises(IntegrityError):
            Item.objects.create(
                title="Wrong Station Status Constraint",
                author="A. Writer",
                item_type=Item.ItemType.BOOK,
                status=Item.Status.TAKEN_OUT,
                current_book_station=self.station,
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
        self.other_user = get_user_model().objects.create_user(
            username="other-item-user",
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
        response = self.client.get(reverse("items:item-list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_list.html")
        self.assertContains(response, "Browse Items")
        self.assertContains(response, "Clean Code")
        self.assertContains(response, "Ocean Dreams")

    def test_get_item_detail_page_renders_item(self):
        response = self.client.get(reverse("items:item-detail", kwargs={"item_id": self.item_here.id}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_detail.html")
        self.assertContains(response, "Item detail")
        self.assertContains(response, "Clean Code")
        self.assertContains(response, "Robert C. Martin")

    def test_item_detail_shows_dash_when_last_seen_is_missing(self):
        item_without_last_seen = Item.objects.create(
            title="Untracked Item",
            author="A. Writer",
            description="",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.TAKEN_OUT,
            current_book_station=None,
            last_seen_at=None,
            added_by=self.user,
        )

        response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": item_without_last_seen.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<span class="text-base-content/70">-</span>',
            html=True,
        )

    def test_item_detail_shows_owner_controls_only_for_owner(self):
        self.client.login(username="item-owner", password="StrongPass123")
        owner_response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": self.item_here.id})
        )

        self.assertContains(
            owner_response,
            reverse("items:item-edit", kwargs={"item_id": self.item_here.id}),
        )
        self.assertContains(
            owner_response,
            reverse("items:item-delete", kwargs={"item_id": self.item_here.id}),
        )

        self.client.login(username="other-item-user", password="StrongPass123")
        other_response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": self.item_here.id})
        )

        self.assertNotContains(
            other_response,
            reverse("items:item-edit", kwargs={"item_id": self.item_here.id}),
        )
        self.assertNotContains(
            other_response,
            reverse("items:item-delete", kwargs={"item_id": self.item_here.id}),
        )

    def test_item_detail_shows_latest_three_movements_and_full_history_link(self):
        self.item_here.status = Item.Status.TAKEN_OUT
        self.item_here.current_book_station = None
        self.item_here.save(reported_by=self.user)

        self.item_here.status = Item.Status.AT_BOOK_STATION
        self.item_here.current_book_station = self.other_station
        self.item_here.save(reported_by=self.user)

        self.item_here.status = Item.Status.LOST
        self.item_here.current_book_station = None
        self.item_here.save(reported_by=self.user)

        response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": self.item_here.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "History")
        self.assertContains(
            response,
            reverse("items:item-history", kwargs={"item_id": self.item_here.id}),
        )
        self.assertContains(response, "Marked lost")
        self.assertContains(response, "Placed in station")
        self.assertContains(response, "Taken out")
        self.assertNotContains(response, "Added to catalog")

        recent_movements = list(response.context["recent_movements"])
        self.assertEqual(len(recent_movements), 3)
        self.assertEqual(
            [movement.movement_type for movement in recent_movements],
            [
                Movement.MovementType.MARKED_LOST,
                Movement.MovementType.PLACED_IN,
                Movement.MovementType.TAKEN_OUT,
            ],
        )

    def test_item_history_page_renders_full_timeline(self):
        self.item_here.status = Item.Status.TAKEN_OUT
        self.item_here.current_book_station = None
        self.item_here.save(reported_by=self.user)

        self.item_here.status = Item.Status.AT_BOOK_STATION
        self.item_here.current_book_station = self.other_station
        self.item_here.save(reported_by=self.user)

        response = self.client.get(
            reverse("items:item-history", kwargs={"item_id": self.item_here.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_history.html")
        self.assertContains(response, "Item journey flow")
        self.assertContains(response, "Visual timeline")
        self.assertContains(response, "First sighting")
        self.assertContains(response, self.station.name)
        self.assertContains(response, self.other_station.name)
        self.assertContains(response, "out for")
        self.assertContains(response, "Out by item-owner, back in by item-owner")
        self.assertNotContains(response, ">new<", html=False)

        movements = list(response.context["movements"])
        journey_steps = response.context["journey_steps"]
        journey_start_station = response.context["journey_start_station"]
        self.assertGreaterEqual(len(movements), 3)
        self.assertEqual(len(journey_steps), 1)
        self.assertEqual(journey_start_station["name"], self.station.name)
        self.assertEqual(journey_steps[0]["station"]["name"], self.other_station.name)
        self.assertEqual(movements[0].movement_type, Movement.MovementType.CREATED)

    def test_owner_can_edit_item(self):
        self.client.login(username="item-owner", password="StrongPass123")

        response = self.client.post(
            reverse("items:item-edit", kwargs={"item_id": self.item_here.id}),
            data={
                "title": "Clean Code 2nd Edition",
                "author": "Robert C. Martin",
                "item_type": Item.ItemType.BOOK,
                "thumbnail_url": "",
                "description": "Updated programming book",
                "status": Item.Status.AT_BOOK_STATION,
                "current_book_station": self.station.id,
                "last_seen_at": self.other_station.id,
                "last_activity": "2026-03-09",
            },
        )

        self.item_here.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": self.item_here.id}),
        )
        self.assertEqual(self.item_here.title, "Clean Code 2nd Edition")
        self.assertEqual(self.item_here.description, "Updated programming book")
        self.assertEqual(self.item_here.last_seen_at, self.station)

    def test_edit_assigning_current_station_sets_status_to_at_book_station(self):
        self.client.login(username="item-owner", password="StrongPass123")

        response = self.client.post(
            reverse("items:item-edit", kwargs={"item_id": self.item_taken.id}),
            data={
                "title": self.item_taken.title,
                "author": self.item_taken.author,
                "item_type": self.item_taken.item_type,
                "thumbnail_url": self.item_taken.thumbnail_url,
                "description": self.item_taken.description,
                "status": self.item_taken.status,
                "current_book_station": self.station.id,
                "last_seen_at": "",
                "last_activity": "2026-03-09",
            },
        )

        self.item_taken.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": self.item_taken.id}),
        )
        self.assertEqual(self.item_taken.status, Item.Status.AT_BOOK_STATION)
        self.assertEqual(self.item_taken.current_book_station, self.station)
        self.assertEqual(self.item_taken.last_seen_at, self.station)

    def test_edit_setting_non_station_status_clears_current_station(self):
        self.client.login(username="item-owner", password="StrongPass123")

        response = self.client.post(
            reverse("items:item-edit", kwargs={"item_id": self.item_here.id}),
            data={
                "title": self.item_here.title,
                "author": self.item_here.author,
                "item_type": self.item_here.item_type,
                "thumbnail_url": self.item_here.thumbnail_url,
                "description": self.item_here.description,
                "status": Item.Status.LOST,
                "current_book_station": self.station.id,
                "last_seen_at": self.station.id,
                "last_activity": "2026-03-09",
            },
        )

        self.item_here.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": self.item_here.id}),
        )
        self.assertEqual(self.item_here.status, Item.Status.LOST)
        self.assertIsNone(self.item_here.current_book_station)

    def test_edit_without_current_station_keeps_existing_last_seen_history(self):
        self.client.login(username="item-owner", password="StrongPass123")

        response = self.client.post(
            reverse("items:item-edit", kwargs={"item_id": self.item_taken.id}),
            data={
                "title": self.item_taken.title,
                "author": self.item_taken.author,
                "item_type": self.item_taken.item_type,
                "thumbnail_url": self.item_taken.thumbnail_url,
                "description": self.item_taken.description,
                "status": Item.Status.TAKEN_OUT,
                "current_book_station": "",
                "last_seen_at": self.other_station.id,
                "last_activity": "2026-03-09",
            },
        )

        self.item_taken.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": self.item_taken.id}),
        )
        self.assertEqual(self.item_taken.status, Item.Status.TAKEN_OUT)
        self.assertIsNone(self.item_taken.current_book_station)
        self.assertEqual(self.item_taken.last_seen_at, self.other_station)

    def test_non_owner_cannot_edit_or_delete_item(self):
        self.client.login(username="other-item-user", password="StrongPass123")

        edit_response = self.client.get(
            reverse("items:item-edit", kwargs={"item_id": self.item_here.id})
        )
        delete_response = self.client.post(
            reverse("items:item-delete", kwargs={"item_id": self.item_here.id})
        )

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(Item.objects.filter(pk=self.item_here.pk).exists())

    def test_owner_can_delete_item(self):
        self.client.login(username="item-owner", password="StrongPass123")

        response = self.client.post(
            reverse("items:item-delete", kwargs={"item_id": self.item_here.id})
        )

        self.assertRedirects(response, reverse("users:profile"))
        self.assertFalse(Item.objects.filter(pk=self.item_here.pk).exists())

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
        response = self.client.get(reverse("items:item-list-create"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 3)
        self.assertEqual(payload[0]["title"], "Bird Atlas")

    def test_get_items_api_filters_by_station(self):
        response = self.client.get(
            reverse("items:item-list-create"),
            {"station": self.station.readable_id},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["title"], "Clean Code")
        self.assertEqual(payload[0]["current_book_station"], "south-park-box")

    def test_get_item_detail_api_returns_item(self):
        response = self.client.get(reverse("items:item-detail-api", kwargs={"item_id": self.item_here.id}))

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
            reverse("items:item-list-create"),
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
            reverse("items:item-list-create"),
            data=payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        created_item = Item.objects.get(title="Gardening Weekly")
        self.assertEqual(created_item.added_by, self.user)
        self.assertTrue(Item.objects.filter(title="Gardening Weekly").exists())
        self.assertEqual(response.json()["current_book_station"], "south-park-box")

    def test_post_items_api_ignores_last_seen_without_station_history(self):
        self.client.login(username="item-owner", password="StrongPass123")
        payload = {
            "title": "Transient API Last Seen",
            "author": "",
            "item_type": Item.ItemType.MAGAZINE,
            "status": Item.Status.UNKNOWN,
            "current_book_station": "",
            "last_seen_at": self.station.readable_id,
        }

        response = self.client.post(
            reverse("items:item-list-create"),
            data=payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        created_item = Item.objects.get(title="Transient API Last Seen")
        self.assertIsNone(created_item.current_book_station)
        self.assertIsNone(created_item.last_seen_at)
        self.assertIsNone(response.json()["last_seen_at"])

    def test_post_items_api_clears_station_when_non_station_status_is_explicit(self):
        self.client.login(username="item-owner", password="StrongPass123")
        payload = {
            "title": "Explicit Lost",
            "author": "",
            "item_type": Item.ItemType.MAGAZINE,
            "status": Item.Status.LOST,
            "current_book_station": self.station.readable_id,
            "last_seen_at": self.station.readable_id,
        }

        response = self.client.post(
            reverse("items:item-list-create"),
            data=payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        created_item = Item.objects.get(title="Explicit Lost")
        self.assertEqual(created_item.status, Item.Status.LOST)
        self.assertIsNone(created_item.current_book_station)
        self.assertIsNone(created_item.last_seen_at)

    def test_post_items_api_rejects_at_station_without_station(self):
        self.client.login(username="item-owner", password="StrongPass123")
        payload = {
            "title": "Broken Item",
            "author": "Some Author",
            "item_type": Item.ItemType.BOOK,
            "status": Item.Status.AT_BOOK_STATION,
        }

        response = self.client.post(
            reverse("items:item-list-create"),
            data=payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("current_book_station", response.json()["errors"])


class ItemCreateFormViewTests(TestCase):
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

    def test_item_create_view_requires_login(self):
        response = self.client.get(reverse("items:item-create"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_item_create_form_requires_author_for_book(self):
        self.client.login(username="form-user", password=self.password)

        response = self.client.post(
            reverse("items:item-create"),
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
            reverse("items:item-create"),
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
            reverse("items:item-detail", kwargs={"item_id": created_item.id}),
        )
        self.assertEqual(created_item.added_by, self.user)
        self.assertEqual(created_item.thumbnail_url, "https://example.com/digest.jpg")

    def test_item_create_form_sets_status_when_current_station_is_selected(self):
        self.client.login(username="form-user", password=self.password)

        response = self.client.post(
            reverse("items:item-create"),
            data={
                "title": "Station Return",
                "author": "",
                "item_type": Item.ItemType.MAGAZINE,
                "status": Item.Status.UNKNOWN,
                "current_book_station": self.station.id,
                "last_seen_at": "",
                "last_activity": "",
                "thumbnail_url": "",
            },
        )

        created_item = Item.objects.get(title="Station Return")
        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": created_item.id}),
        )
        self.assertEqual(created_item.status, Item.Status.AT_BOOK_STATION)
        self.assertEqual(created_item.current_book_station, self.station)
        self.assertEqual(created_item.last_seen_at, self.station)

    def test_item_create_form_clears_station_for_non_station_status(self):
        self.client.login(username="form-user", password=self.password)

        response = self.client.post(
            reverse("items:item-create"),
            data={
                "title": "Away Item",
                "author": "",
                "item_type": Item.ItemType.MAGAZINE,
                "status": Item.Status.LOST,
                "current_book_station": self.station.id,
                "last_seen_at": "",
                "last_activity": "",
                "thumbnail_url": "",
            },
        )

        created_item = Item.objects.get(title="Away Item")
        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": created_item.id}),
        )
        self.assertEqual(created_item.status, Item.Status.LOST)
        self.assertIsNone(created_item.current_book_station)
        self.assertIsNone(created_item.last_seen_at)

    def test_item_create_form_ignores_last_seen_without_station_history(self):
        self.client.login(username="form-user", password=self.password)

        response = self.client.post(
            reverse("items:item-create"),
            data={
                "title": "Transient Last Seen",
                "author": "",
                "item_type": Item.ItemType.MAGAZINE,
                "status": Item.Status.UNKNOWN,
                "current_book_station": "",
                "last_seen_at": self.station.id,
                "last_activity": "",
                "thumbnail_url": "",
            },
        )

        created_item = Item.objects.get(title="Transient Last Seen")
        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": created_item.id}),
        )
        self.assertIsNone(created_item.current_book_station)
        self.assertIsNone(created_item.last_seen_at)
