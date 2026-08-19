"""
Сериализаторы основного приложения (daily) для Django REST Framework.
"""

from rest_framework import serializers
from .models import Task, Bookmark


class TaskSerializer(serializers.ModelSerializer):
    # Выводим человекочитаемое имя закладки (read_only=True означает, что поле только для чтения)
    bookmark_title = serializers.CharField(source="bookmark.title", read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "created_at",
            "reminder_at",
            "comment",
            "status_flag",
            "bookmark_title",
            "owner_username",
        ]


class BookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bookmark
        fields = "__all__"

    # Говорим DRF, что owner не нужно требовать на вход и валидировать от клиента
    extra_kwargs = {"owner": {"read_only": True}}


class BookmarkUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bookmark
        fields = ["id", "title"]

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("Название не может быть пустым.")
        return value.strip()
