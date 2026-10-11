from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from uuid import uuid4

from django import forms
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from openlocationcode import openlocationcode
from PIL import Image, ImageOps

from .models import BookStation


PLUS_CODE_COORDINATE_PRECISION = Decimal("0.000001")


def _normalize_plus_code(value):
    return (value or "").strip().upper().replace(" ", "")


def encode_plus_code(latitude, longitude):
    if latitude in (None, "") or longitude in (None, ""):
        return ""

    try:
        return openlocationcode.encode(float(latitude), float(longitude))
    except (TypeError, ValueError):
        return ""


def decode_plus_code(plus_code):
    normalized_code = _normalize_plus_code(plus_code)
    if not normalized_code:
        return None

    if not openlocationcode.isValid(normalized_code):
        return None

    if not openlocationcode.isFull(normalized_code):
        return None

    try:
        decoded_area = openlocationcode.decode(normalized_code)
    except (TypeError, ValueError):
        return None

    return (
        Decimal(str(decoded_area.latitudeCenter)).quantize(
            PLUS_CODE_COORDINATE_PRECISION,
            rounding=ROUND_HALF_UP,
        ),
        Decimal(str(decoded_area.longitudeCenter)).quantize(
            PLUS_CODE_COORDINATE_PRECISION,
            rounding=ROUND_HALF_UP,
        ),
    )


class BookStationCreateForm(forms.ModelForm):
    plus_code = forms.CharField(
        required=False,
        max_length=20,
        help_text="Optional Plus Code, for example 849VCWC8+Q9.",
    )
    picture_upload = forms.ImageField(
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
        self.fields["location"].required = False
        self.fields["location"].widget.attrs.update(
            {"class": "input input-bordered w-full"}
        )
        self.fields["description"].widget.attrs.update(
            {"class": "textarea textarea-bordered w-full"}
        )
        self.fields["plus_code"].widget.attrs.update(
            {
                "class": "input input-bordered w-full",
                "placeholder": "849VCWC8+Q9",
                "autocomplete": "off",
            }
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

        instance = getattr(self, "instance", None)
        if instance and instance.pk and instance.latitude is not None and instance.longitude is not None:
            inferred_plus_code = encode_plus_code(instance.latitude, instance.longitude)
            if inferred_plus_code:
                self.initial.setdefault("plus_code", inferred_plus_code)

    def clean(self):
        cleaned_data = super().clean()
        normalized_plus_code = _normalize_plus_code(cleaned_data.get("plus_code"))

        if not normalized_plus_code:
            cleaned_data["plus_code"] = ""
        else:
            decoded_coordinates = decode_plus_code(normalized_plus_code)
            if decoded_coordinates is None:
                self.add_error(
                    "plus_code",
                    "Enter a valid full Plus Code (for example 849VCWC8+Q9).",
                )
            else:
                # Plus Code is the source of truth whenever provided.
                cleaned_data["plus_code"] = normalized_plus_code
                cleaned_data["latitude"], cleaned_data["longitude"] = decoded_coordinates
                self.errors.pop("latitude", None)
                self.errors.pop("longitude", None)

        cleaned_data["location"] = (cleaned_data.get("location") or "").strip()
        has_textual_location = bool(cleaned_data["location"])
        has_geolocation = (
            cleaned_data.get("latitude") is not None
            and cleaned_data.get("longitude") is not None
        )

        if not has_textual_location and not has_geolocation:
            message = "Provide either a textual location or both latitude and longitude."
            self.add_error("location", message)
            self.add_error("latitude", message)
            self.add_error("longitude", message)

        return cleaned_data

    def save(self, commit=True):
        station = super().save(commit=False)
        uploaded_picture = self.cleaned_data.get("picture_upload")

        if uploaded_picture:
            uploaded_picture.seek(0)
            with Image.open(uploaded_picture) as original_image:
                image = ImageOps.exif_transpose(original_image)
                image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                has_transparency = "A" in image.getbands() or "transparency" in image.info
                image = image.convert("RGBA" if has_transparency else "RGB")
                optimized_image = BytesIO()
                image.save(optimized_image, format="WEBP", quality=82)

            upload_name = f"uploads/book_stations/images/photos/{uuid4().hex}.webp"
            saved_path = default_storage.save(
                upload_name,
                ContentFile(optimized_image.getvalue()),
            )
            station.picture = saved_path

        if commit:
            station.save()
            self.save_m2m()

        return station
