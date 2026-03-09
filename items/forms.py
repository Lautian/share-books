from django import forms

from .models import Item


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

        current_station = cleaned_data.get("current_book_station")
        if current_station is not None:
            cleaned_data["last_seen_at"] = current_station

        return cleaned_data
