from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import translate_url
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.i18n import set_language as django_set_language

from book_stations.models import BookStation, StationVisit
from items.models import Item

from .models import UserProfile


def _supported(language):
    return language in dict(settings.LANGUAGES)


def _set_language_cookie(response, language):
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN,
        secure=settings.LANGUAGE_COOKIE_SECURE,
        httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
        samesite=settings.LANGUAGE_COOKIE_SAMESITE,
    )


@require_POST
def set_language(request):
    """Switch language and remember the choice on the user's profile."""
    response = django_set_language(request)
    language = request.POST.get("language")
    if request.user.is_authenticated and _supported(language):
        UserProfile.objects.update_or_create(
            user=request.user, defaults={"language": language}
        )
    return response


class LoginView(auth_views.LoginView):
    """Log in and switch to the user's preferred language, if one is stored."""

    def form_valid(self, form):
        response = super().form_valid(form)
        profile = UserProfile.objects.filter(user=self.request.user).first()
        if profile and _supported(profile.language):
            response = redirect(translate_url(response.url, profile.language))
            _set_language_cookie(response, profile.language)
        return response


@login_required(login_url="users:login")
def profile(request):
    user_profile, _created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        language = request.POST.get("language")
        if _supported(language):
            user_profile.language = language
            user_profile.save()
            with translation.override(language):
                messages.success(request, _("Language preference saved."))
                response = redirect("users:profile")
            _set_language_cookie(response, language)
            return response

    added_stations = BookStation.objects.filter(added_by=request.user).order_by("name")
    added_items = Item.objects.filter(added_by=request.user).order_by("title", "id")

    recent_visits = StationVisit.objects.filter(user=request.user).select_related("station")[:3]

    context = {
        "recent_visits": recent_visits,
        "added_stations": added_stations,
        "added_items": added_items,
        "user_profile": user_profile,
    }

    return render(request, "users/profile.html", context)
