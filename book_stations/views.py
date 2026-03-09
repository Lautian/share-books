import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt

from .forms import BookStationCreateForm, ItemCreateForm
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
		"latitude": float(station.latitude) if station.latitude is not None else None,
		"longitude": float(station.longitude) if station.longitude is not None else None,
		"location": station.location,
		"added_by": station.added_by.username,
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
		"thumbnail_url": item.thumbnail_url,
		"description": item.description,
		"item_type": item.item_type,
		"status": item.status,
		"current_book_station": (
			item.current_book_station.readable_id if item.current_book_station else None
		),
		"last_seen_at": item.last_seen_at.readable_id if item.last_seen_at else None,
		"last_activity": item.last_activity.isoformat() if item.last_activity else None,
		"added_by": item.added_by.username,
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
		stations = BookStation.objects.select_related("added_by").all()
		return JsonResponse(
			[_serialize_bookstation(station) for station in stations],
			safe=False,
		)

	if request.method == "POST":
		if not request.user.is_authenticated:
			return JsonResponse({"error": "Authentication required."}, status=403)

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
			added_by=request.user,
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

	station = get_object_or_404(
		BookStation.objects.select_related("added_by"),
		readable_id=readable_id,
	)
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
		items = Item.objects.select_related(
			"current_book_station", "last_seen_at", "added_by"
		).all()
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
		if not request.user.is_authenticated:
			return JsonResponse({"error": "Authentication required."}, status=403)

		try:
			payload = json.loads(request.body.decode("utf-8"))
		except (json.JSONDecodeError, UnicodeDecodeError):
			return JsonResponse({"error": "Invalid JSON payload."}, status=400)

		try:
			item = Item(
				title=payload.get("title", ""),
				author=payload.get("author", ""),
				thumbnail_url=payload.get("thumbnail_url", ""),
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
				added_by=request.user,
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
		Item.objects.select_related("current_book_station", "last_seen_at", "added_by"),
		pk=item_id,
	)
	return JsonResponse(_serialize_item(item))


@login_required(login_url="users:login")
def bookstation_create(request):
	if request.method == "POST":
		form = BookStationCreateForm(request.POST, request.FILES)
		if form.is_valid():
			station = form.save(commit=False)
			station.added_by = request.user
			station.save()
			return redirect(
				"book_stations:bookstation-detail",
				readable_id=station.readable_id,
			)
	else:
		form = BookStationCreateForm()

	return render(request, "book_stations/bookstation_form.html", {"form": form})


@login_required(login_url="users:login")
def item_create(request):
	if request.method == "POST":
		form = ItemCreateForm(request.POST)
		if form.is_valid():
			item = form.save(commit=False)
			item.added_by = request.user
			item.save()
			return redirect("book_stations:item-detail", item_id=item.id)
	else:
		form = ItemCreateForm()

	return render(request, "book_stations/item_form.html", {"form": form})
