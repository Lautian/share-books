from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


def assign_existing_rows_to_test_user(apps, schema_editor):
    book_station_model = apps.get_model("book_stations", "BookStation")
    item_model = apps.get_model("book_stations", "Item")

    user_model_label = settings.AUTH_USER_MODEL
    user_app_label, user_model_name = user_model_label.split(".", 1)
    user_model = apps.get_model(user_app_label, user_model_name)

    username_field = getattr(user_model, "USERNAME_FIELD", "username")
    user_lookup = {username_field: "test_user_1"}
    user_defaults = {}

    if any(field.name == "password" for field in user_model._meta.fields):
        user_defaults["password"] = "!"

    user, _ = user_model.objects.get_or_create(defaults=user_defaults, **user_lookup)

    book_station_model.objects.filter(added_by__isnull=True).update(added_by=user)
    item_model.objects.filter(added_by__isnull=True).update(added_by=user)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("book_stations", "0003_item"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bookstation",
            name="readable_id",
            field=models.SlugField(blank=True, max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name="bookstation",
            name="latitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(-90),
                    django.core.validators.MaxValueValidator(90),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="bookstation",
            name="longitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(-180),
                    django.core.validators.MaxValueValidator(180),
                ],
            ),
        ),
        migrations.AddField(
            model_name="bookstation",
            name="added_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="added_book_stations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="item",
            name="added_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="added_items",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="item",
            name="thumbnail_url",
            field=models.URLField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.RunPython(assign_existing_rows_to_test_user, noop_reverse),
        migrations.AlterField(
            model_name="bookstation",
            name="added_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="added_book_stations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="item",
            name="added_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="added_items",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
