from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from book_stations.models import BookStation, StationVisit
from items.models import Item

@login_required(login_url="users:login")
def profile(request):
    added_stations = BookStation.objects.filter(added_by=request.user).order_by("name")
    added_items = Item.objects.filter(added_by=request.user).order_by("title", "id")

    recent_visits = StationVisit.objects.filter(user=request.user).select_related("station")[:3]

    context = {
        "recent_visits": recent_visits,
        "added_stations": added_stations,
        "added_items": added_items,
    }

    return render(request, "users/profile.html", context)
