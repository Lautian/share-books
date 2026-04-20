import functools
from datetime import date
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from book_stations.models import BookStation
from items.models import Item
from moderation.models import ModerationLog
from moderation.utils import is_moderator

_LEGACY_PENDING_STATUS = "PENDING"
_REVIEWABLE_STATION_STATUSES = [
    BookStation.ModerationStatus.NEW,
    BookStation.ModerationStatus.FLAGGED,
    BookStation.ModerationStatus.REPORTED,
    _LEGACY_PENDING_STATUS,
]
_REVIEWABLE_ITEM_STATUSES = [
    Item.ModerationStatus.NEW,
    Item.ModerationStatus.FLAGGED,
    Item.ModerationStatus.REPORTED,
    _LEGACY_PENDING_STATUS,
]


def _is_edit_revert_snapshot(data):
    return isinstance(data, dict) and data.get("_moderation_type") == "EDIT_REVERT_SNAPSHOT"


def _redirect_to_next(request, fallback):
    """Redirect to the POST 'next' parameter if it's a safe local URL, else use fallback."""
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback)


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


def _new_station_activity_qs():
    """BookStations with NEW status or a pending edit — shown in activity sections."""
    return BookStation.objects.filter(
        Q(moderation_status=BookStation.ModerationStatus.NEW) | Q(pending_edit__isnull=False)
    )


def _new_item_activity_qs():
    """Items with NEW status or a pending edit — shown in activity sections."""
    return Item.objects.filter(
        Q(moderation_status=Item.ModerationStatus.NEW) | Q(pending_edit__isnull=False)
    )


@moderator_required
def moderation_queue(request):
    flagged_new_stations = (
        BookStation.objects.filter(
            moderation_status=BookStation.ModerationStatus.FLAGGED,
            pending_edit__isnull=True,
        )
        .select_related("added_by", "claimed_by")
        .order_by("name")
    )
    flagged_new_items = (
        Item.objects.filter(
            moderation_status=Item.ModerationStatus.FLAGGED,
            pending_edit__isnull=True,
        )
        .select_related("added_by", "claimed_by", "current_book_station")
        .order_by("title", "id")
    )
    flagged_station_edits = (
        BookStation.objects.filter(
            moderation_status=BookStation.ModerationStatus.FLAGGED,
            pending_edit__isnull=False,
        )
        .select_related("added_by")
        .order_by("name")
    )
    flagged_item_edits = (
        Item.objects.filter(
            moderation_status=Item.ModerationStatus.FLAGGED,
            pending_edit__isnull=False,
        )
        .select_related("added_by", "current_book_station")
        .order_by("title", "id")
    )
    reported_stations = (
        BookStation.objects.filter(moderation_status=BookStation.ModerationStatus.REPORTED)
        .select_related("added_by", "claimed_by")
        .order_by("name")
    )
    reported_items = (
        Item.objects.filter(moderation_status=Item.ModerationStatus.REPORTED)
        .select_related("added_by", "claimed_by", "current_book_station")
        .order_by("title", "id")
    )
    recent_station_activity = (
        _new_station_activity_qs().select_related("added_by").order_by("-id")[:20]
    )
    recent_item_activity = (
        _new_item_activity_qs().select_related("added_by", "current_book_station").order_by("-id")[
            :20
        ]
    )

    return render(
        request,
        "moderation/queue.html",
        {
            "flagged_new_stations": flagged_new_stations,
            "flagged_new_items": flagged_new_items,
            "flagged_station_edits": flagged_station_edits,
            "flagged_item_edits": flagged_item_edits,
            "reported_stations": reported_stations,
            "reported_items": reported_items,
            "recent_station_activity": recent_station_activity,
            "recent_item_activity": recent_item_activity,
        },
    )


@moderator_required
def bookstation_activity(request):
    page_obj = Paginator(
        _new_station_activity_qs().select_related("added_by").order_by("-id"),
        20,
    ).get_page(request.GET.get("page"))
    return render(request, "moderation/bookstation_activity.html", {"page_obj": page_obj})


@moderator_required
def item_activity(request):
    page_obj = Paginator(
        _new_item_activity_qs()
        .select_related("added_by", "current_book_station")
        .order_by("-id"),
        20,
    ).get_page(request.GET.get("page"))
    return render(request, "moderation/item_activity.html", {"page_obj": page_obj})


@moderator_required
def claim_bookstation(request, readable_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status__in=_REVIEWABLE_STATION_STATUSES,
        claimed_by__isnull=True,
    )
    station.claimed_by = request.user
    station.save(update_fields=["claimed_by"])
    return _redirect_to_next(request, reverse("moderation:queue"))


