import functools
from decimal import Decimal

from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from book_stations.models import BookStation
from items.models import Item
from moderation.utils import is_moderator


def moderator_required(view_func):
    """Decorator that requires the user to be a moderator."""
    @functools.wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = reverse("users:login")
            return redirect(f"{login_url}?next={request.get_full_path()}")
        if not is_moderator(request.user):
            return HttpResponseForbidden("You do not have permission to access this page.")
        return view_func(request, *args, **kwargs)
    return wrapped


@moderator_required
def moderation_queue(request):
    pending_stations = BookStation.objects.filter(
        moderation_status=BookStation.ModerationStatus.PENDING
    ).select_related("added_by", "claimed_by").order_by("name")

    pending_items = Item.objects.filter(
        moderation_status=Item.ModerationStatus.PENDING
    ).select_related("added_by", "claimed_by", "current_book_station").order_by("title", "id")

    station_edits = BookStation.objects.filter(
        moderation_status=BookStation.ModerationStatus.APPROVED,
        pending_edit__isnull=False,
    ).select_related("added_by").order_by("name")

    item_edits = Item.objects.filter(
        moderation_status=Item.ModerationStatus.APPROVED,
        pending_edit__isnull=False,
    ).select_related("added_by", "current_book_station").order_by("title", "id")

    reported_stations = BookStation.objects.filter(
        moderation_status=BookStation.ModerationStatus.REPORTED
    ).select_related("added_by").order_by("name")

    reported_items = Item.objects.filter(
        moderation_status=Item.ModerationStatus.REPORTED
    ).select_related("added_by", "current_book_station").order_by("title", "id")

    return render(
        request,
        "moderation/queue.html",
        {
            "pending_stations": pending_stations,
            "pending_items": pending_items,
            "station_edits": station_edits,
            "item_edits": item_edits,
            "reported_stations": reported_stations,
            "reported_items": reported_items,
        },
    )


@moderator_required
def claim_bookstation(request, readable_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status=BookStation.ModerationStatus.PENDING,
        claimed_by__isnull=True,
    )
    station.claimed_by = request.user
    station.save(update_fields=["claimed_by"])
    return redirect("moderation:queue")


@moderator_required
def approve_bookstation(request, readable_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status=BookStation.ModerationStatus.PENDING,
    )
    station.moderation_status = BookStation.ModerationStatus.APPROVED
    station.claimed_by = None
    station.save(update_fields=["moderation_status", "claimed_by"])
    return redirect("moderation:queue")


@moderator_required
def claim_item(request, item_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status=Item.ModerationStatus.PENDING,
        claimed_by__isnull=True,
    )
    item.claimed_by = request.user
    item.save(update_fields=["claimed_by"])
    return redirect("moderation:queue")


@moderator_required
def approve_item(request, item_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status=Item.ModerationStatus.PENDING,
    )
    item.moderation_status = Item.ModerationStatus.APPROVED
    item.claimed_by = None
    item.save(update_fields=["moderation_status", "claimed_by"])
    return redirect("moderation:queue")


@moderator_required
def approve_bookstation_edit(request, readable_id):
    """Apply a pending edit to an already-approved BookStation."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status=BookStation.ModerationStatus.APPROVED,
        pending_edit__isnull=False,
    )
    data = station.pending_edit
    station.name = data.get("name", station.name)
    station.location = data.get("location", station.location)
    station.description = data.get("description", station.description)
    raw_lat = data.get("latitude")
    raw_lon = data.get("longitude")
    station.latitude = Decimal(raw_lat) if raw_lat is not None else None
    station.longitude = Decimal(raw_lon) if raw_lon is not None else None
    station.picture = data.get("picture", station.picture)
    station.pending_edit = None
    station.save()
    return redirect("moderation:queue")


@moderator_required
def reject_bookstation_edit(request, readable_id):
    """Discard a pending edit on an already-approved BookStation."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status=BookStation.ModerationStatus.APPROVED,
        pending_edit__isnull=False,
    )
    station.pending_edit = None
    station.save(update_fields=["pending_edit"])
    return redirect("moderation:queue")


@moderator_required
def approve_item_edit(request, item_id):
    """Apply a pending edit to an already-approved Item."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status=Item.ModerationStatus.APPROVED,
        pending_edit__isnull=False,
    )
    data = item.pending_edit
    item.title = data.get("title", item.title)
    item.author = data.get("author", item.author)
    item.thumbnail_url = data.get("thumbnail_url", item.thumbnail_url)
    item.description = data.get("description", item.description)
    item.item_type = data.get("item_type", item.item_type)
    item.status = data.get("status", item.status)
    item.current_book_station_id = data.get("current_book_station_id", item.current_book_station_id)
    item.last_seen_at_id = data.get("last_seen_at_id", item.last_seen_at_id)
    raw_date = data.get("last_activity")
    if raw_date is not None:
        from datetime import date
        item.last_activity = date.fromisoformat(raw_date)
    item.pending_edit = None
    item.save(create_movement=False)
    return redirect("moderation:queue")


@moderator_required
def reject_item_edit(request, item_id):
    """Discard a pending edit on an already-approved Item."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status=Item.ModerationStatus.APPROVED,
        pending_edit__isnull=False,
    )
    item.pending_edit = None
    item.save(update_fields=["pending_edit"])
    return redirect("moderation:queue")


@moderator_required
def approve_reported_bookstation(request, readable_id):
    """Dismiss a report on a BookStation, restoring it to approved."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status=BookStation.ModerationStatus.REPORTED,
    )
    station.moderation_status = BookStation.ModerationStatus.APPROVED
    station.save(update_fields=["moderation_status"])
    return redirect("moderation:queue")


@moderator_required
def reject_reported_bookstation(request, readable_id):
    """Reject a reported BookStation, setting it back to pending moderation."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status=BookStation.ModerationStatus.REPORTED,
    )
    station.moderation_status = BookStation.ModerationStatus.PENDING
    station.save(update_fields=["moderation_status"])
    return redirect("moderation:queue")


@moderator_required
def approve_reported_item(request, item_id):
    """Dismiss a report on an Item, restoring it to approved."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status=Item.ModerationStatus.REPORTED,
    )
    item.moderation_status = Item.ModerationStatus.APPROVED
    item.save(update_fields=["moderation_status"])
    return redirect("moderation:queue")


@moderator_required
def reject_reported_item(request, item_id):
    """Reject a reported Item, setting it back to pending moderation."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status=Item.ModerationStatus.REPORTED,
    )
    item.moderation_status = Item.ModerationStatus.PENDING
    item.save(update_fields=["moderation_status"])
    return redirect("moderation:queue")

