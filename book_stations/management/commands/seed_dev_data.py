from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from book_stations.models import BookStation
from items.models import Item

DEFAULT_PASSWORD = "dev-password-123"

USERS = ["dev_alice", "dev_bob"]

# Every optional field (description, picture, coordinates, location) is filled
# for at least two stations; the others leave some of them empty.
STATIONS = [
	{
		"name": "Central Park Little Library",
		"owner": "dev_alice",
		"description": "A weatherproof cabinet next to the park entrance.",
		"picture": "https://example.com/pictures/central-park.jpg",
		"latitude": Decimal("52.370216"),
		"longitude": Decimal("4.895168"),
		"location": "Central Park, Main Entrance",
	},
	{
		"name": "Station Platform Shelf",
		"owner": "dev_bob",
		"description": "Take a book for the train ride, leave one for the next traveller.",
		"picture": "https://example.com/pictures/station-platform.jpg",
		"latitude": Decimal("51.924420"),
		"longitude": Decimal("4.477733"),
		"location": "Platform 3, Central Station",
	},
	{
		"name": "Corner Cafe Bookcase",
		"owner": "dev_alice",
		"description": "Located inside the cafe, next to the window.",
		"location": "12 Baker Street",
	},
	{
		"name": "Riverside Bench Box",
		"owner": "dev_bob",
		"latitude": Decimal("51.441642"),
		"longitude": Decimal("5.469722"),
	},
	{
		"name": "Community Centre Nook",
		"owner": "dev_alice",
		"location": "Community Centre, Elm Road 5",
	},
]

# Items with a station are created there; items without one use "status".
# Each item gets a creation movement automatically; "history" lists later
# state changes as (status, station name or None, notes), applied in order.
ITEMS = [
	{
		"title": "The Hobbit",
		"author": "J.R.R. Tolkien",
		"owner": "dev_alice",
		"description": "Hardcover, slightly worn.",
		"station": "Central Park Little Library",
	},
	{
		"title": "Pride and Prejudice",
		"author": "Jane Austen",
		"owner": "dev_bob",
		"station": "Station Platform Shelf",
		"thumbnail_url": "https://example.com/covers/pride-and-prejudice.jpg",
	},
	{
		"title": "Dune",
		"author": "Frank Herbert",
		"owner": "dev_alice",
		"station": "Corner Cafe Bookcase",
		"history": [
			(Item.Status.TAKEN_OUT, None, "Borrowed by a regular."),
			(Item.Status.AT_BOOK_STATION, "Corner Cafe Bookcase", "Returned."),
		],
	},
	{
		"title": "National Geographic, May 2020",
		"item_type": Item.ItemType.MAGAZINE,
		"owner": "dev_bob",
		"station": "Riverside Bench Box",
	},
	{
		"title": "Spirited Away",
		"item_type": Item.ItemType.DVD,
		"owner": "dev_alice",
		"station": "Community Centre Nook",
		"history": [
			(Item.Status.AT_BOOK_STATION, "Station Platform Shelf", "Moved to a busier spot."),
			(Item.Status.AT_BOOK_STATION, "Community Centre Nook", "Moved back."),
		],
	},
	{
		"title": "Board Game: Carcassonne",
		"item_type": Item.ItemType.OTHER,
		"owner": "dev_bob",
		"station": "Central Park Little Library",
	},
	{
		"title": "1984",
		"author": "George Orwell",
		"owner": "dev_bob",
		"station": "Station Platform Shelf",
		"history": [
			(Item.Status.TAKEN_OUT, None, "Taken on a trip."),
		],
	},
	{
		"title": "The Great Gatsby",
		"author": "F. Scott Fitzgerald",
		"owner": "dev_alice",
		"station": "Corner Cafe Bookcase",
		"history": [
			(Item.Status.LOST, None, "Not on the shelf anymore."),
		],
	},
	{
		"title": "Moby-Dick",
		"author": "Herman Melville",
		"owner": "dev_bob",
		"station": "Riverside Bench Box",
		"history": [
			(Item.Status.UNKNOWN, None, "Whereabouts unclear."),
		],
	},
	{
		"title": "Brave New World",
		"author": "Aldous Huxley",
		"owner": "dev_alice",
		"status": Item.Status.TAKEN_OUT,
		"station": None,
	},
]


class Command(BaseCommand):
	help = (
		"Populate the database with sample users, book stations and items for "
		"local development. Safe to run repeatedly; existing records are kept."
	)

	def add_arguments(self, parser):
		parser.add_argument(
			"--password",
			default=DEFAULT_PASSWORD,
			help="Password for newly created sample users (default: %(default)s).",
		)
		parser.add_argument(
			"--force",
			action="store_true",
			help="Allow running when DEBUG is False.",
		)

	@transaction.atomic
	def handle(self, *args, **options):
		if not settings.DEBUG and not options["force"]:
			raise CommandError(
				"seed_dev_data is meant for development only. Use --force to run with DEBUG=False."
			)

		users = self._create_users(options["password"])
		stations = self._create_stations(users)
		self._create_items(users, stations)

	def _create_users(self, password):
		user_model = get_user_model()
		users = {}
		for username in USERS:
			user, created = user_model.objects.get_or_create(
				username=username,
				defaults={"email": f"{username}@example.com"},
			)
			if created:
				user.set_password(password)
				user.save()
				self.stdout.write(f"Created user {username}")
			users[username] = user
		return users

	def _create_stations(self, users):
		stations = {}
		for data in STATIONS:
			data = dict(data)
			owner = users[data.pop("owner")]
			name = data.pop("name")
			station, created = BookStation.objects.get_or_create(
				name=name,
				added_by=owner,
				defaults=data,
			)
			if created:
				self.stdout.write(f"Created book station {name}")
			stations[name] = station
		return stations

	def _create_items(self, users, stations):
		for data in ITEMS:
			data = dict(data)
			owner = users[data.pop("owner")]
			station = stations.get(data.pop("station"))
			history = data.pop("history", [])
			status = Item.Status.AT_BOOK_STATION if station else data.pop("status")
			title = data["title"]

			if Item.objects.filter(title=title, added_by=owner).exists():
				continue

			item = Item.objects.create(
				added_by=owner,
				status=status,
				current_book_station=station,
				**data,
			)
			# Replay history in order so each change records a movement.
			for step_status, step_station, notes in history:
				item.status = step_status
				item.current_book_station = stations[step_station] if step_station else None
				item.save(movement_notes=notes)
			self.stdout.write(f"Created item {title}")
