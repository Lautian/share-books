from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render

from book_stations.models import BookStation, Item


def signup(request):
    if request.user.is_authenticated:
        return redirect("users:profile")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("users:profile")
    else:
        form = UserCreationForm()

    return render(request, "users/signup.html", {"form": form})


@login_required(login_url="users:login")
def profile(request):
    added_stations = BookStation.objects.filter(added_by=request.user).order_by("name")
    added_items = Item.objects.filter(added_by=request.user).order_by("title", "id")
    return render(
        request,
        "users/profile.html",
        {
            "added_stations": added_stations,
            "added_items": added_items,
        },
    )
