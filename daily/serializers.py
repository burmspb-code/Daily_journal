"""
Сериализаторы основного приложения (daily) для Django REST Framework.
"""
from typing import ClassVar

from rest_framework import serializers

from .models import Bookmark, Task


class TaskSerializer(serializers.ModelSerializer):
    # Выводим человекочитаемое имя закладки (read_only=True означает, что поле только для чтения)
    bookmark_title = serializers.CharField(source="bookmark.title", read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    status_display = serializers.CharField(source="get_status_flag_display", read_only=True)

    class Meta:
        model = Task
        fields = (
            "id",
            "title",
            "created_at",
            "reminder_at",
            "comment",
            "status_flag",
            "status_display",
            "periodicity_value",
            "periodicity_unit",
            "bookmark_title",
            "owner_username",
        )


class BookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bookmark
        fields = "__all__"

    # Говорим DRF, что owner не нужно требовать на вход и валидировать от клиента
    extra_kwargs: ClassVar[dict] = {"owner": {"read_only": True}}


class BookmarkUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bookmark
        fields = ("id", "title", "description")

    def validate_title(self, value):
        if value and not value.strip():
            raise serializers.ValidationError("Название не может быть пустым.")
        return value.strip() if value else value
