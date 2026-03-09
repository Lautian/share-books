from pathlib import Path
from uuid import uuid4

from django import forms
from django.core.files.storage import default_storage

from .models import BookStation, Item


class BookStationCreateForm(forms.ModelForm):
    picture_upload = forms.FileField(
        required=False,
        help_text="Optional station photo upload.",
    )

    class Meta:
        model = BookStation
        fields = ["name", "location", "description", "latitude", "longitude"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update({"class": "input input-bordered w-full"})
        self.fields["location"].widget.attrs.update(
            {"class": "input input-bordered w-full"}
        )
        self.fields["description"].widget.attrs.update(
            {"class": "textarea textarea-bordered w-full"}
        )
        self.fields["latitude"].widget.attrs.update(
            {"class": "input input-bordered w-full"}
        )
        self.fields["longitude"].widget.attrs.update(
            {"class": "input input-bordered w-full"}
        )
        self.fields["picture_upload"].widget.attrs.update(
            {"class": "file-input file-input-bordered w-full"}
        )

    def save(self, commit=True):
        station = super().save(commit=False)
        uploaded_picture = self.cleaned_data.get("picture_upload")

        if uploaded_picture:
            extension = Path(uploaded_picture.name).suffix.lower()
            upload_name = f"book_stations/images/photos/{uuid4().hex}{extension}"
            saved_path = default_storage.save(upload_name, uploaded_picture)
            station.picture = default_storage.url(saved_path)

        if commit:
            station.save()
            self.save_m2m()

        return station


class ItemCreateForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            "title",
            "author",
            "item_type",
            "thumbnail_url",
            "description",
            "status",
            "current_book_station",
            "last_seen_at",
            "last_activity",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "last_activity": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["author"].required = False
        self.fields["item_type"].required = False
        self.fields["thumbnail_url"].required = False
        self.fields["description"].required = False
        self.fields["status"].required = False
        self.fields["current_book_station"].required = False
        self.fields["last_seen_at"].required = False
        self.fields["last_activity"].required = False

        self.fields["title"].widget.attrs.update({"class": "input input-bordered w-full"})
        self.fields["author"].widget.attrs.update({"class": "input input-bordered w-full"})
        self.fields["item_type"].widget.attrs.update({"class": "select select-bordered w-full"})
        self.fields["thumbnail_url"].widget.attrs.update(
            {"class": "input input-bordered w-full"}
        )
        self.fields["description"].widget.attrs.update(
            {"class": "textarea textarea-bordered w-full"}
        )
        self.fields["status"].widget.attrs.update({"class": "select select-bordered w-full"})
        self.fields["current_book_station"].widget.attrs.update(
            {"class": "select select-bordered w-full"}
        )
        self.fields["last_seen_at"].widget.attrs.update(
            {"class": "select select-bordered w-full"}
        )
        self.fields["last_activity"].widget.attrs.update(
            {"class": "input input-bordered w-full"}
        )

    def clean(self):
        cleaned_data = super().clean()

        if not cleaned_data.get("item_type"):
            cleaned_data["item_type"] = Item.ItemType.BOOK

        if not cleaned_data.get("status"):
            cleaned_data["status"] = Item.Status.UNKNOWN

        if cleaned_data.get("item_type") == Item.ItemType.BOOK and not (
            cleaned_data.get("author") or ""
        ).strip():
            self.add_error("author", "Author is required when the item type is BOOK.")

        return cleaned_data
