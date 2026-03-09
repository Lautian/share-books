from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.templatetags.static import static
from django.utils import timezone


class BookStation(models.Model):
	name = models.CharField(max_length=150)
	readable_id = models.SlugField(max_length=64, unique=True)
	description = models.TextField(blank=True)
	picture = models.CharField(max_length=255, blank=True)
	latitude = models.DecimalField(
		max_digits=9,
		decimal_places=6,
		validators=[MinValueValidator(-90), MaxValueValidator(90)],
	)
	longitude = models.DecimalField(
		max_digits=9,
		decimal_places=6,
		validators=[MinValueValidator(-180), MaxValueValidator(180)],
	)
	location = models.CharField(max_length=255)

	class Meta:
		ordering = ["name"]

	def __str__(self):
		return f"{self.name} ({self.readable_id})"

	@property
	def picture_url(self):
		if not self.picture:
			return ""
		if self.picture.startswith(("http://", "https://", "/")):
			return self.picture
		return static(self.picture)


class Item(models.Model):
	class ItemType(models.TextChoices):
		BOOK = "BOOK", "Book"
		MAGAZINE = "MAGAZINE", "Magazine"
		DVD = "DVD", "DVD"
		OTHER = "OTHER", "Other"

	class Status(models.TextChoices):
		AT_BOOK_STATION = "AT_BOOK_STATION", "At book station"
		TAKEN_OUT = "TAKEN_OUT", "Taken out"
		LOST = "LOST", "Lost"
		UNKNOWN = "UNKNOWN", "Unknown"

	title = models.CharField(max_length=255)
	author = models.CharField(max_length=255, blank=True)
	description = models.TextField(blank=True)
	item_type = models.CharField(
		max_length=16,
		choices=ItemType.choices,
		default=ItemType.BOOK,
	)
	status = models.CharField(
		max_length=24,
		choices=Status.choices,
		default=Status.UNKNOWN,
	)
	current_book_station = models.ForeignKey(
		BookStation,
		related_name="current_items",
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
	)
	last_seen_at = models.ForeignKey(
		BookStation,
		related_name="last_seen_items",
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
	)
	last_activity = models.DateField(null=True, blank=True)

	class Meta:
		ordering = ["title", "id"]
		constraints = [
			models.CheckConstraint(
				condition=(
					~models.Q(status="AT_BOOK_STATION")
					| models.Q(current_book_station__isnull=False)
				),
				name="item_station_required_when_at_station",
			)
		]
		indexes = [
			models.Index(fields=["status", "current_book_station"]),
			models.Index(fields=["item_type"]),
			models.Index(fields=["last_activity"]),
		]

	def __str__(self):
		return f"{self.title} [{self.status}]"

	def clean(self):
		super().clean()
		if self.status == self.Status.AT_BOOK_STATION and self.current_book_station_id is None:
			raise ValidationError(
				{
					"current_book_station": (
						"Current book station is required when status is AT_BOOK_STATION."
					)
				}
			)

	def save(self, *args, **kwargs):
		if self.last_activity is None:
			self.last_activity = timezone.localdate()
		if (
			self.status == self.Status.AT_BOOK_STATION
			and self.current_book_station_id is not None
			and self.last_seen_at_id is None
		):
			self.last_seen_at = self.current_book_station
		super().save(*args, **kwargs)
