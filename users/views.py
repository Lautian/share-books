from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from book_stations.models import BookStation
from items.models import Item

@login_required(login_url="users:login")
def profile(request):
    added_stations = BookStation.objects.filter(added_by=request.user).order_by("name")
    added_items = Item.objects.filter(added_by=request.user).order_by("title", "id")

    context = {
        "added_stations": added_stations,
        "added_items": added_items,
    }

    return render(request, "users/profile.html", context)
