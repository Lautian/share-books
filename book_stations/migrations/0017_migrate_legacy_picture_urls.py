from urllib.parse import parse_qs, unquote, urlsplit

from django.conf import settings
from django.db import migrations


def migrate_legacy_picture_urls(apps, schema_editor):
    BookStation = apps.get_model("book_stations", "BookStation")
    database = schema_editor.connection.alias
    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
    endpoint_url = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
    endpoint_host = urlsplit(endpoint_url).hostname if endpoint_url else None

    for station_id, picture in (
        BookStation.objects.using(database)
        .exclude(picture="")
        .values_list("pk", "picture")
        .iterator()
    ):
        parsed_url = urlsplit(picture)
        query_keys = {key.lower() for key in parse_qs(parsed_url.query)}
        has_signature = "x-amz-signature" in query_keys or {
            "awsaccesskeyid",
            "signature",
        }.issubset(query_keys)
        if parsed_url.scheme not in {"http", "https"} or not has_signature:
            continue

        is_bucket_url = bucket_name and endpoint_host and parsed_url.hostname in {
            endpoint_host,
            f"{bucket_name}.{endpoint_host}",
        }
        if not is_bucket_url:
            continue

        object_key = unquote(parsed_url.path.lstrip("/"))
        if (
            parsed_url.hostname == endpoint_host
            and object_key.startswith(f"{bucket_name}/")
        ):
            object_key = object_key[len(bucket_name) + 1 :]

        if object_key:
            BookStation.objects.using(database).filter(pk=station_id).update(
                picture=object_key
            )


class Migration(migrations.Migration):
    dependencies = [
        ("book_stations", "0016_remove_bookstation_claimed_by_and_more"),
    ]

    operations = [
        migrations.RunPython(
            migrate_legacy_picture_urls,
            migrations.RunPython.noop,
        ),
    ]
