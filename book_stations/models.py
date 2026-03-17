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
	location = models.CharField(max_length=255, blank=True)
	added_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="added_book_stations",
	)

	class ModerationStatus(models.TextChoices):
		PENDING = "PENDING", "Pending moderation"
		APPROVED = "APPROVED", "Approved"
		REPORTED = "REPORTED", "Reported"

	moderation_status = models.CharField(
		max_length=16,
		choices=ModerationStatus.choices,
		default=ModerationStatus.APPROVED,
	)
	claimed_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="claimed_book_stations",
	)
	pending_edit = models.JSONField(
		null=True,
		blank=True,
		default=None,
		help_text="Serialised pending edit fields submitted by the owner. None means no edit is awaiting moderation.",
	)

	class Meta:
		ordering = ["name"]
		constraints = [
			models.CheckConstraint(
				name="bookstation_lat_lon_both_or_none",
				condition=(
					(models.Q(latitude__isnull=True) & models.Q(longitude__isnull=True))
					| (models.Q(latitude__isnull=False) & models.Q(longitude__isnull=False))
				),
			),
			models.CheckConstraint(
				name="bookstation_location_or_geolocation",
				condition=(
					~models.Q(location="")
					| (models.Q(latitude__isnull=False) & models.Q(longitude__isnull=False))
				),
			),
		]

	def __str__(self):
		return f"{self.name} ({self.readable_id})"

	def clean(self):
		super().clean()
		errors = {}
		coordinate_message = "Provide both latitude and longitude, or leave both empty."
		location_or_geo_message = "Provide either a textual location or both latitude and longitude."

		if (self.latitude is None) != (self.longitude is None):
			errors["latitude"] = coordinate_message
			errors["longitude"] = coordinate_message

		has_textual_location = bool((self.location or "").strip())
		has_geolocation = self.latitude is not None and self.longitude is not None

		if not has_textual_location and not has_geolocation:
			errors["location"] = location_or_geo_message
			errors.setdefault("latitude", location_or_geo_message)
			errors.setdefault("longitude", location_or_geo_message)

		if errors:
			raise ValidationError(errors)

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
