import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt

from .models import BookStation


def home(request):
	return render(request, "book_stations/home.html")


def bookstation_list(request):
	sort = request.GET.get("sort", "name")
	stations = BookStation.objects.all()

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


def _serialize_bookstation(station):
	return {
		"name": station.name,
		"readable_id": station.readable_id,
		"description": station.description,
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


def bookstation_detail(request, readable_id):
	if request.method != "GET":
		return HttpResponseNotAllowed(["GET"])

	station = get_object_or_404(BookStation, readable_id=readable_id)
	return JsonResponse(_serialize_bookstation(station))
