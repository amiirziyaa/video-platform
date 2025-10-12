# Generated manually for the video platform project
from __future__ import annotations

import django.contrib.auth.models
import django.contrib.auth.validators
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubscriptionPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("slug", models.SlugField(max_length=110, unique=True)),
                ("description", models.TextField(blank=True)),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="IRR", max_length=8)),
                ("duration_days", models.PositiveIntegerField(default=30)),
                ("level", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["level"]},
        ),
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
                ("username", models.CharField(
                    error_messages={"unique": "A user with that username already exists."},
                    help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                    max_length=150,
                    unique=True,
                    validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                    verbose_name="username",
                )),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("email", models.EmailField(max_length=254, unique=True, verbose_name="email address")),
                ("is_staff", models.BooleanField(default=False, help_text="Designates whether the user can log into this admin site.", verbose_name="staff status")),
                ("is_active", models.BooleanField(default=True, help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.", verbose_name="active")),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
                ("phone_number", models.CharField(blank=True, max_length=32)),
                ("avatar", models.ImageField(blank=True, null=True, upload_to="avatars/")),
                ("bio", models.TextField(blank=True)),
                ("preferred_language", models.CharField(blank=True, max_length=8)),
                ("marketing_opt_in", models.BooleanField(default=False)),
                ("groups", models.ManyToManyField(blank=True, help_text="The groups this user belongs to.", related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups")),
                ("user_permissions", models.ManyToManyField(blank=True, help_text="Specific permissions for this user.", related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions")),
            ],
            options={
                "verbose_name": "user",
                "verbose_name_plural": "users",
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name="VideoCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(max_length=130, unique=True)),
                ("description", models.TextField(blank=True)),
            ],
            options={"ordering": ["name"], "verbose_name_plural": "Video categories"},
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="IRR", max_length=8)),
                ("authority_code", models.CharField(blank=True, max_length=64)),
                ("reference_code", models.CharField(blank=True, max_length=64)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed"), ("refunded", "Refunded")], default="pending", max_length=20)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payments", to="streaming.subscriptionplan")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-requested_at"]},
        ),
        migrations.CreateModel(
            name="Video",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=260, unique=True)),
                ("description", models.TextField(blank=True)),
                ("duration_seconds", models.PositiveIntegerField()),
                ("trailer_url", models.URLField(blank=True)),
                ("stream_url", models.URLField()),
                ("thumbnail_url", models.URLField(blank=True)),
                ("price", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("min_subscription_level", models.PositiveIntegerField(default=1)),
                ("is_premium", models.BooleanField(default=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("published", "Published"), ("archived", "Archived")], default="draft", max_length=20)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="videos", to="streaming.videocategory")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploaded_videos", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("active", "Active"), ("cancelled", "Cancelled"), ("expired", "Expired")], default="pending", max_length=20)),
                ("start_date", models.DateTimeField(default=django.utils.timezone.now)),
                ("end_date", models.DateTimeField()),
                ("auto_renew", models.BooleanField(default=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("payment", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="subscription", to="streaming.payment")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="streaming.subscriptionplan")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subscriptions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-start_date"]},
        ),
        migrations.CreateModel(
            name="VideoBookmark",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bookmarks", to=settings.AUTH_USER_MODEL)),
                ("video", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bookmarked_by", to="streaming.video")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="VideoComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("comment", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_spoiler", models.BooleanField(default=False)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="video_comments", to=settings.AUTH_USER_MODEL)),
                ("video", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="streaming.video")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="WatchHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("watched_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("progress", models.PositiveIntegerField(default=0, help_text="Watch progress in seconds")),
                ("completed", models.BooleanField(default=False)),
                ("rating", models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ("review", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="watch_entries", to="streaming.payment")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="watch_history", to=settings.AUTH_USER_MODEL)),
                ("video", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="watch_history", to="streaming.video")),
            ],
            options={"ordering": ["-watched_at"]},
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                condition=models.Q(status__in=["pending", "active"]),
                fields=("user",),
                name="unique_active_subscription_per_user",
            ),
        ),
        migrations.AlterUniqueTogether(name="videobookmark", unique_together={("user", "video")}),
    ]
