from django.urls import path

from . import views

app_name = "book_stations"

urlpatterns = [
    path("", views.bookstation_list_create, name="bookstation-list-create"),
    path("<slug:readable_id>/", views.bookstation_detail, name="bookstation-detail"),
]
