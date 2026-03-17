from django.urls import path

from . import views

app_name = "moderation"

urlpatterns = [
    path("", views.moderation_queue, name="queue"),
    path(
        "stations/<slug:readable_id>/",
        views.moderate_pending_bookstation,
        name="moderate-bookstation",
    ),
    path(
        "stations/<slug:readable_id>/claim/",
        views.claim_bookstation,
        name="claim-bookstation",
    ),
    path(
        "stations/<slug:readable_id>/unclaim/",
        views.unclaim_bookstation,
        name="unclaim-bookstation",
    ),
    path(
        "stations/<slug:readable_id>/approve/",
        views.approve_bookstation,
        name="approve-bookstation",
    ),
    path(
        "stations/<slug:readable_id>/approve-edit/",
        views.approve_bookstation_edit,
        name="approve-bookstation-edit",
    ),
    path(
        "stations/<slug:readable_id>/reject-edit/",
        views.reject_bookstation_edit,
        name="reject-bookstation-edit",
    ),
    path(
        "stations/<slug:readable_id>/approve-reported/",
        views.approve_reported_bookstation,
        name="approve-reported-bookstation",
    ),
    path(
        "stations/<slug:readable_id>/reject-reported/",
        views.reject_reported_bookstation,
        name="reject-reported-bookstation",
    ),
    path("items/<int:item_id>/", views.moderate_pending_item, name="moderate-item"),
    path(
        "stations/<slug:readable_id>/claim-reported/",
        views.claim_reported_bookstation,
        name="claim-reported-bookstation",
    ),
    path("items/<int:item_id>/claim/", views.claim_item, name="claim-item"),
    path("items/<int:item_id>/unclaim/", views.unclaim_item, name="unclaim-item"),
    path("items/<int:item_id>/approve/", views.approve_item, name="approve-item"),
    path(
        "items/<int:item_id>/approve-edit/",
        views.approve_item_edit,
        name="approve-item-edit",
    ),
    path(
        "items/<int:item_id>/reject-edit/",
        views.reject_item_edit,
        name="reject-item-edit",
    ),
    path(
        "items/<int:item_id>/approve-reported/",
        views.approve_reported_item,
        name="approve-reported-item",
    ),
    path(
        "items/<int:item_id>/reject-reported/",
        views.reject_reported_item,
        name="reject-reported-item",
    ),
    path(
        "items/<int:item_id>/claim-reported/",
        views.claim_reported_item,
        name="claim-reported-item",
    ),
]
