import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from book_stations.models import BookStation
from items.models import Item
from moderation.utils import MODERATOR_GROUP_NAME


class ModerationSetUpMixin:
    def setUp(self):
        User = get_user_model()
        self.password = "SafePass123"
        self.regular_user = User.objects.create_user(
            username="regular",
            password=self.password,
        )
        self.other_user = User.objects.create_user(
            username="other",
            password=self.password,
        )
        self.moderator = User.objects.create_user(
            username="moderator",
            password=self.password,
            is_staff=True,
        )
        self.pending_station = BookStation.objects.create(
            name="Pending Station",
            location="Somewhere",
            added_by=self.regular_user,
            moderation_status=BookStation.ModerationStatus.FLAGGED,
        )
        self.approved_station = BookStation.objects.create(
            name="Approved Station",
            location="Elsewhere",
            added_by=self.regular_user,
            moderation_status=BookStation.ModerationStatus.APPROVED,
        )
        self.pending_item = Item.objects.create(
            title="Pending Book",
            author="Author A",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.UNKNOWN,
            added_by=self.regular_user,
            moderation_status=Item.ModerationStatus.FLAGGED,
        )
        self.approved_item = Item.objects.create(
            title="Approved Book",
            author="Author B",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.UNKNOWN,
            added_by=self.regular_user,
            moderation_status=Item.ModerationStatus.APPROVED,
        )


