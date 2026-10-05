from io import StringIO
import os
import subprocess
import sys

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


class ProductionSettingsTests(TestCase):
    def test_environment_configures_railway_production_services(self):
        environment = os.environ.copy()
        environment.update(
            {
                "SECRET_KEY": "test-production-secret",
                "DATABASE_URL": "postgresql://localhost/sharebooks",
                "RAILWAY_PUBLIC_DOMAIN": "share-books.up.railway.app",
                "AWS_S3_BUCKET_NAME": "share-books-uploads",
                "ENDPOINT": "https://storage.example.test",
                "ACCESS_KEY_ID": "test-access-key",
                "SECRET_ACCESS_KEY": "test-secret-key",
                "REGION": "auto",
            }
        )
        check_settings = """
from share_books.settings import production as settings

assert settings.DEBUG is False
assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
assert "share-books.up.railway.app" in settings.ALLOWED_HOSTS
assert "https://share-books.up.railway.app" in settings.CSRF_TRUSTED_ORIGINS
assert settings.STORAGES["default"]["BACKEND"] == "storages.backends.s3.S3Storage"
assert settings.AWS_STORAGE_BUCKET_NAME == "share-books-uploads"
assert settings.AWS_S3_ENDPOINT_URL == "https://storage.example.test"
assert "whitenoise.middleware.WhiteNoiseMiddleware" in settings.MIDDLEWARE
"""
        result = subprocess.run(
            [sys.executable, "-c", check_settings],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


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
        self.assertNotContains(response, "Sign up")
        mobile_menu = response.content.split(b'aria-label="Open menu"', 1)[1].split(
            b"</ul>", 1
        )[0]
        self.assertNotIn(b'href="/admin/"', mobile_menu)
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
        self.assertLess(
            response.content.index(b'href="/admin/"'),
            response.content.index(b"Log out"),
        )
        self.assertContains(response, "Log out")
        self.assertNotContains(response, reverse("users:login"))
