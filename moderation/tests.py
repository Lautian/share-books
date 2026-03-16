import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from book_stations.models import BookStation
from items.models import Item


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
            moderation_status=BookStation.ModerationStatus.PENDING,
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
            moderation_status=Item.ModerationStatus.PENDING,
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
    """Tests that the moderation queue is only accessible to staff users."""

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

    def test_queue_shows_pending_stations_and_items(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.get(reverse("moderation:queue"))

        self.assertContains(response, "Pending Station")
        self.assertContains(response, "Pending Book")
        self.assertNotContains(response, "Approved Station")
        self.assertNotContains(response, "Approved Book")


class ModerationVisibilityTests(ModerationSetUpMixin, TestCase):
    """Tests that pending content is hidden from public views."""

    def test_bookstation_list_hides_pending_for_anonymous(self):
        response = self.client.get(reverse("book_stations:bookstation-list"))

        self.assertNotContains(response, "Pending Station")
        self.assertContains(response, "Approved Station")

    def test_bookstation_list_hides_pending_for_regular_user(self):
        self.client.login(username="other", password=self.password)

        response = self.client.get(reverse("book_stations:bookstation-list"))

        self.assertNotContains(response, "Pending Station")
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

        self.assertEqual(response.status_code, 404)

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

        self.assertEqual(response.status_code, 404)

    def test_item_list_hides_pending_for_anonymous(self):
        response = self.client.get(reverse("items:item-list"))

        self.assertNotContains(response, "Pending Book")
        self.assertContains(response, "Approved Book")

    def test_pending_item_detail_returns_404_for_anonymous(self):
        response = self.client.get(
            reverse("items:item-detail", kwargs={"item_id": self.pending_item.id})
        )

        self.assertEqual(response.status_code, 404)

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

        self.assertEqual(response.status_code, 404)


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
            BookStation.ModerationStatus.PENDING,
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
            Item.ModerationStatus.PENDING,
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

    def test_claim_item_assigns_moderator(self):
        self.client.login(username="moderator", password=self.password)

        response = self.client.post(
            reverse("moderation:claim-item", kwargs={"item_id": self.pending_item.id})
        )

        self.assertRedirects(response, reverse("moderation:queue"))
        self.pending_item.refresh_from_db()
        self.assertEqual(self.pending_item.claimed_by, self.moderator)

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
            station.moderation_status, BookStation.ModerationStatus.PENDING
        )

    def test_create_item_through_form_is_pending(self):
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
        self.assertEqual(item.moderation_status, Item.ModerationStatus.PENDING)

    def test_edit_approved_bookstation_resets_to_pending(self):
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
        self.assertEqual(
            self.approved_station.moderation_status,
            BookStation.ModerationStatus.PENDING,
        )

    def test_edit_approved_item_resets_to_pending(self):
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
            self.approved_item.moderation_status, Item.ModerationStatus.PENDING
        )

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

        self.assertContains(response, "Awaiting moderation")

    def test_profile_shows_no_badge_for_approved_station(self):
        # Only the pending station is there, so remove it to isolate
        self.pending_station.delete()
        self.pending_item.delete()
        self.client.login(username="regular", password=self.password)

        response = self.client.get(reverse("users:profile"))

        self.assertNotContains(response, "Awaiting moderation")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ModerationImageUploadTests(ModerationSetUpMixin, TestCase):
    """Tests that image uploads on BookStations are subject to moderation."""

    _PICTURE_URL_PREFIX = "/media/book_stations/images/photos/"

    def test_create_station_with_image_is_pending(self):
        """A new station submitted with an image upload must start as PENDING."""
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
        self.assertEqual(
            station.moderation_status,
            BookStation.ModerationStatus.PENDING,
        )
        # The picture URL should already be saved (file stored, pending review)
        self.assertTrue(station.picture.startswith(self._PICTURE_URL_PREFIX))

    def test_uploading_image_to_approved_station_resets_to_pending(self):
        """Uploading a new image to an already-approved station must trigger re-moderation."""
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
        self.assertEqual(
            self.approved_station.moderation_status,
            BookStation.ModerationStatus.PENDING,
        )
        # The picture must be stored already (saved to disk, awaiting moderator review)
        self.assertTrue(
            self.approved_station.picture.startswith(self._PICTURE_URL_PREFIX)
        )

    def test_station_with_new_image_disappears_from_public_list_until_approved(self):
        """After uploading an image to an approved station, it should disappear from
        the public list view until a moderator approves it again."""
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

        # Public view must not show the station with the unreviewed image
        response = self.client.get(reverse("book_stations:bookstation-list"))

        self.assertNotContains(response, self.approved_station.name)

    def test_approved_station_reappears_after_moderator_approves_new_image(self):
        """After a moderator approves the re-submitted station (with new image), it must
        become publicly visible again."""
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

        # Moderator approves
        self.client.login(username="moderator", password=self.password)
        self.client.post(
            reverse(
                "moderation:approve-bookstation",
                kwargs={"readable_id": self.approved_station.readable_id},
            )
        )
        self.client.logout()

        # Station should now be visible again
        response = self.client.get(reverse("book_stations:bookstation-list"))

        self.assertContains(response, self.approved_station.name)

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

