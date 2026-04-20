from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse


class HomePageViewTests(TestCase):
    def test_root_renders_homepage(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")
        self.assertContains(response, "Little libraries")
        self.assertContains(response, "Book stations")


class MigrationConsistencyTests(TestCase):
    """Regression test: ensure every model change has a corresponding migration.

    This guards against the 'no such table' OperationalError that occurs when
    code references a model (e.g. ModerationLog) whose migration was never
    generated after the model was added or altered.
    """

    def test_no_missing_migrations(self):
        out = StringIO()
        try:
            call_command(
                "makemigrations",
                "--check",
                "--dry-run",
                stdout=out,
                stderr=out,
            )
        except SystemExit as exc:
            if exc.code != 0:
                self.fail(
                    f"Missing migrations detected (run 'python manage.py makemigrations'):\n{out.getvalue()}"
                )


class NavigationBarTests(TestCase):
    def test_navbar_contains_browse_items_link(self):
        response = self.client.get("/")

        self.assertContains(response, reverse("items:item-list"))
        self.assertContains(response, "Browse Items")

    def test_navbar_shows_login_actions_for_anonymous_user(self):
        response = self.client.get("/")

        self.assertContains(response, reverse("users:login"))
        self.assertContains(response, reverse("users:signup"))
        self.assertNotContains(response, reverse("users:profile"))

    def test_navbar_shows_account_actions_for_authenticated_user(self):
        user = get_user_model().objects.create_user(
            username="nav-user",
            password="StrongPass123",
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertContains(response, reverse("users:profile"))
        self.assertContains(response, reverse("book_stations:bookstation-create"))
        self.assertContains(response, reverse("items:item-create"))
        self.assertContains(response, "Log out")
        self.assertNotContains(response, reverse("users:login"))
