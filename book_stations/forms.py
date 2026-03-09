from pathlib import Path
from uuid import uuid4

from django import forms
from django.core.files.storage import default_storage

from .models import BookStation


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
