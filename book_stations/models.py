from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class BookStation(models.Model):
	name = models.CharField(max_length=150)
	readable_id = models.SlugField(max_length=64, unique=True)
	description = models.TextField(blank=True)
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
