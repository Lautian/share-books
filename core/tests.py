from io import StringIO

from django.core.management import call_command
from django.test import TestCase


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
