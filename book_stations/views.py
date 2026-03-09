import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

from items.models import Item

from .forms import BookStationCreateForm
from .models import BookStation


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
def bookstation_edit(request, readable_id):
	station = get_object_or_404(
		BookStation,
		readable_id=readable_id,
		added_by=request.user,
	)

	if request.method == "POST":
		form = BookStationCreateForm(request.POST, request.FILES, instance=station)
		if form.is_valid():
			updated_station = form.save()
			return redirect(
				"book_stations:bookstation-detail",
				readable_id=updated_station.readable_id,
			)
	else:
		form = BookStationCreateForm(instance=station)

	return render(
		request,
		"book_stations/bookstation_form.html",
		{
			"form": form,
			"is_edit": True,
			"station": station,
		},
	)


@login_required(login_url="users:login")
def bookstation_delete(request, readable_id):
	station = get_object_or_404(
		BookStation,
		readable_id=readable_id,
		added_by=request.user,
	)

	if request.method == "POST":
		Item.objects.filter(
			current_book_station=station,
			status=Item.Status.AT_BOOK_STATION,
		).update(
			status=Item.Status.UNKNOWN,
			current_book_station=None,
		)
		station.delete()
		return redirect("users:profile")

	return render(
		request,
		"book_stations/bookstation_confirm_delete.html",
		{"station": station},
	)
