import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt

from book_stations.models import BookStation
from movements.models import Movement

from .forms import ItemCreateForm
from .models import Item


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
        "items/item_list.html",
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
    recent_movements = (
        item.movements.select_related(
            "from_book_station",
            "to_book_station",
            "reported_by",
        )
        .order_by("-timestamp", "-id")[:3]
    )
    return render(
        request,
        "items/item_detail.html",
        {
            "item": item,
            "recent_movements": recent_movements,
        },
    )


def item_history_page(request, item_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    item = get_object_or_404(
        Item.objects.select_related("current_book_station", "last_seen_at"),
        pk=item_id,
    )
    movements = Movement.objects.select_related(
        "from_book_station",
        "to_book_station",
        "reported_by",
    ).filter(item=item).order_by("timestamp", "id")
    return render(
        request,
        "items/item_history.html",
        {
            "item": item,
            "movements": movements,
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
            status = payload.get("status", Item.Status.UNKNOWN) or Item.Status.UNKNOWN
            current_station = _resolve_station_reference(
                payload.get("current_book_station"), "current_book_station"
            )
            last_seen_at = _resolve_station_reference(
                payload.get("last_seen_at"), "last_seen_at"
            )
            status_was_explicitly_set = payload.get("status") not in (None, "")

            # Mirror form semantics: choosing a current station auto-places the item
            # unless the client explicitly sets a different status.
            if current_station is not None and not (
                status_was_explicitly_set and status != Item.Status.AT_BOOK_STATION
            ):
                status = Item.Status.AT_BOOK_STATION

            if status != Item.Status.AT_BOOK_STATION:
                current_station = None

            if current_station is not None:
                last_seen_at = current_station
            else:
                # New API-created items should not keep transient last-seen values.
                last_seen_at = None

            item = Item(
                title=payload.get("title", ""),
                author=payload.get("author", ""),
                thumbnail_url=payload.get("thumbnail_url", ""),
                description=payload.get("description", ""),
                item_type=payload.get("item_type", Item.ItemType.BOOK),
                status=status,
                current_book_station=current_station,
                last_seen_at=last_seen_at,
                last_activity=_parse_last_activity(payload.get("last_activity")),
                added_by=request.user,
            )

            item.full_clean()
            item.save(reported_by=request.user)
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
def item_create(request):
    if request.method == "POST":
        form = ItemCreateForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.added_by = request.user
            item.save(reported_by=request.user)
            return redirect("items:item-detail", item_id=item.id)
    else:
        form = ItemCreateForm()

    return render(request, "items/item_form.html", {"form": form})


@login_required(login_url="users:login")
def item_edit(request, item_id):
    item = get_object_or_404(Item, pk=item_id, added_by=request.user)

    if request.method == "POST":
        form = ItemCreateForm(request.POST, instance=item)
        if form.is_valid():
            updated_item = form.save(commit=False)
            updated_item.save(reported_by=request.user)
            form.save_m2m()
            return redirect("items:item-detail", item_id=updated_item.id)
    else:
        form = ItemCreateForm(instance=item)

    return render(
        request,
        "items/item_form.html",
        {
            "form": form,
            "is_edit": True,
            "item": item,
        },
    )


@login_required(login_url="users:login")
def item_delete(request, item_id):
    item = get_object_or_404(Item, pk=item_id, added_by=request.user)

    if request.method == "POST":
        item.delete()
        return redirect("users:profile")

    return render(request, "items/item_confirm_delete.html", {"item": item})
