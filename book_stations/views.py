import base64
import io
import json
from decimal import Decimal, InvalidOperation

import qrcode
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from moderation.utils import is_moderator
from items.models import Item

from .forms import BookStationCreateForm, decode_plus_code, encode_plus_code
from .models import BookStation


def bookstation_list(request):
	sort_by = request.GET.get("sort_by", "name")
	sort_dir = request.GET.get("sort_dir", "asc")

	# Keep backward compatibility with previous sort query values.
	legacy_sort = request.GET.get("sort")
	if legacy_sort and "sort_by" not in request.GET:
		legacy_sort_map = {
			"name": ("name", "asc"),
			"location": ("location", "asc"),
			"slug": ("slug", "asc"),
		}
		sort_by, sort_dir = legacy_sort_map.get(legacy_sort, ("name", "asc"))

	valid_sort_by = {"name", "location", "slug"}
	if sort_by not in valid_sort_by:
		sort_by = "name"

	if sort_dir not in {"asc", "desc"}:
		sort_dir = "asc"

	stations = BookStation.objects.annotate(
		item_count=Count(
			"current_items",
			filter=Q(current_items__status=Item.Status.AT_BOOK_STATION),
		)
	)

	if not is_moderator(request.user):
		stations = stations.filter(
			models.Q(moderation_status=BookStation.ModerationStatus.APPROVED)
			| models.Q(moderation_status=BookStation.ModerationStatus.REPORTED)
		)

	sort_field_map = {
		"name": ["name"],
		"location": ["location", "name"],
		"slug": ["readable_id"],
	}
	order_fields = sort_field_map[sort_by]
	if sort_dir == "desc":
		stations = stations.order_by(f"-{order_fields[0]}", *order_fields[1:])
	else:
		stations = stations.order_by(*order_fields)

	sort_by_options = [
		("name", "Name"),
		("location", "Location"),
		("slug", "Slug"),
	]

	return render(
		request,
		"book_stations/bookstation_list.html",
		{
			"stations": stations,
			"active_sort_by": sort_by,
			"active_sort_dir": sort_dir,
			"sort_by_options": sort_by_options,
		},
	)


def bookstation_detail_page(request, readable_id):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])

	if is_moderator(request.user):
		station = get_object_or_404(BookStation, readable_id=readable_id)
	else:
		qs = BookStation.objects.filter(
			models.Q(moderation_status=BookStation.ModerationStatus.APPROVED)
			| models.Q(moderation_status=BookStation.ModerationStatus.REPORTED)
		)
		if request.user.is_authenticated:
			qs = BookStation.objects.filter(
				models.Q(moderation_status=BookStation.ModerationStatus.APPROVED)
				| models.Q(moderation_status=BookStation.ModerationStatus.REPORTED)
				| models.Q(added_by=request.user)
			)
		station = get_object_or_404(qs, readable_id=readable_id)
	items = Item.objects.filter(
		status=Item.Status.AT_BOOK_STATION,
		current_book_station=station,
	).order_by("title", "id")
	if not is_moderator(request.user):
		items = items.filter(
			models.Q(moderation_status=Item.ModerationStatus.APPROVED)
			| models.Q(moderation_status=Item.ModerationStatus.REPORTED)
		)
	book_like_items = items.exclude(item_type=Item.ItemType.DVD)
	dvd_items = items.filter(item_type=Item.ItemType.DVD)
	return render(
		request,
		"book_stations/bookstation_detail.html",
		{
			"station": station,
			"items": items,
			"book_like_items": book_like_items,
			"dvd_items": dvd_items,
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


def plus_code_encode_api(request):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])

	plus_code = encode_plus_code(
		_to_decimal(request.GET.get("latitude")),
		_to_decimal(request.GET.get("longitude")),
	)
	return JsonResponse({"plus_code": plus_code})


def plus_code_decode_api(request):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])

	decoded_coordinates = decode_plus_code(request.GET.get("plus_code", ""))
	if decoded_coordinates is None:
		return JsonResponse({"latitude": "", "longitude": ""})

	latitude, longitude = decoded_coordinates
	return JsonResponse(
		{
			"latitude": f"{latitude:.6f}",
			"longitude": f"{longitude:.6f}",
		}
	)


@csrf_exempt
def bookstation_list_create(request):
	if request.method == "GET":
		stations = BookStation.objects.select_related("added_by").all()
		if not is_moderator(request.user):
			stations = stations.filter(moderation_status=BookStation.ModerationStatus.APPROVED)
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
			moderation_status=BookStation.ModerationStatus.PENDING,
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

	qs = BookStation.objects.select_related("added_by")
	if not is_moderator(request.user):
		qs = qs.filter(moderation_status=BookStation.ModerationStatus.APPROVED)
	station = get_object_or_404(qs, readable_id=readable_id)
	return JsonResponse(_serialize_bookstation(station))