class ModerationQueueAccessTests(ModerationSetUpMixin, TestCase):
    """Tests that the moderation queue is only accessible to moderators."""

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("moderation:queue"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_regular_user_gets_403(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        self.assertEqual(response.status_code, 403)

    def test_moderator_can_access_queue(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "moderation/queue.html")

    def test_user_in_moderators_group_can_access_queue(self):
        moderators_group, _ = Group.objects.get_or_create(name=MODERATOR_GROUP_NAME)
        self.other_user.groups.add(moderators_group)
        self.client.login(username="other", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "moderation/queue.html")

    def test_queue_shows_pending_stations_and_items(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        self.assertContains(response, "Pending Station")
        self.assertContains(response, "Pending Book")
        self.assertNotContains(response, "Approved Station")
        self.assertNotContains(response, "Approved Book")


class ModerationVisibilityTests(ModerationSetUpMixin, TestCase):
    """Tests that flagged content is visible in public views."""

    def test_bookstation_list_hides_pending_for_anonymous(self):
        response = self.client.get(reverse("book_stations:bookstation-list"))

        self.assertContains(response, "Pending Station")
        self.assertContains(response, "Approved Station")

    def test_bookstation_list_hides_pending_for_regular_user(self):
        self.client.login(username="other", password=self.password)

        response = self.client.get(reverse("book_stations:bookstation-list"))

        self.assertContains(response, "Pending Station")
        self.assertContains(response, "Approved Station")

    def test_bookstation_list_shows_all_for_moderator(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("book_stations:bookstation-list"))

        self.assertContains(response, "Pending Station")
        self.assertContains(response, "Approved Station")

    def test_pending_bookstation_detail_returns_404_for_anonymous(self):
        response = self.client.get(
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_pending_bookstation_detail_visible_to_owner(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.get(
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_pending_bookstation_detail_visible_to_moderator(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_pending_bookstation_detail_returns_404_for_other_user(self):
        self.client.login(username="other", password=self.password)

        response = self.client.get(
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_item_list_hides_pending_for_anonymous(self):
        response = self.client.get(reverse("items:item-list"))

        self.assertContains(response, "Pending Book")
        self.assertContains(response, "Approved Book")

    def test_pending_item_detail_returns_404_for_anonymous(self):
        response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": self.pending_item.id})
        )

        self.assertEqual(response.status_code, 200)

    def test_pending_item_detail_visible_to_owner(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": self.pending_item.id})
        )

        self.assertEqual(response.status_code, 200)

    def test_pending_item_detail_returns_404_for_other_user(self):
        self.client.login(username="other", password=self.password)

        response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": self.pending_item.id})
        )

        self.assertEqual(response.status_code, 200)


class ModerationApproveTests(ModerationSetUpMixin, TestCase):
    """Tests for the approve action."""

    def test_approve_bookstation_sets_status_to_approved(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse(
                "moderation:approve-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.pending_station.refresh_from_db()
        self.assertEqual(
            self.pending_station.moderation_status,
            BookStation.ModerationStatus.APPROVED,
        )

    def test_approve_item_sets_status_to_approved(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse("moderation:approve-item", kwargs={"item_id": self.pending_item.id})
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.pending_item.refresh_from_db()
        self.assertEqual(
            self.pending_item.moderation_status,
            Item.ModerationStatus.APPROVED,
        )

    def test_regular_user_cannot_approve_bookstation(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.post(
            reverse(
                "moderation:approve-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 403)
        self.pending_station.refresh_from_db()
        self.assertEqual(
            self.pending_station.moderation_status,
            BookStation.ModerationStatus.FLAGGED,
        )

    def test_regular_user_cannot_approve_item(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.post(
            reverse("moderation:approve-item", kwargs={"item_id": self.pending_item.id})
        )

        self.assertEqual(response.status_code, 403)
        self.pending_item.refresh_from_db()
        self.assertEqual(
            self.pending_item.moderation_status,
            Item.ModerationStatus.FLAGGED,
        )


class ModerationClaimTests(ModerationSetUpMixin, TestCase):
    """Tests for the claim action."""

    def test_claim_bookstation_assigns_moderator(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse(
                "moderation:claim-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.pending_station.refresh_from_db()
        self.assertEqual(self.pending_station.claimed_by, self.moderator)

    def test_claim_bookstation_respects_next_parameter(self):
        self.client.login(username="moderator", password=self.password)
        detail_url = reverse(
            "book_stations:bookstation-detail",
            kwargs={"readable_id": self.pending_station.readable_id},
        )

        response = self.client.post(
            reverse(
                "moderation:claim-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            ),
            data={"next": detail_url},
        )

        self.assertRedirects(response, detail_url)

    def test_claim_item_assigns_moderator(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse("moderation:claim-item", kwargs={"item_id": self.pending_item.id})
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.pending_item.refresh_from_db()
        self.assertEqual(self.pending_item.claimed_by, self.moderator)

    def test_claim_item_respects_next_parameter(self):
        self.client.login(username="moderator", password=self.password)
        detail_url = reverse("items:item-detail", kwargs={"item_id": self.pending_item.id})

        response = self.client.post(
            reverse("moderation:claim-item", kwargs={"item_id": self.pending_item.id}),
            data={"next": detail_url},
        )

        self.assertRedirects(response, detail_url)

    def test_regular_user_cannot_claim_bookstation(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.post(
            reverse(
                "moderation:claim-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 403)
        self.pending_station.refresh_from_db()
        self.assertIsNone(self.pending_station.claimed_by)


class ModerationWorkflowTests(ModerationSetUpMixin, TestCase):
    """Tests for the full moderation workflow."""

    def test_create_bookstation_through_form_is_pending(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.post(
            reverse("book_stations:bookstation-create"),
            data={
                "name": "Brand New Station",
                "location": "City Park",
                "description": "",
            },
        )

        station = BookStation.objects.get(name="Brand New Station")
        self.assertEqual(
            station.moderation_status, BookStation.ModerationStatus.NEW
        )

    def test_create_item_through_form_is_new(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.post(
            reverse("items:item-create"),
            data={
                "title": "Brand New Book",
                "author": "An Author",
                "item_type": Item.ItemType.BOOK,
                "status": Item.Status.UNKNOWN,
            },
        )

        item = Item.objects.get(title="Brand New Book")
        self.assertEqual(item.moderation_status, Item.ModerationStatus.NEW)

    def test_edit_approved_bookstation_creates_pending_edit(self):
        """Editing an approved station stores a pending_edit instead of resetting to PENDING."""
        self.client.login(username="regular", password=self.password)

        self.client.post(
            reverse(
                "book_stations:bookstation-edit",
                kwargs={"readable_id": self.approved_station.readable_id},
            ),
            data={
                "name": self.approved_station.name,
                "location": "Updated Location",
                "description": "Updated",
            },
        )

        self.approved_station.refresh_from_db()
        # Station stays visible after edit with NEW status; revert snapshot saved in pending_edit.
        self.assertEqual(
            self.approved_station.moderation_status,
            BookStation.ModerationStatus.NEW,
        )
        self.assertIsNotNone(self.approved_station.pending_edit)
        self.assertEqual(self.approved_station.pending_edit["location"], "Elsewhere")

    def test_edit_approved_item_updates_live_record(self):
        """Editing an approved item updates live fields when auto-moderation passes."""
        self.client.login(username="regular", password=self.password)

        self.client.post(
            reverse("items:item-edit", kwargs={"item_id": self.approved_item.id}),
            data={
                "title": self.approved_item.title,
                "author": "Updated Author",
                "item_type": Item.ItemType.BOOK,
                "status": Item.Status.UNKNOWN,
            },
        )

        self.approved_item.refresh_from_db()
        self.assertEqual(
            self.approved_item.moderation_status, Item.ModerationStatus.NEW
        )
        self.assertIsNotNone(self.approved_item.pending_edit)
        self.assertEqual(self.approved_item.author, "Updated Author")

    def test_approved_item_visible_after_moderation_approval(self):
        """After a moderator approves a pending item, it appears in public views."""
        self.client.login(username="moderator", password=self.password)
        self.client.post(
            reverse("moderation:approve-item", kwargs={"item_id": self.pending_item.id})
        )
        self.client.logout()

        response = self.client.get(reverse("items:item-list"))

        self.assertContains(response, "Pending Book")

    def test_approve_clears_claimed_by(self):
        """Approving an item clears the claimed_by field."""
        self.pending_station.claimed_by = self.moderator
        self.pending_station.save(update_fields=["claimed_by"])

        self.client.login(username="moderator", password=self.password)
        self.client.post(
            reverse(
                "moderation:approve-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.pending_station.refresh_from_db()
        self.assertIsNone(self.pending_station.claimed_by)


class ModerationProfileBadgeTests(ModerationSetUpMixin, TestCase):
    """Tests that the profile page shows moderation status badges."""

    def test_profile_shows_pending_badge_for_pending_station(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.get(reverse("users:profile"))

        self.assertContains(response, "Needs moderation follow-up")

    def test_profile_shows_no_badge_for_approved_station(self):
        # Only the pending station is there, so remove it to isolate
        self.pending_station.delete()
        self.pending_item.delete()
        self.client.login(username="regular", password=self.password)

        response = self.client.get(reverse("users:profile"))

        self.assertNotContains(response, "Needs moderation follow-up")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ModerationImageUploadTests(ModerationSetUpMixin, TestCase):
    """Tests that image uploads on BookStations are subject to moderation."""

    _PICTURE_URL_PREFIX = "/media/book_stations/images/photos/"

    def test_create_station_with_image_is_pending(self):
        """A new station submitted with an image upload is visible immediately."""
        self.client.login(username="regular", password=self.password)
        upload = SimpleUploadedFile("photo.jpg", b"fake-jpeg-bytes", content_type="image/jpeg")

        self.client.post(
            reverse("book_stations:bookstation-create"),
            data={
                "name": "Picture Station",
                "location": "Photo Park",
                "description": "",
                "picture_upload": upload,
            },
        )

        station = BookStation.objects.get(name="Picture Station")
        self.assertEqual(station.moderation_status, BookStation.ModerationStatus.NEW)
        # The picture URL should already be saved (file stored, pending review)
        self.assertTrue(station.picture.startswith(self._PICTURE_URL_PREFIX))

    def test_uploading_image_to_approved_station_creates_pending_edit(self):
        """Uploading a new image updates the live record and stores a revert snapshot."""
        self.client.login(username="regular", password=self.password)
        upload = SimpleUploadedFile("update.jpg", b"new-fake-bytes", content_type="image/jpeg")

        self.client.post(
            reverse(
                "book_stations:bookstation-edit",
                kwargs={"readable_id": self.approved_station.readable_id},
            ),
            data={
                "name": self.approved_station.name,
                "location": self.approved_station.location,
                "description": self.approved_station.description,
                "picture_upload": upload,
            },
        )

        self.approved_station.refresh_from_db()
        # Station stays visible and stores a revert snapshot in pending_edit.
        self.assertEqual(
            self.approved_station.moderation_status,
            BookStation.ModerationStatus.NEW,
        )
        self.assertIsNotNone(self.approved_station.pending_edit)
        self.assertTrue(self.approved_station.picture.startswith(self._PICTURE_URL_PREFIX))

    def test_station_remains_visible_in_public_list_while_edit_is_pending(self):
        """After uploading an image to an approved station, the station must remain
        publicly visible (original data) while the edit awaits moderation."""
        self.client.login(username="regular", password=self.password)
        upload = SimpleUploadedFile("another.jpg", b"more-bytes", content_type="image/jpeg")

        self.client.post(
            reverse(
                "book_stations:bookstation-edit",
                kwargs={"readable_id": self.approved_station.readable_id},
            ),
            data={
                "name": self.approved_station.name,
                "location": self.approved_station.location,
                "description": self.approved_station.description,
                "picture_upload": upload,
            },
        )
        self.client.logout()

        # The station remains publicly visible after the live edit.
        response = self.client.get(reverse("book_stations:bookstation-list"))

        self.assertContains(response, self.approved_station.name)

    def test_approved_station_edit_visible_to_moderator_after_image_upload(self):
        """After a user uploads a new image to a station, the moderator should see
        the pending edit in the queue and be able to approve it."""
        self.client.login(username="regular", password=self.password)
        upload = SimpleUploadedFile("reapprove.jpg", b"bytes", content_type="image/jpeg")
        self.client.post(
            reverse(
                "book_stations:bookstation-edit",
                kwargs={"readable_id": self.approved_station.readable_id},
            ),
            data={
                "name": self.approved_station.name,
                "location": self.approved_station.location,
                "description": self.approved_station.description,
                "picture_upload": upload,
            },
        )
        self.client.logout()

        # Moderator approves the pending edit
        self.client.login(username="moderator", password=self.password)
        self.client.post(
            reverse(
                "moderation:approve-bookstation-edit",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )
        self.client.logout()

        self.approved_station.refresh_from_db()
        # After approval, pending_edit is cleared and the picture is applied live.
        self.assertIsNone(self.approved_station.pending_edit)
        self.assertTrue(self.approved_station.picture.startswith(self._PICTURE_URL_PREFIX))

    def test_moderator_sees_station_with_pending_image_in_queue(self):
        """After a user uploads a new image to a station, the moderator should see
        it in the moderation queue."""
        self.client.login(username="regular", password=self.password)
        upload = SimpleUploadedFile("queue.jpg", b"bytes", content_type="image/jpeg")
        self.client.post(
            reverse(
                "book_stations:bookstation-edit",
                kwargs={"readable_id": self.approved_station.readable_id},
            ),
            data={
                "name": self.approved_station.name,
                "location": self.approved_station.location,
                "description": self.approved_station.description,
                "picture_upload": upload,
            },
        )
        self.client.logout()

        self.client.login(username="moderator", password=self.password)
        response = self.client.get(reverse("moderation:queue"))

        self.assertContains(response, self.approved_station.name)

    def test_queue_shows_picture_thumbnail_when_station_has_image(self):
        """The moderation queue must render an <img> tag for the uploaded photo so
        that moderators can visually review the image before approving."""
        self.client.login(username="regular", password=self.password)
        upload = SimpleUploadedFile("thumb.jpg", b"fake-bytes", content_type="image/jpeg")
        self.client.post(
            reverse(
                "book_stations:bookstation-edit",
                kwargs={"readable_id": self.approved_station.readable_id},
            ),
            data={
                "name": self.approved_station.name,
                "location": self.approved_station.location,
                "description": self.approved_station.description,
                "picture_upload": upload,
            },
        )
        self.approved_station.refresh_from_db()
        self.client.logout()

        self.client.login(username="moderator", password=self.password)
        response = self.client.get(reverse("moderation:queue"))

        # The queue still lists the station after image edit.
        self.assertContains(response, self.approved_station.name)

    def test_queue_shows_no_picture_column_placeholder_when_no_image(self):
        """When a pending station has no picture, the queue must show a placeholder
        rather than a broken image tag."""
        # pending_station from setUp has no picture
        self.client.login(username="moderator", password=self.password)
        response = self.client.get(reverse("moderation:queue"))

        # Should NOT contain an <img> for the no-picture station
        self.assertNotContains(response, f'alt="Photo of {self.pending_station.name}"')


class ModerationNavLinkTests(ModerationSetUpMixin, TestCase):
    """Tests that the moderation nav link is visible to moderators and hidden from others."""

    def _get_home(self):
        return self.client.get(reverse("book_stations:bookstation-list"))

    def test_nav_link_hidden_for_anonymous(self):
        response = self._get_home()

        self.assertNotContains(response, reverse("moderation:queue"))

    def test_nav_link_hidden_for_regular_user(self):
        self.client.login(username="regular", password=self.password)

        response = self._get_home()

        self.assertNotContains(response, reverse("moderation:queue"))

    def test_nav_link_visible_for_staff_user(self):
        self.client.login(username="moderator", password=self.password)

        response = self._get_home()

        self.assertContains(response, reverse("moderation:queue"))

    def test_nav_link_visible_for_group_moderator_without_staff(self):
        moderators_group, _ = Group.objects.get_or_create(name=MODERATOR_GROUP_NAME)
        self.other_user.groups.add(moderators_group)
        self.client.login(username="other", password=self.password)

        response = self._get_home()

        self.assertContains(response, reverse("moderation:queue"))


class ModerationLogTests(ModerationSetUpMixin, TestCase):
    """Tests that moderation decisions are recorded in ModerationLog."""

    def setUp(self):
        super().setUp()
        from moderation.models import ModerationLog
        self.ModerationLog = ModerationLog

    def test_approve_item_creates_log_entry(self):
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse("moderation:approve-item", kwargs={"item_id": self.pending_item.id})
        )

        log = self.ModerationLog.objects.get(item=self.pending_item)
        self.assertEqual(log.moderator, self.moderator)
        self.assertEqual(log.action, self.ModerationLog.Action.ITEM_APPROVED)
        self.assertEqual(log.from_status, Item.ModerationStatus.FLAGGED)
        self.assertEqual(log.to_status, Item.ModerationStatus.APPROVED)

    def test_approve_bookstation_creates_log_entry(self):
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse(
                "moderation:approve-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        log = self.ModerationLog.objects.get(book_station=self.pending_station)
        self.assertEqual(log.moderator, self.moderator)
        self.assertEqual(log.action, self.ModerationLog.Action.STATION_APPROVED)
        self.assertEqual(log.from_status, BookStation.ModerationStatus.FLAGGED)
        self.assertEqual(log.to_status, BookStation.ModerationStatus.APPROVED)

    def test_approve_item_edit_creates_log_entry(self):
        self.approved_item.pending_edit = {"title": "New Title"}
        self.approved_item.moderation_status = Item.ModerationStatus.FLAGGED
        self.approved_item.save(update_fields=["pending_edit", "moderation_status"])
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse("moderation:approve-item-edit", kwargs={"item_id": self.approved_item.id})
        )

        log = self.ModerationLog.objects.get(item=self.approved_item)
        self.assertEqual(log.moderator, self.moderator)
        self.assertEqual(log.action, self.ModerationLog.Action.ITEM_EDIT_APPROVED)

    def test_reject_item_edit_creates_log_entry(self):
        self.approved_item.pending_edit = {"title": "New Title"}
        self.approved_item.moderation_status = Item.ModerationStatus.FLAGGED
        self.approved_item.save(update_fields=["pending_edit", "moderation_status"])
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse("moderation:reject-item-edit", kwargs={"item_id": self.approved_item.id})
        )

        log = self.ModerationLog.objects.get(item=self.approved_item)
        self.assertEqual(log.moderator, self.moderator)
        self.assertEqual(log.action, self.ModerationLog.Action.ITEM_EDIT_REJECTED)

    def test_approve_bookstation_edit_creates_log_entry(self):
        self.approved_station.pending_edit = {"name": "New Name", "location": "New Location"}
        self.approved_station.moderation_status = BookStation.ModerationStatus.FLAGGED
        self.approved_station.save(update_fields=["pending_edit", "moderation_status"])
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse(
                "moderation:approve-bookstation-edit",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        log = self.ModerationLog.objects.get(book_station=self.approved_station)
        self.assertEqual(log.moderator, self.moderator)
        self.assertEqual(log.action, self.ModerationLog.Action.STATION_EDIT_APPROVED)

    def test_reject_bookstation_edit_creates_log_entry(self):
        self.approved_station.pending_edit = {"name": "New Name", "location": "New Location"}
        self.approved_station.moderation_status = BookStation.ModerationStatus.FLAGGED
        self.approved_station.save(update_fields=["pending_edit", "moderation_status"])
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse(
                "moderation:reject-bookstation-edit",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        log = self.ModerationLog.objects.get(book_station=self.approved_station)
        self.assertEqual(log.moderator, self.moderator)
        self.assertEqual(log.action, self.ModerationLog.Action.STATION_EDIT_REJECTED)

    def test_no_log_entry_on_claim_item(self):
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse("moderation:claim-item", kwargs={"item_id": self.pending_item.id})
        )

        self.assertFalse(self.ModerationLog.objects.filter(item=self.pending_item).exists())


class ModerationRejectTests(ModerationSetUpMixin, TestCase):
    """Tests for the reject action on newly created (PENDING) items and stations."""

    def test_reject_item_deletes_item(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse("moderation:reject-item", kwargs={"item_id": self.pending_item.id})
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.assertFalse(Item.objects.filter(pk=self.pending_item.id).exists())

    def test_reject_item_creates_log_entry(self):
        from moderation.models import ModerationLog
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse("moderation:reject-item", kwargs={"item_id": self.pending_item.id})
        )

        log = ModerationLog.objects.get(
            action=ModerationLog.Action.ITEM_REJECTED,
            moderator=self.moderator,
        )
        self.assertEqual(log.moderator, self.moderator)
        self.assertEqual(log.from_status, Item.ModerationStatus.FLAGGED)
        self.assertEqual(log.to_status, Item.ModerationStatus.REJECTED)
        self.assertIsNone(log.item)

    def test_rejected_item_not_visible_in_browse_items(self):
        self.client.login(username="moderator", password=self.password)
        self.client.post(
            reverse("moderation:reject-item", kwargs={"item_id": self.pending_item.id})
        )
        self.client.logout()

        response = self.client.get(reverse("items:item-list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.pending_item.title)

    def test_rejected_item_has_no_detail_page(self):
        self.client.login(username="moderator", password=self.password)
        self.client.post(
            reverse("moderation:reject-item", kwargs={"item_id": self.pending_item.id})
        )
        self.client.logout()

        response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": self.pending_item.id})
        )

        self.assertEqual(response.status_code, 404)

    def test_reject_bookstation_sets_status_to_rejected(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse(
                "moderation:reject-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.pending_station.refresh_from_db()
        self.assertEqual(self.pending_station.moderation_status, BookStation.ModerationStatus.REJECTED)

    def test_reject_bookstation_creates_log_entry(self):
        from moderation.models import ModerationLog
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse(
                "moderation:reject-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        log = ModerationLog.objects.get(action=ModerationLog.Action.STATION_REJECTED)
        self.assertEqual(log.moderator, self.moderator)
        self.assertEqual(log.from_status, BookStation.ModerationStatus.FLAGGED)
        self.assertEqual(log.to_status, BookStation.ModerationStatus.REJECTED)
        self.assertEqual(log.book_station, self.pending_station)

    def test_regular_user_cannot_reject_item(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.post(
            reverse("moderation:reject-item", kwargs={"item_id": self.pending_item.id})
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Item.objects.filter(pk=self.pending_item.id).exists())

    def test_regular_user_cannot_reject_bookstation(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.post(
            reverse(
                "moderation:reject-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(BookStation.objects.filter(readable_id=self.pending_station.readable_id).exists())

    def test_reject_item_only_works_on_pending(self):
        """Attempting to reject an already-approved item returns 404."""
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse("moderation:reject-item", kwargs={"item_id": self.approved_item.id})
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Item.objects.filter(pk=self.approved_item.id).exists())

    def test_reject_bookstation_only_works_on_pending(self):
        """Attempting to reject an already-approved station returns 404."""
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse(
                "moderation:reject-bookstation",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(BookStation.objects.filter(readable_id=self.approved_station.readable_id).exists())

    def test_queue_shows_reject_button_for_pending_item(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        self.assertContains(
            response,
            reverse("moderation:reject-item", kwargs={"item_id": self.pending_item.id}),
        )

    def test_queue_shows_reject_button_for_pending_station(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        self.assertContains(
            response,
            reverse("moderation:reject-bookstation", kwargs={"readable_id": self.pending_station.readable_id}),
        )


class ReportItemTests(ModerationSetUpMixin, TestCase):
    """Tests for the report item feature."""

    def test_anonymous_user_is_redirected_when_reporting_item(self):
        response = self.client.post(
            reverse("items:item-report", kwargs={"item_id": self.approved_item.id})
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_logged_in_user_can_report_item(self):
        self.client.login(username="other", password=self.password)

        response = self.client.post(
            reverse("items:item-report", kwargs={"item_id": self.approved_item.id})
        )

        self.assertEqual(response.status_code, 302)
        self.approved_item.refresh_from_db()
        self.assertEqual(self.approved_item.moderation_status, Item.ModerationStatus.REPORTED)

    def test_reporting_item_redirects_to_item_detail(self):
        self.client.login(username="other", password=self.password)

        response = self.client.post(
            reverse("items:item-report", kwargs={"item_id": self.approved_item.id})
        )

        self.assertRedirects(
            response,
            reverse("items:item-detail", kwargs={"item_id": self.approved_item.id}),
        )

    def test_reporting_already_reported_item_is_idempotent(self):
        self.approved_item.moderation_status = Item.ModerationStatus.REPORTED
        self.approved_item.save(update_fields=["moderation_status"], create_movement=False)

        self.client.login(username="other", password=self.password)
        response = self.client.post(
            reverse("items:item-report", kwargs={"item_id": self.approved_item.id})
        )

        self.assertEqual(response.status_code, 302)
        self.approved_item.refresh_from_db()
        self.assertEqual(self.approved_item.moderation_status, Item.ModerationStatus.REPORTED)

    def test_cannot_report_rejected_item(self):
        self.approved_item.moderation_status = Item.ModerationStatus.REJECTED
        self.approved_item.save(update_fields=["moderation_status"], create_movement=False)

        self.client.login(username="other", password=self.password)
        response = self.client.post(
            reverse("items:item-report", kwargs={"item_id": self.approved_item.id})
        )

        self.assertEqual(response.status_code, 404)
        self.approved_item.refresh_from_db()
        self.assertEqual(self.approved_item.moderation_status, Item.ModerationStatus.REJECTED)

    def test_cannot_report_pending_item(self):
        self.approved_item.moderation_status = Item.ModerationStatus.FLAGGED
        self.approved_item.save(update_fields=["moderation_status"], create_movement=False)

        self.client.login(username="other", password=self.password)
        response = self.client.post(
            reverse("items:item-report", kwargs={"item_id": self.approved_item.id})
        )

        self.assertEqual(response.status_code, 302)
        self.approved_item.refresh_from_db()
        self.assertEqual(self.approved_item.moderation_status, Item.ModerationStatus.REPORTED)

    def test_get_request_to_report_item_returns_405(self):
        self.client.login(username="other", password=self.password)

        response = self.client.get(
            reverse("items:item-report", kwargs={"item_id": self.approved_item.id})
        )

        self.assertEqual(response.status_code, 405)

    def test_reported_item_appears_in_moderation_queue(self):
        self.approved_item.moderation_status = Item.ModerationStatus.REPORTED
        self.approved_item.save(update_fields=["moderation_status"], create_movement=False)

        self.client.login(username="moderator", password=self.password)
        response = self.client.get(reverse("moderation:queue"))

        self.assertContains(response, self.approved_item.title)
        self.assertContains(response, "Reported Items")

    def test_moderator_can_approve_reported_item(self):
        self.approved_item.moderation_status = Item.ModerationStatus.REPORTED
        self.approved_item.save(update_fields=["moderation_status"], create_movement=False)

        self.client.login(username="moderator", password=self.password)
        response = self.client.post(
            reverse("moderation:approve-reported-item", kwargs={"item_id": self.approved_item.id})
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.approved_item.refresh_from_db()
        self.assertEqual(self.approved_item.moderation_status, Item.ModerationStatus.APPROVED)

    def test_moderator_can_reject_reported_item(self):
        self.approved_item.moderation_status = Item.ModerationStatus.REPORTED
        self.approved_item.save(update_fields=["moderation_status"], create_movement=False)

        self.client.login(username="moderator", password=self.password)
        response = self.client.post(
            reverse("moderation:reject-reported-item", kwargs={"item_id": self.approved_item.id})
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.assertFalse(Item.objects.filter(pk=self.approved_item.id).exists())

    def test_moderator_can_claim_reported_item(self):
        self.approved_item.moderation_status = Item.ModerationStatus.REPORTED
        self.approved_item.save(update_fields=["moderation_status"], create_movement=False)

        self.client.login(username="moderator", password=self.password)
        response = self.client.post(
            reverse("moderation:claim-reported-item", kwargs={"item_id": self.approved_item.id})
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.approved_item.refresh_from_db()
        self.assertEqual(self.approved_item.claimed_by, self.moderator)

    def test_regular_user_cannot_approve_reported_item(self):
        self.approved_item.moderation_status = Item.ModerationStatus.REPORTED
        self.approved_item.save(update_fields=["moderation_status"], create_movement=False)

        self.client.login(username="other", password=self.password)
        response = self.client.post(
            reverse("moderation:approve-reported-item", kwargs={"item_id": self.approved_item.id})
        )

        self.assertEqual(response.status_code, 403)

    def test_approve_reported_item_creates_log_entry(self):
        from moderation.models import ModerationLog
        self.approved_item.moderation_status = Item.ModerationStatus.REPORTED
        self.approved_item.save(update_fields=["moderation_status"], create_movement=False)
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse("moderation:approve-reported-item", kwargs={"item_id": self.approved_item.id})
        )

        log = ModerationLog.objects.get(action=ModerationLog.Action.REPORTED_ITEM_APPROVED)
        self.assertEqual(log.moderator, self.moderator)
        self.assertEqual(log.from_status, Item.ModerationStatus.REPORTED)
        self.assertEqual(log.to_status, Item.ModerationStatus.APPROVED)
        self.assertEqual(log.item, self.approved_item)

    def test_reject_reported_item_creates_log_entry(self):
        from moderation.models import ModerationLog
        self.approved_item.moderation_status = Item.ModerationStatus.REPORTED
        self.approved_item.save(update_fields=["moderation_status"], create_movement=False)
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse("moderation:reject-reported-item", kwargs={"item_id": self.approved_item.id})
        )

        log = ModerationLog.objects.get(
            action=ModerationLog.Action.REPORTED_ITEM_REJECTED,
            moderator=self.moderator,
        )
        self.assertEqual(log.moderator, self.moderator)
        self.assertEqual(log.from_status, Item.ModerationStatus.REPORTED)
        self.assertEqual(log.to_status, Item.ModerationStatus.REJECTED)
        self.assertIsNone(log.item)


class ReportBookStationTests(ModerationSetUpMixin, TestCase):
    """Tests for the report bookstation feature."""

    def test_anonymous_user_is_redirected_when_reporting_station(self):
        response = self.client.post(
            reverse(
                "book_stations:bookstation-report",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_logged_in_user_can_report_station(self):
        self.client.login(username="other", password=self.password)

        response = self.client.post(
            reverse(
                "book_stations:bookstation-report",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.approved_station.refresh_from_db()
        self.assertEqual(
            self.approved_station.moderation_status, BookStation.ModerationStatus.REPORTED
        )

    def test_reporting_station_redirects_to_station_detail(self):
        self.client.login(username="other", password=self.password)

        response = self.client.post(
            reverse(
                "book_stations:bookstation-report",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": self.approved_station.readable_id},
            ),
        )

    def test_reporting_already_reported_station_is_idempotent(self):
        self.approved_station.moderation_status = BookStation.ModerationStatus.REPORTED
        self.approved_station.save(update_fields=["moderation_status"])

        self.client.login(username="other", password=self.password)
        response = self.client.post(
            reverse(
                "book_stations:bookstation-report",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.approved_station.refresh_from_db()
        self.assertEqual(
            self.approved_station.moderation_status, BookStation.ModerationStatus.REPORTED
        )

    def test_cannot_report_rejected_station(self):
        self.approved_station.moderation_status = BookStation.ModerationStatus.REJECTED
        self.approved_station.save(update_fields=["moderation_status"])

        self.client.login(username="other", password=self.password)
        response = self.client.post(
            reverse(
                "book_stations:bookstation-report",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 404)
        self.approved_station.refresh_from_db()
        self.assertEqual(
            self.approved_station.moderation_status, BookStation.ModerationStatus.REJECTED
        )

    def test_cannot_report_pending_station(self):
        self.approved_station.moderation_status = BookStation.ModerationStatus.FLAGGED
        self.approved_station.save(update_fields=["moderation_status"])

        self.client.login(username="other", password=self.password)
        response = self.client.post(
            reverse(
                "book_stations:bookstation-report",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 302)
        self.approved_station.refresh_from_db()
        self.assertEqual(
            self.approved_station.moderation_status, BookStation.ModerationStatus.REPORTED
        )

    def test_get_request_to_report_station_returns_405(self):
        self.client.login(username="other", password=self.password)

        response = self.client.get(
            reverse(
                "book_stations:bookstation-report",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 405)

    def test_reported_station_appears_in_moderation_queue(self):
        self.approved_station.moderation_status = BookStation.ModerationStatus.REPORTED
        self.approved_station.save(update_fields=["moderation_status"])

        self.client.login(username="moderator", password=self.password)
        response = self.client.get(reverse("moderation:queue"))

        self.assertContains(response, self.approved_station.name)
        self.assertContains(response, "Reported BookStations")

    def test_moderator_can_approve_reported_station(self):
        self.approved_station.moderation_status = BookStation.ModerationStatus.REPORTED
        self.approved_station.save(update_fields=["moderation_status"])

        self.client.login(username="moderator", password=self.password)
        response = self.client.post(
            reverse(
                "moderation:approve-reported-bookstation",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.approved_station.refresh_from_db()
        self.assertEqual(
            self.approved_station.moderation_status, BookStation.ModerationStatus.APPROVED
        )

    def test_moderator_can_reject_reported_station(self):
        self.approved_station.moderation_status = BookStation.ModerationStatus.REPORTED
        self.approved_station.save(update_fields=["moderation_status"])

        self.client.login(username="moderator", password=self.password)
        response = self.client.post(
            reverse(
                "moderation:reject-reported-bookstation",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.approved_station.refresh_from_db()
        self.assertEqual(
            self.approved_station.moderation_status, BookStation.ModerationStatus.REJECTED
        )

    def test_moderator_can_claim_reported_station(self):
        self.approved_station.moderation_status = BookStation.ModerationStatus.REPORTED
        self.approved_station.save(update_fields=["moderation_status"])

        self.client.login(username="moderator", password=self.password)
        response = self.client.post(
            reverse(
                "moderation:claim-reported-bookstation",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.approved_station.refresh_from_db()
        self.assertEqual(self.approved_station.claimed_by, self.moderator)

    def test_regular_user_cannot_approve_reported_station(self):
        self.approved_station.moderation_status = BookStation.ModerationStatus.REPORTED
        self.approved_station.save(update_fields=["moderation_status"])

        self.client.login(username="other", password=self.password)
        response = self.client.post(
            reverse(
                "moderation:approve-reported-bookstation",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_approve_reported_station_creates_log_entry(self):
        from moderation.models import ModerationLog
        self.approved_station.moderation_status = BookStation.ModerationStatus.REPORTED
        self.approved_station.save(update_fields=["moderation_status"])
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse(
                "moderation:approve-reported-bookstation",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        log = ModerationLog.objects.get(action=ModerationLog.Action.REPORTED_STATION_APPROVED)
        self.assertEqual(log.moderator, self.moderator)
        self.assertEqual(log.from_status, BookStation.ModerationStatus.REPORTED)
        self.assertEqual(log.to_status, BookStation.ModerationStatus.APPROVED)
        self.assertEqual(log.book_station, self.approved_station)

    def test_reject_reported_station_creates_log_entry(self):
        from moderation.models import ModerationLog
        self.approved_station.moderation_status = BookStation.ModerationStatus.REPORTED
        self.approved_station.save(update_fields=["moderation_status"])
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse(
                "moderation:reject-reported-bookstation",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        log = ModerationLog.objects.get(action=ModerationLog.Action.REPORTED_STATION_REJECTED)
        self.assertEqual(log.moderator, self.moderator)
        self.assertEqual(log.from_status, BookStation.ModerationStatus.REPORTED)
        self.assertEqual(log.to_status, BookStation.ModerationStatus.REJECTED)
        self.assertEqual(log.book_station, self.approved_station)


class ModerationUnclaimTests(ModerationSetUpMixin, TestCase):
    """Tests for the unclaim action."""

    def setUp(self):
        super().setUp()
        self.pending_station.claimed_by = self.moderator
        self.pending_station.save(update_fields=["claimed_by"])
        self.pending_item.claimed_by = self.moderator
        self.pending_item.save(update_fields=["claimed_by"])

    def test_unclaim_bookstation_clears_claimed_by(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse(
                "moderation:unclaim-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.pending_station.refresh_from_db()
        self.assertIsNone(self.pending_station.claimed_by)

    def test_unclaim_item_clears_claimed_by(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse("moderation:unclaim-item", kwargs={"item_id": self.pending_item.id})
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.pending_item.refresh_from_db()
        self.assertIsNone(self.pending_item.claimed_by)

    def test_unclaim_bookstation_respects_next_parameter(self):
        self.client.login(username="moderator", password=self.password)
        detail_url = reverse(
            "book_stations:bookstation-detail",
            kwargs={"readable_id": self.pending_station.readable_id},
        )

        response = self.client.post(
            reverse(
                "moderation:unclaim-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            ),
            data={"next": detail_url},
        )

        self.assertRedirects(response, detail_url)

    def test_unclaim_item_respects_next_parameter(self):
        self.client.login(username="moderator", password=self.password)
        detail_url = reverse("items:item-detail", kwargs={"item_id": self.pending_item.id})

        response = self.client.post(
            reverse("moderation:unclaim-item", kwargs={"item_id": self.pending_item.id}),
            data={"next": detail_url},
        )

        self.assertRedirects(response, detail_url)

    def test_unclaim_bookstation_returns_404_if_not_claimed(self):
        self.pending_station.claimed_by = None
        self.pending_station.save(update_fields=["claimed_by"])
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse(
                "moderation:unclaim-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_unclaim_item_returns_404_if_not_claimed(self):
        self.pending_item.claimed_by = None
        self.pending_item.save(update_fields=["claimed_by"])
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse("moderation:unclaim-item", kwargs={"item_id": self.pending_item.id})
        )

        self.assertEqual(response.status_code, 404)

    def test_regular_user_cannot_unclaim_bookstation(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.post(
            reverse(
                "moderation:unclaim-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 403)
        self.pending_station.refresh_from_db()
        self.assertEqual(self.pending_station.claimed_by, self.moderator)

    def test_different_moderator_cannot_unclaim_another_moderators_station(self):
        User = self.pending_station.added_by.__class__
        second_moderator = User.objects.create_user(
            username="mod2", password=self.password, is_staff=True
        )
        self.client.login(username="mod2", password=self.password)

        response = self.client.post(
            reverse(
                "moderation:unclaim-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 404)
        self.pending_station.refresh_from_db()
        self.assertEqual(self.pending_station.claimed_by, self.moderator)

    def test_queue_shows_unclaim_button_for_claimed_station(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        self.assertContains(response, "Unclaim")

    def test_queue_pending_station_name_is_a_link(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        expected_url = reverse(
            "moderation:moderate-bookstation",
            kwargs={"readable_id": self.pending_station.readable_id},
        )
        self.assertContains(response, expected_url)

    def test_queue_pending_item_name_is_a_link(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        expected_url = reverse(
            "moderation:moderate-item",
            kwargs={"item_id": self.pending_item.id},
        )
        self.assertContains(response, expected_url)


class ModerationDetailViewTests(ModerationSetUpMixin, TestCase):
    """Tests for the moderation detail views for pending stations and items."""

    def test_moderate_pending_bookstation_redirects_to_detail(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        expected_url = reverse(
            "book_stations:bookstation-detail",
            kwargs={"readable_id": self.pending_station.readable_id},
        )
        self.assertRedirects(response, expected_url)

    def test_moderate_pending_item_redirects_to_detail(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-item",
                kwargs={"item_id": self.pending_item.id},
            )
        )

        expected_url = reverse(
            "items:item-detail",
            kwargs={"item_id": self.pending_item.id},
        )
        self.assertRedirects(response, expected_url)

    def test_moderate_bookstation_returns_403_for_regular_user(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_moderate_item_returns_403_for_regular_user(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-item",
                kwargs={"item_id": self.pending_item.id},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_moderate_approved_bookstation_returns_404(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-bookstation",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_moderate_approved_item_returns_404(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-item",
                kwargs={"item_id": self.approved_item.id},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_moderate_reported_bookstation_redirects_to_detail(self):
        self.approved_station.moderation_status = BookStation.ModerationStatus.REPORTED
        self.approved_station.save(update_fields=["moderation_status"])
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-bookstation",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        expected_url = reverse(
            "book_stations:bookstation-detail",
            kwargs={"readable_id": self.approved_station.readable_id},
        )
        self.assertRedirects(response, expected_url)

    def test_moderate_reported_item_redirects_to_detail(self):
        self.approved_item.moderation_status = Item.ModerationStatus.REPORTED
        self.approved_item.save(update_fields=["moderation_status"])
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-item",
                kwargs={"item_id": self.approved_item.id},
            )
        )

        expected_url = reverse(
            "items:item-detail",
            kwargs={"item_id": self.approved_item.id},
        )
        self.assertRedirects(response, expected_url)

    def test_detail_view_shows_approve_button(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            ),
            follow=True,
        )

        self.assertContains(response, "Approve")

    def test_detail_view_shows_claim_button_when_unclaimed(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            ),
            follow=True,
        )

        self.assertContains(response, "Claim")

    def test_detail_view_shows_unclaim_button_when_claimed(self):
        self.pending_station.claimed_by = self.moderator
        self.pending_station.save(update_fields=["claimed_by"])
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            ),
            follow=True,
        )

        self.assertContains(response, "Unclaim")

    def test_detail_view_uses_regular_bookstation_template(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-bookstation",
                kwargs={"readable_id": self.pending_station.readable_id},
            ),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "book_stations/bookstation_detail.html")
        self.assertContains(response, self.pending_station.name)

    def test_detail_view_uses_regular_item_template(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "moderation:moderate-item",
                kwargs={"item_id": self.pending_item.id},
            ),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "items/item_detail.html")
        self.assertContains(response, self.pending_item.title)

    def test_moderation_panel_hidden_for_non_pending_bookstation(self):
        """Moderation actions panel must not appear on an already-approved station."""
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )

        self.assertEqual(response.status_code, 200)
        approve_url = reverse(
            "moderation:approve-bookstation",
            kwargs={"readable_id": self.approved_station.readable_id},
        )
        self.assertNotContains(response, approve_url)

    def test_moderation_panel_hidden_for_non_pending_item(self):
        """Moderation actions panel must not appear on an already-approved item."""
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(
            reverse(
                "items:item-detail",
                kwargs={"item_id": self.approved_item.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        approve_url = reverse(
            "moderation:approve-item",
            kwargs={"item_id": self.approved_item.id},
        )
        self.assertNotContains(response, approve_url)


class ModerationProfileClaimedItemsTests(ModerationSetUpMixin, TestCase):
    """Tests that the profile page shows items claimed for moderation."""

    def test_profile_shows_claimed_items_section_for_moderator(self):
        self.pending_station.claimed_by = self.moderator
        self.pending_station.save(update_fields=["claimed_by"])
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("users:profile"))

        self.assertContains(response, "moderation claims")
        self.assertContains(response, self.pending_station.name)

    def test_profile_shows_claimed_items_for_moderator(self):
        self.pending_item.claimed_by = self.moderator
        self.pending_item.save(update_fields=["claimed_by"])
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("users:profile"))

        self.assertContains(response, self.pending_item.title)

    def test_profile_hides_claimed_section_for_regular_user(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.get(reverse("users:profile"))

        self.assertNotContains(response, "moderation claims")

    def test_profile_shows_empty_claims_section_for_moderator_with_no_claims(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("users:profile"))

        self.assertContains(response, "moderation claims")
        self.assertContains(response, "You have not claimed any items for moderation")


class UnifiedModerationFlowTests(ModerationSetUpMixin, TestCase):
    """Tests that PENDING and REPORTED items use the same claim/approve/reject flow."""

    def setUp(self):
        super().setUp()
        # Make approved_station and approved_item REPORTED so we can test the unified flow.
        self.approved_station.moderation_status = BookStation.ModerationStatus.REPORTED
        self.approved_station.save(update_fields=["moderation_status"])
        self.approved_item.moderation_status = Item.ModerationStatus.REPORTED
        self.approved_item.save(update_fields=["moderation_status"])

    # --- claim via unified URL ---

    def test_claim_reported_bookstation_via_unified_url(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse("moderation:claim-bookstation", kwargs={"readable_id": self.approved_station.readable_id})
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.approved_station.refresh_from_db()
        self.assertEqual(self.approved_station.claimed_by, self.moderator)

    def test_claim_reported_item_via_unified_url(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse("moderation:claim-item", kwargs={"item_id": self.approved_item.id})
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.approved_item.refresh_from_db()
        self.assertEqual(self.approved_item.claimed_by, self.moderator)

    # --- approve via unified URL records correct log action ---

    def test_approve_reported_bookstation_via_unified_url_records_reported_log_action(self):
        from moderation.models import ModerationLog
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse("moderation:approve-bookstation", kwargs={"readable_id": self.approved_station.readable_id})
        )

        self.approved_station.refresh_from_db()
        self.assertEqual(self.approved_station.moderation_status,
                         BookStation.ModerationStatus.APPROVED)
        log = ModerationLog.objects.get(book_station=self.approved_station)
        self.assertEqual(log.action, ModerationLog.Action.REPORTED_STATION_APPROVED)

    def test_approve_reported_item_via_unified_url_records_reported_log_action(self):
        from moderation.models import ModerationLog
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse("moderation:approve-item", kwargs={"item_id": self.approved_item.id})
        )

        self.approved_item.refresh_from_db()
        self.assertEqual(self.approved_item.moderation_status, Item.ModerationStatus.APPROVED)
        log = ModerationLog.objects.get(item=self.approved_item)
        self.assertEqual(log.action, ModerationLog.Action.REPORTED_ITEM_APPROVED)

    def test_reject_reported_bookstation_via_unified_url_records_reported_log_action(self):
        from moderation.models import ModerationLog
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse("moderation:reject-bookstation", kwargs={"readable_id": self.approved_station.readable_id})
        )

        self.approved_station.refresh_from_db()
        self.assertEqual(self.approved_station.moderation_status,
                         BookStation.ModerationStatus.REJECTED)
        log = ModerationLog.objects.get(book_station=self.approved_station)
        self.assertEqual(log.action, ModerationLog.Action.REPORTED_STATION_REJECTED)

    def test_reject_reported_item_via_unified_url_records_reported_log_action(self):
        from moderation.models import ModerationLog
        self.client.login(username="moderator", password=self.password)

        self.client.post(
            reverse("moderation:reject-item", kwargs={"item_id": self.approved_item.id})
        )

        self.assertFalse(Item.objects.filter(pk=self.approved_item.id).exists())
        log = ModerationLog.objects.get(
            action=ModerationLog.Action.REPORTED_ITEM_REJECTED,
            moderator=self.moderator,
        )
        self.assertIsNone(log.item)
        self.assertEqual(log.action, ModerationLog.Action.REPORTED_ITEM_REJECTED)

    # --- queue shows Unclaim button for claimed reported items ---

    def test_queue_shows_unclaim_button_for_claimed_reported_station(self):
        self.approved_station.claimed_by = self.moderator
        self.approved_station.save(update_fields=["claimed_by"])
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        unclaim_url = reverse("moderation:unclaim-bookstation", kwargs={"readable_id": self.approved_station.readable_id})
        self.assertContains(response, unclaim_url)

    def test_queue_shows_unclaim_button_for_claimed_reported_item(self):
        self.approved_item.claimed_by = self.moderator
        self.approved_item.save(update_fields=["claimed_by"])
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        unclaim_url = reverse("moderation:unclaim-item", kwargs={"item_id": self.approved_item.id})
        self.assertContains(response, unclaim_url)

    # --- queue does NOT show claim button when station/item is already claimed ---

    def test_queue_hides_claim_button_for_reported_station_claimed_by_another(self):
        self.approved_station.claimed_by = self.other_user
        self.approved_station.save(update_fields=["claimed_by"])
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        claim_url = reverse("moderation:claim-bookstation", kwargs={"readable_id": self.approved_station.readable_id})
        self.assertNotContains(response, claim_url)

    def test_queue_hides_claim_button_for_reported_item_claimed_by_another(self):
        self.approved_item.claimed_by = self.other_user
        self.approved_item.save(update_fields=["claimed_by"])
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        claim_url = reverse("moderation:claim-item", kwargs={"item_id": self.approved_item.id})
        self.assertNotContains(response, claim_url)


class ModerationProfileClaimedReportedItemsTests(ModerationSetUpMixin, TestCase):
    """Tests that the profile page shows REPORTED items claimed by the moderator (Bug 2 fix)."""

    def setUp(self):
        super().setUp()
        self.approved_station.moderation_status = BookStation.ModerationStatus.REPORTED
        self.approved_station.claimed_by = self.moderator
        self.approved_station.save(update_fields=["moderation_status", "claimed_by"])

        self.approved_item.moderation_status = Item.ModerationStatus.REPORTED
        self.approved_item.claimed_by = self.moderator
        self.approved_item.save(update_fields=["moderation_status", "claimed_by"])

    def test_profile_shows_claimed_reported_station(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("users:profile"))

        self.assertContains(response, self.approved_station.name)

    def test_profile_shows_claimed_reported_item(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("users:profile"))

        self.assertContains(response, self.approved_item.title)


class AutoModerationTests(TestCase):
    """Unit tests for item auto-moderation checks."""

    # --- clean content ---

    def test_returns_no_flags_for_clean_content(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(
            title="A Fine Title",
            author="A. Author",
            description="A perfectly innocent description.",
        )

        self.assertFalse(result["has_bad_language"])
        self.assertEqual(result["flagged_fields"], [])

    # --- URL / link detection ---

    def test_flags_https_url(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(
            title="Read this at https://example.com",
            author="Author",
            description="",
        )

        self.assertTrue(result["has_bad_language"])
        self.assertEqual(result["flagged_fields"], ["title"])

    def test_flags_bare_domain(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(
            title="Visit myshop.com for deals",
            author="Author",
            description="",
        )

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    # --- Unsuitable language (multilingual word lists) ---

    def test_flags_english_profanity(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(
            title="Title",
            author="Author",
            description="This description contains porn content.",
        )

        self.assertTrue(result["has_bad_language"])
        self.assertEqual(result["flagged_fields"], ["description"])

    def test_flags_dutch_bad_word(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(title="Kut boek", author="", description="")

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    def test_flags_german_bad_word(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(title="Scheiße!", author="", description="")

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    def test_flags_french_bad_word(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(title="Merde alors", author="", description="")

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    def test_flags_spanish_bad_word(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(title="Mierda de libro", author="", description="")

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    # --- Commercial / spam language detection ---

    def test_flags_english_spam_phrase(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(
            title="Limited time offer - buy now",
            author="Author",
            description="Description",
        )

        self.assertTrue(result["has_bad_language"])
        self.assertEqual(result["flagged_fields"], ["title"])

    def test_flags_dutch_spam_phrase(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(title="Klik hier voor informatie", author="", description="")

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    def test_flags_german_spam_phrase(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(title="Jetzt kaufen und sparen", author="", description="")

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    # --- Social-media account / handle detection ---

    def test_flags_at_username_handle(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(title="DM me @myshop123", author="", description="")

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    def test_flags_instagram_profile_link(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(
            title="Follow us on instagram.com/mystore",
            author="",
            description="",
        )

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    def test_flags_whatsapp_phone_number(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(
            title="Order via WhatsApp +31612345678",
            author="",
            description="",
        )

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    def test_flags_symbol_only_bad_word(self):
        from moderation.auto_moderation import auto_moderate_item

        # 🖕 is in the EN bad-word list; it contains no \w characters so the
        # word-boundary trick doesn't apply – the symbol-only branch must handle it.
        result = auto_moderate_item(title="Read this 🖕", author="", description="")

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    # --- Junk-text detection ---

    def test_flags_repeated_characters(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(title="Heyyyyyy looooool", author="", description="")

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    def test_flags_emoji_flood(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(title="🔥🔥🔥 Amazing deal 🚀🚀🚀", author="", description="")

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])

    def test_clean_text_with_single_emoji_not_flagged(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(title="Great book 📚", author="Author", description="")

        self.assertFalse(result["has_bad_language"])

    # --- Stub override ---

    @override_settings(ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS=["title", "description"])
    def test_setting_can_still_force_flagged_fields(self):
        from moderation.auto_moderation import auto_moderate_item

        result = auto_moderate_item(
            title="Title",
            author="Author",
            description="Description",
        )

        self.assertTrue(result["has_bad_language"])
        self.assertIn("title", result["flagged_fields"])
        self.assertIn("description", result["flagged_fields"])

    def test_can_moderate_custom_field_names(self):
        from moderation.auto_moderation import auto_moderate_fields

        result = auto_moderate_fields(
            values={
                "username": "hot_deals_account",
                "bio": "Limited time offer - buy now",
            }
        )

        self.assertTrue(result["has_bad_language"])
        self.assertEqual(result["flagged_fields"], ["bio"])

    @override_settings(ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS=["username", "title"])
    def test_stub_override_uses_configured_check_order_fields(self):
        from moderation.auto_moderation import auto_moderate_fields

        result = auto_moderate_fields(
            values={"username": "clean_name"},
            check_order=("username",),
        )

        self.assertTrue(result["has_bad_language"])
        self.assertEqual(result["flagged_fields"], ["username"])
        self.assertNotIn("title", result["flagged_fields"])

    @override_settings(ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS=["username"])
    def test_stub_flagged_fields_preserve_check_order(self):
        from moderation.auto_moderation import auto_moderate_fields

        result = auto_moderate_fields(
            values={
                "username": "clean_name",
                "bio": "Limited time offer - buy now",
            },
            check_order=("username", "bio"),
        )

        self.assertTrue(result["has_bad_language"])
        self.assertEqual(result["flagged_fields"], ["username", "bio"])

    def test_check_order_deduplicates_flagged_fields(self):
        from moderation.auto_moderation import auto_moderate_fields

        result = auto_moderate_fields(
            values={"bio": "Limited time offer - buy now"},
            check_order=("bio", "bio"),
        )

        self.assertTrue(result["has_bad_language"])
        self.assertEqual(result["flagged_fields"], ["bio"])

    @override_settings(ITEM_AUTOMODERATION_STUB_FLAGGED_FIELDS=["bio"])
    def test_stub_field_not_duplicated_with_duplicate_check_order(self):
        from moderation.auto_moderation import auto_moderate_fields

        result = auto_moderate_fields(
            values={"bio": "Clean bio"},
            check_order=("bio", "bio"),
        )

        self.assertTrue(result["has_bad_language"])
        self.assertEqual(result["flagged_fields"], ["bio"])


class ActivityViewAccessTests(ModerationSetUpMixin, TestCase):
    """Tests that activity views are only accessible to moderators."""

    def test_anonymous_user_redirected_from_bookstation_activity(self):
        response = self.client.get(reverse("moderation:bookstation-activity"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_regular_user_gets_403_for_bookstation_activity(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.get(reverse("moderation:bookstation-activity"))

        self.assertEqual(response.status_code, 403)

    def test_moderator_can_access_bookstation_activity(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:bookstation-activity"))

        self.assertEqual(response.status_code, 200)

    def test_anonymous_user_redirected_from_item_activity(self):
        response = self.client.get(reverse("moderation:item-activity"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_regular_user_gets_403_for_item_activity(self):
        self.client.login(username="regular", password=self.password)

        response = self.client.get(reverse("moderation:item-activity"))

        self.assertEqual(response.status_code, 403)

    def test_moderator_can_access_item_activity(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:item-activity"))

        self.assertEqual(response.status_code, 200)


class ActivityViewContentTests(ModerationSetUpMixin, TestCase):
    """Tests that activity views show the correct records."""

    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.new_station = BookStation.objects.create(
            name="New Station",
            location="Somewhere",
            added_by=self.regular_user,
            moderation_status=BookStation.ModerationStatus.NEW,
        )
        self.new_item = Item.objects.create(
            title="New Book",
            author="Author C",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.UNKNOWN,
            added_by=self.regular_user,
            moderation_status=Item.ModerationStatus.NEW,
        )
        self.client.login(username="moderator", password=self.password)

    def test_bookstation_activity_shows_new_stations(self):
        response = self.client.get(reverse("moderation:bookstation-activity"))

        self.assertContains(response, "New Station")

    def test_bookstation_activity_does_not_show_approved_stations(self):
        response = self.client.get(reverse("moderation:bookstation-activity"))

        self.assertNotContains(response, "Approved Station")

    def test_bookstation_activity_shows_stations_with_pending_edit(self):
        self.approved_station.pending_edit = {"name": "Updated Name"}
        self.approved_station.save()

        response = self.client.get(reverse("moderation:bookstation-activity"))

        self.assertContains(response, "Approved Station")

    def test_item_activity_shows_new_items(self):
        response = self.client.get(reverse("moderation:item-activity"))

        self.assertContains(response, "New Book")

    def test_item_activity_does_not_show_approved_items(self):
        response = self.client.get(reverse("moderation:item-activity"))

        self.assertNotContains(response, "Approved Book")

    def test_item_activity_shows_items_with_pending_edit(self):
        self.approved_item.pending_edit = {"title": "Updated Title"}
        self.approved_item.save(create_movement=False)

        response = self.client.get(reverse("moderation:item-activity"))

        self.assertContains(response, "Approved Book")

    def test_bookstation_activity_pagination(self):
        # Create enough stations to trigger pagination (page size = 20).
        for i in range(25):
            BookStation.objects.create(
                name=f"Extra Station {i}",
                location="Somewhere",
                added_by=self.regular_user,
                moderation_status=BookStation.ModerationStatus.NEW,
            )

        response = self.client.get(reverse("moderation:bookstation-activity"))
        self.assertEqual(response.status_code, 200)

        response_page2 = self.client.get(
            reverse("moderation:bookstation-activity"), {"page": 2}
        )
        self.assertEqual(response_page2.status_code, 200)

    def test_item_activity_pagination(self):
        # Create enough items to trigger pagination (page size = 20).
        for i in range(25):
            Item.objects.create(
                title=f"Extra Book {i}",
                author="Author",
                item_type=Item.ItemType.BOOK,
                status=Item.Status.UNKNOWN,
                added_by=self.regular_user,
                moderation_status=Item.ModerationStatus.NEW,
            )

        response = self.client.get(reverse("moderation:item-activity"))
        self.assertEqual(response.status_code, 200)

        response_page2 = self.client.get(
            reverse("moderation:item-activity"), {"page": 2}
        )
        self.assertEqual(response_page2.status_code, 200)
