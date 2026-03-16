from django.urls import path

from . import views

app_name = "moderation"

urlpatterns = [
    path("", views.moderation_queue, name="queue"),
    path(
        "stations/<slug:readable_id>/claim/",
        views.claim_bookstation,
        name="claim-bookstation",
    ),
    path(
        "stations/<slug:readable_id>/approve/",
        views.approve_bookstation,
        name="approve-bookstation",
    ),
    path("items/<int:item_id>/claim/", views.claim_item, name="claim-item"),
    path("items/<int:item_id>/approve/", views.approve_item, name="approve-item"),
]
