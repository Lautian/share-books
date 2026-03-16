import functools

from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from book_stations.models import BookStation
from items.models import Item


def is_moderator(user):
    """Return True if the user has moderator privileges (staff or superuser)."""
    return user.is_active and (user.is_staff or user.is_superuser)


def moderator_required(view_func):
    """Decorator that requires the user to be a moderator."""
    @functools.wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = reverse("users:login")
            return redirect(f"{login_url}?next={request.path}")
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

    return render(
        request,
        "moderation/queue.html",
        {
            "pending_stations": pending_stations,
            "pending_items": pending_items,
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
def moderation_queue(request):
    pending_stations = BookStation.objects.filter(
        moderation_status=BookStation.ModerationStatus.PENDING
    ).select_related("added_by", "claimed_by").order_by("name")

    pending_items = Item.objects.filter(
        moderation_status=Item.ModerationStatus.PENDING
    ).select_related("added_by", "claimed_by", "current_book_station").order_by("title", "id")

    return render(
        request,
        "moderation/queue.html",
        {
            "pending_stations": pending_stations,
            "pending_items": pending_items,
        },
    )


@moderator_required
def claim_bookstation(request, readable_id):
    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])

    station = get_object_or_404(
        BookStation,
        readable_id=readable_id,
        moderation_status=BookStation.ModerationStatus.PENDING,
    )
    station.claimed_by = request.user
    station.save(update_fields=["claimed_by"])
    return redirect("moderation:queue")


@moderator_required
def approve_bookstation(request, readable_id):
    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
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
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        Item,
        pk=item_id,
        moderation_status=Item.ModerationStatus.PENDING,
    )
    item.claimed_by = request.user
    item.save(update_fields=["claimed_by"])
    return redirect("moderation:queue")


@moderator_required
def approve_item(request, item_id):
    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
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

