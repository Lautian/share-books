import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt

from .models import BookStation, Item


def bookstation_list(request):
	sort = request.GET.get("sort", "name")
	stations = BookStation.objects.annotate(
		item_count=Count(
			"current_items",
			filter=Q(current_items__status=Item.Status.AT_BOOK_STATION),
		)
	)

	if sort == "location":
		stations = stations.order_by("location", "name")
	elif sort == "slug":
		stations = stations.order_by("readable_id")
	else:
		sort = "name"
		stations = stations.order_by("name")

	return render(
		request,
		"book_stations/bookstation_list.html",
		{
			"stations": stations,
			"active_sort": sort,
		},
	)


def bookstation_detail_page(request, readable_id):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])

	station = get_object_or_404(BookStation, readable_id=readable_id)
	inventory_items = Item.objects.filter(
		status=Item.Status.AT_BOOK_STATION,
		current_book_station=station,
	).order_by("title")
	return render(
		request,
		"book_stations/bookstation_detail.html",
		{
			"station": station,
			"inventory_items": inventory_items,
		},
	)


def _serialize_bookstation(station):
	return {
		"name": station.name,
		"readable_id": station.readable_id,
		"description": station.description,
		"picture": station.picture,
		"latitude": float(station.latitude),
		"longitude": float(station.longitude),
		"location": station.location,
	}


def _to_decimal(value):
	if value is None:
		return None
	try:
		return Decimal(str(value))
	except (InvalidOperation, TypeError, ValueError):
		return value


def _serialize_item(item):
	return {
		"id": item.id,
		"title": item.title,
		"author": item.author,
		"description": item.description,
		"item_type": item.item_type,
		"status": item.status,
		"current_book_station": (
			item.current_book_station.readable_id if item.current_book_station else None
		),
		"last_seen_at": item.last_seen_at.readable_id if item.last_seen_at else None,
		"last_activity": item.last_activity.isoformat() if item.last_activity else None,
	}


def _resolve_station_reference(value, field_name):
	if value in (None, ""):
		return None

	station = None
	if isinstance(value, int):
		station = BookStation.objects.filter(pk=value).first()
	elif isinstance(value, str):
		if value.isdigit():
			station = BookStation.objects.filter(pk=int(value)).first()
		if station is None:
			station = BookStation.objects.filter(readable_id=value).first()

	if station is None:
		raise ValidationError(
			{field_name: "Book station must reference an existing id or readable_id."}
		)

	return station


def _parse_last_activity(value):
	if value in (None, ""):
		return None
	if isinstance(value, str):
		parsed_date = parse_date(value)
		if parsed_date is not None:
			return parsed_date
	raise ValidationError({"last_activity": "Use ISO date format YYYY-MM-DD."})


@csrf_exempt
def bookstation_list_create(request):
	if request.method == "GET":
		stations = BookStation.objects.all()
		return JsonResponse(
			[_serialize_bookstation(station) for station in stations],
			safe=False,
		)

	if request.method == "POST":
		try:
			payload = json.loads(request.body.decode("utf-8"))
		except (json.JSONDecodeError, UnicodeDecodeError):
			return JsonResponse({"error": "Invalid JSON payload."}, status=400)

		station = BookStation(
			name=payload.get("name", ""),
			readable_id=payload.get("readable_id", ""),
			description=payload.get("description", ""),
			picture=payload.get("picture", ""),
			latitude=_to_decimal(payload.get("latitude")),
			longitude=_to_decimal(payload.get("longitude")),
			location=payload.get("location", ""),
		)

		try:
			station.full_clean()
			station.save()
		except ValidationError as error:
			return JsonResponse({"errors": error.message_dict}, status=400)

		return JsonResponse(_serialize_bookstation(station), status=201)

	return HttpResponseNotAllowed(["GET", "POST"])


def bookstation_detail_api(request, readable_id):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])

	station = get_object_or_404(BookStation, readable_id=readable_id)
	return JsonResponse(_serialize_bookstation(station))