@moderator_required
def approve_bookstation(request, readable_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status__in=_REVIEWABLE_STATION_STATUSES,
        # New/create moderation actions only target records that don't represent edits.
        pending_edit__isnull=True,
    )
    from_status = station.moderation_status
    station.moderation_status = BookStation.ModerationStatus.APPROVED
    station.claimed_by = None
    station.save(update_fields=["moderation_status", "claimed_by"])
    action = (
        ModerationLog.Action.REPORTED_STATION_APPROVED
        if from_status == BookStation.ModerationStatus.REPORTED
        else ModerationLog.Action.STATION_APPROVED
    )
    ModerationLog.objects.create(
        moderator=request.user,
        book_station=station,
        action=action,
        from_status=from_status,
        to_status=station.moderation_status,
    )
    return _redirect_to_next(request, reverse("moderation:queue"))


@moderator_required
def reject_bookstation(request, readable_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status__in=_REVIEWABLE_STATION_STATUSES,
        # New/create moderation actions only target records that don't represent edits.
        pending_edit__isnull=True,
    )
    from_status = station.moderation_status
    station.moderation_status = BookStation.ModerationStatus.REJECTED
    station.claimed_by = None
    station.save(update_fields=["moderation_status", "claimed_by"])
    action = (
        ModerationLog.Action.REPORTED_STATION_REJECTED
        if from_status == BookStation.ModerationStatus.REPORTED
        else ModerationLog.Action.STATION_REJECTED
    )
    ModerationLog.objects.create(
        moderator=request.user,
        book_station=station,
        action=action,
        from_status=from_status,
        to_status=station.moderation_status,
    )
    return _redirect_to_next(request, reverse("moderation:queue"))


@moderator_required
def claim_item(request, item_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status__in=_REVIEWABLE_ITEM_STATUSES,
        claimed_by__isnull=True,
    )
    item.claimed_by = request.user
    item.save(update_fields=["claimed_by"])
    return _redirect_to_next(request, reverse("moderation:queue"))


@moderator_required
def approve_item(request, item_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status__in=_REVIEWABLE_ITEM_STATUSES,
        # New/create moderation actions only target records that don't represent edits.
        pending_edit__isnull=True,
    )
    from_status = item.moderation_status
    item.moderation_status = Item.ModerationStatus.APPROVED
    item.claimed_by = None
    item.save(update_fields=["moderation_status", "claimed_by"])
    action = (
        ModerationLog.Action.REPORTED_ITEM_APPROVED
        if from_status == Item.ModerationStatus.REPORTED
        else ModerationLog.Action.ITEM_APPROVED
    )
    ModerationLog.objects.create(
        moderator=request.user,
        item=item,
        action=action,
        from_status=from_status,
        to_status=item.moderation_status,
    )
    return _redirect_to_next(request, reverse("moderation:queue"))


@moderator_required
def reject_item(request, item_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status__in=_REVIEWABLE_ITEM_STATUSES,
        # New/create moderation actions only target records that don't represent edits.
        pending_edit__isnull=True,
    )
    from_status = item.moderation_status
    action = (
        ModerationLog.Action.REPORTED_ITEM_REJECTED
        if from_status == Item.ModerationStatus.REPORTED
        else ModerationLog.Action.ITEM_REJECTED
    )
    ModerationLog.objects.create(
        moderator=request.user,
        item=item,
        action=action,
        from_status=from_status,
        to_status=Item.ModerationStatus.REJECTED,
    )
    item.delete()
    return _redirect_to_next(request, reverse("moderation:queue"))


