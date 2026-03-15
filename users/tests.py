from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from book_stations.models import BookStation
from items.models import Item

from .tokens import email_verification_token


@override_settings(
    RECAPTCHA_PUBLIC_KEY="test-public-key",
    RECAPTCHA_PRIVATE_KEY="test-private-key",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_URL="http://testserver",
)
class UserAuthorizationTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.password = "SafePassword123"
        self.user = self.user_model.objects.create_user(
            username="reader",
            password=self.password,
        )
        self.other_user = self.user_model.objects.create_user(
            username="other-reader",
            password=self.password,
        )

    def test_signup_page_loads(self):
        response = self.client.get(reverse("users:signup"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/signup.html")

    def test_signup_creates_inactive_user_and_sends_verification_email(self):
        from django_recaptcha.client import RecaptchaResponse

        with patch("django_recaptcha.fields.client.submit") as mock_submit:
            mock_submit.return_value = RecaptchaResponse(is_valid=True)
            response = self.client.post(
                reverse("users:signup"),
                data={
                    "username": "newreader",
                    "email": "newreader@example.com",
                    "password1": "StrongPass123",
                    "password2": "StrongPass123",
                    "g-recaptcha-response": "PASSED",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/signup_verify_email.html")
        user = self.user_model.objects.get(username="newreader")
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("newreader@example.com", mail.outbox[0].to)
        self.assertIn("verify", mail.outbox[0].body.lower())

    def test_email_verification_activates_user_and_logs_in(self):
        unverified = self.user_model.objects.create_user(
            username="unverified",
            email="unverified@example.com",
            password="StrongPass123",
            is_active=False,
        )
        uid = urlsafe_base64_encode(force_bytes(unverified.pk))
        token = email_verification_token.make_token(unverified)

        response = self.client.get(
            reverse("users:verify-email", kwargs={"uidb64": uid, "token": token})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/email_verified.html")
        unverified.refresh_from_db()
        self.assertTrue(unverified.is_active)
        self.assertEqual(
            str(self.client.session.get("_auth_user_id")), str(unverified.id)
        )

    def test_email_verification_invalid_token(self):
        unverified = self.user_model.objects.create_user(
            username="unverified2",
            email="unverified2@example.com",
            password="StrongPass123",
            is_active=False,
        )
        uid = urlsafe_base64_encode(force_bytes(unverified.pk))

        response = self.client.get(
            reverse("users:verify-email", kwargs={"uidb64": uid, "token": "bad-token"})
        )

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "users/email_verification_invalid.html")
        unverified.refresh_from_db()
        self.assertFalse(unverified.is_active)

    def test_email_verification_invalid_uid(self):
        response = self.client.get(
            reverse("users:verify-email", kwargs={"uidb64": "not-valid", "token": "bad-token"})
        )

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "users/email_verification_invalid.html")

    def test_login_page_loads(self):
        response = self.client.get(reverse("users:login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")

    def test_login_authenticates_user(self):
        response = self.client.post(
            reverse("users:login"),
            data={"username": "reader", "password": self.password},
        )

        self.assertRedirects(response, reverse("users:profile"))
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(self.user.id))

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse("users:profile"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_profile_view_for_authenticated_user(self):
        self.client.login(username="reader", password=self.password)

        station = BookStation.objects.create(
            name="Profile Station",
            location="City Center",
            added_by=self.user,
        )
        Item.objects.create(
            title="Profile Item",
            author="Writer",
            item_type=Item.ItemType.BOOK,
            status=Item.Status.UNKNOWN,
            added_by=self.user,
        )
        BookStation.objects.create(
            name="Other User Station",
            location="Elsewhere",
            added_by=self.other_user,
        )

        response = self.client.get(reverse("users:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")
        self.assertContains(response, "reader")
        self.assertContains(response, "Profile Station")
        self.assertContains(response, "Profile Item")
        self.assertNotContains(response, "Other User Station")
        self.assertContains(response, reverse("book_stations:bookstation-create"))
        self.assertContains(response, reverse("items:item-create"))
        self.assertContains(
            response,
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": station.readable_id},
            ),
        )
        self.assertContains(
            response,
            reverse(
                "book_stations:bookstation-edit",
                kwargs={"readable_id": station.readable_id},
            ),
        )
        self.assertContains(
            response,
            reverse(
                "book_stations:bookstation-delete",
                kwargs={"readable_id": station.readable_id},
            ),
        )
        user_item = Item.objects.get(title="Profile Item")
        self.assertContains(
            response,
            reverse("items:item-edit", kwargs={"item_id": user_item.id}),
        )
        self.assertContains(
            response,
            reverse("items:item-delete", kwargs={"item_id": user_item.id}),
        )

    def test_logout_clears_session(self):
        self.client.login(username="reader", password=self.password)

        response = self.client.post(reverse("users:logout"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/logged_out.html")
        self.assertIsNone(self.client.session.get("_auth_user_id"))

