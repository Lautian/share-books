from django.urls import path

from . import views

app_name = "book_stations"

urlpatterns = [
    path("", views.bookstation_list, name="bookstation-list"),
    path("items/", views.item_list, name="item-list"),
    path("items/<int:item_id>/", views.item_detail_page, name="item-detail"),
    path("api/stations/", views.bookstation_list_create, name="bookstation-list-create"),
    path("api/items/", views.item_list_create, name="item-list-create"),
    path("api/items/<int:item_id>/", views.item_detail_api, name="item-detail-api"),
    path(
        "api/stations/<slug:readable_id>/",
        views.bookstation_detail_api,
        name="bookstation-detail-api",
    ),
    path(
        "<slug:readable_id>/inventory/",
        views.bookstation_inventory_page,
        name="bookstation-inventory",
    ),
    path("<slug:readable_id>/", views.bookstation_detail_page, name="bookstation-detail"),
]
