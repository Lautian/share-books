from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.test import TestCase, override_settings
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
        self.assertContains(response, "Timeline")
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
        self.assertIsNotNone(self.item_here.pending_edit)
        self.assertEqual(self.item_here.pending_edit["title"], "Clean Code")

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
        self.assertIsNotNone(self.item_here.pending_edit)

    @override_settings(ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS=["title", "description"])
    def test_flagged_edit_requires_confirmation_before_pending_review(self):
        self.client.login(username="item-owner", password="StrongPass123")

        response = self.client.post(
            reverse("items:item-edit", kwargs={"item_id": self.item_here.id}),
            data={
                "title": "Flagged Title",
                "author": "Robert C. Martin",
                "item_type": Item.ItemType.BOOK,
                "thumbnail_url": "",
                "description": "Flagged description",
                "status": Item.Status.AT_BOOK_STATION,
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
        self.assertEqual(self.item_here.moderation_status, Item.ModerationStatus.FLAGGED)
        self.assertIsNotNone(self.item_here.pending_edit)
        self.assertEqual(self.item_here.pending_edit["title"], "Clean Code")

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

    def test_station_detail_uses_bookshelf_and_inventory_page_uses_full_width_list(self):
        Item.objects.create(
            title="Blade Runner",
            author="",
            description="",
            item_type=Item.ItemType.DVD,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            added_by=self.user,
        )

        detail_response = self.client.get(
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": self.station.readable_id},
            )
        )
        inventory_response = self.client.get(
            reverse(
                "book_stations:bookstation-inventory",
                kwargs={"readable_id": self.station.readable_id},
            )
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'class="dvd-group"', html=False)
        self.assertContains(detail_response, 'class="dvd-case"', html=False)
        self.assertContains(detail_response, "Blade Runner")

        self.assertEqual(inventory_response.status_code, 200)
        self.assertNotContains(inventory_response, 'class="dvd-case"', html=False)
        self.assertContains(inventory_response, "Items currently at this book station")
        self.assertContains(inventory_response, "Sort by")
        self.assertContains(inventory_response, 'class="inventory-list mt-4 space-y-3"', html=False)
        self.assertContains(inventory_response, "Blade Runner")

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

    @override_settings(ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS=["title"])
    def test_post_items_api_sets_pending_when_auto_moderation_flags_content(self):
        self.client.login(username="item-owner", password="StrongPass123")
        payload = {
            "title": "Flagged API Title",
            "author": "Some Author",
            "item_type": Item.ItemType.BOOK,
            "status": Item.Status.UNKNOWN,
        }

        response = self.client.post(
            reverse("items:item-list-create"),
            data=payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        created_item = Item.objects.get(title="Flagged API Title")
        self.assertEqual(created_item.moderation_status, Item.ModerationStatus.FLAGGED)


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
        self.assertEqual(created_item.moderation_status, Item.ModerationStatus.NEW)
        self.assertEqual(created_item.added_by, self.user)
        self.assertEqual(created_item.thumbnail_url, "https://example.com/digest.jpg")

    @override_settings(ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS=["title", "description"])
    def test_item_create_form_flagged_content_requires_confirmation(self):
        self.client.login(username="form-user", password=self.password)

        response = self.client.post(
            reverse("items:item-create"),
            data={
                "title": "Flagged Create Title",
                "author": "Some Author",
                "item_type": Item.ItemType.BOOK,
                "status": Item.Status.UNKNOWN,
                "description": "Flagged create description",
            },
        )

        created_item = Item.objects.get(title="Flagged Create Title")
        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": created_item.id}),
        )
        self.assertEqual(created_item.moderation_status, Item.ModerationStatus.FLAGGED)

    def test_item_create_form_url_content_is_created_as_flagged(self):
        self.client.login(username="form-user", password=self.password)

        response = self.client.post(
            reverse("items:item-create"),
            data={
                "title": "Read this: https://example.com/offer",
                "author": "Some Author",
                "item_type": Item.ItemType.BOOK,
                "status": Item.Status.UNKNOWN,
                "description": "",
            },
        )

        created_item = Item.objects.get(title="Read this: https://example.com/offer")
        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": created_item.id}),
        )
        self.assertEqual(created_item.moderation_status, Item.ModerationStatus.FLAGGED)

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


class ItemQRCodeViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="qr-item-owner",
            password="StrongPass123",
        )
        self.station = BookStation.objects.create(
            name="QR Item Station",
            readable_id="qr-item-station",
            description="",
            latitude=51.5,
            longitude=-0.1,
            location="QR Item Lane",
            added_by=self.user,
        )
        self.item = Item.objects.create(
            title="QR Test Book",
            author="QR Author",
            description="A book for QR tests",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            last_activity=date(2026, 1, 1),
            added_by=self.user,
        )

    def test_qr_page_returns_200(self):
        response = self.client.get(
            reverse("items:item-qr", kwargs={"item_id": self.item.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_qr.html")

    def test_qr_page_contains_item_title(self):
        response = self.client.get(
            reverse("items:item-qr", kwargs={"item_id": self.item.id})
        )

        self.assertContains(response, "QR Test Book")

    def test_qr_page_contains_detail_url(self):
        response = self.client.get(
            reverse("items:item-qr", kwargs={"item_id": self.item.id})
        )

        self.assertContains(response, f"/items/{self.item.id}/")

    def test_qr_page_embeds_image_data_uri(self):
        response = self.client.get(
            reverse("items:item-qr", kwargs={"item_id": self.item.id})
        )

        self.assertContains(response, "data:image/png;base64,")

    def test_qr_download_returns_png(self):
        response = self.client.get(
            reverse("items:item-qr", kwargs={"item_id": self.item.id}),
            {"download": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertIn(f"qr-item-{self.item.id}.png", response["Content-Disposition"])

    def test_qr_page_404_for_unknown_item(self):
        response = self.client.get(
            reverse("items:item-qr", kwargs={"item_id": 999999})
        )

        self.assertEqual(response.status_code, 404)

    def test_qr_page_rejects_post(self):
        response = self.client.post(
            reverse("items:item-qr", kwargs={"item_id": self.item.id})
        )

        self.assertEqual(response.status_code, 405)

    def test_item_detail_page_links_to_qr(self):
        response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": self.item.id})
        )

        self.assertContains(
            response,
            reverse("items:item-qr", kwargs={"item_id": self.item.id}),
        )


class ItemMoveViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="move-owner",
            password="StrongPass123",
        )
        self.other_user = get_user_model().objects.create_user(
            username="move-other",
            password="StrongPass123",
        )
        self.station = BookStation.objects.create(
            name="Move Station A",
            readable_id="move-station-a",
            description="",
            latitude=51.5,
            longitude=-0.1,
            location="Move Street",
            added_by=self.user,
        )
        self.other_station = BookStation.objects.create(
            name="Move Station B",
            readable_id="move-station-b",
            description="",
            latitude=51.6,
            longitude=-0.2,
            location="Other Move Street",
            added_by=self.user,
        )
        self.item_at_station = Item.objects.create(
            title="Move Test Book",
            author="Move Author",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station,
            last_activity=date(2026, 1, 1),
            added_by=self.user,
        )
        self.item_taken = Item.objects.create(
            title="Taken Out Book",
            author="Take Author",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.TAKEN_OUT,
            current_book_station=None,
            last_seen_at=self.station,
            last_activity=date(2026, 1, 1),
            added_by=self.user,
        )

    # --- Anonymous user behaviour ---

    def test_anonymous_user_is_redirected_on_get(self):
        url = reverse("items:item-move", kwargs={"item_id": self.item_at_station.id})
        response = self.client.get(url + "?action=take_out")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login/", response["Location"])

    def test_anonymous_user_is_redirected_on_post(self):
        url = reverse("items:item-move", kwargs={"item_id": self.item_at_station.id})
        response = self.client.post(url, {"action": "take_out"})

        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login/", response["Location"])

    def test_item_detail_shows_login_link_for_anonymous(self):
        response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": self.item_at_station.id})
        )

        self.assertContains(response, "Log in to move item")
        login_url = reverse("users:login")
        self.assertContains(response, login_url)

    # --- Logged-in user: detail page ---

    def test_item_detail_shows_move_buttons_for_authenticated_user(self):
        self.client.login(username="move-owner", password="StrongPass123")
        response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": self.item_at_station.id})
        )

        self.assertContains(response, "Take Out")
        self.assertContains(response, "Put In")
        self.assertContains(response, "Mark Lost")

    def test_item_detail_does_not_show_login_link_for_authenticated_user(self):
        self.client.login(username="move-owner", password="StrongPass123")
        response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": self.item_at_station.id})
        )

        self.assertNotContains(response, "Log in to move item")

    # --- GET confirmation page ---

    def test_get_take_out_confirmation_page(self):
        self.client.login(username="move-owner", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_at_station.id})
        response = self.client.get(url + "?action=take_out")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_move_confirm.html")
        self.assertContains(response, "take_out")
        self.assertContains(response, "Move Test Book")

    def test_get_put_in_confirmation_page_lists_stations(self):
        self.client.login(username="move-owner", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_taken.id})
        response = self.client.get(url + "?action=put_in")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_move_confirm.html")
        self.assertContains(response, "Move Station A")
        self.assertContains(response, "Move Station B")

    def test_get_mark_lost_confirmation_page(self):
        self.client.login(username="move-owner", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_at_station.id})
        response = self.client.get(url + "?action=mark_lost")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_move_confirm.html")
        self.assertContains(response, "mark_lost")

    def test_get_invalid_action_redirects_to_detail(self):
        self.client.login(username="move-owner", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_at_station.id})
        response = self.client.get(url + "?action=invalid")

        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": self.item_at_station.id}),
        )

    # --- POST: take out ---

    def test_post_take_out_updates_item_status(self):
        self.client.login(username="move-other", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_at_station.id})
        response = self.client.post(url, {"action": "take_out"})

        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": self.item_at_station.id}),
        )
        self.item_at_station.refresh_from_db()
        self.assertEqual(self.item_at_station.status, Item.Status.TAKEN_OUT)
        self.assertIsNone(self.item_at_station.current_book_station)

    def test_post_take_out_creates_movement_with_reporter(self):
        self.client.login(username="move-other", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_at_station.id})
        self.client.post(url, {"action": "take_out"})

        movement = self.item_at_station.movements.order_by("-timestamp", "-id").first()
        self.assertEqual(movement.reported_by.username, "move-other")

    # --- POST: put in ---

    def test_post_put_in_updates_item_to_station(self):
        self.client.login(username="move-other", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_taken.id})
        response = self.client.post(
            url, {"action": "put_in", "station_id": self.other_station.id}
        )

        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": self.item_taken.id}),
        )
        self.item_taken.refresh_from_db()
        self.assertEqual(self.item_taken.status, Item.Status.AT_BOOK_STATION)
        self.assertEqual(self.item_taken.current_book_station, self.other_station)

    def test_post_put_in_creates_placed_in_movement(self):
        self.client.login(username="move-other", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_taken.id})
        self.client.post(
            url, {"action": "put_in", "station_id": self.other_station.id}
        )

        movement = self.item_taken.movements.order_by("-timestamp", "-id").first()
        self.assertEqual(movement.reported_by.username, "move-other")

    def test_post_put_in_without_station_re_renders_form(self):
        self.client.login(username="move-owner", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_taken.id})
        response = self.client.post(url, {"action": "put_in", "station_id": ""})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_move_confirm.html")
        self.assertContains(response, "Please select a station.")

    def test_post_put_in_with_nonexistent_station_re_renders_form(self):
        self.client.login(username="move-owner", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_taken.id})
        response = self.client.post(url, {"action": "put_in", "station_id": "999999"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_move_confirm.html")
        self.assertContains(response, "Selected station not found")
        self.item_taken.refresh_from_db()
        self.assertEqual(self.item_taken.status, Item.Status.TAKEN_OUT)

    # --- POST: mark lost ---

    def test_post_mark_lost_updates_item_status(self):
        self.client.login(username="move-other", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_at_station.id})
        response = self.client.post(url, {"action": "mark_lost"})

        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": self.item_at_station.id}),
        )
        self.item_at_station.refresh_from_db()
        self.assertEqual(self.item_at_station.status, Item.Status.LOST)
        self.assertIsNone(self.item_at_station.current_book_station)

    def test_post_mark_lost_creates_marked_lost_movement(self):
        self.client.login(username="move-other", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_at_station.id})
        self.client.post(url, {"action": "mark_lost"})

        movement = self.item_at_station.movements.order_by("-timestamp", "-id").first()
        self.assertEqual(movement.reported_by.username, "move-other")

    # --- POST: invalid action ---

    def test_post_invalid_action_redirects_to_detail(self):
        self.client.login(username="move-owner", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": self.item_at_station.id})
        response = self.client.post(url, {"action": "fly_away"})

        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": self.item_at_station.id}),
        )

    def test_get_404_for_unknown_item(self):
        self.client.login(username="move-owner", password="StrongPass123")
        url = reverse("items:item-move", kwargs={"item_id": 999999})
        response = self.client.get(url + "?action=take_out")

        self.assertEqual(response.status_code, 404)


class ItemBulkAddViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="bulk-add-user",
            password="StrongPass123",
        )
        self.station = BookStation.objects.create(
            name="Bulk Station",
            readable_id="bulk-station",
            location="Bulk Road",
            added_by=self.user,
        )
        self.url = reverse("items:item-bulk-add")

    # --- GET ---

    def test_get_requires_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"/users/login/?next={self.url}")

    def test_get_renders_bulk_add_page(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bulk Add Items")

    # --- POST: validation ---

    def test_post_requires_login(self):
        response = self.client.post(self.url, {"csv_text": "title\nA Book"})
        self.assertRedirects(response, f"/users/login/?next={self.url}")

    def test_post_without_input_shows_error(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please provide either CSV text or a CSV file")

    # --- POST: CSV text ---

    def test_post_csv_text_creates_items(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        csv_text = "title,author,item_type\nMoby Dick,Herman Melville,BOOK\nNature Mag,,MAGAZINE"
        response = self.client.post(self.url, {"csv_text": csv_text})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2 items added successfully")
        self.assertTrue(Item.objects.filter(title="Moby Dick").exists())
        self.assertTrue(Item.objects.filter(title="Nature Mag").exists())

    def test_post_csv_text_items_owned_by_logged_in_user(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        csv_text = "title,author\nOwnership Test,Someone"
        self.client.post(self.url, {"csv_text": csv_text})
        item = Item.objects.get(title="Ownership Test")
        self.assertEqual(item.added_by.username, "bulk-add-user")

    def test_post_csv_missing_title_reports_error(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        csv_text = "title,author\n,No Title Author"
        response = self.client.post(self.url, {"csv_text": csv_text})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "title is required")
        self.assertFalse(Item.objects.filter(author="No Title Author").exists())

    def test_post_csv_book_missing_author_reports_error(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        csv_text = "title,item_type\nNo Author Book,BOOK"
        response = self.client.post(self.url, {"csv_text": csv_text})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 row could not be added")
        self.assertFalse(Item.objects.filter(title="No Author Book").exists())

    def test_post_csv_partial_success_reports_both(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        csv_text = "title,author,item_type\nGood Book,Author A,BOOK\n,Missing Title,BOOK"
        response = self.client.post(self.url, {"csv_text": csv_text})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 item added successfully")
        self.assertContains(response, "1 row could not be added")

    def test_post_csv_with_station_places_item_at_station(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        csv_text = f"title,author,current_book_station\nStation Book,Author B,{self.station.readable_id}"
        self.client.post(self.url, {"csv_text": csv_text})
        item = Item.objects.get(title="Station Book")
        self.assertEqual(item.status, Item.Status.AT_BOOK_STATION)
        self.assertEqual(item.current_book_station, self.station)

    def test_post_csv_invalid_station_reports_error(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        csv_text = "title,author,current_book_station\nBad Station Book,Author C,nonexistent-station"
        response = self.client.post(self.url, {"csv_text": csv_text})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 row could not be added")
        self.assertFalse(Item.objects.filter(title="Bad Station Book").exists())

    def test_post_csv_empty_rows_reports_error(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        csv_text = "title,author"
        response = self.client.post(self.url, {"csv_text": csv_text})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No data rows found in CSV")

    def test_post_csv_file_upload_creates_items(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        csv_content = b"title,author\nFile Upload Book,File Author"
        csv_file = ContentFile(csv_content, name="items.csv")
        response = self.client.post(self.url, {"csv_file": csv_file})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 item added successfully")
        self.assertTrue(Item.objects.filter(title="File Upload Book").exists())

    def test_post_csv_link_on_add_item_page(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        response = self.client.get(reverse("items:item-create"))
        self.assertContains(response, reverse("items:item-bulk-add"))

    # --- POST: both inputs provided ---

    def test_post_both_inputs_provided_shows_error(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        csv_content = b"title,author\nDouble Input Book,Author"
        csv_file = ContentFile(csv_content, name="items.csv")
        response = self.client.post(
            self.url, {"csv_text": "title\nSome Book", "csv_file": csv_file}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please use only one input")
        self.assertFalse(Item.objects.filter(title="Double Input Book").exists())
        self.assertFalse(Item.objects.filter(title="Some Book").exists())

    # --- POST: file size limit ---

    def test_post_csv_file_exceeding_size_limit_shows_error(self):
        from items.views import _BULK_CSV_MAX_FILE_BYTES

        self.client.login(username="bulk-add-user", password="StrongPass123")
        oversized_content = b"title,author\n" + b"A Book,Author\n" * (
            _BULK_CSV_MAX_FILE_BYTES // len(b"A Book,Author\n") + 1
        )
        csv_file = ContentFile(oversized_content, name="big.csv")
        response = self.client.post(self.url, {"csv_file": csv_file})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "exceeds the")
        self.assertContains(response, "size limit")

    # --- POST: row count limit ---

    def test_post_csv_row_limit_stops_at_250(self):
        from items.views import _BULK_CSV_MAX_ROWS

        self.client.login(username="bulk-add-user", password="StrongPass123")
        rows = "\n".join(
            f"Row {i} Title,,MAGAZINE" for i in range(1, _BULK_CSV_MAX_ROWS + 10)
        )
        csv_text = f"title,author,item_type\n{rows}"
        response = self.client.post(self.url, {"csv_text": csv_text})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Row limit")
        self.assertEqual(Item.objects.filter(added_by=self.user).count(), _BULK_CSV_MAX_ROWS)

    # --- POST: invalid status / item_type ---

    def test_post_csv_invalid_status_reports_error(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        csv_text = "title,author,status\nStatus Test Book,Author,NOT_A_STATUS"
        response = self.client.post(self.url, {"csv_text": csv_text})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 row could not be added")
        self.assertContains(response, "not a valid status")
        self.assertFalse(Item.objects.filter(title="Status Test Book").exists())

    def test_post_csv_invalid_item_type_reports_error(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        csv_text = "title,author,item_type\nType Test Book,Author,NOT_A_TYPE"
        response = self.client.post(self.url, {"csv_text": csv_text})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 row could not be added")
        self.assertContains(response, "not a valid type")
        self.assertFalse(Item.objects.filter(title="Type Test Book").exists())

    # --- GET: limits shown on page ---

    def test_get_shows_limits_info(self):
        self.client.login(username="bulk-add-user", password="StrongPass123")
        response = self.client.get(self.url)
        self.assertContains(response, "250")
        self.assertContains(response, "512")