def bookstation_inventory_page(request, readable_id):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])

	if is_moderator(request.user):
		station = get_object_or_404(BookStation, readable_id=readable_id)
	else:
		import django.db.models as _m
		qs = BookStation.objects.filter(moderation_status=BookStation.ModerationStatus.APPROVED)
		if request.user.is_authenticated:
			qs = BookStation.objects.filter(
				_m.Q(moderation_status=BookStation.ModerationStatus.APPROVED)
				| _m.Q(added_by=request.user)
			)
		station = get_object_or_404(qs, readable_id=readable_id)
	sort_by = request.GET.get("sort_by", "title")
	sort_dir = request.GET.get("sort_dir")
	if sort_dir is None:
		if "sort_by" in request.GET:
			sort_dir = "asc"
		else:
			sort_dir = "asc"

	# Keep compatibility with previous sort query values.
	legacy_sort = request.GET.get("sort")
	if legacy_sort and "sort_by" not in request.GET:
		legacy_sort_map = {
			"title": ("title", "asc"),
			"title_desc": ("title", "desc"),
			"author": ("author", "asc"),
			"item_type": ("item_type", "asc"),
			"recent_activity": ("last_activity", "desc"),
			"oldest_activity": ("last_activity", "asc"),
		}
		sort_by, sort_dir = legacy_sort_map.get(legacy_sort, ("title", "asc"))

	valid_sort_by = {"title", "author", "item_type", "last_activity"}
	if sort_by not in valid_sort_by:
		sort_by = "title"

	if sort_dir not in {"asc", "desc"}:
		sort_dir = "asc"

	items = Item.objects.filter(
		status=Item.Status.AT_BOOK_STATION,
		current_book_station=station,
	)

	if not is_moderator(request.user):
		items = items.filter(moderation_status=Item.ModerationStatus.APPROVED)

	sort_field_map = {
		"title": ["title", "id"],
		"author": ["author", "title", "id"],
		"item_type": ["item_type", "title", "id"],
		"last_activity": ["last_activity", "title", "id"],
	}
	order_fields = sort_field_map[sort_by]
	if sort_dir == "desc":
		items = items.order_by(f"-{order_fields[0]}", *order_fields[1:])
	else:
		items = items.order_by(*order_fields)

	sort_by_options = [
		("title", "Title"),
		("author", "Author"),
		("item_type", "Type"),
		("last_activity", "Last activity"),
	]

	return render(
		request,
		"book_stations/station_inventory.html",
		{
			"station": station,
			"items": items,
			"active_sort_by": sort_by,
			"active_sort_dir": sort_dir,
			"sort_by_options": sort_by_options,
		},
	)


@login_required(login_url="users:login")
def bookstation_create(request):
	if request.method == "POST":
		form = BookStationCreateForm(request.POST, request.FILES)
		if form.is_valid():
			station = form.save(commit=False)
			station.added_by = request.user
			station.moderation_status = BookStation.ModerationStatus.PENDING
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

	# Block further edits while any edit (or new submission) is awaiting moderation.
	if station.moderation_status == BookStation.ModerationStatus.PENDING or station.pending_edit is not None:
		return render(
			request,
			"book_stations/bookstation_form.html",
			{
				"is_edit": True,
				"station": station,
				"edit_blocked": True,
			},
		)

	# Station is APPROVED with no pending edit — the edit is stored as a pending diff
	# so the original live data stays publicly visible while moderation is in progress.
	if request.method == "POST":
		form = BookStationCreateForm(request.POST, request.FILES, instance=station)
		if form.is_valid():
			# Build the pending snapshot from the validated form data.
			updated = form.save(commit=False)
			pending_data = {
				"name": updated.name,
				"location": updated.location,
				"description": updated.description,
				"latitude": str(updated.latitude) if updated.latitude is not None else None,
				"longitude": str(updated.longitude) if updated.longitude is not None else None,
				"picture": updated.picture,
			}
			station.pending_edit = pending_data
			station.claimed_by = None
			station.save(update_fields=["pending_edit", "claimed_by"])
			return redirect(
				"book_stations:bookstation-detail",
				readable_id=station.readable_id,
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


def _generate_qr_png_bytes(url):
	qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M)
	qr.add_data(url)
	qr.make(fit=True)
	img = qr.make_image(fill_color="black", back_color="white")
	buf = io.BytesIO()
	img.save(buf, format="PNG")
	buf.seek(0)
	return buf.read()


@login_required(login_url="users:login")
def bookstation_report(request, readable_id):
	if request.method != "POST":
		return HttpResponseNotAllowed(["POST"])

	station = get_object_or_404(
		BookStation,
		readable_id=readable_id,
		moderation_status__in=[BookStation.ModerationStatus.APPROVED, BookStation.ModerationStatus.REPORTED],
	)
	if station.moderation_status != BookStation.ModerationStatus.REPORTED:
		station.moderation_status = BookStation.ModerationStatus.REPORTED
		station.save(update_fields=["moderation_status"])
	return redirect("book_stations:bookstation-detail", readable_id=readable_id)


def bookstation_qr_code(request, readable_id):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])

	station = get_object_or_404(BookStation, readable_id=readable_id)
	detail_url = request.build_absolute_uri(
		reverse("book_stations:bookstation-detail", kwargs={"readable_id": readable_id})
	)
	png_bytes = _generate_qr_png_bytes(detail_url)

	if request.GET.get("download"):
		response = HttpResponse(png_bytes, content_type="image/png")
		response["Content-Disposition"] = f'attachment; filename="qr-{readable_id}.png"'
		return response

	qr_data_uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode()
	return render(
		request,
		"book_stations/bookstation_qr.html",
		{
			"station": station,
			"qr_data_uri": qr_data_uri,
			"detail_url": detail_url,
		},
	)
