from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from book_stations.models import BookStation
from items.models import Item
from users.models import UserProfile


class UserAuthorizationTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.password = "ReaderPassword123!"
        self.user = self.user_model.objects.create_user(
            username="reader",
        )
        self.user.set_password(self.password)
        self.user.save()
        self.other_user = self.user_model.objects.create_user(
            username="other-reader",
        )

    def test_public_signup_is_unavailable(self):
        response = self.client.get("/users/signup/")

        self.assertEqual(response.status_code, 404)

    def test_users_remain_available_in_admin(self):
        self.assertTrue(admin.site.is_registered(self.user_model))

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
        self.client.force_login(self.user)

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
        self.client.force_login(self.user)

        response = self.client.post(reverse("users:logout"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/logged_out.html")
        self.assertIsNone(self.client.session.get("_auth_user_id"))

    def test_logout_shows_user_login_link_not_admin(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("users:logout"))

        self.assertTemplateUsed(response, "users/logged_out.html")
        self.assertContains(
            response,
            f'<a href="{reverse("users:login")}" class="btn btn-primary">Log in again</a>',
            html=True,
        )


class LanguagePreferenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="lang")
        self.user.set_password("pw12345!")
        self.user.save()

    def test_nl_prefix_renders_dutch(self):
        response = self.client.get("/nl/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Language"], "nl")
        self.assertContains(response, 'lang="nl"')
        self.assertContains(response, "Stations bekijken")

    def test_default_language_has_no_prefix(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Language"], "en")

    def test_set_language_saves_preference_for_logged_in_user(self):
        self.client.force_login(self.user)
        response = self.client.post("/i18n/setlang/", {"language": "nl", "next": "/"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/nl/")
        self.assertEqual(UserProfile.objects.get(user=self.user).language, "nl")

    def test_profile_form_saves_language(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("users:profile"), {"language": "nl"})
        self.assertRedirects(response, "/nl/users/profile/")
        self.assertEqual(self.user.profile.language, "nl")

    def test_login_switches_to_preferred_language(self):
        UserProfile.objects.create(user=self.user, language="nl")
        response = self.client.post(
            reverse("users:login"), {"username": "lang", "password": "pw12345!"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/nl/users/profile/")
        self.assertEqual(response.cookies["django_language"].value, "nl")
