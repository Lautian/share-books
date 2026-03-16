from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("signup/pending/", views.signup_pending, name="signup-pending"),
    path("verify-email/<uidb64>/<token>/", views.verify_email, name="verify-email"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
            next_page="users:profile",
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(template_name="registration/logged_out.html"),
        name="logout",
    ),
    path("profile/", views.profile, name="profile"),
]
