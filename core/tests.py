from django.test import TestCase


class HomePageViewTests(TestCase):
    def test_root_renders_homepage(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")
        self.assertContains(response, "Little libraries")
        self.assertContains(response, "Book stations")
