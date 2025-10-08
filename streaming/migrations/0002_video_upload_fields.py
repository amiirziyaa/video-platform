# Generated manually because Django is unavailable in the execution environment.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("streaming", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="video",
            name="thumbnail_image",
            field=models.ImageField(blank=True, null=True, upload_to="thumbnails/"),
        ),
        migrations.AddField(
            model_name="video",
            name="video_file",
            field=models.FileField(blank=True, null=True, upload_to="videos/"),
        ),
        migrations.AlterField(
            model_name="video",
            name="stream_url",
            field=models.URLField(blank=True),
        ),
    ]
