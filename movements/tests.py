from django.contrib.auth import get_user_model
from django.test import TestCase

from book_stations.models import BookStation
from items.models import Item

from .models import Movement


class MovementTrackingTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="movement-owner",
            password="StrongPass123",
        )
        self.reporter = get_user_model().objects.create_user(
            username="movement-reporter",
            password="StrongPass123",
        )
        self.station_a = BookStation.objects.create(
            name="Station A",
            readable_id="station-a",
            latitude=51.500000,
            longitude=-0.090000,
            location="Main Street",
            added_by=self.owner,
        )
        self.station_b = BookStation.objects.create(
            name="Station B",
            readable_id="station-b",
            latitude=51.510000,
            longitude=-0.080000,
            location="Second Street",
            added_by=self.owner,
        )

    def test_item_creation_creates_created_movement(self):
        item = Item.objects.create(
            title="New Item",
            item_type=Item.ItemType.OTHER,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station_a,
            added_by=self.owner,
        )

        movement = Movement.objects.get(item=item)
        self.assertEqual(movement.movement_type, Movement.MovementType.CREATED)
        self.assertIsNone(movement.from_book_station)
        self.assertEqual(movement.to_book_station, self.station_a)
        self.assertEqual(movement.reported_by, self.owner)

    def test_station_transfer_creates_transferred_movement(self):
        item = Item.objects.create(
            title="Transfer Item",
            item_type=Item.ItemType.OTHER,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station_a,
            added_by=self.owner,
        )

        item.current_book_station = self.station_b
        item.status = Item.Status.AT_BOOK_STATION
        item.save(reported_by=self.reporter)

        latest_movement = item.movements.first()
        self.assertEqual(latest_movement.movement_type, Movement.MovementType.TRANSFERRED)
        self.assertEqual(latest_movement.from_book_station, self.station_a)
        self.assertEqual(latest_movement.to_book_station, self.station_b)
        self.assertEqual(latest_movement.reported_by, self.reporter)

    def test_mark_lost_creates_marked_lost_movement(self):
        item = Item.objects.create(
            title="Lost Item",
            item_type=Item.ItemType.OTHER,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station_a,
            added_by=self.owner,
        )

        item.status = Item.Status.LOST
        item.current_book_station = None
        item.save(reported_by=self.reporter)

        latest_movement = item.movements.first()
        self.assertEqual(latest_movement.movement_type, Movement.MovementType.MARKED_LOST)
        self.assertEqual(latest_movement.from_book_station, self.station_a)
        self.assertIsNone(latest_movement.to_book_station)

    def test_lost_item_placed_in_station_creates_marked_found_movement(self):
        item = Item.objects.create(
            title="Found Item",
            item_type=Item.ItemType.OTHER,
            status=Item.Status.LOST,
            current_book_station=None,
            added_by=self.owner,
        )

        item.status = Item.Status.AT_BOOK_STATION
        item.current_book_station = self.station_b
        item.save(reported_by=self.reporter)

        latest_movement = item.movements.first()
        self.assertEqual(latest_movement.movement_type, Movement.MovementType.MARKED_FOUND)
        self.assertIsNone(latest_movement.from_book_station)
        self.assertEqual(latest_movement.to_book_station, self.station_b)

    def test_non_movement_fields_do_not_create_extra_movement(self):
        item = Item.objects.create(
            title="Rename Me",
            item_type=Item.ItemType.OTHER,
            status=Item.Status.AT_BOOK_STATION,
            current_book_station=self.station_a,
            added_by=self.owner,
        )

        self.assertEqual(item.movements.count(), 1)

        item.title = "Renamed"
        item.save(reported_by=self.reporter)

        self.assertEqual(item.movements.count(), 1)
