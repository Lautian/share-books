from django.urls import path

from . import views

app_name = "book_stations"

urlpatterns = [
    path("", views.bookstation_list, name="bookstation-list"),
    path("api/stations/", views.bookstation_list_create, name="bookstation-list-create"),
    path(
        "api/stations/<slug:readable_id>/",
        views.bookstation_detail_api,
        name="bookstation-detail-api",
    ),
    path("<slug:readable_id>/", views.bookstation_detail_page, name="bookstation-detail"),
]
