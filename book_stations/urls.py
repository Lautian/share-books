from django.urls import path

from . import views

app_name = "book_stations"

urlpatterns = [
    path("", views.bookstation_list, name="bookstation-list"),
    path("add/", views.bookstation_create, name="bookstation-create"),
    path("api/plus-codes/encode/", views.plus_code_encode_api, name="pluscode-encode"),
    path("api/plus-codes/decode/", views.plus_code_decode_api, name="pluscode-decode"),
    path(
        "<slug:readable_id>/edit/",
        views.bookstation_edit,
        name="bookstation-edit",
    ),
    path(
        "<slug:readable_id>/delete/",
        views.bookstation_delete,
        name="bookstation-delete",
    ),
    path("api/stations/", views.bookstation_list_create, name="bookstation-list-create"),
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
    path("<slug:readable_id>/report/", views.bookstation_report, name="bookstation-report"),
    path("<slug:readable_id>/qr/", views.bookstation_qr_code, name="bookstation-qr"),
    path("<slug:readable_id>/", views.bookstation_detail_page, name="bookstation-detail"),
]
