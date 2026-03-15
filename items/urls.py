from django.urls import path

from . import views

app_name = "items"

urlpatterns = [
    path("", views.item_list, name="item-list"),
    path("add/", views.item_create, name="item-create"),
    path("<int:item_id>/history/", views.item_history_page, name="item-history"),
    path("<int:item_id>/move/", views.item_move, name="item-move"),
    path("<int:item_id>/edit/", views.item_edit, name="item-edit"),
    path("<int:item_id>/delete/", views.item_delete, name="item-delete"),
    path("<int:item_id>/qr/", views.item_qr_code, name="item-qr"),
    path("<int:item_id>/", views.item_detail_page, name="item-detail"),
    path("api/", views.item_list_create, name="item-list-create"),
    path("api/<int:item_id>/", views.item_detail_api, name="item-detail-api"),
]
