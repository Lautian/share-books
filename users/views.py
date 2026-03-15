import logging

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from book_stations.models import BookStation
from items.models import Item

from .forms import SignupForm
from .tokens import email_verification_token

logger = logging.getLogger(__name__)


def signup(request):
    if request.user.is_authenticated:
        return redirect("users:profile")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            email_sent = _send_verification_email(request, user)
            return render(
                request,
                "users/signup_verify_email.html",
                {"email": user.email, "email_sent": email_sent},
            )
    else:
        form = SignupForm()

    return render(request, "users/signup.html", {"form": form})


def _send_verification_email(request, user):
    """Send a verification email to the user. Returns True on success, False on failure."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    site_url = getattr(settings, "SITE_URL", request.build_absolute_uri("/").rstrip("/"))
    verify_url = f"{site_url}/users/verify-email/{uid}/{token}/"
    subject = "Verify your Little Libraries account"
    message = (
        f"Hi {user.username},\n\n"
        "Thank you for registering! Please verify your email address by clicking the link below:\n\n"
        f"{verify_url}\n\n"
        "This link expires after 3 days.\n\n"
        "If you did not create this account, you can ignore this email.\n"
    )
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
        return True
    except Exception:
        logger.exception("Failed to send verification email to %s", user.email)
        return False


def verify_email(request, uidb64, token):
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and user.is_active:
        # Already verified – redirect to login
        return redirect("users:login")

    if user is not None and email_verification_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return render(request, "users/email_verified.html")

    return render(request, "users/email_verification_invalid.html", status=400)


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

