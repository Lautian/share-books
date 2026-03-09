from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.db import models
from django.templatetags.static import static
from django.utils.text import slugify


class BookStation(models.Model):
	name = models.CharField(max_length=150)
	readable_id = models.SlugField(max_length=64, unique=True, blank=True)
	description = models.TextField(blank=True)
	picture = models.CharField(max_length=255, blank=True)
	latitude = models.DecimalField(
		max_digits=9,
		decimal_places=6,
		null=True,
		blank=True,
		validators=[MinValueValidator(-90), MaxValueValidator(90)],
	)
	longitude = models.DecimalField(
		max_digits=9,
		decimal_places=6,
		null=True,
		blank=True,
		validators=[MinValueValidator(-180), MaxValueValidator(180)],
	)
	location = models.CharField(max_length=255)
	added_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="added_book_stations",
	)

	class Meta:
		ordering = ["name"]

	def __str__(self):
		return f"{self.name} ({self.readable_id})"

	def clean(self):
		super().clean()
		if (self.latitude is None) != (self.longitude is None):
			raise ValidationError(
				{
					"latitude": "Provide both latitude and longitude, or leave both empty.",
					"longitude": "Provide both latitude and longitude, or leave both empty.",
				}
			)

	def _generate_unique_readable_id(self):
		base_slug = slugify(self.name)[:64] or "station"
		candidate = base_slug
		suffix = 2

		while BookStation.objects.exclude(pk=self.pk).filter(readable_id=candidate).exists():
			suffix_token = f"-{suffix}"
			candidate = f"{base_slug[:64 - len(suffix_token)]}{suffix_token}"
			suffix += 1

		return candidate

	def save(self, *args, **kwargs):
		if not self.readable_id:
			self.readable_id = self._generate_unique_readable_id()
		super().save(*args, **kwargs)

	@property
	def picture_url(self):
		if not self.picture:
			return ""
		if self.picture.startswith(("http://", "https://", "/")):
			return self.picture
		return static(self.picture)
