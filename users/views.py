from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render


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
    return render(request, "users/profile.html")
