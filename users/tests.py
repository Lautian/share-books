from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from book_stations.models import BookStation, Item


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

    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("users:signup"),
            data={
                "username": "newreader",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )

        self.assertRedirects(response, reverse("users:profile"))
        self.assertTrue(self.user_model.objects.filter(username="newreader").exists())
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(self.user_model.objects.get(username="newreader").id))

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
        self.assertContains(response, reverse("book_stations:item-create"))
        self.assertContains(
            response,
            reverse(
                "book_stations:bookstation-detail",
                kwargs={"readable_id": station.readable_id},
            ),
        )

    def test_logout_clears_session(self):
        self.client.login(username="reader", password=self.password)

        response = self.client.post(reverse("users:logout"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/logged_out.html")
        self.assertIsNone(self.client.session.get("_auth_user_id"))