def item_list(request):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])

	items = Item.objects.select_related("current_book_station", "last_seen_at").all()
	selected_status = request.GET.get("status", "")
	selected_type = request.GET.get("item_type", "")
	selected_station = request.GET.get("station", "")

	if selected_status in Item.Status.values:
		items = items.filter(status=selected_status)
	else:
		selected_status = ""

	if selected_type in Item.ItemType.values:
		items = items.filter(item_type=selected_type)
	else:
		selected_type = ""

	if selected_station:
		try:
			station = _resolve_station_reference(selected_station, "station")
			items = items.filter(current_book_station=station)
		except ValidationError:
			selected_station = ""

	items = items.order_by("title", "id")

	return render(
		request,
		"book_stations/item_list.html",
		{
			"items": items,
			"status_choices": Item.Status.choices,
			"item_type_choices": Item.ItemType.choices,
			"selected_status": selected_status,
			"selected_type": selected_type,
			"selected_station": selected_station,
		},
	)


def item_detail_page(request, item_id):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])

	item = get_object_or_404(
		Item.objects.select_related("current_book_station", "last_seen_at"),
		pk=item_id,
	)
	return render(request, "book_stations/item_detail.html", {"item": item})


def bookstation_inventory_page(request, readable_id):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])

	station = get_object_or_404(BookStation, readable_id=readable_id)
	items = Item.objects.filter(
		status=Item.Status.AT_BOOK_STATION,
		current_book_station=station,
	).order_by("title", "id")
	book_like_items = items.exclude(item_type=Item.ItemType.DVD)
	dvd_items = items.filter(item_type=Item.ItemType.DVD)

	return render(
		request,
		"book_stations/station_inventory.html",
		{
			"station": station,
			"items": items,
			"book_like_items": book_like_items,
			"dvd_items": dvd_items,
		},
	)


@csrf_exempt
def item_list_create(request):
	if request.method == "GET":
		items = Item.objects.select_related("current_book_station", "last_seen_at").all()
		status = request.GET.get("status")
		item_type = request.GET.get("item_type")
		station_reference = request.GET.get("station")

		if status in Item.Status.values:
			items = items.filter(status=status)
		if item_type in Item.ItemType.values:
			items = items.filter(item_type=item_type)
		if station_reference:
			try:
				station = _resolve_station_reference(station_reference, "station")
			except ValidationError as error:
				errors = getattr(error, "message_dict", {"__all__": error.messages})
				return JsonResponse({"errors": errors}, status=400)
			items = items.filter(current_book_station=station)

		items = items.order_by("title", "id")
		return JsonResponse([_serialize_item(item) for item in items], safe=False)

	if request.method == "POST":
		try:
			payload = json.loads(request.body.decode("utf-8"))
		except (json.JSONDecodeError, UnicodeDecodeError):
			return JsonResponse({"error": "Invalid JSON payload."}, status=400)

		try:
			item = Item(
				title=payload.get("title", ""),
				author=payload.get("author", ""),
				description=payload.get("description", ""),
				item_type=payload.get("item_type", Item.ItemType.BOOK),
				status=payload.get("status", Item.Status.UNKNOWN),
				current_book_station=_resolve_station_reference(
					payload.get("current_book_station"), "current_book_station"
				),
				last_seen_at=_resolve_station_reference(
					payload.get("last_seen_at"), "last_seen_at"
				),
				last_activity=_parse_last_activity(payload.get("last_activity")),
			)

			item.full_clean()
			item.save()
		except ValidationError as error:
			errors = getattr(error, "message_dict", {"__all__": error.messages})
			return JsonResponse({"errors": errors}, status=400)

		return JsonResponse(_serialize_item(item), status=201)

	return HttpResponseNotAllowed(["GET", "POST"])


def item_detail_api(request, item_id):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])

	item = get_object_or_404(
		Item.objects.select_related("current_book_station", "last_seen_at"),
		pk=item_id,
	)
	return JsonResponse(_serialize_item(item))