@moderator_required
def approve_bookstation_edit(request, readable_id):
    """Approve a station edit waiting for moderation follow-up."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status__in=_REVIEWABLE_STATION_STATUSES,
        pending_edit__isnull=False,
    )
    data = station.pending_edit or {}
    if not _is_edit_revert_snapshot(data):
        station.name = data.get("name", station.name)
        station.location = data.get("location", station.location)
        station.description = data.get("description", station.description)
        raw_lat = data.get("latitude")
        raw_lon = data.get("longitude")
        station.latitude = Decimal(raw_lat) if raw_lat is not None else None
        station.longitude = Decimal(raw_lon) if raw_lon is not None else None
        station.picture = data.get("picture", station.picture)
    from_status = station.moderation_status
    station.pending_edit = None
    station.moderation_status = BookStation.ModerationStatus.APPROVED
    station.claimed_by = None
    station.save()
    ModerationLog.objects.create(
        moderator=request.user,
        book_station=station,
        action=ModerationLog.Action.STATION_EDIT_APPROVED,
        from_status=from_status,
        to_status=station.moderation_status,
    )
    return _redirect_to_next(request, reverse("moderation:queue"))


@moderator_required
def reject_bookstation_edit(request, readable_id):
    """Reject a station edit; revert to the previous approved content when possible."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status__in=_REVIEWABLE_STATION_STATUSES,
        pending_edit__isnull=False,
    )
    data = station.pending_edit or {}
    from_status = station.moderation_status
    if _is_edit_revert_snapshot(data):
        station.name = data.get("name", station.name)
        station.location = data.get("location", station.location)
        station.description = data.get("description", station.description)
        raw_lat = data.get("latitude")
        raw_lon = data.get("longitude")
        station.latitude = Decimal(raw_lat) if raw_lat is not None else None
        station.longitude = Decimal(raw_lon) if raw_lon is not None else None
        station.picture = data.get("picture", station.picture)
        station.moderation_status = data.get(
            "moderation_status",
            BookStation.ModerationStatus.APPROVED,
        )
    station.pending_edit = None
    station.claimed_by = None
    station.save()
    ModerationLog.objects.create(
        moderator=request.user,
        book_station=station,
        action=ModerationLog.Action.STATION_EDIT_REJECTED,
        from_status=from_status,
        to_status=station.moderation_status,
    )
    return _redirect_to_next(request, reverse("moderation:queue"))


@moderator_required
def approve_item_edit(request, item_id):
    """Approve an item edit waiting for moderation follow-up."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status__in=_REVIEWABLE_ITEM_STATUSES,
        pending_edit__isnull=False,
    )
    data = item.pending_edit or {}
    if not _is_edit_revert_snapshot(data):
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
            item.last_activity = date.fromisoformat(raw_date)
    from_status = item.moderation_status
    item.pending_edit = None
    item.moderation_status = Item.ModerationStatus.APPROVED
    item.claimed_by = None
    item.save(create_movement=False)
    ModerationLog.objects.create(
        moderator=request.user,
        item=item,
        action=ModerationLog.Action.ITEM_EDIT_APPROVED,
        from_status=from_status,
        to_status=item.moderation_status,
    )
    return _redirect_to_next(request, reverse("moderation:queue"))


@moderator_required
def reject_item_edit(request, item_id):
    """Reject an item edit; revert to the previous approved content when possible."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status__in=_REVIEWABLE_ITEM_STATUSES,
        pending_edit__isnull=False,
    )
    data = item.pending_edit or {}
    from_status = item.moderation_status
    if _is_edit_revert_snapshot(data):
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
            item.last_activity = date.fromisoformat(raw_date)
        item.moderation_status = data.get("moderation_status", Item.ModerationStatus.APPROVED)
    item.pending_edit = None
    item.claimed_by = None
    item.save(create_movement=False)
    ModerationLog.objects.create(
        moderator=request.user,
        item=item,
        action=ModerationLog.Action.ITEM_EDIT_REJECTED,
        from_status=from_status,
        to_status=item.moderation_status,
    )
    return _redirect_to_next(request, reverse("moderation:queue"))


@moderator_required
def unclaim_bookstation(request, readable_id):
    """Unclaim a BookStation so another moderator can pick it up."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status__in=_REVIEWABLE_STATION_STATUSES,
        claimed_by=request.user,
    )
    station.claimed_by = None
    station.save(update_fields=["claimed_by"])
    return _redirect_to_next(request, reverse("moderation:queue"))


@moderator_required
def unclaim_item(request, item_id):
    """Unclaim an Item so another moderator can pick it up."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status__in=_REVIEWABLE_ITEM_STATUSES,
        claimed_by=request.user,
    )
    item.claimed_by = None
    item.save(update_fields=["claimed_by"])
    return _redirect_to_next(request, reverse("moderation:queue"))


@moderator_required
def moderate_pending_bookstation(request, readable_id):
    """Redirect to BookStation detail if the station has moderation work pending."""
    get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status__in=_REVIEWABLE_STATION_STATUSES,
    )
    return redirect("book_stations:bookstation-detail", readable_id=readable_id)


@moderator_required
def moderate_pending_item(request, item_id):
    """Redirect to Item detail if the item has moderation work pending."""
    get_object_or_404(
        Item,
        pk=item_id,
        moderation_status__in=_REVIEWABLE_ITEM_STATUSES,
    )
    return redirect("items:item-detail", item_id=item_id)
